# ========================
# CONFIGURAÇÕES INICIAIS
# ========================
options(repos = c(CRAN = "https://cloud.r-project.org"), digits = 2)
library(shiny)
library(readxl)
library(dplyr)
library(stringr)
library(janitor)
library(lubridate)
library(sf)
library(leaflet)
# ========================
# FUNÇÕES UTILITÁRIAS
# ========================

remover_acentos <- function(texto) {
  iconv(texto, to = "ASCII//TRANSLIT")
}

limpar_texto <- function(texto) {
  texto %>%
    remover_acentos() %>%
    tolower() %>%
    str_remove_all("[0-9,.:;]") %>%
    str_squish()
}

limpar_doc <- function(coluna) {
  coluna %>%
    as.character() %>%
    gsub("[^0-9]", "", .) %>%
    { if_else(nchar(.) %in% c(11, 14, 8), ., NA_character_) }
}

cep_limpo <- function(coluna) {
  gsub("[^0-9]", "", as.character(coluna))
}

calcular_mais_frequente <- function(coluna) {
  if (length(coluna) == 0 || all(is.na(coluna))) return("Desconhecido")
  names(sort(table(coluna), decreasing = TRUE))[1]
}

# ========================
# CARREGAMENTO E PREPARO DOS DADOS
# ========================

cr <- read_xlsx("Cadastro Produtor.xlsx", na = c("", "NA", "1943/")) %>%
  clean_names() %>%
  filter(cidade == "Recife") %>%
  mutate(across(c(nome, bairro), limpar_texto),
         cep = cep_limpo(cep)) %>%
  distinct(nome, .keep_all = TRUE)

SIC <- read_xlsx("SICGeral.xlsx", sheet = "Geral") %>%
  janitor::clean_names() %>%
  mutate(nome = limpar_texto(nome),
         projeto = limpar_texto(projeto),
         estilo = limpar_texto(estilo),
         ano = suppressWarnings(year(as.Date(ano))),
         mic_fic = limpar_texto(mic_fic)) %>%
  select(-n_cad)
# Aprovados
Apv <- read_xlsx("AprovadoSIC.xlsx", sheet = "Todos") %>%
  janitor::clean_names() %>%
  mutate(projeto = limpar_texto(projeto),
         estilo = limpar_texto(estilo),
         nome = limpar_texto(nome),
         valor = as.numeric(valor),
         ano_pag = suppressWarnings(year(as.Date(ano_pag))),
         mic_fic = limpar_texto(mic_fic))  %>%
  group_by(projeto, estilo, valor,ano_pag,mic_fic) %>%
  slice(1) %>%
  ungroup()
# Relacionando aprovados e inscritos, usando os dados limpos (Sem repetições)
SA <- SIC %>%
  left_join(Apv,
            by = c("projeto" = "projeto",
                   "mic_fic" = "mic_fic",
                   "estilo" = "estilo",
                   "nome" = "nome",
                   "ano"="ano_pag"))  %>%
  group_by(projeto, estilo, valor,ano,mic_fic) %>%
  slice(1) %>%
  ungroup()

#teste para ver junções faltantes
ifiguala0_Ok <- Apv %>%
  anti_join(SA,
            by = c("projeto" = "projeto",
                   "nome" = "nome",
                   "mic_fic" = "mic_fic",
                   "estilo" = "estilo",
                   "ano_pag"="ano"))

# Dados do SIC unidos com dados do Cultura Recife
SICulT <- SA %>%
  left_join(cr, by = "nome") 

pbcr_SICul <- SICulT %>%
  group_by(bairro, ano) %>%
  summarise(
    inscritos = n(),
    idade_media = round(mean(idade, na.rm = TRUE), 0),
    genero = calcular_mais_frequente(genero),
    investimento = sum(valor, na.rm = TRUE),
    aprovados = sum(!is.na(valor)),
    estilo = calcular_mais_frequente(estilo),
    escolaridade = calcular_mais_frequente(grau_formacao),
    raca = calcular_mais_frequente(cor_raca),
    med = if_else(aprovados > 0, round(investimento / aprovados, 2), 0),
    .groups = "drop"
  ) %>%
  filter(!is.na(bairro))

# ========================
# MAPA E JUNÇÃO GEOGRÁFICA
# ========================

rec <- st_read("bvisualizacao_fcbairro.geojson", quiet = TRUE) %>%
  st_transform(4326) %>%
  mutate(bairro = limpar_texto(EBAIRRNOMEOF)) %>%
  select(bairro, geometry)

mapb_SICul <- rec %>%
  left_join(pbcr_SICul, by = "bairro") %>%
  st_as_sf()

# ========================
# UI
# ========================
ui <- fluidPage(
  titlePanel("Dashboard Interativo - SIC"),
  sidebarLayout(
    sidebarPanel(
      selectInput("ano_select", "Ano:", choices = sort(unique(mapb_SICul$ano), decreasing = TRUE)),
      selectInput("genero", "Gênero:", choices = c("Todos", unique(na.omit(mapb_SICul$genero))), selected = "Todos"),
      selectInput("estilo", "Linguagem:", choices = c("Todos", unique(na.omit(mapb_SICul$estilo))), selected = "Todos"),
      selectInput("escolaridade", "Escolaridade:", choices = c("Todos", unique(na.omit(mapb_SICul$escolaridade))), selected = "Todos"),
      selectInput("raca", "Raça:", choices = c("Todos", unique(na.omit(mapb_SICul$raca))), selected = "Todos"),
      helpText("Fonte: Cultura Recife")
    ),
    mainPanel(
      leafletOutput("mapa", height = 600)
    )
  )
)

# ========================
# SERVER
# ========================
server <- function(input, output, session) {
  dados_filtrados <- reactive({
    dados <- mapb_SICul
    
    filtros <- list(
      ano = input$ano_select,
      genero = input$genero,
      estilo = input$estilo,
      escolaridade = input$escolaridade,
      raca = input$raca
    )
    
    for (filtro in names(filtros)) {
      valor <- filtros[[filtro]]
      if (!is.null(valor) && valor != "Todos") {
        dados <- dados[dados[[filtro]] == valor, ]
      }
    }
    
    dados
  })
  
  output$mapa <- renderLeaflet({
    dados <- dados_filtrados()
    
    if (nrow(dados) == 0) {
      return(leaflet() %>%
               addTiles() %>%
               addControl("Nenhum dado disponível para os filtros selecionados", position = "topright"))
    }
    
    pal <- colorNumeric("YlOrRd", domain = dados$inscritos)
    
    leaflet(dados) %>%
      addTiles() %>%
      addPolygons(
        fillColor = ~pal(inscritos),
        weight = 1,
        color = "#444444",
        fillOpacity = 0.7,
        popup = ~paste0(
          "<b>Bairro:</b> ", bairro, "<br>",
          "<b>Ano:</b> ", ano, "<br>",
          "<b>Inscritos:</b> ", inscritos, "<br>",
          "<b>Aprovados:</b> ", aprovados, "<br>",
          "<b>Investimento:</b> R$ ", format(investimento, big.mark = ".", decimal.mark = ","), "<br>",
          "<b>Média por aprovado:</b> R$ ", format(med, big.mark = ".", decimal.mark = ","), "<br>",
          "<b>Gênero:</b> ", genero, "<br>",
          "<b>Escolaridade:</b> ", escolaridade, "<br>",
          "<b>Raça:</b> ", raca, "<br>",
          "<b>Linguagem:</b> ", estilo
        )
      ) %>%
      addLegend(pal = pal, values = ~inscritos, position = "bottomright", title = "Inscrições")
  })
}

# ========================
# EXECUÇÃO DO APP
# ========================
shinyApp(ui = ui, server = server)

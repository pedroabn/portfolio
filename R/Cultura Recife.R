# ===========
# Pacotes
# ============
if(require(tidyverse) == F) install.packages('tidyverse'); require(tidyverse)
if(require(readxl) == F) install.packages('readxl'); require(readxl)
if(require(writexl) == F) install.packages('writexl'); require(writexl)
if(require(geobr)== F) install.packages("geobr"); require(geobr)
if(require(sf) == F) install.packages('sf'); require(sf)
if(require(janitor) == F) install.packages('janitor'); require(janitor)
if(require(here) == F) install.packages('here'); require(here)
if(require(leaflet) == F) install.packages('leaflet'); require(leaflet)
if(require(htmlwidgets) == F) install.packages('htmlwidgets'); require(htmlwidgets)
if(require(RColorBrewer) == F) install.packages('RColorBrewer'); require(RColorBrewer)
if(require(ggplot2) == F) install.packages('ggplot2'); require(ggplot2)
if(require(purrr) == F) install.packages('purrr'); require(purrr)
if(require(sp) == F) install.packages('sp'); require(sp)
remover_acentos <- function(texto) iconv(texto, to = "ASCII//TRANSLIT")
limpar_texto <- function(texto) {
  texto <- remover_acentos(texto) %>% tolower()
  texto <- stringr::str_remove_all(texto, paste0("\\b", collapse = "|"))
  texto <- stringr::str_remove_all(texto, "[0-9,.:;]") %>% stringr::str_squish()
  return(texto)
}
calcular_mais_frequente <- function(coluna) {
  tab <- table(coluna)
  if (length(tab) > 0) names(sort(tab, decreasing = TRUE))[1] else "Desconhecido"
}
limpar_doc <- function(coluna) {
  doc_limpo <- gsub("[^0-9]", "", as.character(coluna))
  doc_limpo <- ifelse(nchar(doc_limpo) %in% c(11, 14, 8), doc_limpo, NA)
  return(doc_limpo)
}
cep_limpo <- function(coluna) {
  gsub("[^0-9]", "", as.character(coluna)) }
calcular_mais_frequente <- function(coluna) {tab <- table(coluna)
if (length(tab) > 0) {names(sort(tab, decreasing = TRUE))[1]
} else {"Desconhecido"}}
options(digits=2)
options(scipen = 999)
# ===========
# Limpando culrec
# ===========
cr <- read_xlsx("Cadastro Produtor.xlsx") %>%
  janitor :: clean_names()%>%
  filter(cidade == "Recife") %>%
  mutate(bairro = limpar_texto(bairro),
         nome = limpar_texto(nome),
         cep = cep_limpo(cep))%>%
  distinct(nome, .keep_all = TRUE)
# ===========
# Dados de cadastro e mapa por bairro
# ===========
pb_Cad <- cr %>%
  group_by(bairro) %>%
  summarise(
    cadastros = n(),
    idade_media = round(mean(idade, na.rm = TRUE), 0),
    genero = calcular_mais_frequente(genero),
    escolaridade = calcular_mais_frequente(grau_formacao),
    raca = calcular_mais_frequente(cor_raca)) %>%
  filter(!is.na(bairro))
# Mapa
rec <- st_read("bvisualizacao_fcbairro.geojson", quiet = TRUE) %>%
  st_transform(4326) %>%
  mutate(bairro = limpar_texto(EBAIRRNOMEOF)) %>%
  select(bairro, geometry)

pb_map <- pb_Cad %>%
  left_join(rec, by = "bairro") %>%
  st_as_sf()
# leaflet
pal <- colorNumeric(palette = "RdYlGn", domain = pb_map$cadastros)

leaflet(pb_map) %>%
  addTiles() %>%
  addPolygons(
    fillColor = ~pal(cadastros),  
    weight = 1,
    color = "black",
    fillOpacity = 0.5,
    highlightOptions = highlightOptions(
      weight = 2,
      color = "black",
      fillOpacity = 0.7,
      bringToFront = TRUE
    ),
    popup = ~paste0(
      bairro, "<br>",
      "<b>Total de Cadastros:</b> ", cadastros, "<br>", 
      "<b>Gênero Mais Visto:</b> ", genero, "<br>",
      "<b>Escolaridade média:</b> ", escolaridade, "<br>",
      "<b>Raça mediana:</b> ", raca, "<br>"
    ),
    labelOptions = labelOptions(
      style = list("font-weight" = "normal", padding = "3px 8px"),
      textsize = "13px",
      direction = "auto")) %>%
  addLegend(pal = pal, values = ~cadastros, 
    opacity = 0.7, title = "Nº de produtores",
    position = "bottomright")
# ===========
# Junção de cadastro e dados SIC
# ===========
# Inscritos - Limpos os repetidos
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

# SIC & DADOS POR BAIRRO

pbcr_SICul <- SICulT %>%
  group_by(bairro) %>%
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

# Mapa
rec <- st_read("bvisualizacao_fcbairro.geojson", quiet = TRUE) %>%
  st_transform(4326) %>%
  mutate(EBAIRRNOMEOF = limpar_texto(EBAIRRNOMEOF)) %>%
  rename(bairro = EBAIRRNOMEOF) %>%
  select("bairro", "geometry", "DB2GSE.ST_Area.SHAPE.","DB2GSE.SdeLength.SHAPE.")

# Junção pb
mapbcr_SICul <- rec %>%
left_join(pbcr_SICul, by = "bairro")
mapbcr_SICul <- st_as_sf(mapbcr_SICul)

mappowerbi <-  mapbcr_SICul2 %>%
  arrange(bairro,estilo,ano)%>%
  st_centroid(of_largest_polygon = TRUE) %>%
  mutate(
    lon = st_coordinates(.)[, 1],
    lat = st_coordinates(.)[, 2]
  ) %>%
  st_drop_geometry()
write.csv(mappowerbi, "centros_bairros.csv", row.names = FALSE)

# leaflet dados por bairro

pal <- colorNumeric(palette = "RdYlGn", domain = pbcr_SICul$inscritos,
                    na.color = "red")

leaflet(mapbcr_SICul) %>%
  addTiles() %>%
  addPolygons(
    fillColor = ~pal(inscritos),
    weight = 1,
    color = "black",
    fillOpacity = 0.5,
    highlightOptions = highlightOptions(
      weight = 2,
      color = "black",
      fillOpacity = 0.7,
      bringToFront = TRUE),
    popup = ~paste0(bairro, "<br>",
                    "<b>Total de Inscritos:</b> ", inscritos, "<br>",
                    "<b>Total de aprovados:</b> ", aprovados, "<br>",
                    "<b>Investimento geral:</b> R$ ", format(investimento, big.mark = ".", decimal.mark = ","), "<br>",
                    "<b>Média por aprovado:</b> R$ ", format(med, big.mark = ".", decimal.mark = ","), "<br>",
                    "<b>Gênero Mais Visto:</b> ", genero, "<br>",
                    "<b>Escolaridade mediana:</b> ", escolaridade, "<br>",
                    "<b>Raça mediana:</b> ", raca,"<br>",
                    "<b>Idade média:</b> ", idade_media),
    labelOptions = labelOptions(
      style = list("font-weight" = "normal", padding = "3px 8px"),
      textsize = "13px",
      direction = "auto")) %>%
  addLegend(pal = pal, values = ~pbcr_SICul$inscritos, opacity = 0.7,
            title = "Nº de produtores",
            position = "bottomright")
# Baixando resultados
write_xlsx(mapbcr_SICul, "georreferenciadoSICpb.xlsx")
write_xlsx(SICulT, "SICad.xlsx")
write_xlsx(pbcr_SICul, "SICpb.xlsx")
st_write(mapbcr_SICul, "mapa_produtores.geojson", driver = "GeoJSON")

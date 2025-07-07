####Funções e libs####
if(require(tidyverse) == F) install.packages('tidyverse'); require(tidyverse)
if(require(readxl) == F) install.packages('readxl'); require(readxl)
if(require(writexl) == F) install.packages('writexl'); require(writexl)
if(require(geobr)== F) install.packages("geobr"); require(geobr)
if(require(sf) == F) install.packages('sf'); require(sf)
if(require(patchwork) == F) install.packages('patchwork'); require(patchwork)
if(require(here) == F) install.packages('here'); require(here)
if(require(leaflet) == F) install.packages('leaflet'); require(leaflet)
if(require(RColorBrewer) == F) install.packages('RColorBrewer'); require(RColorBrewer)
if(require(purrr) == F) install.packages('purrr'); require(purrr)
if(require(sp) == F) install.packages('sp'); require(sp)
if(require(htmltools) == F) install.packages('htmltools'); require(htmltools)
remover_acentos <- function(texto) iconv(texto, to = "ASCII//TRANSLIT")
limpar_texto <- function(texto) {
  palavras_irrelevantes <- c("rua", "avenida", "av", "travessa", "tv", "praca", "praça", 
                             "estrada", "rodovia", "r", "alameda", "al", "bairro", 
                             "bloco", "casa","apt","seg.", "1a", "1ª","2ª", "2a")
  texto <- remover_acentos(texto) %>% tolower()
  texto <- stringr::str_remove_all(texto, paste0("\\b", palavras_irrelevantes, "\\b", collapse = "|"))
  texto <- stringr::str_remove_all(texto, "[0-9,.:;]") %>% stringr::str_squish()
  return(texto)
}
remover_acentos <- function(texto) iconv(texto, to = "ASCII//TRANSLIT")
limpar_end <- function(texto) {
  palavras_irrelevantes <- c("rua", "avenida", "av", "travessa", "tv", 
                             "praca", "praça","estrada", "rodovia", "r", "alameda", "al", "bairro", 
                             "bloco", "casa","apt","seg.", "trv", "travesa", "1ª", "2ª","primeira",
                             "segunda","primeiro","segundo")
  texto <- remover_acentos(texto) %>% tolower()
  texto <- str_remove_all(texto, paste0("\\b", palavras_irrelevantes, "\\b", collapse = "|"))
  texto <- str_remove_all(texto, "[0-9,.:;]") %>% str_squish()
  return(texto)}
calcular_mais_frequente <- function(coluna) {
  tab <- table(coluna)
  if (length(tab) > 0) names(sort(tab, decreasing = TRUE))[1] else "Desconhecido"
}
limpar_doc <- function(coluna) {
  # Remove tudo que não for número
  doc_limpo <- gsub("[^0-9]", "", as.character(coluna))
  
  # Mantém apenas CPFs (11 dígitos) e CNPJs (14 dígitos) válidos
  doc_limpo <- ifelse(nchar(doc_limpo) %in% c(11, 14), doc_limpo, NA)
  
  return(doc_limpo)
}
calcular_mais_frequente <- function(coluna) {tab <- table(coluna)
if (length(tab) > 0) {names(sort(tab, decreasing = TRUE))[1]
} else {"Desconhecido"}}
###dadosdosmapasbrutos####
bairros <- st_read("bvisualizacao_fcbairro.geojson", quiet = TRUE) %>%
  st_transform(4326) %>%
  mutate(EBAIRRNOMEOF = tolower(EBAIRRNOMEOF)) %>%
  select(EBAIRRNOMEOF,geometry)
logradouros <- st_read("trechos-de-logradouros.geojson", quiet = TRUE) %>%
  select(NLGPAVOFIC, geometry)
####juncao de mapas####
logradouros <- logradouros %>%
  mutate(centro = st_centroid(geometry)) %>%
  mutate(longitude = st_coordinates(centro)[,1],
         latitude = st_coordinates(centro)[,2])

ruas_limpo <- logradouros %>%
  group_by(NLGPAVOFIC) %>%
  summarise(latitude = mean(latitude, na.rm = TRUE),
            longitude = mean(longitude, na.rm = TRUE),
            geometry = st_union(geometry))

ruas_bairro <- ruas_limpo %>%
  st_join(bairros,join = st_intersects,
          left = TRUE,largest = TRUE) %>%
  rename(nome_logradouro = NLGPAVOFIC)
##ancine####
ancine <- read_xlsx("ancine.xlsx")
####juncao ancine e mapa####
mapancine <- ancine %>%
  left_join(ruas_bairro, by = "nome_logradouro") 
sm_ancine <- mapancine %>% group_by(EBAIRRNOMEOF)%>%
  summarise(
    total = n(),
    desc_atv = calcular_mais_frequente(desc_atividade),
    perfil = calcular_mais_frequente(natureza_juridica))
####criando mapavisual####
pb_ancine <- bairros %>%
  left_join(sm_ancine, by = "EBAIRRNOMEOF") %>%
  filter(!is.na(total))
pal <- colorNumeric(palette = "Greens",
                    domain = sm_ancine$total)

# Criar o mapa com leaflet
mapa <- leaflet(pb_ancine) %>%
  addTiles() %>%
  addPolygons(fillColor = ~pal(total),
              color = "black",
              weight = 1,fillOpacity = 0.7,
              label = ~lapply(paste0(  "<b>Bairro:</b> ", EBAIRRNOMEOF, "<br>",
                                       "<b>Total de Registrados:</b> ", total, "<br>",
                                       "<b>Descrição de Atividades:</b> ", desc_atv, "<br>",
                                       "<b>Natureza Jurídica:</b> ", perfil), HTML),
              highlightOptions = highlightOptions(weight = 2,color = "#666",
                               fillOpacity = 0.8,bringToFront = TRUE)) %>%
  addLegend(pal = pal,values = ~total,opacity = 0.7,
            title = "Total de Cadastros",position = "bottomright")
mapa

####exportar.html####

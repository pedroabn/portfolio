###########
# Instalar pacotes necessários (se ainda não tiver)
if(require(tidyverse) == F) install.packages('tidyverse'); require(tidyverse)
if(require(readxl) == F) install.packages('readxl'); require(readxl)
if(require(writexl) == F) install.packages('writexl'); require(writexl)
if(require(geobr)== F) install.packages("geobr"); require(geobr)
if(require(here)== F) install.packages(here); require(here)
if(require(sf) == F) install.packages('sf'); require(sf)
if(require(ggspatial) == F) install.packages('ggspatial'); require(ggspatial)
if(require(patchwork) == F) install.packages('patchwork'); require(patchwork)
if(require(tidygeocoder) == F) install.packages('tidygeocoder'); require(tidygeocoder)
if(require(leaflet) == F) install.packages('leaflet'); require(leaflet)
#nova função para tirar os ascentos
remover_acentos <- function(texto) {
  texto <- iconv(texto, to = "ASCII//TRANSLIT")
  return(texto) }

######
#carregando bases de mapa e transformando em sf
#Unidades de saude
maparec <-st_read(here("Dados abertos recife/trechos-de-logradouros.geojson"))
maparec_sf <- st_sf(maparec)
recrpa_map <- st_read(here("bvisualizacao_fcrpa.geojson"))
recrpa_map <- st_sf(recrpa_map)
recbairros <- read_neighborhood() %>%
  filter(code_muni == 2611606)

  #unidades de sau

#######
unidades_saude <- read.csv(here("Dados abertos recife/rede_saude.csv"),sep=";")
unidades_saude <- unidades_saude %>%
geocode(address = endereço, method = "osm", lat = latitude, long = longitude)
unidades_sf <- st_as_sf(unidades_saude,
coords = c("longitude...17", "latitude...16"), crs = 4326)

########
#por rpa
soma_rpa <- unidades_saude %>% group_by(rpa) %>%
  filter(rpa != "" & !is.na(rpa)) %>%
  summarise(Quantidade = n(), .groups = "drop")
#centro cultural 

#########
#Filtrando por Recife, retirando os valores n informados e
#retirando os numeros da coluna das ruas. Retirei as colunas de lat e long (estavam erradas)
centro_cult <- read.csv(here("Dados abertos recife/Mapa-Cultural.csv")) %>%
  select(-c(Latitude, Longitude)) %>%
  filter(Município == "Recife", Endereço != "Não informado") %>%
  mutate(Endereço=tolower(Endereço), Endereço = remover_acentos(Endereço))
  gsub("[^a-z]+$", "",centro_cult$Endereço)


##########

locais_unidade <- cross_join(maparec, unidades_saude)
  
unidades_bairros <- st_join(unidades_sf, maparec_sf, join = st_within)
#mapa por rpa
rpa_map <- recrpa_map %>%
  inner_join(soma_rpa, by = c("CRPAAACODI" = "rpa"))

#Pegando geom por rua - Aqui eu selecionei colunas e mudei para lower case,
# facilitando o reconhecimento para o join
recmap_limpo <- maparec_sf %>%
  select(NLGPAVOFIC, geometry) %>%
  mutate(NLGPAVOFIC = tolower(NLGPAVOFIC),NLGPAVOFIC = remover_acentos(NLGPAVOFIC))
#
ferinha <- centro_cult %>%
  inner_join(recmap_limpo, by =c("Endereço"="NLGPAVOFIC"))
coordenadas <- st_coordinates(ferinha$geometry)
# Calcular os centroides de cada MULTILINESTRING
ferinha_centroids <- st_centroid(ferinha$geometry)
# Extrair as coordenadas dos centroides
coordenadas <- st_coordinates(ferinha_centroids)
# Adicionar as coordenadas ao dataframe original
ferinha_com_coords <- ferinha %>%
  mutate(Longitude = coordenadas[, "X"],
    Latitude = coordenadas[, "Y"])
###########
mapa <- leaflet(ferinha_com_coords) %>%
  addTiles() %>%  # Adicionar o mapa base (OpenStreetMap)
  addCircleMarkers(
    lng = ~Longitude,           # Longitude dos pontos
    lat = ~Latitude,            # Latitude dos pontos
    radius = 5,                 # Tamanho dos pontos
    color = "blue",             # Cor dos pontos
    popup = ~paste(             # Popup com Nome e Tipo
      "<b>Nome:</b>", Artista/Grupo, "<br>",
      "<b>Tipo:</b>", Tipo)) %>%
  setView(lng = -34.8813, lat = -8.0543, zoom = 12)m
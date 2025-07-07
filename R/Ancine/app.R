library(shiny)
library(leaflet)
library(sf)
library(htmltools)

# Carregar dados já processados
pb_ancine <- readRDS("pb_ancine.rds")
pal <- readRDS("paleta.rds")

# UI
ui <- fluidPage(
  titlePanel("Mapa da ANCINE - Recife"),
  leafletOutput("mapa", height = "700px")
)

# Server
server <- function(input, output, session) {
  output$mapa <- renderLeaflet({
    leaflet(pb_ancine) %>%
      addTiles() %>%
      addPolygons(
        fillColor = ~pal(total),
        color = "black",
        weight = 1,
        fillOpacity = 0.7,
        label = ~lapply(paste0(
          "<b>Bairro:</b> ", EBAIRRNOMEOF, "<br>",
          "<b>Total de Registrados:</b> ", total, "<br>",
          "<b>Descrição de Atividades:</b> ", desc_atv, "<br>",
          "<b>Natureza Jurídica:</b> ", perfil
        ), HTML),
        highlightOptions = highlightOptions(
          weight = 2,
          color = "#666",
          fillOpacity = 0.8,
          bringToFront = TRUE
        )
      ) %>%
      addLegend(
        pal = pal,
        values = ~total,
        opacity = 0.7,
        title = "Total de Cadastros",
        position = "bottomright"
      )
  })
}

# Executar app
shinyApp(ui, server)

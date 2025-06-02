library("tidyverse")
limpar_texto <- function(texto) {
  texto %>%
    stringi::stri_trans_general("Latin-ASCII") %>%
    tolower() %>%
    stringr::str_remove_all("[ºª]") %>%
    stringr::str_remove_all("[:punct:]") %>%
    stringr::str_replace_all("([0-9])([^0-9]|$)", "\\1 \\2") %>%
    stringr::str_squish()
}

bd <- read.csv("eventos.csv")%>%
  mutate(Nome = limpar_texto(Nome))%>%
  distinct(Nome, .keep_all = TRUE)


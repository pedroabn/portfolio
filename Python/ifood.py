# defs
#def classificar_faixa_etaria(Idade):
#    if Idade < 30:
#        return 'Jovem'
#    elif Idade >= 30 <= 59:
#        return 'Adulto'
#    else:
#        return 'Idoso'

######################################################
# Imports e df    
import numpy as np    
import pandas as pd
import matplotlib as mtp
import matplotlib.pyplot as plt
import seaborn as sns
df = pd.read_csv("ifood/ifood_df.csv")
# Análise por Campanhas
cmp1 = df.drop(columns=["AcceptedCmp1", "AcceptedCmp2", "AcceptedCmp3", "AcceptedCmp4"]).groupby("AcceptedCmp5")
print(cmp1.describe())
col = ['Income', 'Kidhome', 'Teenhome', 'Recency','Age','NumCatalogPurchases', 'NumStorePurchases', 'NumWebVisitsMonth']
cor_cmp1 = cmp1[col].corr()
sns.heatmap(cor_cmp1, 
            linewidths=0.2,    # espessura das linhas
            linecolor='black',  # cor das linhas
            cmap='coolwarm')  # mapa de cores
plt.title("Matriz de Correlação")
plt.show()
# Agrupamento por idade e soma da renda
#age_income = (
#    df.groupby("Age", as_index=False)["Income"]
#    .sum()
#    .rename(columns={"Income": "Renda","Age":"Idade"})
#    .sort_values("Idade")



######
if(require(tidyverse) == F) install.packages('tidyverse'); require(tidyverse)
if(require(ggplot2) == F) install.packages('ggplot2'); require(ggplot2)
if(require(janitor) == F) install.packages('janitor'); require(janitor)
if(require(ggcorrplot) == F) install.packages('ggcorrplot'); require(ggcorrplot)
#################################################
df <- read.csv("ifood.csv") %>%
  clean_names() %>%
  mutate(casado = if_else(`marital_status` == "Married", 1, 0),
         solteiro = if_else(`marital_status` == "Single", 1, 0),
         viuva = if_else(`marital_status` == "Widow", 1, 0),
         junto = if_else(`marital_status` == "Together", 1, 0),
         divorciado = if_else(`marital_status` == "Divorced", 1, 0),
         graduation = if_else(`education` == "Graduation", 1, 0),
         phd = if_else(`education` == "PhD", 1, 0),
         master = if_else(`education` == "Master", 1, 0),
         n_cycle = if_else(`education` == "2n Cycle", 1, 0),
         idade = (2025 - year_birth),
         client_since = as.integer(interval(ymd(dt_customer),
                                   today()) / years(1)),
         kidhome = if_else(kidhome %in% c(1, 2), 1, 0),
         teenhome = if_else(teenhome %in% c(1, 2), 1, 0),
         income = as.numeric(income)) %>%
  relocate(client_since, .after = dt_customer)
########
#correlation
c<- df %>% select(-marital_status,-education,-dt_customer ,-year_birth, -id,
                  -z_revenue, -z_cost_contact) 
cd <- round(cor(c,use = "pairwise.complete.obs", method = "spearman"),2)
cd <- as.data.frame(as.table(cd)) %>%
  rename(var1 = Var1, var2 = Var2, valor = Freq)  %>%
  rowwise() %>%
  mutate(par = paste(sort(c(var1, var2)), collapse = "_")) %>%
  ungroup() %>%
  distinct(par, .keep_all = TRUE) %>%
  select(-par)

c1<- c %>%
  summarise(round(across(-accepted_cmp1,
  ~ cor(., c$accepted_cmp1, use = "complete.obs")),2)) %>%
  pivot_longer(everything(), names_to = "variavel",
  values_to = "correlacao") %>%
  arrange(desc(abs(correlacao)))

c2<- c %>%
  summarise(round(across(-accepted_cmp2,
  ~ cor(., c$accepted_cmp2, use = "complete.obs")),2)) %>%
  pivot_longer(everything(), names_to = "variavel",
  values_to = "correlacao") %>%
  arrange(desc(abs(correlacao)))

c3<- c %>%
  summarise(round(across(-accepted_cmp3,
  ~ cor(., c$accepted_cmp3, use = "complete.obs")),2)) %>%
  pivot_longer(everything(), names_to = "variavel",
  values_to = "correlacao") %>%
  arrange(desc(abs(correlacao)))

c4<- c %>%
  summarise(round(across(-accepted_cmp4,
   ~ cor(., c$accepted_cmp4, use = "complete.obs")),2)) %>%
  pivot_longer(everything(), names_to = "variavel",
  values_to = "correlacao") %>%
  arrange(desc(abs(correlacao)))

c5<- c %>%
  summarise(round(across(-accepted_cmp5,
  ~ cor(., c$accepted_cmp5, use = "complete.obs")),2)) %>%
  pivot_longer(everything(), names_to = "variavel",
  values_to = "correlacao") %>%
  arrange(desc(abs(correlacao)))

c6<- c %>%
  summarise(round(across(-response,
  ~ cor(., c$response, use = "complete.obs")),2)) %>%
  pivot_longer(everything(), names_to = "variavel",
  values_to = "correlacao") %>%
  arrange(desc(abs(correlacao)))

########
#correlation
vdd <- df %>%
  select(income, recency, complain, response,kidhome,num_web_purchases,
         num_catalog_purchases,num_store_purchases,num_web_visits_month,
         casado, solteiro, viuva, junto, divorciado) %>% 
  cor(use = "complete.obs")
ggcorrplot(vdd, lab = FALSE)
#####
edu <- df %>%
  select(education, income ) %>%
  group_by(education) %>%
  summarise(qtd = n(),
            income = mean(income)) %>%
  mutate(education = fct_reorder(education, qtd))
ggplot(edu, aes(x = fct_rev(education), y = qtd, fill = education)) +
  geom_bar(stat = "identity") +
  xlab("Categoria") +
  ylab("Frequência") +
  theme_minimal()
#####




#)
#age_income["Idade"] = age_income["Idade"].astype(int)
#cf = age_income
#cf["Faixa_Etaria"] = cf["Idade"].apply(classificar_faixa_etaria)

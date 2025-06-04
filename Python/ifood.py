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
#)
#age_income["Idade"] = age_income["Idade"].astype(int)
#cf = age_income
#cf["Faixa_Etaria"] = cf["Idade"].apply(classificar_faixa_etaria)

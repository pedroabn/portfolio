# Classificação por faixa etária
def classificar_faixa_etaria(Idade):
    if Idade < 30:
        return 'Jovem'
    elif Idade >= 30 <= 59:
        return 'Adulto'
    else:
        return 'Idoso'
import pandas as pd
df = pd.read_csv("ifood_df.csv")
print(df.columns)

# Agrupamento por idade e soma da renda
age_income = (
    df.groupby("Age", as_index=False)["Income"]
    .sum()
    .rename(columns={"Income": "Renda","Age":"Idade"})
    .sort_values("Idade")
)
age_income["Idade"] = age_income["Idade"].astype(int)
print(age_income)

cf = age_income
cf["Faixa_Etaria"] = cf["Idade"].apply(classificar_faixa_etaria)

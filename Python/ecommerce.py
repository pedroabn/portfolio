# Imports e df    
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib as mpl
import matplotlib.pyplot as plt
from datetime import datetime
from functools import reduce
from scipy import stats as sts
## defs
def fx_etaria(idade):
    if idade < 30:
        return 'jovem'
    elif  30 <= idade <= 59:
        return 'adulto'
    else:
        return 'idoso'

def renda(income):
    if income >= 51381:
        return "rich"
    elif 35303 < income < 51381:
        return 'middle'
    elif 10000 < income <= 35303:
        return 'low'
    else:
        return 'poor'
    
def grp_idade(idade):
    if idade < 30:
        return '20-29'
    elif 30 <= idade <= 39:
        return '30-39'
    elif 40 <= idade <= 49:
        return '40-49'
    elif 50 <= idade <= 59:
        return '50-59'
    elif 60 <= idade <= 70:
        return '60-70'
    else:
        return '70+'

def limpar_txt(serie):
    return (
        serie
        .astype(str)
        .str.strip()
        .str.lower()
        .str.replace(' ', '_')
        .str.replace('-', '_')
    )

def limpar_col(df):
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(' ', '_')
        .str.replace('-', '_')
    )
    return df

def corcada(target):
    corrs = {}
    for col in c.columns:
        if col != target:
            cor = c[[col, target]].corr(method='spearman').iloc[0, 1]
            corrs[col] = round(cor, 2)
    return (
        pd.DataFrame.from_dict(corrs, orient='index', columns=['correlacao']).abs().
        sort_values(by='correlacao', ascending=False).reset_index().rename(columns={'index': 'variavel'})
    )
# Leitura do arquivo
try:
    df = pd.read_csv('ifood/aifu.csv')
except FileNotFoundError :
    print(f'Não encontrou o arquivo. Procurar caminho correto')        

# Normalizar nomes das colunas (equivalente a clean_names do janitor)
# Normalizar nomes das colunas
df = limpar_col(df)
df['marital_status'] = limpar_txt(df['marital_status'])
df['education'] = limpar_txt(df['education'])
    
# Corrigir income para numérico
df['income'] = pd.to_numeric(df['income'], errors='coerce')

# Ajuste de kidhome e teenhome
df['kidhome'] = df['kidhome'].apply(lambda x: 1 if x in [1, 2] else 0)
df['teenhome'] = df['teenhome'].apply(lambda x: 1 if x in [1, 2] else 0)

# Tempo
hoje = datetime.now()

# Calcular novas colunas
df['idade'] = hoje.year - df['year_birth']
df.loc[df['idade'] > 100, 'idade'] = np.nan
df['dt_customer'] = pd.to_datetime(df['dt_customer'], errors='coerce')
df['client_since'] = ((hoje - df['dt_customer']).dt.days / 365.25).astype(int)
df['mnttotal'] =  df[['mntgoldprods', 'mntsweetproducts', "mntfishproducts","mntmeatproducts","mntfruits","mntwines"]].sum(axis=1)
df['renda'] = df['income'].apply(renda)
df['fx_etaria'] = df['idade'].apply(fx_etaria)
df["grp_idade"] = df['idade'].apply(grp_idade)

# Criar colunas dummies
dummies = pd.get_dummies(df[['marital_status','education','renda','fx_etaria']], 
                         prefix='', prefix_sep='', dtype=int)
df = pd.concat([df, dummies], axis=1)

# Reordenar coluna
df.insert(df.columns.get_loc('dt_customer') + 1, 'client_since', df.pop('client_since'))
Ifood = df
try:
    Ifood.to_excel("Ifood/Ifood.xlsx", sheet_name= "limpo")
    print('Deu bom')
except RuntimeError:
    print('F')

### Correlação geral ###
c = df.drop(columns=['marital_status', 'education', 'dt_customer', 'year_birth', 'id',
                     'z_revenue', 'z_costcontact','renda','fx_etaria',"grp_idade"])

# Matriz de correlação (Spearman)
cd = c.corr(method='spearman').round(2)

# Derretendo para obter pares únicos
### Correlação visual com ggcorrplot (usando seaborn) ###
mask = cd.abs() <= 0.5
filtered_corr = cd.mask(mask)
mapa_calor = plt.figure(figsize=(30, 25))
sns.heatmap(filtered_corr, linewidths=0.5, linecolor='black',
            annot=True,cmap='coolwarm',center=0, vmin=-1, vmax=1)
plt.title('Correlação | > 0.5')
plt.savefig('meu_heatmap.png', dpi=300,bbox_inches='tight')

# Correlações de cada campanha
c1 = corcada('acceptedcmp1').rename(columns={'correlacao': 'acceptedcmp1'})
c2 = corcada('acceptedcmp2').rename(columns={'correlacao': 'acceptedcmp2'})
c3 = corcada('acceptedcmp3').rename(columns={'correlacao': 'acceptedcmp3'})
c4 = corcada('acceptedcmp4').rename(columns={'correlacao': 'acceptedcmp4'})
c5 = corcada('acceptedcmp5').rename(columns={'correlacao': 'acceptedcmp5'})
c6 = corcada('response').rename(columns={'correlacao': 'response'})
# União para 
cam = ['acceptedcmp1', 'acceptedcmp2', 'acceptedcmp3', 'acceptedcmp4', 'acceptedcmp5', 'response']
# Gera e une os DataFrames de correlação com rename
Cc = reduce(
    lambda left, right: pd.merge(left, right, on='variavel', how='outer'),
    [corcada(col).rename(columns={'correlacao': col}) for col in cam])
with pd.ExcelWriter('ifood/correlacoes_ifood.xlsx', engine='openpyxl') as writer:
    Cc.to_excel(writer, index=False)

### Correlação visual com ggcorrplot (usando seaborn) ###
mask = cd.abs() <= 0.5
filtered_corr = cd.mask(mask)
mapa_calor = plt.figure(figsize=(30, 25))
sns.heatmap(filtered_corr, linewidths=0.5, linecolor='black',
            annot=True,cmap='coolwarm',center=0, vmin=-1, vmax=1)
plt.title('Correlação | > 0.5')
plt.savefig('ifood/meu_heatmap.png', dpi=300,bbox_inches='tight')



######################################################
# Imports e df    
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib as mpl
import matplotlib.pyplot as plt
from datetime import datetime
from scipy.stats import spearmanr
from sklearn.preprocessing import LabelBinarizer
## defs
def fx_etaria(Idade):
    if Idade < 30:
        return 'Jovem'
    elif Idade >= 30 <= 59:
        return 'Adulto'
    else:
        return 'Idoso'

def renda(income):
    if income >= 62972:
        return "high"
    elif 40246 < income < 62972:
        return 'middle'
    elif 10000 < income <= 40246:
        return 'low'
    else:
        return 'poor'
        
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
            cor = c[[col, target]].corr(method='pearson').iloc[0, 1]
            corrs[col] = round(cor, 2)
    return (
        pd.DataFrame.from_dict(corrs, orient='index', columns=['correlacao']).abs().
        sort_values(by='correlacao', ascending=False).reset_index().rename(columns={'index': 'variavel'})
    )
# Leitura do arquivo
url = "https://raw.githubusercontent.com/nailson/ifood-data-business-analyst-test/master/ml_project1_data.csv"
try:
    df = pd.read_csv(url)
except FileNotFoundError :
    print(f'Não encontrou o arquivo. Procurar caminho correto')        

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
df['dt_customer'] = pd.to_datetime(df['dt_customer'], errors='coerce')
df['client_since'] = ((hoje - df['dt_customer']).dt.days / 365.25).astype(int)
df['mnttotal'] =  df[['mntgoldprods', 'mntsweetproducts', "mntfishproducts","mntmeatproducts","mntfruits","mntwines"]].sum()
df['renda'] = df['income'].apply(renda)

# Criar colunas dummies
df = pd.get_dummies(df, columns=['marital_status'], prefix='', prefix_sep='', dtype=int)
df = pd.get_dummies(df, columns=['education'], prefix='', prefix_sep='', dtype=int)
df = pd.get_dummies(df, columns=['renda'], prefix='', prefix_sep='', dtype=int)

# Reordenar coluna
df.insert(df.columns.get_loc('dt_customer') + 1, 'client_since', df.pop('client_since'))

Ifood_df = df
Ifood_df.to_excel("Ifood/Ifood.xlsx", sheet_name= "limpo")

### Correlação geral ###
c = df.drop(columns=['marital_status', 'education', 'dt_customer', 'year_birth', 'id',
                     'z_revenue', 'z_cost_contact'], errors='ignore')
# Matriz de correlação (Spearman)
cd = c.corr(method='spearman').round(2)
# Derretendo para obter pares únicos
cd_r = cd.stack().reset_index()
cd_r.columns = ['var1', 'var2', 'valor']
cd_r['par'] = cd_r.apply(lambda x: '_'.join(sorted([x['var1'], x['var2']])), axis=1)
correlacoes_limpo = cd_r.drop_duplicates(subset='par').drop(columns='par')

# Correlações de cada campanha
c1 = corcada('acceptedcmp1').rename(columns={'variavel': 'acceptedcmp1'})
c2 = corcada('acceptedcmp2').rename(columns={'variavel': 'acceptedcmp2'})
c3 = corcada('acceptedcmp3').rename(columns={'variavel': 'acceptedcmp3'})
c4 = corcada('acceptedcmp4').rename(columns={'variavel': 'acceptedcmp4'})
c5 = corcada('acceptedcmp5').rename(columns={'variavel': 'acceptedcmp5'})
c6 = corcada('response').rename(columns={'variavel': 'response'})
with pd.ExcelWriter('ifood/correlacoes_ifood.xlsx', engine='openpyxl') as writer:
    c1.to_excel(writer, sheet_name='acceptedcmp1', index=False)
    c2.to_excel(writer, sheet_name='acceptedcmp2', index=False)
    c3.to_excel(writer, sheet_name='acceptedcmp3', index=False)
    c4.to_excel(writer, sheet_name='acceptedcmp4', index=False)
    c5.to_excel(writer, sheet_name='acceptedcmp5', index=False)
    c6.to_excel(writer, sheet_name='response', index=False)


### Correlação visual com ggcorrplot (usando seaborn) ###
mask = cd.abs() <= 0.5
filtered_corr = cd.mask(mask)
mapa_calor = plt.figure(figsize=(30, 25))
sns.heatmap(filtered_corr, linewidths=0.5, linecolor='black',
            annot=True,cmap='coolwarm',center=0, vmin=-1, vmax=1)
plt.title('Correlação | > 0.5')
plt.savefig('ifood/meu_heatmap.png', dpi=300,bbox_inches='tight')


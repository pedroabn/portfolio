#%% libs
import pandas as pd
import numpy as np
import os
import time
from functools import reduce
from dic import dic_aa
from columnsdel import empresasdel
import re

#%% defs
def coalesce(df, cols):
    primeira_coluna = df[cols[0]]
    colunas_restantes = df[cols[1:]]
    return reduce(lambda acc, col: acc.combine_first(col), 
                  [df[c] for c in cols])   

def burro(texto):
    texto = texto.astype(str)
    if pd.isnull(texto):
        return texto
    texto = re.sub(r'SIM', '1', texto)
    texto = re.sub(r'NÃO', '0', texto)
    return texto

#%% Dataframe
geral = pd.read_excel(r'C:\Users\pedro.bastos\Documents\vscode\Cadastros\resultados\Infopbruto.xlsx')
cads = pd.read_excel(r'C:\Users\pedro.bastos\Documents\vscode\Cadastros\db\Cadastrados.xlsx')

#%% Clusters
centro = [  'SÃO JOSÉ',
            'SANTO ANTÔNIO',
            'RECIFE',
            'SANTO AMARO',
            'BOA VISTA'] 

zn_ricos = [ 'GRAÇAS',
            'POÇO',
            'JAQUEIRA',
            'ESPINHEIRO',
            'CASA FORTE',
            'TAMARINEIRA']

zo = [       'VÁRZEA',
            'IPUTINGA',
            'CORDEIRO']

zs =        ['BOA VIAGEM',
            'PINA']
#%% Manipulação de info por bairro geral
geral = geral.fillna(0)
geral["cluster"] = np.select(
    [   geral["EBAIRRNOMEOF"].isin(centro),
        geral["EBAIRRNOMEOF"].isin(zn_ricos),
        geral["EBAIRRNOMEOF"].isin(zo),
        geral["EBAIRRNOMEOF"].isin(zs)],
        ["centro_infl",
        "poço_infl",
        "UF_infl",
        "BV_infl"],
        default="Fora de núcleos")
dummies = pd.get_dummies(geral['cluster'], dtype=int)
geral = pd.concat([geral, dummies], axis=1)
#%% Manipulação de cadastrados
gb_cads = cads.groupby(['bairros_cep','area_atuacao']).agg(
    inscritos = ('nome','size'),
    genero_mv = ('genero', pd.Series.mode),
    idade_mv = ('idade', 'mean'),
    raca_mv = ('raca',  pd.Series.mode),
    escolaridade_mv = ('escolaridade',  pd.Series.mode)
    ).reset_index()
gb_cads['idade_mv'] = round(gb_cads['idade_mv'],1)
gb_cads['bairros_cep'] = gb_cads['bairros_cep'].str.upper()
gb_cads["cluster"] = np.select(
    [   gb_cads["EBAIRRNOMEOF"].isin(centro),
        gb_cads["EBAIRRNOMEOF"].isin(zn_ricos),
        gb_cads["EBAIRRNOMEOF"].isin(zo),
        gb_cads["EBAIRRNOMEOF"].isin(zs)],
        ["centro_infl",
        "poço_infl",
        "UF_infl",
        "BV_infl"],
        default="Fora de núcleos")
dummies = pd.get_dummies(gb_cads['cluster'], dtype=int)
modas = ['raca_mv','escolaridade_mv','genero_mv']
gb_cads[modas] = (
    gb_cads[modas]
    .apply(lambda x: 
        x.str.replace(r"['", "", regex=False)   # remove ['
         .str.replace(r"]", "", regex=False)
         .str.replace(r"[", "", regex=False)      # remove ´]
         .str.replace(r"']", "", regex = False)   # remove ']
         .str.replace(r"' '", ",", regex=False) # troca ' ' por ,
    ))
gb_cads = gb_cads.dropna(subset=['bairros_cep'])
gb_cads = gb_cads.rename(columns={'bairros_cep': 'EBAIRRNOMEOF'})
gb_cads['area_atuacao'] = gb_cads['area_atuacao'].fillna('Não informado')
gb_cads['area_atuacao'] = gb_cads['area_atuacao'].map(dic_aa).fillna(gb_cads['area_atuacao'])
#%%
pauba = gb_cads.merge(geral, how = 'left', on = 'EBAIRRNOMEOF')
pauba['pct_fzd_area'] = round(((pauba['inscritos_x'] / pauba['inscritos_y'])*100),2).astype(float)
pauba = pauba.dropna(subset = ['total_pessoas'])
pauba = pauba.rename(columns={'inscritos_y':'insc_total', 'inscritos_x':'inscritos'})
pauba['pct_fazedores'] = ((pauba['insc_total']/pauba['total_pessoas'])*100).round(2)
pauba['md_inscritos'] = (pauba['inscritos'].sum()/pauba['EBAIRRNOMEOF'].drop_duplicates().count()).round(2)
pauba = pauba.sort_values(by='EBAIRRNOMEOF')
#pauba.to_excel("resultados/Infopauba.xlsx", index=False)

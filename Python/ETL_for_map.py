#%% Instalando e importando bibliotecas
import pandas as pd
import geopandas as gpd
import numpy as np
from functools import reduce
import requests
import re
import unicodedata
import folium
from folium.elements import Element
from folium.plugins import MarkerCluster, MiniMap, GroupedLayerControl, HeatMap
import branca.colormap as cm
from shapely.geometry import Point
#Import para limpeza de colunas
from utils.columnsdel import matdel, escdel, unddel, casadel, gbm, empresasdel, coracadel, malhadel, demodel, vereadores, setordel
#Import de dicionário
from utils.dic import dic_aa, dic_censo, dic_demo, RPA1, RPA2, RPA3, RPA4, RPA5, RPA6
# Import do load
from utils.load import GDriveWarehouse
# %% Defs 
def limpar_texto(texto):
    if pd.isnull(texto):
        return texto

    palavras_irrelevantes = [
    "escola","creche","colegio","educandario","academia", "centro de educacação","centro",
    "centro educaional", "curso","escola tecnica"]

    texto = texto.lower()

    # Remove palavras irrelevantes (como palavras isoladas)
    pattern = r'\b(' + '|'.join(re.escape(p) for p in palavras_irrelevantes) + r')\b'
    texto = re.sub(pattern, '', texto)

    # Remove números e pontuação
    texto = re.sub(r'[0-9.:;]', '', texto)

    # Remove espaços duplos e trim
    texto = re.sub(r'\s+', ' ', texto).strip()

    return texto

def limpar_acento(txt):
    if pd.isnull(txt):
        return txt
    txt = ''.join(ch for ch in unicodedata.normalize('NFKD', txt) 
        if not unicodedata.combining(ch))
    return txt
    
def burro(texto):
    if pd.isnull(texto):
        return texto
    texto = str(texto)
    texto = re.sub(r'SIM', '1', texto)
    texto = re.sub(r'NÃO', '0', texto)
    texto = int(texto)
    return texto

def limpar_col(df):
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(' ', '_')
        .str.replace('-', '_')
    )
    return df
   
def coalesce(df, cols):
    primeira_coluna = df[cols[0]]
    colunas_restantes = df[cols[1:]]
    return reduce(lambda acc, col: acc.combine_first(col), 
                  [df[c] for c in cols])   

def get_local(df, mapa,col):
    """
        Retorna o nome do bairro para cada linha do DataFrame `df`
        usando latitude e longitude, com base no GeoDataFrame `map`
        e os nomes de referência, com base na coluna "col".
        Parâmetros:
        - df: DataFrame contendo colunas 'Latitude' e 'Longitude'
        - map: GeoDataFrame com polígonos dos bairros e coluna 'bairro' (ou nome equivalente)
        - col: Coluna com o nome que vai receber
    """
    local = []
    for _, row in df.iterrows():
        lat = row["latitude"]
        lon = row["longitude"]
        try:
            lat = float(str(lat).replace(",", "."))
            lon = float(str(lon).replace(",", "."))
        except (ValueError, TypeError):
            local.append(np.nan)
            continue       
        # Caso latitude ou longitude seja zero → retorna NaN
        if pd.isna(lat) or pd.isna(lon)  or lat == 0 or lon == 0:
            local.append(np.nan)
            continue
        ponto = Point(lon, lat)  # Shapely espera (x, y) = (lon, lat)
        # Busca o polígono que contém o ponto
        match = mapa[mapa.geometry.contains(ponto)]
        if not match.empty:
            local.append(match.iloc[0][col])  # Ajustar para o nome real da coluna no 
        else:
            local.append(np.nan)
    return local

def get_ze(valor):
    """Explode string de seções em lista de inteiros"""
    if pd.isna(valor): return []
    s = str(valor)
    parts = [p.strip() for p in re.split(r",|;|\n", s) if p.strip()]
    secoes = []
    for p in parts:
        m = re.match(r"^(\d{1,4})\s*(?:-|–|a|até)\s*(\d{1,4})$", p)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            secoes.extend(range(min(a,b), max(a,b)+1))
        else:
            num = re.sub(r"[^\d]", "", p)
            if num: secoes.append(int(num))
    return secoes

def to_int_or_na(x):
    try: return int(str(x).strip())
    except: return pd.NA

def loc(cep):
  #utiliza a API do CEP aberto para retornar a cidade, lat e long de cada CEP
    url = f"https://www.cepaberto.com/api/v3/cep?cep={cep}"
    headers = {"Authorization": f"Token token=4c76f8b5011d351307319f70c6df0019"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return {
                "bairro": data.get("bairro"),
                "cidade": data.get("cidade", {}).get("nome"),
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude")}
        else:
            print(f"❌ Erro {response.status_code} ao consultar o CEP {cep}")
            return {"bairro": "0", "cidade": None, "latitude": None, "longitude": None}
    except Exception as e:
        print(f"❌ Erro ao processar o CEP {cep}: {e}")
        return {"bairro": "0", "cidade": None, "latitude": None, "longitude": None}

def porbairro(df, col):
   pb = (df.groupby(["EBAIRRNOMEOF"])
    .size()
    .reset_index(name=col))
   return pb

wh = GDriveWarehouse(
        cache_ttl_minutes=30)
#%% Base de mapas
gdf = wh.get_table('bairros')
gdf['EBAIRRNOMEOF'] = gdf['EBAIRRNOMEOF'].str.upper().apply(limpar_acento)
gdf = gdf[["EBAIRRNOMEOF","geometry","CBAIRRCODI"]]

#%% Manipulação da base de cadastros
cad_cpl = wh.get_table('Cadastrados')
LinhasTotal = len(cad_cpl)
cad_cpl['area_atuacao'] = cad_cpl['area_atuacao'].str.replace(">","").astype(str)
cad_cpl = cad_cpl.rename(columns={'latitudes_cep':'latitude','longitudes_cep':'longitude'})
cad_cpl['bairro'] = cad_cpl['bairros_cep'].str.upper().replace({'COHAB':'COHAB - IBURA DE CIMA',
                                                                'SÍTIO DOS PINTOS':'SÍTIO DOS PINTOS - SÃO BRÁS',
                                                                })
cad_cpl['latitude'] = cad_cpl['latitude'].astype(float)
cad_cpl['longitude'] = cad_cpl['longitude'].astype(float)
cad_cpl['area_atuacao'] = cad_cpl['area_atuacao'].fillna('Não informado')
cad_cpl['area_atuacao'] = cad_cpl['area_atuacao'].map(dic_aa).fillna(cad_cpl['area_atuacao'])

#cad_cpl.to_excel("resultados/Cadastrados.xlsx", sheet_name='Cadastrados', index=False)

sic_f = cad_cpl.dropna(subset=["latitude","longitude"])
LinhaSemNA = len(sic_f)

print(f'Cadastros não localizados: {LinhasTotal-LinhaSemNA}')

#%% Group by por bairro e nº de cadastro por bairro
gb_t = cad_cpl.groupby(['bairro']).agg(
    inscritos = ('nome', 'size'),
    genero_mv = ('genero', pd.Series.mode),
    idade_mv = ('idade', 'mean'),
    raca_mv = ('raca',  pd.Series.mode),
    escolaridade_mv = ('escolaridade',  pd.Series.mode)
).reset_index()
gb_t["raca_mv"] = gb_t["raca_mv"].astype(str)
gb_t["escolaridade_mv"] = gb_t["escolaridade_mv"].astype(str)
gb_t["genero_mv"] = gb_t["genero_mv"].astype(str)
gb_t.rename(columns={'bairro': 'EBAIRRNOMEOF'}, inplace=True)
gb_t['EBAIRRNOMEOF'] = gb_t['EBAIRRNOMEOF'].str.upper().apply(limpar_acento)
print('Group by por bairro feito')

#Group_by por area e bairro
gb_ta = cad_cpl.groupby(['bairros_cep','area_atuacao']).size().reset_index(name='inscritos')
gb_ta['bairros_cep'] = gb_ta['bairros_cep'].str.upper().apply(limpar_acento)
gb_ta.rename(columns={'bairros_cep': 'EBAIRRNOMEOF'}, inplace=True)
gb_ta = gb_ta.merge(gdf, on='EBAIRRNOMEOF', how='right')
print('Group by por bairro/area feito')


#%% Malha de subdivisões
malha = wh.get_table('malharec')

malha['NM_FCU'] = malha['NM_FCU'].str.replace(r'\s+', ' ', regex=True).str.strip()
malha['NM_FCU'] = malha['NM_FCU'].replace('', np.nan)
unirpc = ["NM_FCU","NM_BAIRRO"]
malha['nome'] = coalesce(malha, unirpc)
malha = malha.rename(columns={'CD_SETOR':"CD_Setor"})
malha = malha.drop(columns= malhadel)

# Atualizando a Malha com os dados
# Trazer o setor de cada um
cad_cpl['CD_Setor'] = get_local(cad_cpl,malha, "CD_Setor")
# Group_by por setor 
gb_cadset = cad_cpl.groupby('CD_Setor').size().reset_index(name= 'inscritos')
print('Group by por setor feito')
gs_cad = cad_cpl.groupby(['CD_Setor','area_atuacao']).size().reset_index(name= 'inscritos')
print('Group by por setor/area feito')
malha = malha.merge(gb_cadset, on = 'CD_Setor', how='left')
malha['inscritos'] = malha['inscritos'].fillna(0)
malhapa = malha.merge(gs_cad, on = 'CD_Setor', how='left')
malhapa['inscritos'] = malha['inscritos'].fillna(0)
# malhapa.to_excel('resultados/CadastroPorArea_ps.xlsx', index = False)
#%% Zeis & Favelas
zeis = wh.get_table('zeis')
fvl = wh.get_table('favelas')

# Identificação e agrupamento por ZEIs
zeis = zeis.rename(columns={"NMNOME":"ZEI"})
cad_cpl['ZEI'] = get_local(cad_cpl,zeis, "ZEI")
gb_cadzei = cad_cpl.groupby('ZEI').size().reset_index(name= 'inscritos')
zeis = zeis.merge(gb_cadzei, on = "ZEI", how="left")
zeis['inscritos'] = zeis['inscritos'].fillna(0)
zeis = zeis.rename(columns={"ZEI":"Nome"})
zeis["Comunidade"] = "ZEI"
print('Group by por ZEI feito')

# Identificação e agrupamento por favelas
fvl = fvl.rename(columns={"nome_atual":"Favela"})
cad_cpl['Favela'] = get_local(cad_cpl,fvl, "Favela")
gb_cadfvl = cad_cpl.groupby('Favela').size().reset_index(name= 'inscritos')
fvl = fvl.merge(gb_cadfvl, on = "Favela", how="left")
fvl['inscritos'] = fvl['inscritos'].fillna(0)
fvl['Comunidade'] = "Favela"
fvl = fvl.rename(columns={"Favela":"Nome"})
print('Group by por Favela feito')

# Seleção das colunas básicas e iguais em ambas as listas
zeis_f = zeis[['Nome',"Comunidade","inscritos","geometry"]]
fvl_f = fvl[['Nome',"Comunidade","inscritos","geometry"]]

# União para facilitar a visualização
zeis_fvl = pd.concat([fvl_f, zeis_f], axis = 0).sort_values("Nome").reset_index()

#%% Carregando as Escolas e matrículas
escolas = wh.get_table('escolas')
matriculas = wh.get_table("matriculas")
unidades = wh.get_table("unidades")
#Excluindo colunas não necessárias e transformando em dummies
matriculas = matriculas.drop(columns = matdel)
matriculas['UNIDADE_DE_ENSINO'] = matriculas['UNIDADE_DE_ENSINO'].apply(limpar_texto)
dummies = pd.get_dummies(matriculas[['SEXO','ETNIA']],dtype=int)

escolas = escolas.drop(columns = escdel)
escolas['NO_ENTIDADE'] = escolas['NO_ENTIDADE'].apply(limpar_texto)

unidades = limpar_col(unidades.drop(columns = unddel))
unidades['escola'] = unidades['escola'].apply(limpar_texto)

# Merger de colunas
info_alunos = pd.concat([matriculas,dummies], axis=1).drop(columns = ["SEXO","ETNIA"])
alunos = info_alunos.groupby(by = gbm, as_index=False).sum()
alunos = limpar_col(alunos).drop(columns=["sexo_",'etnia_'])

# Info completa das escolas
undmat = unidades.merge(alunos, how = 'left', left_on = 'escola',
                        right_on= 'unidade_de_ensino')
uniresc = ['inep_x', 'inep_y']
undmat['inep'] = coalesce(undmat, uniresc)
undmat = undmat.dropna(subset='inep')

#Registro de informações faltantes. Foram encontrados 311 resultados com o merge, de um total de 359.
escpl = undmat.merge(escolas, how = 'inner', left_on = 'inep',
                        right_on= 'CO_ENTIDADE')
escpl = limpar_col(escpl).dropna(subset= ['latitude','longitude'])
escpl['latitude'] = escpl['latitude'].astype(float)
escpl['longitude'] = escpl['longitude'].astype(float)
unireg = ['quadra_coberta', 'quadra_descoberta']
escpl['quadra'] = coalesce(undmat, unireg)
escpl['quadra'] = escpl['quadra'].apply(burro)
#escpl.to_excel("escpl.xlsx", sheet_name='escolas', index=False)

#Registro de informações faltantes. Foram encontrados 342 resultados com o merge, de um total de 359.
# Group by por bairro de escolas
escpl['EBAIRRNOMEOF'] = get_local(escpl,gdf,'EBAIRRNOMEOF')
escpl['EBAIRRNOMEOF'] = escpl['EBAIRRNOMEOF'].apply(limpar_acento)
escpl['CD_Setor'] = get_local(escpl, malha, 'CD_Setor')
gb_e = escpl.groupby(['EBAIRRNOMEOF']).agg(
    qtd_aluno = ('qtd_alunos','sum'),
    n_escolas = ('bairro', 'size'),
    qtd_quadra = ('quadra', 'sum'),
    qtd_atelie = ('in_sala_atelie_artes', 'sum'),
    qtd_danca = ('in_sala_estudio_danca', 'sum'),
    com_eja = ('in_eja','sum')
    ).reset_index()
#Por setor
gs_e = escpl.groupby(['CD_Setor']).agg(
    qtd_aluno = ('qtd_alunos','sum'),
    n_escolas = ('bairro', 'size'),
    qtd_quadra = ('quadra', 'sum'),
    qtd_atelie = ('in_sala_atelie_artes', 'sum'),
    qtd_danca = ('in_sala_estudio_danca', 'sum'),
    com_eja = ('in_eja','sum')
    ).reset_index()
#%%Pontos de cultura
#Carregando os pontos de cultura
pont_cult = wh.get_table("mapacultural")

#Filtrando para pontos de cultura
pont_cult = pont_cult[pont_cult["Município"] == "Recife"]
pont_cult = pont_cult.rename(columns= {"Latitude":'latitude','Longitude':'longitude'})

#Contabilizando valores NA
semnapc = pont_cult['latitude'].isna().sum()

#Limpando a base para leitura em mapa e agrupamento
pont_cult['latitude'] = pont_cult['latitude'].astype(str).str.replace(",", ".", regex=False).astype(float).fillna(0.)
pont_cult['longitude'] = pont_cult['longitude'].astype(str).str.replace(",", ".", regex=False).astype(float).fillna(0.)

# Group_by por bairro de pontos de cultura
pont_cult["bairro"] = get_local(pont_cult,gdf,'EBAIRRNOMEOF')
gb_ptc = pont_cult.groupby(['bairro']).agg(
    qtd_ptc = ('Id','size'),
    tipo_mais_visto = ('Tipo', pd.Series.mode)
    ).reset_index()
gb_ptc = gb_ptc.rename(columns={'bairro': 'EBAIRRNOMEOF'})
gb_ptc['EBAIRRNOMEOF'] = gb_ptc['EBAIRRNOMEOF'].apply(limpar_acento)
#Por setor
pont_cult["CD_Setor"] = get_local(pont_cult,malha,'CD_Setor')
gs_ptc = pont_cult.groupby(['CD_Setor']).agg(
    qtd_ptc = ('Id','size'),
    tipo_mais_visto = ('Tipo', pd.Series.mode)
    ).reset_index()

#%%Praças e parques
pracarua = wh.get_table("parquespracas")
pracarua['CD_Setor'] = get_local(pracarua,malha,'CD_Setor')
pracarua = pracarua.rename(columns={"nome_bairro": 'EBAIRRNOMEOF'})

gb_prc = porbairro(pracarua,'qtd_pracas')
gb_prc["qtd_pracas"] = gb_prc["qtd_pracas"].astype(int)
gb_prc['EBAIRRNOMEOF'] = gb_prc['EBAIRRNOMEOF'].astype(str).str.upper().apply(limpar_acento)
gb_prc['qtd_pracas'] = gb_prc['qtd_pracas'].fillna(0).astype(int)
#Por setor
gs_prc = (pracarua.groupby(["CD_Setor"])
          .size()
          .reset_index(name="qtd_pracas"))
gs_prc["qtd_pracas"] = gs_prc["qtd_pracas"].astype(int)

#%%COMPAZ
compaz = wh.get_table("compaz")
compaz = compaz.fillna(0).rename(columns={'bairro':'EBAIRRNOMEOF'})
compaz['EBAIRRNOMEOF'] = compaz['EBAIRRNOMEOF'].apply(limpar_acento)
gb_compaz = compaz.groupby(["EBAIRRNOMEOF",'nome']).size().reset_index(name="compaz")
#%%Equipamentos diversos
equip_pub = wh.get_table("Equipamentos")

equip_pub = equip_pub.rename(columns={'bairro':"EBAIRRNOMEOF"})
equip_pub['latitude'] = equip_pub['latitude'].astype(str).str.replace(",", ".", regex=False).astype(float)
equip_pub['longitude'] = equip_pub['longitude'].astype(str).str.replace(",", ".", regex=False).astype(float)
equip_pub = equip_pub.fillna(0)
equip_pub["EBAIRRNOMEOF"] = equip_pub["EBAIRRNOMEOF"].astype(str).str.upper().replace({'COHAB':'COHAB - IBURA DE CIMA',
                                                                                       'MORRO DA CONCEIÇÃO':'CASA AMARELA'}).apply(limpar_acento)
equip_pub['CD_Setor'] = get_local(equip_pub, malha,"CD_Setor")
gb_ep = equip_pub.groupby(["EBAIRRNOMEOF"]).size().reset_index(name="Qtd_equipamentos")
gs_ep = equip_pub.groupby(["CD_Setor"]).size().reset_index(name="Qtd_equipamentos")

# Dividindo teatros e anfiteatros dos outros equipamentos
cultura = ['Anfiteatro','Teatro', 'Museu','Centro de Formação']
teatro = equip_pub.query("tipo in @cultura")
equip_pub = equip_pub.query("tipo not in @cultura")

#%% USF
usf = wh.get_table("usf")
gb_usf = porbairro(usf, 'qtd_usf')

#%% UBS
ubs = wh.get_table("ubs")

ubs['especialidade'] = ubs['especialidade'].apply(limpar_texto)
dummies = pd.get_dummies(ubs['especialidade'],dtype=int)
ubs = pd.concat([ubs, dummies], axis=1).reset_index(drop=True).rename(columns={'bairro':'EBAIRRNOMEOF'})
ubs['EBAIRRNOMEOF'] = ubs['EBAIRRNOMEOF'].astype(str).str.upper().replace({'COHAB':'COHAB - IBURA DE CIMA',
                                                                   'MORRO DA CONCEIÇÃO':'CASA AMARELA'}).apply(limpar_acento)
gb_ubs = porbairro(ubs, 'qtd_ubs')

#União de ubs e usf
gb_saude = gb_ubs.merge(gb_usf, on= 'EBAIRRNOMEOF', how='outer').fillna(0)
#%% CAPS
caps = wh.get_table("caps")
caps['latitude'] = caps['latitude'].astype(float).fillna(0.)
caps['longitude'] = caps['longitude'].astype(float).fillna(0.)
caps = caps.rename(columns={'bairro':"EBAIRRNOMEOF"})
caps["EBAIRRNOMEOF"] = caps["EBAIRRNOMEOF"].astype(str).str.upper().apply(limpar_acento)
caps['CD_Setor'] = get_local(caps, malha,"CD_Setor")
gb_cp = caps.groupby(["EBAIRRNOMEOF"]).size().reset_index(name="Qtd_caps")
gs_cp = caps.groupby(["CD_Setor"]).size().reset_index(name="Qtd_caps")
#%% CRAS
cras = wh.get_table("cras")

cras['latitude'] = cras['latitude'].astype(str).str.replace(",", ".", regex=False).astype(float).fillna(0.)
cras['longitude'] = cras['longitude'].astype(str).str.replace(",", ".", regex=False).astype(float).fillna(0.)
cras = cras.rename(columns={'bairro':"EBAIRRNOMEOF"})
cras["EBAIRRNOMEOF"] = cras["EBAIRRNOMEOF"].astype(str).str.upper().replace({'COHAB':'COHAB - IBURA DE CIMA'}).apply(limpar_acento)
cras['CD_Setor'] = get_local(cras, malha,'CD_Setor')

gb_cr = porbairro(cras, 'Qtd_cras')
gs_cr = cras.groupby(["CD_Setor"]).size().reset_index(name="Qtd_cras")

#Concatenação dos gb
gb_equipub = gb_compaz.merge(gb_ep, on="EBAIRRNOMEOF", how="outer") \
                  .merge(gb_cp, on="EBAIRRNOMEOF", how="outer") \
                  .merge(gb_cr, on="EBAIRRNOMEOF", how="outer")
gb_equipub = gb_equipub.fillna(0)
#Por setor
gs_equipub = gs_ep.merge(gs_cp, on="CD_Setor", how="outer") \
                  .merge(gs_cr, on="CD_Setor", how="outer")
gs_equipub = gs_equipub.fillna(0)
#%% IBGE
casa = wh.get_table("censobairro")
casa = casa.rename(columns={"NM_BAIRRO":'EBAIRRNOMEOF',
                              'v0001':'total_pessoas', 
                    'v0002':'total_casas','v0005':"md_moradores"})
#Limpeza de colunas desnecessárias para análise
casa = casa.drop(columns = casadel)
casa['EBAIRRNOMEOF'] = casa['EBAIRRNOMEOF'].astype(str).str.upper().apply(limpar_acento)
#Por setor

#%% Cor_Raça
print('#1')
cr = wh.get_table("cor-raca")
# Mantendo as de recife
cr = cr[cr['CD_BAIRRO'].astype(str).str.contains('26116060')]
cr = cr.drop(columns= coracadel)
cr = cr.rename(columns=dic_censo)
cr['EBAIRRNOMEOF'] = cr['EBAIRRNOMEOF'].astype(str).str.upper().apply(limpar_acento)
print('#2')
# Leitura de quantas crianças estão presentes 
cr['Crianças'] = cr.filter(like='Criança').sum(axis=1)
total = ['Branco', 'Preto', 'Amarelo', 'Pardo','Indígena']
cr['Total'] = cr[total].sum(axis=1)


#Forçando para numerico para realizar o calculo
cr['Branco'] = pd.to_numeric(cr['Branco'], errors='coerce')
cr['Preto']  = pd.to_numeric(cr['Preto'], errors='coerce')
cr['Pardo']  = pd.to_numeric(cr['Pardo'], errors='coerce')
cr['Total']  = pd.to_numeric(cr['Total'], errors='coerce')

print('#3')
# Pct de pretos e brancos por bairros
cr['pct_brancos'] = (cr['Branco'] / cr['Total']).round(2)
cr['pct_pretos'] = ((cr['Preto'] + cr['Pardo'] )/ cr['Total']).round(2)
cr_b = cr.drop(columns=['Criança','Total'])

#Por setor
cors = wh.get_table("coracasetor")
# Mantendo os setores de Recife
cors = cors[cors['CD_Setor'].astype(str).str.contains('261160605')]
cors = cors.drop(columns= coracadel)
cors = cors.rename(columns=dic_censo)
print('#4')

# Leitura de quantas corsianças estão presentes 
cors['Crianças'] = cors.filter(like='Criança').sum(axis=1)
cors['Total'] = cors[total].sum(axis=1)

#Forçando para numerico para realizar o calculo
cors['Branco'] = pd.to_numeric(cors['Branco'], errors='coerce')
cors['Preto']  = pd.to_numeric(cors['Preto'], errors='coerce')
cors['Total']  = pd.to_numeric(cors['Total'], errors='coerce')
cors['Pardo']  = pd.to_numeric(cors['Pardo'], errors='coerce')

print('#5')
# Pct de pretos e brancos por bairros
cors['pct_brancos'] = (cors['Branco'] / cors['Total']).round(2)
cors['pct_pretosepardos'] = ((cors['Preto'] + cors['Pardo']) / cors['Total']).round(2)
cr_s = cors.drop(columns=['Criança','Total'])
#%% Demografico
#Demo
dm = wh.get_table("demografia")
dm = dm.drop(columns= demodel)
dm = dm[dm['CD_BAIRRO'].astype(str).str.contains('26116060')]
dm = dm.rename(columns=dic_demo)
dm['Infancia'] = dm.filter(like='Criança').sum(axis=1)
dm['Idosos'] = dm.filter(like='velho').sum(axis=1)
total = ['Masculino', 'Feminino']
dm['Total'] = dm[total].sum(axis=1)
#Forçando para numerico para realizar o calculo
dm['Masculino'] = pd.to_numeric(dm['Masculino'], errors='coerce')
dm['Feminino']  = pd.to_numeric(dm['Feminino'], errors='coerce')
dm['Total']  = pd.to_numeric(dm['Total'], errors='coerce')

dm['pct_homem'] = round((dm['Masculino']/dm['Total']),2)
dm['pct_mulher'] = round((dm['Feminino']/dm['Total']),2)

demo_b = dm.drop(columns=['Criança','Total','velho'])
print('Foi por bairro')
#Por setor
dms = wh.get_table("demosetor")
dms = dms.drop(columns= setordel)
dms = dms[dms['CD_Setor'].astype(str).str.contains('261160605')]
dms = dms.rename(columns=dic_demo)
dms['Infancia'] = dms.filter(like='Criança').sum(axis=1)
dms['Idosos'] = dms.filter(like='velho').sum(axis=1)
total = ['Masculino', 'Feminino']
dms['Total'] = dms[total].sum(axis=1)
print('foi primeira parte')
#Forçando para numerico para realizar o calculo
dms['Masculino'] = pd.to_numeric(dms['Masculino'], errors='coerce')
dms['Feminino']  = pd.to_numeric(dms['Feminino'], errors='coerce')
dms['Total']  = pd.to_numeric(dms['Total'], errors='coerce')
dms['pct_homem'] = round((dms['Masculino']/dms['Total']),2)
dms['pct_mulher'] = round((dms['Feminino']/dms['Total']),2)
print('Realizou calculos')
demo_s = dms.drop(columns=['Criança','Total','velho'])

#%% União dados IBGE
gb_demo = cr_b.merge(demo_b, on = "CD_BAIRRO", how = 'left')
gb_demo = gb_demo.merge(casa, on= 'EBAIRRNOMEOF', how = 'left')
gb_demo = gb_demo.drop(columns=['CD_BAIRRO','NM_MUN','AREA_KM2'])
gb_demo['EBAIRRNOMEOF'] = gb_demo['EBAIRRNOMEOF'].str.upper().apply(limpar_acento).replace('COHAB', 'COHAB - IBURA DE CIMA')

gs_demo = cr_s.merge(demo_s, on = 'CD_Setor', how='left')
gs_demo['CD_Setor'] = gs_demo['CD_Setor'].astype(str)
#%% Empresas ativas
emp = wh.get_table("empresas")
emp = emp.rename(columns={"cod_bairro":"CBAIRRCODI"})
empcult = (emp[~emp['desc_atividade']
               .isin(empresasdel)]
               .reset_index(drop=True)
               .drop_duplicates(subset=['razao_social']))
gb_emp = empcult.groupby('CBAIRRCODI').size().reset_index(name = 'qtd_empresas_total')
gb_empportp = emp.groupby(['CBAIRRCODI','desc_atividade']).size().reset_index(name='qtd_emprcr_besas')
empcult['CD_Setor'] = get_local(empcult, malha,'CD_Setor')
gs_emp = empcult.groupby('CD_Setor').size().reset_index(name = 'qtd_empresas_total')

#gb_empportp.to_excel('resultados/empresas-por-bairro.xlsx',index=False)

#%% Agenda cultural
agenda = wh.get_table("eventos")
agenda[['Local', 'Logradouro']] = agenda['Endereço'].str.split('-', n = 1, expand=True)
agenda['Logradouro'] = agenda['Logradouro'].str.replace(r'^.*?- ', '', regex=True)
agenda['Logradouro'] = agenda['Logradouro'].str.replace(r'^.*?- ', '', regex=True)
agenda['Logradouro'] = (agenda['Logradouro']
    .str.replace(r'^\s*C\s+', 'CAIS ', regex=True).str.replace(r'(PRC)\b', 'PRAÇA', regex=True)
    .str.replace(r'(AV)\b', 'AVENIDA', regex=True).str.replace(r'^(LGO)\b', 'LARGO', regex=True)
    .str.replace(r'(TRV)\b', 'TRAVESSA', regex=True).str.replace(r'(EST)\b', 'ESTRADA', regex=True)) 
agenda[['Logradouro','EBAIRRNOMEOF','Cidade']] = agenda['Logradouro'].str.split(',', n=2, expand=True) # As informações truncadas foram divididas
agenda['EBAIRRNOMEOF'] = agenda['EBAIRRNOMEOF'].str.lstrip().apply(limpar_acento) #retira todos os espaços no início da célula

gb_agenda = agenda.groupby('EBAIRRNOMEOF').agg(
    qtd_eventos = ('Nome' ,'size'),
    cat_eve = ('Categoria Evento', pd.Series.mode)
).reset_index().dropna(subset='EBAIRRNOMEOF')
gb_agenda['cat_eve'] = gb_agenda['cat_eve'].astype(str)


gb_agenda_pe = agenda.groupby(['Categoria Evento','EBAIRRNOMEOF']).agg(
    qtd_eventos = ('Nome','size'),
    gratuito = ('Gratuito',pd.Series.mode)).reset_index()
#%% Conecta
conecta = wh.get_table("usuarios_conecta")

#%% Base de dados para o Esgoto/Trans.Pub/CadUnico
df = wh.get_table("dados_seplag", sheet_name='Dados')
df['NM_BAIRRO'] = df['NM_BAIRRO'].apply(limpar_acento).str.upper().replace({'COHAB':'COHAB - IBURA DE CIMA',
                                                               'SÍTIO DOS PINTOS':'SÍTIO DOS PINTOS - SÃO BRÁS'})
df = df.rename(columns={'NM_BAIRRO':'EBAIRRNOMEOF'})
#%% Esgoto
columns_esgoto = ['CD_SETOR', 'CD_BAIRRO', 'EBAIRRNOMEOF', 'quant_dppo_redegeral',
       'perc_dppo_acesso_redegeral_agua','perc_dppo_esgoto_adeq',
       'percent_dppo_agua','total_dppo']
dfe = df[columns_esgoto]
dfe_pb = dfe.groupby('EBAIRRNOMEOF').agg(
    perc_esgoto = ('perc_dppo_esgoto_adeq', "mean"),
    perc_agua = ('percent_dppo_agua', 'mean'),
    total_agua = ('total_dppo','sum')
)
dfe_pb['perc_agua'] = dfe_pb['perc_agua'].round(3)
dfe_pb['perc_esgoto'] = dfe_pb['perc_esgoto'].round(3)

#%% Transporte público
columns_transport = ['CD_SETOR', 'CD_BAIRRO', 'EBAIRRNOMEOF',
                     'metrovia','quant_ponto_onibus']
dft = df[columns_transport]
dft = dft.fillna(0)
dft_pb = dft.groupby('EBAIRRNOMEOF').agg(
    metro = ('metrovia','max'),
    quant_ponto_onibus = ('quant_ponto_onibus','sum'),
)
dft_pb = dft_pb.replace({1:"Sim",0:"Não"})
#%% CadUnico
columns_cad = ['CD_SETOR', 'CD_BAIRRO', 'EBAIRRNOMEOF',
               'quant_fam_cadunico','quant_pessoa_cadunico']
dfc = df[columns_cad]
dfc_pb = dfc.groupby('EBAIRRNOMEOF').agg(
    fam_cadunico = ('quant_fam_cadunico',"sum"),
    ind_cadunico = ('quant_pessoa_cadunico','sum')
)
#%% Group_by dados da SEPLAG
gb_seplag = dfe_pb.merge(dft_pb, on = 'EBAIRRNOMEOF', how='left')
gb_seplag = gb_seplag.merge(dfc_pb, on= 'EBAIRRNOMEOF', how = 'left')
#%% Group_by por bairro
# Merge inicial
pb = gdf.merge(gb_emp, on='CBAIRRCODI', how='left')
pb = pb.drop(columns='CBAIRRCODI')

# Lista de merges a aplicar em ordem
merges = [
    {"df": gb_t },   
    {"df": conecta},
    {"df": gb_seplag },
    {"df": gb_e }, 
    {"df": gb_ptc},   
    {"df": gb_prc},
    {"df": gb_saude},
    {"df": gb_equipub},   
    {"df": gb_agenda}, 
    {"df": gb_demo}]

# Loop de merges automatizado
for m in merges:
    pb = pb.merge(m["df"], on=["EBAIRRNOMEOF"], how="left")

pb = pb.fillna(0)
pb["tipo_mais_visto"] = pb["tipo_mais_visto"].fillna("Sem Registro").astype(str)

pb["RPA"] = np.select(
    [
        pb["EBAIRRNOMEOF"].isin(RPA1),
        pb["EBAIRRNOMEOF"].isin(RPA2),
        pb["EBAIRRNOMEOF"].isin(RPA3),
        pb["EBAIRRNOMEOF"].isin(RPA4),
        pb["EBAIRRNOMEOF"].isin(RPA5),
        pb["EBAIRRNOMEOF"].isin(RPA6),
    ],
    ['RPA1', 'RPA2', 'RPA3', 'RPA4', 'RPA5', 'RPA6'],
    default="Fora"
)

pb = gpd.GeoDataFrame(pb, geometry="geometry", crs="EPSG:4326")
pb.to_excel('resultados/Infopbruto.xlsx')
#pb.to_file("Infopbruto.geojson", driver="GeoJSON")
#%% Group_by por setor
# # Primeiro a relação com as empresas, já que a base de dados serão conectados por uma coluna que será retirada após o merge
ps_emp = gs_emp.merge(malha, on='CD_Setor', how='right')
# ESCOLAS
ps_esc = ps_emp.merge(gs_e, on='CD_Setor', how='left')
ps_esc['n_escolas'] = ps_esc['n_escolas'].fillna(0).astype(int)
ps_esc['qtd_aluno'] = ps_esc['qtd_aluno'].fillna(0).astype(int)

# Pontos de cultura
ps_pc = ps_esc.merge(gs_ptc, on='CD_Setor', how='left')
ps_pc['qtd_ptc'] = ps_pc['qtd_ptc'].fillna(0).astype(int)
ps_pc['tipo_mais_visto'] = ps_pc['tipo_mais_visto'].fillna("Sem Registro").astype(str)
# Praças
ps_praca = ps_pc.merge(gs_prc, on='CD_Setor', how = "left")
# Equipamentos
ps_equippub = ps_praca.merge(gs_equipub, on = 'CD_Setor', how = 'left')
ps_equippub['CD_Setor'] = ps_equippub['CD_Setor'].astype(str)

# Demográfico de bairro
ps_demo = ps_equippub.merge(gs_demo, on = "CD_Setor", how = 'left')
ps_demo = ps_demo.fillna(0)
ps_demo = gpd.GeoDataFrame(ps_demo, geometry="geometry", crs="EPSG:4326")
#%% Vereadores e zonas de apoio
votos = wh.get_table("votoporsecao")
zonascru = wh.get_table("tse")

# Limpar e manipular dados dos votos
#Filtro para apenas os vereadores
vset = {str(x) for x in vereadores}
votos = votos[votos['nome'].isin(vset)]
votos['secao'] = votos['secao'].astype(int)
votos['zona'] = votos['zona'].astype(int)

gb_vg = votos.groupby(['zona','secao']).agg(
    votos_recebidos = ('votos_recebidos','max')
            ).reset_index()

gb_vg['secao'] = gb_vg['secao'].astype(int)
gb_vg['zona'] = gb_vg['zona'].astype(int)
#retornar os mais votados
mv = gb_vg.merge(
    votos,
    on=['zona', 'secao', 'votos_recebidos'],
    how='left'
)
# Empates: agrega os nomes empatados em uma lista (ordenada, sem duplicatas)
gb_maisvoto = (
    mv
    .groupby(['zona', 'secao', 'votos_recebidos'], as_index=False)
    .agg(vereador=('nome', lambda s: sorted(set(map(str, s)))))
)
gb_maisvoto['vereador'] = (gb_maisvoto['vereador'].
                            apply(lambda xs: ','.join(xs)))
# Leitura do tse e divisão para cada seção e 
zonascru['CD_Local'] = zonascru['CD_Local'].astype(int)
linhas = []
for _, r in zonascru.iterrows():
    for s in get_ze(r["secao"]):
        linhas.append({
            "zona": int(r["zona"]),
            "secao": s,
            "CD_Local": int(r["CD_Local"]),
            "local": r["Nome do Local"],
            "endereco": r["Endereço"],
            "EBAIRRNOMEOF": r["Bairro"],
            "latitude": str(r["Latitude"]),
            "longitude": str(r["Longitude"])
        })
zonas = pd.DataFrame(linhas)

fsttse = gb_maisvoto.merge(
    zonas,
    on=['zona','secao'],
    how="left")
# Encontrando o indice de candidato com mais voto por local
idx = fsttse.groupby("CD_Local")["votos_recebidos"].idxmax()
politica = fsttse.loc[idx].reset_index(drop=True)
politica['latitude'] = politica['latitude'].fillna(0).astype(str).str.replace(",",".").astype(float)
politica['longitude'] = politica['longitude'].fillna(0).astype(str).str.replace(",",".").astype(float)

#%% Criação de mapa
# 1. Coordenadas para centralização do mapa.
recife_coords = [-8.05428, -34.88126]
# 2. Criando a base do mapa e plugins.
m = folium.Map(location=recife_coords, zoom_start=13, tiles="OpenStreetMap")
# Plugins
marker_cluster = MarkerCluster(name='Cadastros totais', show=True).add_to(m)
MiniMap(toggle_display=True).add_to(m)
linear = cm.linear.Oranges_06.scale(0,20)
linear.add_to(m)

#Mapa
fghm = folium.FeatureGroup(name='Mapa de Calor', show = True)
#Heatmap
HeatMap(
    data = sic_f[["latitude","longitude"]].values.tolist(),
    radius=10,
    blur=5,
    max_zoom=1
    ).add_to(fghm)
fghm.add_to(m)

# 1. Add marcações de bairro
fgmr = folium.FeatureGroup(name='Malha de subdivisão de bairros', show = True)
#Malha do recife
folium.GeoJson(
    ps_demo,
    name= "nome",
    style_function=lambda feature: {
        'fillColor': linear(feature['properties'].get('inscritos', 0)),
        'color': 'grey',
        'weight': 0.5,
        'fillOpacity': 0.5,
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["CD_Setor", "inscritos", 'Infancia',
            'n_escolas','qtd_ptc', 'qtd_quadra', 'pct_pretosepardos',
            'Qtd_equipamentos', 'Qtd_caps', 'Qtd_cras','com_eja', 'qtd_pracas'
            ],

    aliases=["Setor: ", "Nº de cadastrados: ", "Nº total de crianças: ",
             "Qtd Escolas: ", "Pontos de cultura: ", 'Quadras: ', 'Pretos e Pardos: ',
             'Equipamentos: ', 'CAPS: ', 'CRAS: ', 'Escolas com EJA: ', 'Áreas verdes: ',
             ])
    ).add_to(fgmr)
fgmr.add_to(m)

# Info bairro
fgpb = folium.FeatureGroup(name='Resumo por Bairro', show = True)
folium.GeoJson(
    pb,
    name="EBAIRRNOMEOF",
        style_function=lambda feature: {
        'color': 'black',
        'weight': 0.5
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["EBAIRRNOMEOF", "inscritos",'total_pessoas', 'qtd_eventos',
            'n_escolas','qtd_ptc',  'compaz',
            'Qtd_equipamentos', 'Qtd_caps', 'Qtd_cras'
            ],

    aliases=["Bairro: ", "Nº de cadastrados: ", "Nº total de pessoas: ",'Eventos: ',
             "Qtd Escolas: ", "Pontos de cultura: ", 'Compaz: ',
             'Equipamentos: ', 'CAPS', 'CRAS',
             ])
    ).add_to(fgpb)
fgpb.add_to(m)

# Info de ZEI
fgpz = folium.FeatureGroup(name='Resumo por ZEI', show = True)
folium.GeoJson(
    zeis_f,
    name="Nome",
        style_function=lambda feature: {
        'color': 'green',
        'weight': 0.5
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["Nome", "inscritos"],
    aliases=["ZEI: ", "Nº de cadastrados: "])
    ).add_to(fgpz)
fgpz.add_to(m)

#Info de Favela
fgpf = folium.FeatureGroup(name='Resumo por Favela', show = True)
folium.GeoJson(
    fvl_f,
    name="Nome",
        style_function=lambda feature: {
        'color': 'blue',
        'weight': 0.2
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["Nome", "inscritos"],
    aliases=["Favela: ", "Nº de cadastrados: "])
    ).add_to(fgpf)
fgpf.add_to(m)

#2. Add marcações individuais
fgpp = folium.FeatureGroup(name='Vereadores', show = True)
for row in politica.itertuples():
    radius = 200
    popup_fgpp = folium.Popup(
        f"Vereador: {row.vereador} \n Votos: {row.votos_recebidos} \n Local: {row.local}",
                  parse_html=True, max_width="100")
    folium.Circle(
        location = (row.latitude, row.longitude),
        radius=radius,
        color="black",
        weight=0,
        fill_opacity=0.3,
        opacity=1,
        fill_color="red",
        fill=False,  # gets overridden by fill_color
        popup=popup_fgpp,
        tooltip=row.vereador,
    ).add_to(fgpp)
fgpp.add_to(m)

#Cadastrados
for row in sic_f.itertuples():
    #Definição de onde se encontra o local
    location = (row.latitude, row.longitude)
    popup_textl = folium.Popup(
        f"Genero: {row.genero} \n Raça: {row.raca} \n Estilo: {row.area_atuacao}",
                  parse_html=True, max_width="100")
    folium.Circle(
        location=location,
        radius=10, fill_color="green",
        fill_opacity=0.4, color="white",
        popup=popup_textl,
        tooltip = row.area_atuacao
    ).add_to(marker_cluster)

grupos_area = {}
for area in sic_f['area_atuacao'].dropna().unique():
    fcad = folium.FeatureGroup(name=area, show=False)
    cluster = MarkerCluster().add_to(fcad)

    df_area = sic_f[sic_f['area_atuacao'] == area]
    for _, row in df_area.iterrows():
        location = (row.latitude, row.longitude)
        popup_textl = folium.Popup(
        f"Genero: {row.genero} \n Raça: {row.raca} \n Estilo: {row.area_atuacao}",
                  parse_html=True, max_width="100")
        folium.Circle(
            location = location,
            popup=popup_textl,
            radius=10, fill_color="white",
            fill_opacity=1, color="black", weight=1,
            tooltip = row.nome
        ).add_to(cluster)

    grupos_area[area] = fcad
    m.add_child(fcad)

#Pontos de escola
fgesc = folium.FeatureGroup(name='Escolas', show = True)

for row in escpl.itertuples():
    #Definição de onde se encontra o local
    location_e = (row.latitude, row.longitude)
    popup_texte = folium.Popup(
        f"Escola: {row.escola} \n Qtd_Alunos: {row.qtd_alunos} \n Quadra: {row.quadra}",
                  parse_html=True, max_width="100%")
    folium.Circle(
        location=location_e,
        radius=70, fill_color="yellow",
        fill_opacity=0.4, color="black", weight =  0.5,
        popup=popup_texte,
        tooltip=row.escola
    ).add_to(fgesc)
fgesc.add_to(m)

#Pontos de cultura
fgpc = folium.FeatureGroup(name='Pontos de cultura', show = True)
for row in pont_cult.itertuples():
    #Definição de onde se encontra o local
    location_e = (row.latitude, row.longitude)
    popup_texte = folium.Popup(
        f"Nome: {row.Nome}  \n Tipo: {row.Tipo}",
                  parse_html=True, max_width="100%")
    folium.Circle(
        location=location_e,
        radius=100, fill_color="blue",
        fill_opacity=0.8, color="black", weight =  0.5,
        popup=popup_texte,
        tooltip=row.Nome
    ).add_to(fgpc)
fgpc.add_to(m)

#Praças
fgprc = folium.FeatureGroup(name='Áreas verdes', show = True)
for  row in pracarua.itertuples():
    #Definição de onde se encontra o local
    location_e = (row.latitude, row.longitude)
    popup_fgprc = folium.Popup(
        f"Nome: {row.nome_equip_urbano}  \n Tipo: {row.tipo_equip_urbano}",
                  parse_html=True, max_width="100%")
    folium.Circle(
        location=location_e,
        radius=100, fill_color="green",
        fill_opacity=0.8, color="black", weight =  0.5,
        popup=popup_fgprc,
        tooltip=row.nome_equip_urbano
    ).add_to(fgprc)
fgprc.add_to(m)

# Equipamentos culturais
fgt = folium.FeatureGroup(name='Teatro', show = True)
for row in teatro.itertuples():
    #Definição de onde se encontra o local
    location_e = (row.latitude, row.longitude)
    popup_textep = folium.Popup(
        f"Nome: {row.equipamento}  \n Tipo: {row.tipo} \n Natureza: {row.natureza}",
                  parse_html=True, max_width="100%")
    folium.Marker(
        location=location_e,
        popup=popup_textep,
        tooltip=row.equipamento
    ).add_to(fgt)
fgt.add_to(m)

#Equipamentos
fgeqp = folium.FeatureGroup(name='Equipamentos', show = True)
for row in equip_pub.itertuples():
    #Definição de onde se encontra o local
    location = (row.latitude, row.longitude)
    popup_textl = folium.Popup(
        f"Nome: {row.equipamento}  \n Tipo: {row.tipo} \n Natureza: {row.natureza}",
                  parse_html=True, max_width="100%")
    folium.Circle(
            location = location,
            popup=popup_textl,
            radius=70, fill_color="white",
            fill_opacity=0.8, color="black", weight=1,
            tooltip = row.equipamento
        ).add_to(fgeqp)
fgeqp.add_to(m)

 #Compaz
fgcp = folium.FeatureGroup(name='COMPAZ', show = True)
for row in compaz.itertuples():
    #Definição de onde se encontra o local
    location_e = (row.latitude, row.longitude)
    popup_cp = folium.Popup(
        f"Nome: {row.nome}",
          parse_html=True, max_width="100%")
    folium.Circle(
        location=location_e,
        radius=100, fill_color="cyan",
        fill_opacity=0.4, color="black", weight =  0.5,
        popup=popup_cp,
        tooltip= row.nome
    ).add_to(fgcp)
fgcp.add_to(m)

# Painéis de seleções
GroupedLayerControl( exclusive_groups= False,
 groups={'Individuais': [fgesc, fgpc, fgprc, fgeqp, fgt ,fgcp, fgpp],
         'Por Bairro': [fgmr, fgpb, fghm, fgpz, fgpf],
         
         },
    overlays= {"Individuais": [fgt, fgesc, fgpc, fgprc, fgeqp, fgcp, fgpp],
               "Por Bairro": [fgmr, fgpb, fghm, fgpz, fgpf]},
 collapsed=False
).add_to(m)
    #Seleção por área de atuação
GroupedLayerControl(exclusive_groups= False,
    groups={ 'Total': [marker_cluster],
        'Por Área de Atuação': list(grupos_area.values())},
    collapsed=False,
    position = 'topleft'
).add_to(m)
# Salva o mapa
#m
m.save("mapa/mapa.html")

#%% Testes de mapa
# 1. Coordenadas para centralização do mapa.
recife_coords = [-8.05428, -34.88126]
# 2. Criando a base do mapa e plugins.
m = folium.Map(location=recife_coords, zoom_start=13, tiles="OpenStreetMap")
# Plugins
marker_cluster = MarkerCluster(name='Cadastros totais', show=True).add_to(m)
MiniMap(toggle_display=True).add_to(m)
linear = cm.linear.Oranges_06.scale(0,20)
linear.add_to(m)

# #Mapa
# fghm = folium.FeatureGroup(name='Mapa de Calor', show = True)
# #Heatmap
# HeatMap(
#     data = sic_f[["latitude","longitude"]].values.tolist(),
#     radius=10,
#     blur=5,
#     max_zoom=1
#     ).add_to(fghm)
# fghm.add_to(m)

# # 1. Add marcações de bairro
# fgmr = folium.FeatureGroup(name='Malha de subdivisão de bairros', show = True)
#     #Malha do recife
# folium.GeoJson(
#     ps_demo,
#     name= "nome",
#     style_function=lambda feature: {
#         'fillColor': linear(feature['properties'].get('inscritos', 0)),
#         'color': 'grey',
#         'weight': 0.5,
#         'fillOpacity': 0.5,
#     },
#     tooltip=folium.GeoJsonTooltip(
#         fields=["CD_Setor", "inscritos", 'Infancia',
#             'n_escolas','qtd_ptc', 'qtd_quadra', 'pct_pretosepardos',
#             'Qtd_equipamentos', 'Qtd_caps', 'Qtd_cras','com_eja', 'qtd_pracas'
#             ],

#     aliases=["Setor: ", "Nº de cadastrados: ", "Nº total de crianças: ",
#              "Qtd Escolas: ", "Pontos de cultura: ", 'Quadras: ', 'Pretos e Pardos: ',
#              'Equipamentos: ', 'CAPS: ', 'CRAS: ', 'Escolas com EJA: ', 'Áreas verdes: ',
#              ])
#     ).add_to(fgmr)
# fgmr.add_to(m)

# # Info bairro
# fgpb = folium.FeatureGroup(name='Resumo por Bairro', show = True)

# folium.GeoJson(
#     pb_demo,
#     name="EBAIRRNOMEOF",
#         style_function=lambda feature: {
#         'color': 'black',
#         'weight': 0.5
#     },
#     tooltip=folium.GeoJsonTooltip(
#         fields=["EBAIRRNOMEOF", "inscritos",'total_pessoas',
#             'n_escolas','qtd_ptc',  'compaz',
#             'Qtd_equipamentos', 'Qtd_caps', 'Qtd_cras'
#             ],

#     aliases=["Bairro: ", "Nº de cadastrados: ", "Nº total de pessoas: ",
#              "Qtd Escolas: ", "Pontos de cultura: ", 'Compaz: ',
#              'Equipamentos: ', 'CAPS', 'CRAS',
#              ])
#     ).add_to(fgpb)
# fgpb.add_to(m)


# Info de ZEI
fgpz = folium.FeatureGroup(name='Resumo por ZEI', show = True)

folium.GeoJson(
    zeis_f,
    name="Nome",
        style_function=lambda feature: {
        'color': 'green',
        'weight': 0.5
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["Nome", "inscritos"],
    aliases=["ZEI: ", "Nº de cadastrados: "])
    ).add_to(fgpz)
fgpz.add_to(m)

fgpf = folium.FeatureGroup(name='Resumo por Favela', show = True)

folium.GeoJson(
    fvl_f,
    name="Nome",
        style_function=lambda feature: {
        'color': 'blue',
        'weight': 0.2
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["Nome", "inscritos"],
    aliases=["Favela: ", "Nº de cadastrados: "])
    ).add_to(fgpf)
fgpf.add_to(m)

#2. Add marcações individuais
# fgpp = folium.FeatureGroup(name='Vereadores', show = True)
# for row in politica.itertuples():
#     radius = 200
#     popup_fgpp = folium.Popup(
#         f"Vereador: {row.vereador} \n Votos: {row.votos_recebidos} \n Local: {row.local}",
#                   parse_html=True, max_width="100")
#     folium.Circle(
#         location = (row.latitude, row.longitude),
#         radius=radius,
#         color="black",
#         weight=0,
#         fill_opacity=0.3,
#         opacity=1,
#         fill_color="red",
#         fill=False,  # gets overridden by fill_color
#         popup=popup_fgpp,
#         tooltip=row.vereador,
#     ).add_to(fgpp)
# fgpp.add_to(m)

#Cadastrados
for row in sic_f.itertuples():
    #Definição de onde se encontra o local
    location = (row.latitude, row.longitude)
    popup_textl = folium.Popup(
        f"Genero: {row.genero} \n Raça: {row.raca} \n Estilo: {row.area_atuacao}",
                  parse_html=True, max_width="100")
    folium.Circle(
        location=location,
        radius=10, fill_color="green",
        fill_opacity=0.4, color="white",
        popup=popup_textl,
        tooltip = row.area_atuacao
    ).add_to(marker_cluster)


grupos_area = {}
for area in sic_f['area_atuacao'].dropna().unique():
    fcad = folium.FeatureGroup(name=area, show=False)
    cluster = MarkerCluster().add_to(fcad)

    df_area = sic_f[sic_f['area_atuacao'] == area]
    for _, row in df_area.iterrows():
        location = (row.latitude, row.longitude)
        popup_textl = folium.Popup(
        f"Genero: {row.genero} \n Raça: {row.raca} \n Estilo: {row.area_atuacao}",
                  parse_html=True, max_width="100")
        folium.Circle(
            location = location,
            popup=popup_textl,
            radius=10, fill_color="white",
            fill_opacity=1, color="black", weight=1,
            tooltip = row.nome
        ).add_to(cluster)

    grupos_area[area] = fcad
    m.add_child(fcad)
# #Pontos de escola
# fgesc = folium.FeatureGroup(name='Escolas', show = True)

# for row in escpl.itertuples():
#     #Definição de onde se encontra o local
#     location_e = (row.latitude, row.longitude)
#     popup_texte = folium.Popup(
#         f"Escola: {row.escola} \n Qtd_Alunos: {row.qtd_alunos} \n Quadra: {row.quadra}",
#                   parse_html=True, max_width="100%")
#     folium.Circle(
#         location=location_e,
#         radius=70, fill_color="yellow",
#         fill_opacity=0.4, color="black", weight =  0.5,
#         popup=popup_texte,
#         tooltip=row.escola
#     ).add_to(fgesc)
# fgesc.add_to(m)

# #Pontos de cultura
# fgpc = folium.FeatureGroup(name='Pontos de cultura', show = True)
# for row in pont_cult.itertuples():
#     #Definição de onde se encontra o local
#     location_e = (row.latitude, row.longitude)
#     popup_texte = folium.Popup(
#         f"Nome: {row.Nome}  \n Tipo: {row.Tipo}",
#                   parse_html=True, max_width="100%")
#     folium.Circle(
#         location=location_e,
#         radius=100, fill_color="blue",
#         fill_opacity=0.8, color="black", weight =  0.5,
#         popup=popup_texte,
#         tooltip=row.Nome
#     ).add_to(fgpc)
# fgpc.add_to(m)

# #Praças
# fgprc = folium.FeatureGroup(name='Áreas verdes', show = True)
# for  row in pracarua.itertuples():
#     #Definição de onde se encontra o local
#     location_e = (row.latitude, row.longitude)
#     popup_fgprc = folium.Popup(
#         f"Nome: {row.nome_equip_urbano}  \n Tipo: {row.tipo_equip_urbano}",
#                   parse_html=True, max_width="100%")
#     folium.Circle(
#         location=location_e,
#         radius=100, fill_color="green",
#         fill_opacity=0.8, color="black", weight =  0.5,
#         popup=popup_fgprc,
#         tooltip=row.nome_equip_urbano
#     ).add_to(fgprc)
# fgprc.add_to(m)


# Teatro
fgt = folium.FeatureGroup(name='Teatro', show = True)
for row in teatro.itertuples():
    #Definição de onde se encontra o local
    location_e = (row.latitude, row.longitude)
    popup_textep = folium.Popup(
        f"Nome: {row.equipamento}  \n Tipo: {row.tipo} \n Natureza: {row.natureza}",
                  parse_html=True, max_width="100%")
    folium.Marker(
        location=location_e,
        popup=popup_textep,
        tooltip=row.equipamento
    ).add_to(fgt)
fgt.add_to(m)

#Equipamentos
fgeqp = folium.FeatureGroup(name='Equipamentos', show = True)
for row in equip_pub.itertuples():
    #Definição de onde se encontra o local
    location = (row.latitude, row.longitude)
    popup_textl = folium.Popup(
        f"Nome: {row.equipamento}  \n Tipo: {row.tipo} \n Natureza: {row.natureza}",
                  parse_html=True, max_width="100%")
    folium.Circle(
            location = location,
            popup=popup_textl,
            radius=100, fill_color="white",
            fill_opacity=1, color="black", weight=1,
            tooltip = row.equipamento
        ).add_to(fgeqp)
fgeqp.add_to(m)


#  #Compaz
# fgcp = folium.FeatureGroup(name='COMPAZ', show = True)
# for row in compaz.itertuples():
#     #Definição de onde se encontra o local
#     location_e = (row.latitude, row.longitude)
#     popup_cp = folium.Popup(
#         f"Nome: {row.nome}",
#           parse_html=True, max_width="100%")
#     folium.Circle(
#         location=location_e,
#         radius=100, fill_color="cyan",
#         fill_opacity=0.4, color="black", weight =  0.5,
#         popup=popup_cp,
#         tooltip= row.nome
#     ).add_to(fgcp)
# fgcp.add_to(m)

# GroupedLayerControl( exclusive_groups= False,
#  groups={'Individuais': [fgesc, fgpc, fgprc, fgeqp, fgcp, ],
#          'Por Bairro': [fgmr, fgpb, fghm],
         
#          }, 
#     overlays= {"Individuais": [fgesc, fgpc, fgprc, fgeqp, fgcp, ],
#                "Por Bairro": [fgmr, fgpb, fghm]},
#  collapsed=False
# ).add_to(m)

# GroupedLayerControl(exclusive_groups= False,
#     groups={ 'Total': [marker_cluster],
#         'Por Área de Atuação': list(grupos_area.values())},
#     collapsed=False,
#     position = 'topleft'
# ).add_to(m)
# Salva o mapa
m
m.save("mapa/mapateste.html")

#%% Teste de codigos

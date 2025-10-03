#%% Libs
import pandas as pd
import re
import numpy as np
#%% defs e lists
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

vereadores = [
       'Aderaldo Pinto',
      ...]

#%% Vereadores e zonas de apoio
votos = pd.read_excel(r'')
zonascru = pd.read_excel(r'')
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


politica.to_excel('output/Vereadores_map.xlsx')

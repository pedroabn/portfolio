import pandas as pd
import numpy as np
from Funcoes.limpeza import limpar_texto, cep_limpo, mais_visto

# Leitura e limpeza de dados

cr = pd.read_excel("cr.xlsx", engine="openpyxl")
cr.columns = cr.columns.str.lower().str.replace(' ', '_')

# Filtro e limpeza
cr = cr[cr["cidade"] == "Recife"].copy()
cr["bairro"] = cr["bairro"].apply(limpar_texto)
cr["nome"] = cr["nome"].apply(limpar_texto)
cr["cep"] = cep_limpo(cr["cep"])
cr = cr.drop_duplicates(subset=["nome"])

# Agrupamento por bairro
pb_Cad = cr.groupby("bairro").agg(
    cadastros=("bairro", "count"),
    idade_media=("idade", lambda x: round(np.nanmean(x), 0)),
    genero=("genero", mais_visto),
    escolaridade=("grau_formacao", mais_visto),
    raca=("cor_raca", mais_visto)
).reset_index()

pb_Cad = pb_Cad[pb_Cad["bairro"].notna()]

Cadastro_mapeado = pd.DataFrame(pb_Cad)

# Exportar para XLSX
Cadastro_mapeado.to_excel("CadastroMapeado.xlsx", sheet_name="Dados")

print(f"Tabela exportada com sucesso para CadastroMapeado.xlsx!")

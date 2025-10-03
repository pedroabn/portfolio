import sys
import subprocess
def instalar_pacote(pacote):
  subprocess.check_call([sys.executable, "-m","pip","install", pacote])
instalar_pacote("ydata-profiling")
instalar_pacote("openpyxl")
import pandas as pd
from ydata_profiling import ProfileReport
caminho_arquivo = "https://docs.google.com/spreadsheets/d/1hFpnEn9-Ku4V0If4v5u2aMQTX3ResBtmTLz5vJjdJ2g/export?format=xlsx&gid=2029340840"
df = pd.read_excel(caminho_arquivo, engine = "openpyxl")
profile = ProfileReport(df, title="Relatório de Análise de Dados")
profile.to_file("relatorio.html")
print("gerou")
from google.colab import files
files.download("relatorio.html")

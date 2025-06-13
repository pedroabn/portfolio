!pip install --quiet gspread pandas gspread_dataframe
import pandas as pd
import gspread
from google.colab import files
from gspread_dataframe import get_as_dataframe
from google.auth import default
from google.colab import auth
import json
from google.oauth2.service_account import Credentials
import time

uploaded = files.upload()
SERVICE_ACCOUNT_FILE = "cred_api_google.json"  # Troque pelo nome real
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scope)
gc = gspread.authorize(creds)

from pickle import FALSE
def carregar_aba(spreadsheet_id, aba):
    try:
        sh = gc.open_by_key(spreadsheet_id)
        worksheet = sh.worksheet(aba)
        df = get_as_dataframe(worksheet, skiprows=7, header=0, evaluate_formulas=True, index = FALSE)
        print(f"✅ Planilha {spreadsheet_id} - Aba '{aba}' carregada.")
        return df
    except Exception as e:
        print(f"⚠️ Planilha {spreadsheet_id} - Aba '{aba}' não encontrada: {e}")
        return None


ids_planilhas = [
    "1NAvzbm4q3wgomZ-PdwhzwxF05g8SwbD50-o2yoyw4jI", "1xYmgiKRGPlxb3HReUGRtfQkUXzX3hrqm7k9a3PPbAkQ",
    "16D5pG7zPScTif5hkvJ_tFHEkZ_G4o4USSlJG-QjlxXY","1WVCSpCGL_qSB61qf_Qw_S2YeQILVEuTv8FYPfo87L_4",
    "1Qk8ZWoE0xeQ8rMcz3HrN1D8-EuPGE9XL-IVtiU4yL34",
    "1X2xlYKeEz1u8M6uguUCIKVucaHhyj1raDSCCfOV83Uw", "1h1T7K2m63Skfa7XbAjZvDZCardqCBTs1cSUc9ebAlCA",
    "1Y5xFDiopRzeRrKoQpsVNMrdIy-pbI7nAzSR6wLaLBvI", "1id7sowbw3SSGnf5AhKpLxM29BuJOrhuHjzkpCgLf0dE",
    "1E9T3sLJwNfnbcM88mD0UmluqguGbQLhMaB5uyG8U_7M", "1uABl0uv7CMgZHKcsbU4lg_Pc6vwZ-XmQGuY3aFCJIVA",
    "1qGasW-RNViNgukVG4dg0C9rJulP0L4cz92wJWV7ghps", "1Jj3y-ywv3B72x5IqKJlZec--y-rW_eNK94TQUmmKuHo"
]

planilha_opera_id = "1mKknfMIISkU6QfZpmtYiJHbPR6NQdbeXYf_GwosDbu4"

lista_fic = []
lista_mic = []

for spreadsheet_id in ids_planilhas:
    df_fic = carregar_aba(spreadsheet_id, "RANKING FIC")
    if df_fic is not None:
        lista_fic.append(df_fic)

    df_mic = carregar_aba(spreadsheet_id, "RANKING MIC")
    if df_mic is not None:
        lista_mic.append(df_mic)

    time.sleep(60)

for spreadsheet_id in ids_planilhas:
  if spreadsheet_id == planilha_opera_id:
      df_opera = carregar_aba(spreadsheet_id, "RANKING ÓPERA FIC")
      if df_opera is not None:
          lista_fic.append(df_opera)
  time.sleep(10)

if lista_fic:
    pd.concat(lista_fic, ignore_index=True).to_excel("FIC.xlsx", index=False)
    print("✅ FIC.xlsx salvo.")
else:
    print("⚠️ Nenhuma aba FIC encontrada.")

if lista_mic:
    pd.concat(lista_mic, ignore_index=True).to_excel("MIC.xlsx", index=False)
    print("✅ MIC.xlsx salvo.")
else:
    print("⚠️ Nenhuma aba MIC encontrada.")

files.download("FIC.xlsx")
files.download("MIC.xlsx")

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

service = build('sheets', 'v4', credentials=creds)


##### TESTE DE LINKS ######
for sid in ids_planilhas:
    try:
        service.spreadsheets().get(spreadsheetId=sid).execute()
        print(f"{sid}: ✅ OK (acesso garantido)")
    except HttpError as err:
        code = err.resp.status
        if code == 404:
            print(f"{sid}: ❌ Inexistente ou inválido (404)")
        elif code == 403:
            print(f"{sid}: 🚫 Sem permissão – precisa compartilhar com a conta de serviço (403)")
        elif code == 503:
            print(f"{sid}: ⚠️ Erro temporário (503) — tente novamente mais tarde")
        else:
            print(f"{sid}: ❌ Erro {code} – {err}")

import io
import json
import os
import hashlib
from typing import Dict, List, Optional, Union
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import geopandas as gpd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from dotenv import load_dotenv
#############################################################
class GDriveWarehouse:
    """
    Data Warehouse usando Google Drive como storage.
    Suporta CSV, Excel (XLSX/XLS), JSON e Google Sheets.
    Cache em memória com lazy loading (só baixa quando necessário).
    """
    
    def __init__(
        self,
        folder_id: Optional[str] = None,
        credentials_path: Optional[str] = None,
        cache_ttl_minutes: int = 30,
        sheet_name: Union[str, int] = 0,
        load_env: bool = True
    ):
        """
        Args:
            folder_id: ID da pasta raiz no Google Drive (ou define via GDRIVE_FOLDER_ID no .env)
            credentials_path: Caminho para credentials.json (ou define via GDRIVE_CREDENTIALS_PATH no .env)
            cache_ttl_minutes: Tempo de vida do cache em minutos
            sheet_name: Nome ou índice da aba do Excel (0 = primeira aba, padrão)
            load_env: Se True, carrega variáveis do arquivo .env
        """
        # Carrega variáveis de ambiente
        if load_env:
            load_dotenv()
        
        # Obtém configurações (prioridade: parâmetro > .env > erro)
        self.folder_id = folder_id or os.getenv('GDRIVE_FOLDER_ID')
        credentials_path = credentials_path or os.getenv('GDRIVE_CREDENTIALS_PATH')
        
        if not self.folder_id:
            raise ValueError(
                "folder_id não fornecido. Defina via parâmetro ou variável GDRIVE_FOLDER_ID no .env"
            )
        
        if not credentials_path:
            raise ValueError(
                "credentials_path não fornecido. Defina via parâmetro ou variável GDRIVE_CREDENTIALS_PATH no .env"
            )
        
        if not Path(credentials_path).exists():
            raise FileNotFoundError(f"Arquivo de credenciais não encontrado: {credentials_path}")
        
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self.sheet_name = sheet_name
        
        # Autenticação
        SCOPES = [
            'https://www.googleapis.com/auth/drive.readonly',
            'https://www.googleapis.com/auth/spreadsheets.readonly'
        ]
        
        try:
            creds = service_account.Credentials.from_service_account_file(
                credentials_path, scopes=SCOPES
            )
            self.drive_service = build('drive', 'v3', credentials=creds)
            self.sheets_service = build('sheets', 'v4', credentials=creds)
            print("✓ Autenticação realizada com sucesso")
        except Exception as e:
            raise Exception(f"Erro ao autenticar com Google: {str(e)}")
        
        # Cache em memória
        self._cache = {}  # {file_id: {'df': DataFrame, 'timestamp': datetime, ...}}
        self._file_index = None  # {nome_tabela: file_info}
        self._file_index_timestamp = None
        
        # Metadados
        self.metadata = {}
    
    def _is_cache_valid(self, cache_entry: Dict) -> bool:
        """Verifica se o cache ainda é válido."""
        if not cache_entry:
            return False
        
        timestamp = cache_entry.get('timestamp')
        if not timestamp:
            return False
        
        return datetime.now() - timestamp < self.cache_ttl
    
    def _get_file_hash(self, file_id: str) -> str:
        """Gera hash do arquivo baseado no ID e modified time."""
        try:
            file_meta = self.drive_service.files().get(
                fileId=file_id, fields='id,modifiedTime'
            ).execute()
            hash_string = f"{file_id}_{file_meta.get('modifiedTime', '')}"
            return hashlib.md5(hash_string.encode()).hexdigest()
        except Exception as e:
            print(f"  Aviso: Erro ao obter hash: {e}")
            return hashlib.md5(file_id.encode()).hexdigest()
    
    def _build_file_index(self, force_refresh: bool = False) -> Dict[str, Dict]:
        """
        Constrói índice de arquivos disponíveis (sem baixar).
        Retorna: {nome_tabela: file_info}
        """
        # Verifica cache do índice
        if not force_refresh and self._file_index is not None:
            if self._file_index_timestamp and \
               datetime.now() - self._file_index_timestamp < self.cache_ttl:
                return self._file_index
        
        print("📋 Indexando arquivos no Google Drive...")
        
        all_files = self._list_files_recursive(self.folder_id)
        
        # Filtra apenas arquivos suportados
        file_index = {}
        for file in all_files:
            mime_type = file['mimeType']
            file_name = file['name']
            
            # Google Sheets
            if mime_type == 'application/vnd.google-apps.spreadsheet':
                key = file_name
                file_index[key] = file
            
            # Arquivos regulares
            else:
                ext = file_name.lower().split('.')[-1]
                if ext in ['csv', 'xlsx', 'xls', 'json','geojson']:
                    key = file_name.rsplit('.', 1)[0]  # Remove extensão
                    file_index[key] = file
        
        self._file_index = file_index
        self._file_index_timestamp = datetime.now()
        
        print(f"✓ {len(file_index)} arquivos indexados\n")
        
        return file_index
    
    def _list_files_recursive(self, folder_id: str) -> List[Dict]:
        """Lista todos os arquivos da pasta recursivamente."""
        all_files = []
        query = f"'{folder_id}' in parents and trashed=false"
        page_token = None
        
        while True:
            results = self.drive_service.files().list(
                q=query,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageSize=100,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, parents)",
                pageToken=page_token
            ).execute()
            
            files = results.get('files', [])
            
            for file in files:
                mime_type = file['mimeType']
                
                # Se for pasta, busca recursivamente
                if mime_type == 'application/vnd.google-apps.folder':
                    subfolder_files = self._list_files_recursive(file['id'])
                    all_files.extend(subfolder_files)
                else:
                    all_files.append(file)
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
        
        return all_files
    
    def _download_file(self, file_id: str) -> io.BytesIO:
        """Baixa arquivo do Drive direto na memória."""
        request = self.drive_service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"  Download: {int(status.progress() * 100)}%", end='\r')
        
        print()  # Nova linha após o download
        buffer.seek(0)
        return buffer
    
    def _read_google_sheet(self, file_id: str, file_name: str, sheet_name: Union[str, int, None] = None) -> Optional[pd.DataFrame]:
        """
        Lê um Google Spreadsheet e retorna DataFrame.
        """
        try:
            target_sheet = sheet_name if sheet_name is not None else self.sheet_name
            
            spreadsheet = self.sheets_service.spreadsheets().get(
                spreadsheetId=file_id
            ).execute()
            
            sheets = spreadsheet.get('sheets', [])
            
            if not sheets:
                print(f"  ⚠️  Nenhuma aba encontrada em: {file_name}")
                return None
            
            # Determina qual aba ler
            if isinstance(target_sheet, int):
                if target_sheet >= len(sheets):
                    print(f"  ⚠️  Índice {target_sheet} inválido. Total de abas: {len(sheets)}")
                    return None
                sheet_title = sheets[target_sheet]['properties']['title']
            else:
                sheet_title = target_sheet
                sheet_names = [s['properties']['title'] for s in sheets]
                if sheet_title not in sheet_names:
                    print(f"  ⚠️  Aba '{sheet_title}' não encontrada. Disponíveis: {sheet_names}")
                    return None
            
            # Lê os dados da aba
            range_name = f"'{sheet_title}'!A1:ZZ"
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=file_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            
            if not values:
                print(f"  ⚠️  Aba vazia: {sheet_title}")
                return None
            
            df = pd.DataFrame(values[1:], columns=values[0])
            df.columns = df.columns.str.strip()
            
            print(f"  📊 Google Sheet (aba: {sheet_title})")
            
            return df
            
        except Exception as e:
            print(f"  ✗ ERRO ao ler Google Sheet {file_name}: {str(e)}")
            return None
    
    def _read_file(self, file_info: Dict, sheet_name: Union[str, int, None] = None) -> Optional[Union[pd.DataFrame, gpd.GeoDataFrame]]:
        """
        Lê um arquivo e retorna DataFrame ou GeoDataFrame.
        Verifica cache antes de baixar.
        """
        file_name = file_info['name']
        file_id = file_info['id']
        mime_type = file_info['mimeType']
        
        # Identifica o tipo
        is_google_sheet = mime_type == 'application/vnd.google-apps.spreadsheet'
        
        if is_google_sheet:
            file_type = 'google_sheet'
        else:
            ext = file_name.lower().split('.')[-1]
            if ext not in ['csv', 'xlsx', 'xls', 'json', 'geojson']:
                return None
            file_type = ext
        
        # Verifica cache
        cache_key = f"{file_id}_{sheet_name if sheet_name else self.sheet_name}"
        
        if cache_key in self._cache:
            cache_entry = self._cache[cache_key]
            
            if self._is_cache_valid(cache_entry):
                current_hash = self._get_file_hash(file_id)
                if current_hash == cache_entry.get('hash'):
                    print(f"📦 Cache: {file_name}")
                    return cache_entry['df'].copy()
        
        # Download e leitura
        print(f"↓ Carregando: {file_name}")
        
        try:
            if is_google_sheet:
                df = self._read_google_sheet(file_id, file_name, sheet_name)
            else:
                buffer = self._download_file(file_id)
                
                excel_sheet = sheet_name if sheet_name is not None else self.sheet_name
                
                if file_type == 'csv':
                    # Tenta UTF-8 primeiro, depois Latin-1
                    seps = [";", ",", "|"]
                    encodings = ["utf-8", "latin-1"]
                    df = None
                    for enc in encodings:
                        for sep in seps:
                            try:
                                buffer.seek(0)
                                df_test = pd.read_csv(buffer, encoding=enc, sep=sep)
                                # valida: se veio mais de 1 coluna, o sep está correto
                                if df_test.shape[1] > 1:
                                    df = df_test
                                    print(f"  📄 Encoding: {enc} | sep: '{sep}'")
                                    break
                            except Exception:
                                pass
                        if df is not None:
                            break

                elif file_type in ['xlsx', 'xls']:
                    df = pd.read_excel(buffer, sheet_name=excel_sheet)
                    
                elif file_type == 'json':
                    buffer.seek(0)
                    data = json.load(buffer)
                    
                    # Verifica se é um GeoJSON disfarçado
                    if isinstance(data, dict) and data.get('type') == 'FeatureCollection':
                        # É um GeoJSON, usa geopandas
                        buffer.seek(0)
                        df = gpd.read_file(buffer)
                        print(f"  🗺️  GeoJSON detectado ({df.crs})")
                    else:
                        # JSON normal
                        if isinstance(data, list):
                            df = pd.json_normalize(data)
                        elif isinstance(data, dict):
                            # Se for dict com lista de registros
                            if any(isinstance(v, list) for v in data.values()):
                                # Tenta encontrar a lista principal
                                for key, value in data.items():
                                    if isinstance(value, list) and len(value) > 0:
                                        df = pd.json_normalize(value)
                                        print(f"  📄 Usando chave: '{key}'")
                                        break
                                else:
                                    df = pd.DataFrame([data])
                            else:
                                df = pd.DataFrame([data])
                        else:
                            df = pd.DataFrame([data])
                        print(f"  📄 JSON carregado")                
                elif file_type == 'geojson':
                    buffer.seek(0)
                    df = gpd.read_file(buffer)
                    print(f"  🗺️  GeoJSON carregado ({df.crs})")
            
            if df is None:
                return None
            
            # Limpa nomes de colunas (exceto GeoDataFrame que já vem limpo)
            if isinstance(df, pd.DataFrame) and not isinstance(df, gpd.GeoDataFrame):
                df.columns = df.columns.str.strip()
            
            # Armazena no cache
            file_hash = self._get_file_hash(file_id)
            self._cache[cache_key] = {
                'df': df.copy(),
                'timestamp': datetime.now(),
                'hash': file_hash,
                'file_name': file_name
            }
            
            print(f"✓ {file_name}: {df.shape[0]} linhas × {df.shape[1]} colunas\n")
            
            return df
            
        except Exception as e:
            print(f"✗ ERRO ao processar {file_name}: {str(e)}\n")
            return None
    
    def list_tables(self, force_refresh: bool = False) -> List[str]:
        """
        Lista todas as tabelas disponíveis no warehouse (sem baixar).
        
        Args:
            force_refresh: Se True, atualiza o índice de arquivos
        
        Returns:
            Lista com nomes das tabelas disponíveis
        """
        file_index = self._build_file_index(force_refresh=force_refresh)
        return sorted(file_index.keys())
    
    def get_table(
        self, 
        name: str, 
        sheet_name: Union[str, int, None] = None,
        force_refresh: bool = False
    ) -> Optional[Union[pd.DataFrame, gpd.GeoDataFrame]]:
        """
        Retorna uma tabela específica (baixa apenas se necessário).
        
        Args:
            name: Nome da tabela (sem extensão)
            sheet_name: Nome ou índice da aba (para Excel/Sheets)
            force_refresh: Se True, ignora cache e recarrega
        
        Returns:
            DataFrame, GeoDataFrame ou None se não encontrado
        """
        # Constrói índice se necessário
        file_index = self._build_file_index()
        
        # Busca o arquivo
        if name not in file_index:
            print(f"⚠️  Tabela '{name}' não encontrada")
            print(f"Tabelas disponíveis: {', '.join(sorted(file_index.keys())[:5])}...")
            return None
        
        file_info = file_index[name]
        
        # Remove do cache se force_refresh
        if force_refresh:
            cache_key = f"{file_info['id']}_{sheet_name if sheet_name else self.sheet_name}"
            if cache_key in self._cache:
                del self._cache[cache_key]
        
        # Lê o arquivo
        df = self._read_file(file_info, sheet_name=sheet_name)
        
        # Atualiza metadados
        if df is not None:
            is_geo = isinstance(df, gpd.GeoDataFrame)
            
            self.metadata[name] = {
                'file_name': file_info['name'],
                'file_type': 'Google Sheet' if file_info['mimeType'] == 'application/vnd.google-apps.spreadsheet' else file_info['name'].split('.')[-1].upper(),
                'is_geospatial': is_geo,
                'crs': str(df.crs) if is_geo else None,
                'shape': df.shape,
                'columns': list(df.columns),
                'modified_time': file_info.get('modifiedTime'),
                'loaded_at': datetime.now().isoformat()
            }
        
        return df
    
    def get_tables(
        self, 
        names: List[str], 
        sheet_name: Union[str, int, None] = None
    ) -> Dict[str, Union[pd.DataFrame, gpd.GeoDataFrame]]:
        """
        Retorna múltiplas tabelas de uma vez.
        
        Args:
            names: Lista de nomes de tabelas
            sheet_name: Nome ou índice da aba (para Excel/Sheets)
        
        Returns:
            Dicionário {nome: DataFrame ou GeoDataFrame}
        """
        print(f"\n{'='*60}")
        print(f"CARREGANDO {len(names)} TABELAS")
        print(f"{'='*60}\n")
        
        results = {}
        for name in names:
            df = self.get_table(name, sheet_name=sheet_name)
            if df is not None:
                results[name] = df
        
        print(f"{'='*60}")
        print(f"✓ {len(results)}/{len(names)} tabelas carregadas")
        print(f"{'='*60}\n")
        
        return results
    
    def search_tables(self, keyword: str) -> List[str]:
        """
        Busca tabelas por palavra-chave no nome.
        
        Args:
            keyword: Palavra-chave para busca
        
        Returns:
            Lista de nomes de tabelas encontradas
        """
        file_index = self._build_file_index()
        return [name for name in file_index.keys() if keyword.lower() in name.lower()]
    
    def get_metadata(self, name: Optional[str] = None) -> Union[Dict, Dict[str, Dict]]:
        """Retorna metadados de uma tabela ou de todas as carregadas."""
        if name:
            return self.metadata.get(name, {})
        return self.metadata
    
    def join_tables(
        self,
        left_table: str,
        right_table: str,
        on: Union[str, List[str]],
        how: str = 'left',
        sheet_name: Union[str, int, None] = None
    ) -> pd.DataFrame:
        """
        Realiza join entre duas tabelas (carrega automaticamente se necessário).
        
        Args:
            left_table: Nome da tabela esquerda
            right_table: Nome da tabela direita
            on: Coluna(s) para o join
            how: Tipo de join ('inner', 'left', 'right', 'outer')
            sheet_name: Nome ou índice da aba (para Excel/Sheets)
        """
        # Carrega tabelas se necessário
        left_df = self.get_table(left_table, sheet_name=sheet_name)
        right_df = self.get_table(right_table, sheet_name=sheet_name)
        
        if left_df is None or right_df is None:
            raise ValueError(f"Não foi possível carregar as tabelas para o join")
        
        return pd.merge(left_df, right_df, on=on, how=how)
    
    def list_tables(self, force_refresh: bool = False) -> List[str]:
        """
        Lista todas as tabelas disponíveis no warehouse (sem baixar).
        
        Args:
            force_refresh: Se True, atualiza o índice de arquivos
        
        Returns:
            Lista com nomes das tabelas disponíveis
        """
        file_index = self._build_file_index(force_refresh=force_refresh)
        return sorted(file_index.keys())
    
    def get_table(
        self, 
        name: str, 
        sheet_name: Union[str, int, None] = None,
        force_refresh: bool = False
    ) -> Optional[pd.DataFrame]:
        """
        Retorna uma tabela específica (baixa apenas se necessário).
        
        Args:
            name: Nome da tabela (sem extensão)
            sheet_name: Nome ou índice da aba (para Excel/Sheets)
            force_refresh: Se True, ignora cache e recarrega
        
        Returns:
            DataFrame ou None se não encontrado
        """
        # Constrói índice se necessário
        file_index = self._build_file_index()
        
        # Busca o arquivo
        if name not in file_index:
            print(f"⚠️  Tabela '{name}' não encontrada")
            print(f"Tabelas disponíveis: {', '.join(sorted(file_index.keys())[:5])}...")
            return None
        
        file_info = file_index[name]
        
        # Remove do cache se force_refresh
        if force_refresh:
            cache_key = f"{file_info['id']}_{sheet_name if sheet_name else self.sheet_name}"
            if cache_key in self._cache:
                del self._cache[cache_key]
        
        # Lê o arquivo
        df = self._read_file(file_info, sheet_name=sheet_name)
        
        # Atualiza metadados
        if df is not None:
            self.metadata[name] = {
                'file_name': file_info['name'],
                'file_type': 'Google Sheet' if file_info['mimeType'] == 'application/vnd.google-apps.spreadsheet' else file_info['name'].split('.')[-1].upper(),
                'shape': df.shape,
                'columns': list(df.columns),
                'modified_time': file_info.get('modifiedTime'),
                'loaded_at': datetime.now().isoformat()
            }
        
        return df
    
    def get_tables(
        self, 
        names: List[str], 
        sheet_name: Union[str, int, None] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Retorna múltiplas tabelas de uma vez.
        
        Args:
            names: Lista de nomes de tabelas
            sheet_name: Nome ou índice da aba (para Excel/Sheets)
        
        Returns:
            Dicionário {nome: DataFrame}
        """
        print(f"\n{'='*60}")
        print(f"CARREGANDO {len(names)} TABELAS")
        print(f"{'='*60}\n")
        
        results = {}
        for name in names:
            df = self.get_table(name, sheet_name=sheet_name)
            if df is not None:
                results[name] = df
        
        print(f"{'='*60}")
        print(f"✓ {len(results)}/{len(names)} tabelas carregadas")
        print(f"{'='*60}\n")
        
        return results
    
    def search_tables(self, keyword: str) -> List[str]:
        """
        Busca tabelas por palavra-chave no nome.
        Args:
            keyword: Palavra-chave para busca
        Returns:
            Lista de nomes de tabelas encontradas
        """
        file_index = self._build_file_index()
        return [name for name in file_index.keys() if keyword.lower() in name.lower()]
    
    def get_metadata(self, name: Optional[str] = None) -> Union[Dict, Dict[str, Dict]]:
        """Retorna metadados de uma tabela ou de todas as carregadas."""
        if name:
            return self.metadata.get(name, {})
        return self.metadata
    
    def join_tables(
        self,
        left_table: str,
        right_table: str,
        on: Union[str, List[str]],
        how: str = 'left',
        sheet_name: Union[str, int, None] = None
    ) -> pd.DataFrame:
        """
        Realiza join entre duas tabelas (carrega automaticamente se necessário).
        
        Args:
            left_table: Nome da tabela esquerda
            right_table: Nome da tabela direita
            on: Coluna(s) para o join
            how: Tipo de join ('inner', 'left', 'right', 'outer')
            sheet_name: Nome ou índice da aba (para Excel/Sheets)
        """
        # Carrega tabelas se necessário
        left_df = self.get_table(left_table, sheet_name=sheet_name)
        right_df = self.get_table(right_table, sheet_name=sheet_name)
        
        if left_df is None or right_df is None:
            raise ValueError(f"Não foi possível carregar as tabelas para o join")
        
        return pd.merge(left_df, right_df, on=on, how=how)
    
    def clear_cache(self):
        """Limpa o cache em memória."""
        self._cache.clear()
        self._file_index = None
        self._file_index_timestamp = None
        print("✓ Cache em memória limpo com sucesso")
    
    def get_cache_info(self) -> Dict:
        """Retorna informações sobre o cache atual."""
        total_size = 0
        valid_entries = 0
        
        for cache_key, cache_entry in self._cache.items():
            if self._is_cache_valid(cache_entry):
                valid_entries += 1
                df = cache_entry['df']
                total_size += df.memory_usage(deep=True).sum() / (1024 * 1024)
        
        return {
            'total_entries': len(self._cache),
            'valid_entries': valid_entries,
            'expired_entries': len(self._cache) - valid_entries,
            'estimated_size_mb': round(total_size, 2),
            'ttl_minutes': self.cache_ttl.seconds // 60,
            'indexed_files': len(self._file_index) if self._file_index else 0
        }
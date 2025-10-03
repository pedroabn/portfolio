import os
import json
import pandas as pd
import sqlalchemy as sq
from sqlalchemy import text, Text, Integer, Float, Boolean, DateTime
from sqlalchemy.dialects.mysql import LONGTEXT, MEDIUMTEXT
from pandas import json_normalize
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler('import_process.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def create_database_engine():
    """Cria e configura a engine do banco de dados"""
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "45705254Pn!")
    host = os.getenv("DB_HOST", "localhost")
    database = os.getenv("DB_DATABASE", "cadastrocultural")
    port = os.getenv("DB_PORT", "3306")
    
    connection_string = f'mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}'
    
    try:
        engine = sq.create_engine(
            connection_string,
            connect_args={
                'connect_timeout': 300,
                'autocommit': True,
                'sql_mode': 'TRADITIONAL',
                'charset': 'utf8mb4',
                'collation': 'utf8mb4_unicode_ci'
            },
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=10,
            max_overflow=20,
            echo=False
        )
        
        # Testar conexão
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Conexão com banco estabelecida com sucesso")
        return engine
        
    except Exception as e:
        logger.error(f"❌ Erro ao estabelecer conexão: {e}")
        raise

def read_file_with_encoding(file_path: str, encodings: list = ['utf-8', 'latin-1']) -> str:
    """Tenta ler arquivo com diferentes encodings"""
    content = None
    used_encoding = None
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
                used_encoding = encoding
                break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.warning(f"Erro ao ler {file_path} com encoding {encoding}: {e}")
            continue
    
    if content is None:
        raise ValueError(f"Não foi possível ler o arquivo {file_path} com nenhum dos encodings: {encodings}")
    
    logger.info(f"Arquivo {file_path} lido com encoding: {used_encoding}")
    return content, used_encoding

def normalize_objects(df: pd.DataFrame) -> pd.DataFrame:
    """Converte dicts e listas em strings JSON"""
    for col in df.columns:
        if df[col].dtype == 'object':
            # Verificar se há objetos complexos na coluna
            has_complex_objects = df[col].apply(lambda x: isinstance(x, (dict, list))).any()
            if has_complex_objects:
                logger.info(f"Normalizando objetos complexos na coluna: {col}")
                df[col] = df[col].apply(
                    lambda x: json.dumps(x, ensure_ascii=False, default=str) 
                    if isinstance(x, (dict, list)) else x
                )
    return df

def optimize_data_types(df: pd.DataFrame) -> pd.DataFrame:
    """Otimiza tipos de dados para reduzir uso de memória"""
    logger.info("Otimizando tipos de dados...")
    
    for col in df.columns:
        col_type = df[col].dtype
        
        # Otimizar inteiros
        if col_type == 'int64':
            col_min, col_max = df[col].min(), df[col].max()
            if col_min >= -128 and col_max <= 127:
                df[col] = df[col].astype('int8')
            elif col_min >= -32768 and col_max <= 32767:
                df[col] = df[col].astype('int16')
            elif col_min >= -2147483648 and col_max <= 2147483647:
                df[col] = df[col].astype('int32')
        
        # Otimizar floats
        elif col_type == 'float64':
            df[col] = pd.to_numeric(df[col], downcast='float')
        
        # Detectar colunas categóricas
        elif col_type == 'object':
            unique_count = df[col].nunique()
            total_count = len(df[col])
            if unique_count / total_count < 0.5 and unique_count > 1:  # Se menos de 50% dos valores são únicos
                df[col] = df[col].astype('category')
                logger.info(f"Coluna {col} convertida para categoria")
    
    return df

def smart_truncate_data(df: pd.DataFrame, max_length: int = 65535) -> pd.DataFrame:
    """Trunca dados baseado no tipo de coluna"""
    for col in df.columns:
        if df[col].dtype == 'object' or str(df[col].dtype) == 'category':
            # Determinar limite baseado no nome da coluna
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in ['features', 'description', 'content', 'text']):
                limit = 4294967295  # LONGTEXT
            elif any(keyword in col_lower for keyword in ['summary', 'note', 'comment']):
                limit = 16777215  # MEDIUMTEXT
            else:
                limit = max_length  # TEXT
            
            # Truncar apenas se necessário
            mask = df[col].astype(str).str.len() > limit
            if mask.any():
                logger.warning(f"Truncando {mask.sum()} registros na coluna {col}")
                df.loc[mask, col] = df.loc[mask, col].astype(str).str[:limit]
    
    return df

def convert_pandas_to_sql_types(df: pd.DataFrame) -> Dict[str, Any]:
    """Converte tipos do pandas para SQLAlchemy"""
    dtype_mapping = {}
    
    for col in df.columns:
        pandas_type = str(df[col].dtype)
        col_lower = col.lower()
        
        if pandas_type.startswith('int'):
            dtype_mapping[col] = Integer()
        elif pandas_type.startswith('float'):
            dtype_mapping[col] = Float()
        elif pandas_type.startswith('bool'):
            dtype_mapping[col] = Boolean()
        elif pandas_type.startswith('datetime'):
            dtype_mapping[col] = DateTime()
        elif pandas_type == 'category':
            # Para categóricas, usar VARCHAR otimizado
            max_len = df[col].astype(str).str.len().max()
            if max_len <= 255:
                dtype_mapping[col] = sq.VARCHAR(255)
            else:
                dtype_mapping[col] = Text()
        else:
            # Para texto, escolher tipo baseado no conteúdo e nome
            max_length = df[col].astype(str).str.len().max() if not df[col].empty else 0
            
            if any(keyword in col_lower for keyword in ['features', 'description', 'content']):
                dtype_mapping[col] = LONGTEXT()
            elif any(keyword in col_lower for keyword in ['summary', 'note', 'comment']) or max_length > 65535:
                dtype_mapping[col] = MEDIUMTEXT()
            elif max_length <= 255:
                dtype_mapping[col] = sq.VARCHAR(255)
            else:
                dtype_mapping[col] = Text()
    
    return dtype_mapping

def safe_drop_table(engine, table_name: str) -> bool:
    """Remove tabela de forma segura"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with engine.begin() as conn:
                conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
                conn.execute(text(f"DROP TABLE IF EXISTS `{table_name}`"))
                conn.execute(text("SET FOREIGN_KEY_CHECKS=1;"))
            logger.info(f"Tabela {table_name} removida com sucesso")
            return True
        except Exception as e:
            logger.warning(f"Tentativa {attempt + 1} falhou ao remover tabela {table_name}: {e}")
            if attempt == max_retries - 1:
                logger.error(f"Falha ao remover tabela {table_name} após {max_retries} tentativas")
                return False
            time.sleep(2)
    return False

def read_csv_smart(file_path: str) -> Optional[pd.DataFrame]:
    """Lê CSV com suporte a utf-8 e latin-1"""
    encodings = ['utf-8', 'latin-1']
    separators = [';', ',', '\t', '|']
    
    for encoding in encodings:
        for sep in separators:
            try:
                # Testar com algumas linhas primeiro
                df_test = pd.read_csv(file_path, encoding=encoding, delimiter=sep, nrows=5)
                if len(df_test.columns) > 1:  # Se tiver mais de uma coluna
                    # Ler arquivo completo
                    df = pd.read_csv(
                        file_path, 
                        encoding=encoding, 
                        delimiter=sep,
                        low_memory=False,
                        na_values=['', 'NULL', 'null', 'N/A', 'n/a', 'NA', 'nan']
                    )
                    logger.info(f"CSV lido - Encoding: {encoding}, Separador: '{sep}', Linhas: {len(df)}, Colunas: {len(df.columns)}")
                    return df
            except Exception:
                continue
    
    # Última tentativa com parâmetros padrão
    for encoding in encodings:
        try:
            df = pd.read_csv(file_path, encoding=encoding, low_memory=False)
            logger.info(f"CSV lido com configuração padrão - Encoding: {encoding}, Linhas: {len(df)}")
            return df
        except Exception as e:
            logger.warning(f"Falha com encoding {encoding}: {e}")
            continue
    
    logger.error(f"Não foi possível ler o CSV: {file_path}")
    return None

def read_json_smart(file_path: str) -> Optional[pd.DataFrame]:
    """Lê JSON com suporte a utf-8 e latin-1"""
    encodings = ['utf-8', 'latin-1']
    
    # Tentar pandas read_json primeiro
    for encoding in encodings:
        try:
            df = pd.read_json(file_path, encoding=encoding)
            if not df.empty:
                logger.info(f"JSON lido com pandas - Encoding: {encoding}, Linhas: {len(df)}")
                return df
        except Exception:
            continue
    
    # Tentar como objeto JSON
    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                dados = json.load(f)
            
            # Processar diferentes estruturas
            df = None
            if isinstance(dados, list):
                df = json_normalize(dados)
            elif isinstance(dados, dict):
                # Procurar arrays que podem ser dados tabulares
                potential_data = None
                for key, value in dados.items():
                    if isinstance(value, list) and len(value) > 0:
                        if isinstance(value[0], dict):
                            potential_data = value
                            break
                
                if potential_data:
                    df = json_normalize(potential_data)
                else:
                    df = json_normalize([dados])
            else:
                df = pd.DataFrame([dados])
            
            if df is not None and not df.empty:
                logger.info(f"JSON lido como objeto - Encoding: {encoding}, Linhas: {len(df)}, Colunas: {len(df.columns)}")
                return df
                
        except Exception as e:
            logger.warning(f"Falha ao ler JSON com encoding {encoding}: {e}")
            continue
    
    logger.error(f"Não foi possível ler o JSON: {file_path}")
    return None

def process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica todas as transformações no DataFrame"""
    logger.info(f"Processando DataFrame com {len(df)} registros...")
    
    # Aplicar transformações
    df = normalize_objects(df)
    df = optimize_data_types(df)
    df = smart_truncate_data(df)
    
    return df

def process_single_file(engine, file_path: str, file_type: str) -> Tuple[bool, str]:
    """Processa um único arquivo"""
    try:
        file_name = Path(file_path).name
        table_name = Path(file_path).stem
        
        logger.info(f'Iniciando processamento: {file_name}')
        
        # Ler arquivo baseado no tipo
        if file_type == 'csv':
            df = read_csv_smart(file_path)
        elif file_type == 'json':
            df = read_json_smart(file_path)
        else:
            return False, f"Tipo de arquivo não suportado: {file_type}"
        
        if df is None or df.empty:
            return False, f"Arquivo vazio ou não pôde ser lido: {file_name}"
        
        # Processar DataFrame
        df = process_dataframe(df)
        
        # Converter tipos para SQL
        dtype_dict = convert_pandas_to_sql_types(df)
        logger.info(f"Tipos SQL mapeados: {len(dtype_dict)} colunas")
        
        # Remover tabela existente
        if not safe_drop_table(engine, table_name):
            return False, f"Não foi possível remover tabela existente: {table_name}"
        
        # Inserir dados
        try:
            df.to_sql(
                table_name,
                con=engine,
                if_exists="fail",
                index=False,
                chunksize=1000,
                dtype=dtype_dict,
                method='multi'
            )
            
            success_msg = f"✅ {file_type.upper()} importado: {file_name} -> {table_name} ({len(df)} registros)"
            logger.info(success_msg)
            return True, success_msg
            
        except Exception as e:
            error_msg = f"Erro ao inserir dados na tabela {table_name}: {e}"
            logger.error(error_msg)
            return False, error_msg
            
    except Exception as e:
        error_msg = f"❌ Erro ao processar {Path(file_path).name}: {e}"
        logger.error(error_msg)
        return False, error_msg

def process_files_in_directory(engine, directory: str, file_extension: str, max_workers: int = 3) -> Dict[str, Any]:
    """Processa arquivos de um diretório"""
    if not os.path.exists(directory):
        logger.warning(f"Diretório não encontrado: {directory}")
        return {"success": [], "errors": [], "total": 0}
    
    # Encontrar arquivos
    files = [f for f in os.listdir(directory) if f.lower().endswith(f'.{file_extension}')]
    
    if not files:
        logger.warning(f"Nenhum arquivo {file_extension.upper()} encontrado em: {directory}")
        return {"success": [], "errors": [], "total": 0}
    
    logger.info(f"Encontrados {len(files)} arquivos {file_extension.upper()}")
    
    results = {"success": [], "errors": [], "total": len(files)}
    
    # Processar arquivos (paralelo se mais de 1 worker, senão sequencial)
    if max_workers > 1 and len(files) > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(process_single_file, engine, os.path.join(directory, file), file_extension): file 
                for file in files
            }
            
            for future in as_completed(future_to_file):
                file = future_to_file[future]
                try:
                    success, message = future.result()
                    if success:
                        results["success"].append(message)
                    else:
                        results["errors"].append(f"{file}: {message}")
                except Exception as e:
                    results["errors"].append(f"{file}: Erro inesperado - {e}")
    else:
        # Processamento sequencial
        for file in files:
            try:
                success, message = process_single_file(engine, os.path.join(directory, file), file_extension)
                if success:
                    results["success"].append(message)
                else:
                    results["errors"].append(f"{file}: {message}")
            except Exception as e:
                results["errors"].append(f"{file}: Erro inesperado - {e}")
    
    return results

def generate_detailed_report(csv_results: Dict, json_results: Dict) -> str:
    """Gera relatório detalhado do processamento"""
    report = "\n" + "="*50 + " RELATÓRIO DE IMPORTAÇÃO " + "="*50 + "\n"
    
    # CSVs
    report += f"\n📊 ARQUIVOS CSV:\n"
    report += f"  Total: {csv_results['total']}\n"
    report += f"  Sucesso: {len(csv_results['success'])}\n"
    report += f"  Erros: {len(csv_results['errors'])}\n"
    
    if csv_results['success']:
        report += f"\n  ✅ Sucessos:\n"
        for msg in csv_results['success']:
            report += f"    {msg}\n"
    
    if csv_results['errors']:
        report += f"\n  ❌ Erros:\n"
        for msg in csv_results['errors']:
            report += f"    {msg}\n"
    
    # JSONs
    report += f"\n📄 ARQUIVOS JSON:\n"
    report += f"  Total: {json_results['total']}\n"
    report += f"  Sucesso: {len(json_results['success'])}\n"
    report += f"  Erros: {len(json_results['errors'])}\n"
    
    if json_results['success']:
        report += f"\n  ✅ Sucessos:\n"
        for msg in json_results['success']:
            report += f"    {msg}\n"
    
    if json_results['errors']:
        report += f"\n  ❌ Erros:\n"
        for msg in json_results['errors']:
            report += f"    {msg}\n"
    
    # Resumo final
    total_files = csv_results['total'] + json_results['total']
    total_success = len(csv_results['success']) + len(json_results['success'])
    total_errors = len(csv_results['errors']) + len(json_results['errors'])
    
    report += f"\n🎯 RESUMO FINAL:\n"
    report += f"  Total de arquivos: {total_files}\n"
    report += f"  Importados com sucesso: {total_success}\n"
    report += f"  Arquivos com erro: {total_errors}\n"
    if total_files > 0:
        report += f"  Taxa de sucesso: {(total_success/total_files*100):.1f}%\n"
    else:
        report += f"  Taxa de sucesso: 0%\n"
    
    report += "\n" + "="*115 + "\n"
    
    return report

def cleanup_engine(engine):
    """Limpa recursos do banco"""
    if engine:
        engine.dispose()
        logger.info("Recursos do banco liberados")

def main():
    """Função principal"""
    start_time = time.time()
    
    # Configurar caminhos
    pasta_csv = os.getenv("CSV_PATH", r"C:\Users\pedro.bastos\Documents\vscode\Cadastros\db")
    pasta_json = os.getenv("JSON_PATH", r"C:\Users\pedro.bastos\Documents\vscode\Cadastros\jsons")
    max_workers = int(os.getenv("MAX_WORKERS", "3"))
    
    engine = None
    try:
        # Criar engine do banco
        logger.info("🚀 Iniciando processamento de arquivos...")
        engine = create_database_engine()
        
        # Processar arquivos CSV
        logger.info(f"Verificando pasta CSV: {pasta_csv}")
        csv_results = process_files_in_directory(engine, pasta_csv, 'csv', max_workers)
        
        # Processar arquivos JSON  
        logger.info(f"Verificando pasta JSON: {pasta_json}")
        json_results = process_files_in_directory(engine, pasta_json, 'json', max_workers)
        
        # Gerar relatório
        report = generate_detailed_report(csv_results, json_results)
        print(report)
        logger.info("Relatório gerado")
        
        # Salvar relatório
        try:
            with open('import_report.txt', 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info("Relatório salvo em import_report.txt")
        except Exception as e:
            logger.warning(f"Erro ao salvar relatório: {e}")
        
        # Tempo de execução
        elapsed_time = time.time() - start_time
        logger.info(f"⏱️ Tempo total: {elapsed_time:.2f} segundos")
        
        logger.info("🎉 Processamento concluído!")
        
    except Exception as e:
        logger.error(f"❌ Erro crítico: {e}")
        raise
    finally:
        cleanup_engine(engine)

if __name__ == "__main__":
    main()
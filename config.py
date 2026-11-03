"""
config.py
---------
Parâmetros centrais do projeto + leitura das credenciais do arquivo .env.

Nenhuma senha fica escrita aqui: tudo que é sensível vem do .env
(que está no .gitignore e, portanto, nunca vai para o GitHub).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# --------------------------------------------------------------------------
# Caminhos
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"          # ignorada pelo Git
ZIP_PATH = DATA_DIR / "viagens_2025.zip"
CSV_DIR = DATA_DIR / "csv"
IMG_DIR = BASE_DIR / "img"            # gráficos exportados (usados no README)

# --------------------------------------------------------------------------
# Fonte dos dados (Google Drive) - basta UMA das duas opções:
#
# Opção 1 (preferencial): ID do arquivo .zip.
#   Link do tipo https://drive.google.com/file/d/<ID>/view -> cole só o <ID>
# Opção 2 (automática): link da PASTA do Drive que contém o .zip
#   (é o link "arquivo .zip" do enunciado). Usada se a opção 1 estiver vazia.
# --------------------------------------------------------------------------
DRIVE_FILE_ID = "COLE_AQUI_O_ID_DO_ARQUIVO"
DRIVE_FOLDER_URL = ("https://drive.google.com/drive/folders/"
                    "1b9Yc_s9gm6TAERY3BjOw2bixu70X3tZL")

# --------------------------------------------------------------------------
# Formato dos CSVs do Portal da Transparência
# --------------------------------------------------------------------------
CSV_SEP = ";"
CSV_ENCODING = "latin-1"
CHUNK_SIZE = 10_000      # linhas lidas por bloco do CSV
BATCH_SIZE = 5_000       # linhas por INSERT em lote

# --------------------------------------------------------------------------
# Banco de dados (valores vindos do .env)
# --------------------------------------------------------------------------
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "dbname": os.getenv("DB_NAME", "viagens_db"),
}

# --------------------------------------------------------------------------
# Mapeamento CSV -> tabela Raw
# A ordem das colunas abaixo é a MESMA ordem das colunas do CSV.
# A camada Raw replica o CSV inteiro (inclusive colunas que a Silver não usa).
# --------------------------------------------------------------------------
RAW_TABELAS = {
    "raw_viagem": {
        "arquivo": "2025_Viagem.csv",
        "colunas": [
            "id_viagem", "num_proposta", "situacao", "viagem_urgente",
            "justificativa_urgencia", "cod_orgao_superior",
            "nome_orgao_superior", "cod_orgao_solicitante",
            "nome_orgao_solicitante", "cpf_viajante", "nome_viajante",
            "cargo", "funcao", "descricao_funcao", "data_inicio",
            "data_fim", "destinos", "motivo", "valor_diarias",
            "valor_passagens", "valor_devolucao", "valor_outros_gastos",
        ],
    },
    "raw_pagamento": {
        "arquivo": "2025_Pagamento.csv",
        "colunas": [
            "id_viagem", "num_proposta", "cod_orgao_superior",
            "nome_orgao_superior", "cod_orgao_pagador",
            "nome_orgao_pagador", "cod_ug_pagadora", "nome_ug_pagadora",
            "tipo_pagamento", "valor",
        ],
    },
    "raw_passagem": {
        "arquivo": "2025_Passagem.csv",
        "colunas": [
            "id_viagem", "num_proposta", "meio_transporte",
            "pais_origem_ida", "uf_origem_ida", "cidade_origem_ida",
            "pais_destino_ida", "uf_destino_ida", "cidade_destino_ida",
            "pais_origem_volta", "uf_origem_volta", "cidade_origem_volta",
            "pais_destino_volta", "uf_destino_volta", "cidade_destino_volta",
            "valor_passagem", "taxa_servico", "data_emissao", "hora_emissao",
        ],
    },
    "raw_trecho": {
        "arquivo": "2025_Trecho.csv",
        "colunas": [
            "id_viagem", "num_proposta", "sequencia_trecho", "origem_data",
            "origem_pais", "origem_uf", "origem_cidade", "destino_data",
            "destino_pais", "destino_uf", "destino_cidade",
            "meio_transporte", "numero_diarias", "missao",
        ],
    },
}

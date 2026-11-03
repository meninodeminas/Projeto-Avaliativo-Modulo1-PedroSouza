"""
1_extrair.py
------------
Fase 1 - Extração e camada Raw.

    1. Baixa o .zip do Google Drive (sem intervenção manual).
    2. Descompacta e localiza os 4 CSVs.
    3. Lê cada CSV em blocos (chunks), SEM alterar o conteúdo (tudo texto).
    4. Carrega nas tabelas raw_*.

Idempotente: cada tabela recebe TRUNCATE antes da carga, então rodar o
script várias vezes nunca duplica registros.
Resiliente: cada etapa tem try/except com mensagem clara.

Execução:  python 1_extrair.py
"""
import shutil
import sys
import zipfile
from pathlib import Path

import gdown
import pandas as pd

from banco import consultar, executar, inserir_em_lote
from config import (CHUNK_SIZE, CSV_DIR, CSV_ENCODING, CSV_SEP, DATA_DIR,
                    DRIVE_FILE_ID, DRIVE_FOLDER_URL, RAW_TABELAS, ZIP_PATH)


def _id_preenchido():
    return bool(DRIVE_FILE_ID) and not DRIVE_FILE_ID.startswith("COLE_AQUI")


def _baixar_arquivo():
    """Opção 1: baixa o .zip pelo ID do arquivo."""
    print(f"[download] Baixando arquivo do Google Drive (id={DRIVE_FILE_ID})")
    caminho = gdown.download(id=DRIVE_FILE_ID, output=str(ZIP_PATH),
                             quiet=False)
    if caminho is None or not ZIP_PATH.exists():
        raise RuntimeError("Download falhou: verifique o ID e se o arquivo "
                           "está compartilhado como 'Qualquer pessoa com o link'.")


def _baixar_pasta():
    """
    Opção 2: baixa a PASTA do Drive inteira e localiza o .zip dentro dela.
    Útil quando só temos o link da pasta (como no enunciado).
    """
    destino = DATA_DIR / "drive"
    if destino.exists():
        shutil.rmtree(destino)          # idempotência: começa sempre limpo
    print(f"[download] Baixando pasta do Google Drive: {DRIVE_FOLDER_URL}")
    arquivos = gdown.download_folder(url=DRIVE_FOLDER_URL, output=str(destino),
                                     quiet=False)
    if not arquivos:
        raise RuntimeError("Download da pasta falhou: verifique o link e se "
                           "ela está compartilhada como 'Qualquer pessoa com o link'.")
    zips = sorted(destino.rglob("*.zip"))
    if not zips:
        raise FileNotFoundError(f"Nenhum .zip encontrado na pasta. Arquivos "
                                f"baixados: {[Path(a).name for a in arquivos]}")
    if len(zips) > 1:
        print(f"[download] Aviso: {len(zips)} zips na pasta, usando {zips[0].name}")
    shutil.copyfile(zips[0], ZIP_PATH)


def baixar_zip():
    """Baixa o .zip do Google Drive para data/ (por ID ou pela pasta)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()               # nunca reaproveita download antigo
    if _id_preenchido():
        _baixar_arquivo()
    elif DRIVE_FOLDER_URL:
        _baixar_pasta()
    else:
        raise ValueError("Preencha DRIVE_FILE_ID ou DRIVE_FOLDER_URL no config.py.")
    tamanho_mb = ZIP_PATH.stat().st_size / 1_048_576
    print(f"[download] OK -> {ZIP_PATH} ({tamanho_mb:.1f} MB)")


def descompactar_zip():
    """Extrai o .zip e devolve {nome_do_arquivo: caminho} dos CSVs."""
    if CSV_DIR.exists():
        shutil.rmtree(CSV_DIR)          # remove CSVs de execuções anteriores
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH) as arquivo_zip:
        arquivo_zip.extractall(CSV_DIR)
    # rglob: funciona mesmo se os CSVs estiverem dentro de uma subpasta do zip
    encontrados = {p.name: p for p in CSV_DIR.rglob("*.csv")}
    print(f"[zip] CSVs encontrados: {sorted(encontrados)}")
    return encontrados


def carregar_csv_na_raw(tabela, caminho_csv, colunas):
    """
    Lê o CSV em blocos e insere na tabela Raw, sem transformar os valores.

    dtype=str + keep_default_na=False garantem que nada seja convertido:
    '1272,97' continua '1272,97', '05/01/2025' continua '05/01/2025' e
    células vazias continuam como texto vazio.
    """
    executar(f"TRUNCATE TABLE {tabela}")          # idempotência

    leitor = pd.read_csv(
        caminho_csv,
        sep=CSV_SEP,
        encoding=CSV_ENCODING,
        dtype=str,
        keep_default_na=False,
        chunksize=CHUNK_SIZE,
    )

    total = 0
    for numero, bloco in enumerate(leitor, start=1):
        if len(bloco.columns) != len(colunas):
            raise ValueError(
                f"{caminho_csv.name}: esperava {len(colunas)} colunas e "
                f"encontrou {len(bloco.columns)}.\nCabeçalho do arquivo: "
                f"{list(bloco.columns)}\nAjuste RAW_TABELAS no config.py e "
                f"o 0_criar_banco.sql."
            )
        if numero == 1:
            print(f"   cabeçalho original: {list(bloco.columns)[:4]} ...")
        bloco.columns = colunas                   # renomeia pela posição
        linhas = list(bloco.itertuples(index=False, name=None))
        total += inserir_em_lote(tabela, colunas, linhas)
        print(f"   bloco {numero}: {total:,} linhas carregadas")
    return total


def conferir_carga(tabela, linhas_lidas):
    """Compara o que foi lido do CSV com o que está no banco."""
    no_banco = int(consultar(f"SELECT COUNT(*) AS n FROM {tabela}")["n"][0])
    status = "OK" if no_banco == linhas_lidas else "DIVERGENTE"
    print(f"[{status}] {tabela}: CSV={linhas_lidas:,} | banco={no_banco:,}")
    return no_banco == linhas_lidas


def main():
    try:
        baixar_zip()
        csvs = descompactar_zip()
    except Exception as erro:  # noqa: BLE001 - queremos qualquer falha aqui
        print(f"[ERRO] Falha no download/descompactação: {erro}")
        sys.exit(1)

    falhas = []
    for tabela, info in RAW_TABELAS.items():
        print(f"\n[carga] {info['arquivo']} -> {tabela}")
        try:
            caminho = csvs.get(info["arquivo"])
            if caminho is None:
                raise FileNotFoundError(f"{info['arquivo']} não está no zip.")
            linhas = carregar_csv_na_raw(tabela, Path(caminho), info["colunas"])
            if not conferir_carga(tabela, linhas):
                falhas.append(tabela)
        except Exception as erro:  # noqa: BLE001
            print(f"[ERRO] {tabela}: {erro}")
            falhas.append(tabela)

    if falhas:
        print(f"\nCamada Raw concluída COM FALHAS em: {falhas}")
        sys.exit(1)
    print("\nCamada Raw carregada com sucesso.")


if __name__ == "__main__":
    main()

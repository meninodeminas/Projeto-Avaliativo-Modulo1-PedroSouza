"""
banco.py
--------
Conexão com o PostgreSQL e funções utilitárias usadas por todo o pipeline:

    conectar()            -> abre uma conexão
    executar(sql)         -> roda um comando (DDL/DML) e faz commit
    executar_em_sessao()  -> roda vários comandos na MESMA conexão/transação
    inserir_em_lote()     -> INSERT em blocos (execute_values)
    consultar(sql)        -> SELECT que devolve um pandas.DataFrame
"""
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from config import BATCH_SIZE, DB_CONFIG


def conectar():
    """Abre uma conexão com o banco configurado no .env."""
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_client_encoding("UTF8")
    return conn


def executar(sql, params=None):
    """Executa um único comando e devolve o número de linhas afetadas."""
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            linhas = cur.rowcount
        conn.commit()
        return linhas
    except psycopg2.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def executar_em_sessao(comandos):
    """
    Executa uma lista de comandos na mesma conexão e na mesma transação:
    ou todos dão certo (commit), ou nenhum é aplicado (rollback).
    """
    conn = conectar()
    try:
        with conn.cursor() as cur:
            for sql in comandos:
                cur.execute(sql)
        conn.commit()
    except psycopg2.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def inserir_em_lote(tabela, colunas, linhas, tamanho_lote=BATCH_SIZE):
    """
    Insere uma lista de tuplas em `tabela`, em blocos de `tamanho_lote`.
    execute_values monta um único INSERT com vários VALUES por bloco,
    muito mais rápido que inserir linha a linha.
    Devolve quantas linhas foram inseridas.
    """
    if not linhas:
        return 0
    nomes = ", ".join(f'"{c}"' for c in colunas)
    sql = f'INSERT INTO "{tabela}" ({nomes}) VALUES %s'

    conn = conectar()
    total = 0
    try:
        with conn.cursor() as cur:
            for inicio in range(0, len(linhas), tamanho_lote):
                lote = linhas[inicio:inicio + tamanho_lote]
                execute_values(cur, sql, lote, page_size=tamanho_lote)
                conn.commit()
                total += len(lote)
    except psycopg2.Error:
        conn.rollback()
        raise
    finally:
        conn.close()
    return total


def consultar(sql, params=None):
    """Executa um SELECT e devolve o resultado como DataFrame."""
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            colunas = [d[0] for d in cur.description]
            return pd.DataFrame(cur.fetchall(), columns=colunas)
    finally:
        conn.close()

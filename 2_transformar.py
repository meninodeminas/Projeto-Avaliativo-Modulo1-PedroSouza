"""
2_transformar.py
----------------
Fase 2 - Transformação: Raw -> Silver.

    1. Lê as tabelas raw_* (tudo texto).
    2. Converte tipos com funções específicas:
         texto_para_decimal  '1.272,97' -> Decimal('1272.97')
         texto_para_data     '05/01/2025' -> date(2025, 1, 5)
         texto_para_inteiro  '2' -> 2
    3. Limpa: tira espaços, troca vazio por NULL, remove duplicidades e
       descarta linhas que violariam as constraints da Silver.
    4. Garante integridade referencial: pagamento/passagem/trecho só entram
       se o id_viagem existir em silver_viagem.
    5. Calcula valor_total e duracao_dias.
    6. Carrega silver_viagem primeiro (mãe) e depois as filhas.

Idempotente: as tabelas Silver são esvaziadas antes da carga.

Execução:  python 2_transformar.py
"""
import math
import sys
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import pandas as pd

from banco import consultar, executar_em_sessao, inserir_em_lote

VALORES_VAZIOS = {"", "sem informação", "sem informacao", "null", "nan",
                  "none", "-"}
FORMATOS_DATA = ("%d/%m/%Y", "%Y-%m-%d")


# =========================================================================
# 1. Funções de conversão (5.6 do enunciado)
# =========================================================================
def eh_nulo(valor):
    """True para None e para o NaN que o pandas usa como 'faltante'."""
    return valor is None or (isinstance(valor, float) and math.isnan(valor))


def eh_vazio(valor):
    """True para nulo, texto vazio ou marcadores como 'Sem informação'."""
    return eh_nulo(valor) or str(valor).strip().lower() in VALORES_VAZIOS


def texto_para_decimal(valor):
    """
    Converte valores monetários do Portal para Decimal com 2 casas.
    '1272,97' -> 1272.97 | '1.272,97' -> 1272.97 | '' -> None
    """
    if eh_vazio(valor):
        return None
    texto = str(valor).strip().replace("R$", "").replace(" ", "")
    if "," in texto:                       # formato brasileiro
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return Decimal(texto).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def texto_para_data(valor):
    """Converte 'DD/MM/AAAA' em datetime.date. Inválido/vazio -> None."""
    if eh_vazio(valor):
        return None
    texto = str(valor).strip()
    for formato in FORMATOS_DATA:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def texto_para_inteiro(valor):
    """Converte '3' (ou '3,0') em int. Inválido/vazio -> None."""
    numero = texto_para_decimal(valor)
    if numero is None or numero != numero.to_integral_value():
        return None
    return int(numero)


def limpar_texto(valor, tamanho_max):
    """Tira espaços nas pontas, vazio -> None e corta no tamanho da coluna."""
    if eh_nulo(valor):
        return None
    texto = " ".join(str(valor).split())   # também colapsa espaços duplos
    return texto[:tamanho_max] if texto else None


# =========================================================================
# 2. Colunas calculadas
# =========================================================================
def calcular_valor_total(diarias, passagens, outros, devolucao):
    """valor_total = diárias + passagens + outros gastos - devolução."""
    zero = Decimal("0.00")
    return ((diarias or zero) + (passagens or zero) + (outros or zero)
            - (devolucao or zero))


def calcular_duracao_dias(inicio, fim):
    """
    Dias de viagem contando o primeiro e o último dia
    (ida e volta no mesmo dia = 1 dia). Datas inválidas -> None.
    """
    if not isinstance(inicio, date) or not isinstance(fim, date):
        return None
    if fim < inicio:
        return None
    return (fim - inicio).days + 1


# =========================================================================
# 3. Preparação de cada tabela (funções puras: DataFrame -> DataFrame)
# =========================================================================
def _aplicar(df, regras):
    """Aplica {coluna: função} e devolve um novo DataFrame só com elas."""
    # dtype=object preserva None, int, Decimal e date exatamente como as
    # funções devolveram (o pandas não troca None por NaN nem int por float).
    return pd.DataFrame(
        {coluna: pd.Series([funcao(v) for v in df[coluna]],
                           index=df.index, dtype=object)
         for coluna, funcao in regras.items()})


def _descartar(df, mascara, motivo, relatorio):
    """Remove as linhas marcadas e registra quantas foram e por quê."""
    qtd = int(mascara.sum())
    if qtd:
        relatorio[motivo] = relatorio.get(motivo, 0) + qtd
    return df[~mascara]


def _negativo(serie):
    return serie.map(lambda v: v is not None and v < 0).astype(bool)


def preparar_viagem(raw):
    relatorio = {}
    df = _aplicar(raw, {
        "id_viagem": lambda v: limpar_texto(v, 20),
        "num_proposta": lambda v: limpar_texto(v, 20),
        "situacao": lambda v: limpar_texto(v, 50),
        "viagem_urgente": lambda v: limpar_texto(v, 5),
        "cod_orgao_superior": lambda v: limpar_texto(v, 20),
        "nome_orgao_superior": lambda v: limpar_texto(v, 255),
        "nome_viajante": lambda v: limpar_texto(v, 255),
        "cargo": lambda v: limpar_texto(v, 255),
        "data_inicio": texto_para_data,
        "data_fim": texto_para_data,
        "destinos": lambda v: limpar_texto(v, 4000),
        "motivo": lambda v: limpar_texto(v, 4000),
        "valor_diarias": texto_para_decimal,
        "valor_passagens": texto_para_decimal,
        "valor_devolucao": texto_para_decimal,
        "valor_outros_gastos": texto_para_decimal,
    })

    df = _descartar(df, df["id_viagem"].isna(), "id_viagem vazio", relatorio)
    df = _descartar(df, df["id_viagem"].duplicated(keep="first"),
                    "id_viagem duplicado", relatorio)
    df = _descartar(df, df["nome_orgao_superior"].isna(),
                    "nome_orgao_superior vazio", relatorio)
    df = _descartar(df, _negativo(df["valor_diarias"]),
                    "valor_diarias negativo", relatorio)

    df = df.copy()
    df["valor_total"] = pd.Series([
        calcular_valor_total(d, p, o, dv) for d, p, o, dv in zip(
            df["valor_diarias"], df["valor_passagens"],
            df["valor_outros_gastos"], df["valor_devolucao"])
    ], index=df.index, dtype=object)
    df["duracao_dias"] = pd.Series([
        calcular_duracao_dias(i, f)
        for i, f in zip(df["data_inicio"], df["data_fim"])
    ], index=df.index, dtype=object)
    return df, relatorio


def _filtrar_fk(df, ids_viagem, relatorio):
    """Integridade referencial: só fica quem tem viagem correspondente."""
    df = _descartar(df, df["id_viagem"].isna(), "id_viagem vazio", relatorio)
    return _descartar(df, ~df["id_viagem"].isin(list(ids_viagem)),
                      "id_viagem inexistente em silver_viagem", relatorio)


def preparar_pagamento(raw, ids_viagem):
    relatorio = {}
    raw = _descartar(raw, raw.duplicated(keep="first"),
                     "linha duplicada", relatorio)
    df = _aplicar(raw, {
        "id_viagem": lambda v: limpar_texto(v, 20),
        "num_proposta": lambda v: limpar_texto(v, 20),
        "nome_orgao_pagador": lambda v: limpar_texto(v, 255),
        "nome_ug_pagadora": lambda v: limpar_texto(v, 255),
        "tipo_pagamento": lambda v: limpar_texto(v, 50),
        "valor": texto_para_decimal,
    })
    df = _filtrar_fk(df, ids_viagem, relatorio)
    df = _descartar(df, df["tipo_pagamento"].isna(),
                    "tipo_pagamento vazio", relatorio)
    df = _descartar(df, _negativo(df["valor"]), "valor negativo", relatorio)
    return df, relatorio


def preparar_passagem(raw, ids_viagem):
    relatorio = {}
    raw = _descartar(raw, raw.duplicated(keep="first"),
                     "linha duplicada", relatorio)
    df = _aplicar(raw, {
        "id_viagem": lambda v: limpar_texto(v, 20),
        "meio_transporte": lambda v: limpar_texto(v, 50),
        "pais_origem_ida": lambda v: limpar_texto(v, 60),
        "uf_origem_ida": lambda v: limpar_texto(v, 40),
        "cidade_origem_ida": lambda v: limpar_texto(v, 80),
        "pais_destino_ida": lambda v: limpar_texto(v, 60),
        "uf_destino_ida": lambda v: limpar_texto(v, 40),
        "cidade_destino_ida": lambda v: limpar_texto(v, 80),
        "valor_passagem": texto_para_decimal,
        "taxa_servico": texto_para_decimal,
        "data_emissao": texto_para_data,
    })
    df = _filtrar_fk(df, ids_viagem, relatorio)
    df = _descartar(df, _negativo(df["valor_passagem"]),
                    "valor_passagem negativo", relatorio)
    df = _descartar(df, _negativo(df["taxa_servico"]),
                    "taxa_servico negativa", relatorio)
    return df, relatorio


def preparar_trecho(raw, ids_viagem):
    relatorio = {}
    df = _aplicar(raw, {
        "id_viagem": lambda v: limpar_texto(v, 20),
        "sequencia_trecho": texto_para_inteiro,
        "origem_data": texto_para_data,
        "origem_uf": lambda v: limpar_texto(v, 40),
        "origem_cidade": lambda v: limpar_texto(v, 80),
        "destino_data": texto_para_data,
        "destino_uf": lambda v: limpar_texto(v, 40),
        "destino_cidade": lambda v: limpar_texto(v, 80),
        "meio_transporte": lambda v: limpar_texto(v, 50),
        "numero_diarias": texto_para_decimal,
    })
    df = _filtrar_fk(df, ids_viagem, relatorio)
    df = _descartar(df, _negativo(df["numero_diarias"]),
                    "numero_diarias negativo", relatorio)
    # Respeita o UNIQUE (id_viagem, sequencia_trecho)
    df = _descartar(
        df, df.duplicated(subset=["id_viagem", "sequencia_trecho"],
                          keep="first"),
        "trecho duplicado (id_viagem + sequencia)", relatorio)
    return df, relatorio


# =========================================================================
# 4. Orquestração (I/O com o banco)
# =========================================================================
def limpar_silver():
    """
    Esvazia a Silver. No PostgreSQL, uma tabela referenciada por FK só pode
    ser truncada junto com as tabelas que apontam para ela, por isso as 4
    vão no mesmo comando. RESTART IDENTITY reinicia os ids (1, 2, 3...).
    """
    executar_em_sessao([
        "TRUNCATE TABLE silver_trecho, silver_passagem, silver_pagamento, "
        "silver_viagem RESTART IDENTITY",
    ])


def _para_sql(valor):
    """Garante que faltantes cheguem ao banco como NULL (e não 'nan')."""
    return None if eh_nulo(valor) else valor


def gravar(tabela, df, linhas_raw, relatorio):
    linhas = [tuple(_para_sql(v) for v in r)
              for r in df.itertuples(index=False, name=None)]
    inseridas = inserir_em_lote(tabela, list(df.columns), linhas)
    print(f"[{tabela}] raw={linhas_raw:,} -> silver={inseridas:,}")
    for motivo, qtd in relatorio.items():
        print(f"     descartadas {qtd:,} linha(s): {motivo}")


def main():
    try:
        print("[silver] Limpando tabelas Silver...")
        limpar_silver()

        raw = consultar("SELECT * FROM raw_viagem")
        viagem, rel = preparar_viagem(raw)
        gravar("silver_viagem", viagem, len(raw), rel)
        ids = set(viagem["id_viagem"])

        etapas = [
            ("raw_pagamento", "silver_pagamento", preparar_pagamento),
            ("raw_passagem", "silver_passagem", preparar_passagem),
            ("raw_trecho", "silver_trecho", preparar_trecho),
        ]
        for tabela_raw, tabela_silver, preparar in etapas:
            raw = consultar(f"SELECT * FROM {tabela_raw}")
            df, rel = preparar(raw, ids)
            gravar(tabela_silver, df, len(raw), rel)

    except Exception as erro:  # noqa: BLE001
        print(f"[ERRO] Transformação interrompida: {erro}")
        sys.exit(1)

    print("\nCamada Silver carregada com sucesso.")


if __name__ == "__main__":
    main()

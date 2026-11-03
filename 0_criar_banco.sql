-- =====================================================================
-- 0_criar_banco.sql  (PostgreSQL)
-- Fase 0: cria as 8 tabelas (4 Raw + 4 Silver).
--
-- RAW    -> cópia fiel do CSV: todas as colunas VARCHAR, sem constraints.
-- SILVER -> dados tipados, com PRIMARY KEY, FOREIGN KEY e 2 constraints
--           extras por tabela (NOT NULL / CHECK / UNIQUE).
--
-- PASSO 1 (uma única vez): criar o database
--     pgAdmin: botão direito em "Databases" > Create > Database > viagens_db
--     ou psql: psql -U postgres -c "CREATE DATABASE viagens_db ENCODING 'UTF8'"
--
-- PASSO 2: rodar este script CONECTADO ao viagens_db
--     pgAdmin: clique em viagens_db > Query Tool > abrir este arquivo > F5
--     ou psql: psql -U postgres -d viagens_db -f 0_criar_banco.sql
-- =====================================================================

-- Remove tudo antes de recriar, para o script poder ser executado quantas
-- vezes for preciso. CASCADE remove junto as FKs e as views Gold que
-- dependem dessas tabelas (o notebook as recria).
DROP TABLE IF EXISTS silver_trecho    CASCADE;
DROP TABLE IF EXISTS silver_passagem  CASCADE;
DROP TABLE IF EXISTS silver_pagamento CASCADE;
DROP TABLE IF EXISTS silver_viagem    CASCADE;
DROP TABLE IF EXISTS raw_trecho       CASCADE;
DROP TABLE IF EXISTS raw_passagem     CASCADE;
DROP TABLE IF EXISTS raw_pagamento    CASCADE;
DROP TABLE IF EXISTS raw_viagem       CASCADE;


-- =====================================================================
-- CAMADA RAW (tudo VARCHAR sem limite de tamanho, sem PK/FK/constraints)
-- Sem limite para que nenhum texto do CSV seja rejeitado ou cortado.
-- =====================================================================

CREATE TABLE raw_viagem (
    id_viagem               VARCHAR,
    num_proposta            VARCHAR,
    situacao                VARCHAR,
    viagem_urgente          VARCHAR,
    justificativa_urgencia  VARCHAR,
    cod_orgao_superior      VARCHAR,
    nome_orgao_superior     VARCHAR,
    cod_orgao_solicitante   VARCHAR,
    nome_orgao_solicitante  VARCHAR,
    cpf_viajante            VARCHAR,
    nome_viajante           VARCHAR,
    cargo                   VARCHAR,
    funcao                  VARCHAR,
    descricao_funcao        VARCHAR,
    data_inicio             VARCHAR,
    data_fim                VARCHAR,
    destinos                VARCHAR,
    motivo                  VARCHAR,
    valor_diarias           VARCHAR,
    valor_passagens         VARCHAR,
    valor_devolucao         VARCHAR,
    valor_outros_gastos     VARCHAR
);

CREATE TABLE raw_pagamento (
    id_viagem               VARCHAR,
    num_proposta            VARCHAR,
    cod_orgao_superior      VARCHAR,
    nome_orgao_superior     VARCHAR,
    cod_orgao_pagador       VARCHAR,
    nome_orgao_pagador      VARCHAR,
    cod_ug_pagadora         VARCHAR,
    nome_ug_pagadora        VARCHAR,
    tipo_pagamento          VARCHAR,
    valor                   VARCHAR
);

CREATE TABLE raw_passagem (
    id_viagem               VARCHAR,
    num_proposta            VARCHAR,
    meio_transporte         VARCHAR,
    pais_origem_ida         VARCHAR,
    uf_origem_ida           VARCHAR,
    cidade_origem_ida       VARCHAR,
    pais_destino_ida        VARCHAR,
    uf_destino_ida          VARCHAR,
    cidade_destino_ida      VARCHAR,
    pais_origem_volta       VARCHAR,
    uf_origem_volta         VARCHAR,
    cidade_origem_volta     VARCHAR,
    pais_destino_volta      VARCHAR,
    uf_destino_volta        VARCHAR,
    cidade_destino_volta    VARCHAR,
    valor_passagem          VARCHAR,
    taxa_servico            VARCHAR,
    data_emissao            VARCHAR,
    hora_emissao            VARCHAR
);

CREATE TABLE raw_trecho (
    id_viagem               VARCHAR,
    num_proposta            VARCHAR,
    sequencia_trecho        VARCHAR,
    origem_data             VARCHAR,
    origem_pais             VARCHAR,
    origem_uf               VARCHAR,
    origem_cidade           VARCHAR,
    destino_data            VARCHAR,
    destino_pais            VARCHAR,
    destino_uf              VARCHAR,
    destino_cidade          VARCHAR,
    meio_transporte         VARCHAR,
    numero_diarias          VARCHAR,
    missao                  VARCHAR
);


-- =====================================================================
-- CAMADA SILVER (tipada, com PK, FK e constraints)
-- =====================================================================

-- Tabela "mãe": todas as outras apontam para ela via id_viagem.
CREATE TABLE silver_viagem (
    id_viagem               VARCHAR(20)     NOT NULL,
    num_proposta            VARCHAR(20),
    situacao                VARCHAR(50),
    viagem_urgente          VARCHAR(5),
    cod_orgao_superior      VARCHAR(20),
    nome_orgao_superior     VARCHAR(255)    NOT NULL,          -- constraint 1
    nome_viajante           VARCHAR(255),
    cargo                   VARCHAR(255),
    data_inicio             DATE,
    data_fim                DATE,
    destinos                VARCHAR(4000),
    motivo                  VARCHAR(4000),
    valor_diarias           DECIMAL(10,2),
    valor_passagens         DECIMAL(10,2),
    valor_devolucao         DECIMAL(10,2),
    valor_outros_gastos     DECIMAL(10,2),
    valor_total             DECIMAL(12,2),                     -- calculado
    duracao_dias            INT,                               -- calculado
    CONSTRAINT pk_silver_viagem PRIMARY KEY (id_viagem),
    CONSTRAINT chk_viagem_valor_diarias CHECK (valor_diarias >= 0)  -- constraint 2
);

CREATE TABLE silver_pagamento (
    id_pagamento            INT GENERATED ALWAYS AS IDENTITY,
    id_viagem               VARCHAR(20)     NOT NULL,
    num_proposta            VARCHAR(20),
    nome_orgao_pagador      VARCHAR(255),
    nome_ug_pagadora        VARCHAR(255),
    tipo_pagamento          VARCHAR(50)     NOT NULL,          -- constraint 2
    valor                   DECIMAL(10,2),
    CONSTRAINT pk_silver_pagamento PRIMARY KEY (id_pagamento),
    CONSTRAINT fk_pagamento_viagem FOREIGN KEY (id_viagem)
        REFERENCES silver_viagem (id_viagem),
    CONSTRAINT chk_pagamento_valor CHECK (valor >= 0)            -- constraint 1
);

CREATE TABLE silver_passagem (
    id_passagem             INT GENERATED ALWAYS AS IDENTITY,
    id_viagem               VARCHAR(20)     NOT NULL,
    meio_transporte         VARCHAR(50),
    pais_origem_ida         VARCHAR(60),
    uf_origem_ida           VARCHAR(40),
    cidade_origem_ida       VARCHAR(80),
    pais_destino_ida        VARCHAR(60),
    uf_destino_ida          VARCHAR(40),
    cidade_destino_ida      VARCHAR(80),
    valor_passagem          DECIMAL(10,2),
    taxa_servico            DECIMAL(10,2),
    data_emissao            DATE,
    CONSTRAINT pk_silver_passagem PRIMARY KEY (id_passagem),
    CONSTRAINT fk_passagem_viagem FOREIGN KEY (id_viagem)
        REFERENCES silver_viagem (id_viagem),
    CONSTRAINT chk_passagem_valor CHECK (valor_passagem >= 0),   -- constraint 1
    CONSTRAINT chk_passagem_taxa  CHECK (taxa_servico >= 0)      -- constraint 2
);

CREATE TABLE silver_trecho (
    id_trecho               INT GENERATED ALWAYS AS IDENTITY,
    id_viagem               VARCHAR(20)     NOT NULL,
    sequencia_trecho        INT,
    origem_data             DATE,
    origem_uf               VARCHAR(40),
    origem_cidade           VARCHAR(80),
    destino_data            DATE,
    destino_uf              VARCHAR(40),
    destino_cidade          VARCHAR(80),
    meio_transporte         VARCHAR(50),
    numero_diarias          DECIMAL(10,2),
    CONSTRAINT pk_silver_trecho PRIMARY KEY (id_trecho),
    CONSTRAINT fk_trecho_viagem FOREIGN KEY (id_viagem)
        REFERENCES silver_viagem (id_viagem),
    CONSTRAINT chk_trecho_diarias CHECK (numero_diarias >= 0),            -- constraint 1
    CONSTRAINT uq_trecho_viagem_seq UNIQUE (id_viagem, sequencia_trecho)  -- constraint 2
);

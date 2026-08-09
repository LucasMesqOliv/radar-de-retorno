CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS series_mercado (
    codigo TEXT NOT NULL,
    data TEXT NOT NULL,
    valor DOUBLE PRECISION NOT NULL,
    atualizado_em TEXT NOT NULL,
    PRIMARY KEY (codigo, data)
);

CREATE TABLE IF NOT EXISTS cotas_fundos (
    cnpj TEXT NOT NULL,
    data TEXT NOT NULL,
    cota DOUBLE PRECISION NOT NULL,
    patrimonio DOUBLE PRECISION,
    captacao_dia DOUBLE PRECISION,
    resgate_dia DOUBLE PRECISION,
    cotistas DOUBLE PRECISION,
    atualizado_em TEXT NOT NULL,
    PRIMARY KEY (cnpj, data)
);

CREATE TABLE IF NOT EXISTS periodos_consultados (
    tipo TEXT NOT NULL,
    identificador TEXT NOT NULL,
    periodo TEXT NOT NULL,
    possui_dados INTEGER NOT NULL,
    consultado_em TEXT NOT NULL,
    PRIMARY KEY (tipo, identificador, periodo)
);

CREATE TABLE IF NOT EXISTS cadastro_fundos (
    cnpj TEXT NOT NULL PRIMARY KEY,
    nome TEXT NOT NULL,
    data_constituicao TEXT,
    situacao TEXT,
    tipo TEXT,
    classificacao TEXT,
    classificacao_anbima TEXT,
    indicador_desempenho TEXT,
    publico_alvo TEXT,
    patrimonio_cadastral DOUBLE PRECISION,
    data_patrimonio_cadastral TEXT,
    administrador TEXT,
    gestor TEXT,
    em_funcionamento INTEGER NOT NULL,
    busca TEXT NOT NULL DEFAULT '',
    atualizado_em TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS cadastro_fundos_busca_trgm_idx
ON cadastro_fundos USING gin (busca gin_trgm_ops);

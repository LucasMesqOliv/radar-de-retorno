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

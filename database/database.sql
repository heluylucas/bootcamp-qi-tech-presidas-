-- Data de movimento (RN-GER-13): o "hoje" do banco. Uma linha por dia aberto,
-- nunca alterada; a data atual é a maior reference_date. Nasce com a data real
-- e só avança pelo fechamento do dia.
CREATE TABLE business_day(
    id                              SERIAL PRIMARY KEY,
    reference_date                  DATE NOT NULL UNIQUE,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO business_day (reference_date) VALUES (CURRENT_DATE);

CREATE TABLE customer(
    id                              SERIAL PRIMARY KEY,
    customer_key                    CHAR(36) NOT NULL UNIQUE,
    name                            TEXT NOT NULL,
    document_number                 CHAR(14) NOT NULL UNIQUE,
    birth_date                      DATE NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE account_status(
    id                              SERIAL PRIMARY KEY,
    enumerator                      VARCHAR(50) NOT NULL UNIQUE,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO account_status (enumerator) VALUES
('ACTIVE'),
('BLOCKED'),
('CLOSED');

CREATE TABLE account(
    id                              SERIAL PRIMARY KEY,
    account_key                     CHAR(36) NOT NULL UNIQUE,
    customer_id                     INTEGER NOT NULL REFERENCES customer(id),
    status_id                       INTEGER NOT NULL REFERENCES account_status(id),
    balance                         BIGINT NOT NULL DEFAULT 0 CHECK (balance >= 0),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE account_status_event(
    id                              SERIAL PRIMARY KEY,
    account_id                      INTEGER NOT NULL REFERENCES account(id),
    from_status_id                  INTEGER REFERENCES account_status(id),
    to_status_id                    INTEGER NOT NULL REFERENCES account_status(id),
    reason                          VARCHAR(255),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE transaction_type(
    id                              SERIAL PRIMARY KEY,
    enumerator                      VARCHAR(50) NOT NULL UNIQUE,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO transaction_type (enumerator) VALUES
('DEPOSIT'),
('WITHDRAWAL'),
('TRANSFER'),
('INVESTMENT_APPLY'),
('INVESTMENT_REDEEM');

CREATE TABLE transaction(
    id                              SERIAL PRIMARY KEY,
    transaction_key                 CHAR(36) NOT NULL UNIQUE,
    type_id                         INTEGER NOT NULL REFERENCES transaction_type(id),
    requester_account_id            INTEGER NOT NULL REFERENCES account(id),
    origin_account_id               INTEGER REFERENCES account(id),
    destination_account_id          INTEGER REFERENCES account(id),
    amount                          BIGINT NOT NULL CHECK (amount > 0),
    fee_amount                      BIGINT NOT NULL DEFAULT 0 CHECK (fee_amount >= 0),
    description                     VARCHAR(140),
    idempotency_key                 CHAR(36) NOT NULL,
    request_hash                    CHAR(64) NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(requester_account_id, idempotency_key)
);

CREATE TABLE ledger_entry(
    id                              SERIAL PRIMARY KEY,
    entry_key                       CHAR(36) NOT NULL UNIQUE,
    transaction_id                  INTEGER NOT NULL REFERENCES transaction(id),
    account_id                      INTEGER NOT NULL REFERENCES account(id),
    direction                       VARCHAR(6) NOT NULL CHECK (direction IN ('DEBIT', 'CREDIT')),
    category                        VARCHAR(9) NOT NULL CHECK (category IN ('PRINCIPAL', 'FEE')),
    amount                          BIGINT NOT NULL CHECK (amount > 0),
    balance_after                   BIGINT NOT NULL CHECK (balance_after >= 0),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ledger_entry_account_created_idx ON ledger_entry (account_id, created_at);

-- Rede de segurança: no máximo uma conta não encerrada por cliente. 3 = CLOSED (ordem do seed acima).
CREATE UNIQUE INDEX account_one_open_per_customer_idx ON account (customer_id) WHERE status_id <> 3;

-- =====================================================================
-- Suitability
-- =====================================================================

CREATE TABLE suitability_question(
    id                              SERIAL PRIMARY KEY,
    code                            VARCHAR(3) NOT NULL UNIQUE,
    text                            TEXT NOT NULL,
    dimension                       VARCHAR(30) NOT NULL,
    position                        SMALLINT NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE suitability_option(
    id                              SERIAL PRIMARY KEY,
    question_id                     INTEGER NOT NULL REFERENCES suitability_question(id),
    code                            SMALLINT NOT NULL,
    text                            TEXT NOT NULL,
    points                          SMALLINT NOT NULL CHECK (points BETWEEN 1 AND 4),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(question_id, code)
);

CREATE TABLE investor_profile(
    id                              SERIAL PRIMARY KEY,
    enumerator                      VARCHAR(50) NOT NULL UNIQUE,
    min_score                       SMALLINT NOT NULL,
    max_score                       SMALLINT NOT NULL,
    max_risk_level                  SMALLINT NOT NULL CHECK (max_risk_level BETWEEN 1 AND 5),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE suitability_assessment(
    id                              SERIAL PRIMARY KEY,
    assessment_key                  CHAR(36) NOT NULL UNIQUE,
    customer_id                     INTEGER NOT NULL REFERENCES customer(id),
    profile_id                      INTEGER NOT NULL REFERENCES investor_profile(id),
    score                           SMALLINT NOT NULL,
    forced_by_rule                  BOOLEAN NOT NULL DEFAULT false,
    valid_until                     TIMESTAMPTZ NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX suitability_assessment_customer_created_idx ON suitability_assessment (customer_id, created_at);

CREATE TABLE suitability_answer(
    id                              SERIAL PRIMARY KEY,
    assessment_id                   INTEGER NOT NULL REFERENCES suitability_assessment(id),
    question_id                     INTEGER NOT NULL REFERENCES suitability_question(id),
    option_id                       INTEGER NOT NULL REFERENCES suitability_option(id),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(assessment_id, question_id)
);

INSERT INTO investor_profile (enumerator, min_score, max_score, max_risk_level) VALUES
('CONSERVATIVE', 7, 13, 2),
('MODERATE', 14, 20, 3),
('AGGRESSIVE', 21, 28, 5);

INSERT INTO suitability_question (code, text, dimension, position) VALUES
('Q1', 'Por quanto tempo pretende deixar o dinheiro investido?', 'objetivo', 1),
('Q2', 'Qual o principal objetivo?', 'objetivo', 2),
('Q3', 'Se seus investimentos caíssem 10% em um mês, você...', 'tolerância', 3),
('Q4', 'Quanto da sua renda mensal sobra para investir?', 'situação financeira', 4),
('Q5', 'Você pode precisar deste dinheiro de repente?', 'liquidez', 5),
('Q6', 'Em quais produtos você já investiu?', 'experiência', 6),
('Q7', 'Como você descreve seu conhecimento financeiro?', 'conhecimento', 7);

-- Em todas as perguntas, a opção de código N vale N pontos.
INSERT INTO suitability_option (question_id, code, text, points)
SELECT q.id, o.code, o.text, o.code
FROM (VALUES
    ('Q1', 1, 'Menos de 1 ano'),
    ('Q1', 2, '1 a 3 anos'),
    ('Q1', 3, '3 a 5 anos'),
    ('Q1', 4, 'Mais de 5 anos'),
    ('Q2', 1, 'Preservar o dinheiro'),
    ('Q2', 2, 'Reserva com algum ganho'),
    ('Q2', 3, 'Crescer o patrimônio'),
    ('Q2', 4, 'Maximizar o retorno aceitando oscilações'),
    ('Q3', 1, 'Resgataria tudo'),
    ('Q3', 2, 'Resgataria uma parte'),
    ('Q3', 3, 'Manteria'),
    ('Q3', 4, 'Aplicaria mais'),
    ('Q4', 1, 'Quase nada'),
    ('Q4', 2, 'Até 10%'),
    ('Q4', 3, '10% a 30%'),
    ('Q4', 4, 'Mais de 30%'),
    ('Q5', 1, 'Sim, a qualquer momento'),
    ('Q5', 2, 'Provavelmente em até 1 ano'),
    ('Q5', 3, 'Dificilmente'),
    ('Q5', 4, 'Não'),
    ('Q6', 1, 'Nenhum ou só poupança'),
    ('Q6', 2, 'Tesouro/CDB'),
    ('Q6', 3, 'Fundos multimercado ou de ações'),
    ('Q6', 4, 'Ações, derivativos ou cripto'),
    ('Q7', 1, 'Nenhum'),
    ('Q7', 2, 'Básico'),
    ('Q7', 3, 'Intermediário (entendo risco e retorno)'),
    ('Q7', 4, 'Avançado (formação ou atuação na área)')
) AS o(question_code, code, text)
JOIN suitability_question q ON q.code = o.question_code;

-- =====================================================================
-- Produtos e preços
-- =====================================================================

CREATE TABLE product_type(
    id                              SERIAL PRIMARY KEY,
    enumerator                      VARCHAR(50) NOT NULL UNIQUE,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO product_type (enumerator) VALUES
('PUBLIC_BOND'),
('PRIVATE_BOND'),
('FUND');

CREATE TABLE product(
    id                              SERIAL PRIMARY KEY,
    product_key                     CHAR(36) NOT NULL UNIQUE,
    name                            VARCHAR(100) NOT NULL,
    type_id                         INTEGER NOT NULL REFERENCES product_type(id),
    issuer                          VARCHAR(100) NOT NULL,
    indexer                         VARCHAR(8) NOT NULL CHECK (indexer IN ('SELIC', 'CDI', 'PREFIXED', 'IPCA', 'QUOTA')),
    rate_description                VARCHAR(100) NOT NULL,
    risk_level                      SMALLINT NOT NULL CHECK (risk_level BETWEEN 1 AND 5),
    liquidity                       VARCHAR(11) NOT NULL CHECK (liquidity IN ('DAILY', 'AT_MATURITY')),
    maturity_date                   DATE,
    min_application                 BIGINT NOT NULL CHECK (min_application > 0),
    is_active                       BOOLEAN NOT NULL DEFAULT true,
    own_issue                       BOOLEAN NOT NULL DEFAULT false,
    cdi_percentage_bps              SMALLINT CHECK (cdi_percentage_bps > 0),
    admin_fee_bps                   SMALLINT CHECK (admin_fee_bps >= 0),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE reference_rate(
    id                              SERIAL PRIMARY KEY,
    code                            VARCHAR(5) NOT NULL UNIQUE,
    annual_rate_bps                 INTEGER NOT NULL CHECK (annual_rate_bps > 0),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE product_price(
    id                              SERIAL PRIMARY KEY,
    product_id                      INTEGER NOT NULL REFERENCES product(id),
    reference_date                  DATE NOT NULL,
    unit_price                      NUMERIC(20,8) NOT NULL CHECK (unit_price > 0),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(product_id, reference_date)
);

INSERT INTO reference_rate (code, annual_rate_bps) VALUES
('CDI', 1490),
('SELIC', 1500);

INSERT INTO product (product_key, name, type_id, issuer, indexer, rate_description, risk_level, liquidity,
                     maturity_date, min_application, own_issue, cdi_percentage_bps, admin_fee_bps)
SELECT gen_random_uuid()::text, v.name, t.id, v.issuer, v.indexer, v.rate_description, v.risk_level, v.liquidity,
       v.maturity_date::date, v.min_application, v.own_issue, v.cdi_percentage_bps, v.admin_fee_bps
FROM (VALUES
    ('Tesouro Selic 2031',     'PUBLIC_BOND',  'Tesouro Nacional',  'SELIC',    '100% da Selic',           1, 'DAILY',       '2031-03-01', 5000,  false, NULL, NULL),
    ('CDB Quant Bank Liquidez','PRIVATE_BOND', 'Quant Bank',        'CDI',      '95% do CDI',              2, 'DAILY',       NULL,         5000,  true,  9500, NULL),
    ('LCI Quant Bank 2027',    'PRIVATE_BOND', 'Quant Bank',        'CDI',      '93% do CDI, isento de IR',2, 'AT_MATURITY', '2027-03-01', 10000, true,  9300, NULL),
    ('Tesouro Prefixado 2029', 'PUBLIC_BOND',  'Tesouro Nacional',  'PREFIXED', '13% a.a.',                2, 'DAILY',       '2029-01-01', 5000,  false, NULL, NULL),
    ('Tesouro IPCA+ 2035',     'PUBLIC_BOND',  'Tesouro Nacional',  'IPCA',     'IPCA + 6% a.a.',          3, 'DAILY',       '2035-05-15', 5000,  false, NULL, NULL),
    ('FGV Quant Capital FIM',  'FUND',         'FGV Quant Capital', 'QUOTA',    'Varia com a cota',        3, 'DAILY',       NULL,         10000, false, NULL, 100)
) AS v(name, type, issuer, indexer, rate_description, risk_level, liquidity,
       maturity_date, min_application, own_issue, cdi_percentage_bps, admin_fee_bps)
JOIN product_type t ON t.enumerator = v.type;

-- Preços dos últimos 30 dias corridos (RN-PRO-06), todos partindo de 100,00.
-- d = dias úteis desde o primeiro dia; no fim de semana o preço repete.
-- Títulos: P = 100 * (1 + taxa anual)^(d/252). Prefixado 13% a.a.; IPCA+ = IPCA 4,5% + 6%.
-- Fundo (RN-REC-04): a cada dia útil, P = P_anterior * (1 + r) * (1 - 1%)^(1/252),
-- com retorno bruto r = 0,06% + 0,8% * sen(n), que sobe e desce sem ser aleatório.
WITH days AS (
    SELECT day::date AS day,
           day::date - (CURRENT_DATE - 29) AS n,
           CASE WHEN day::date > CURRENT_DATE - 29 AND EXTRACT(ISODOW FROM day) < 6 THEN 1 ELSE 0 END AS is_business_day
    FROM generate_series(CURRENT_DATE - 29, CURRENT_DATE, INTERVAL '1 day') AS day
), series AS (
    SELECT day,
           SUM(is_business_day) OVER (ORDER BY day) AS d,
           SUM(CASE WHEN is_business_day = 1
                    THEN ln((1.0006 + 0.008 * sin(n)::numeric) * power(0.99::numeric, 1 / 252.0))
                    ELSE 0 END) OVER (ORDER BY day) AS fund_log
    FROM days
), rates AS (
    SELECT (SELECT annual_rate_bps FROM reference_rate WHERE code = 'CDI') / 10000.0 AS cdi,
           (SELECT annual_rate_bps FROM reference_rate WHERE code = 'SELIC') / 10000.0 AS selic
)
INSERT INTO product_price (product_id, reference_date, unit_price)
SELECT p.id, s.day, ROUND(
    CASE p.indexer
        WHEN 'QUOTA' THEN 100 * exp(s.fund_log)
        ELSE 100 * power(1 + CASE p.indexer
            WHEN 'SELIC'    THEN r.selic
            WHEN 'CDI'      THEN r.cdi * p.cdi_percentage_bps / 10000
            WHEN 'PREFIXED' THEN 0.13
            WHEN 'IPCA'     THEN 1.045 * 1.06 - 1
        END, s.d / 252.0)
    END, 8)
FROM product p CROSS JOIN series s CROSS JOIN rates r;

-- =====================================================================
-- Carteira sugerida
-- =====================================================================

CREATE TABLE model_portfolio(
    id                              SERIAL PRIMARY KEY,
    profile_id                      INTEGER NOT NULL UNIQUE REFERENCES investor_profile(id),
    name                            VARCHAR(100) NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE model_portfolio_item(
    id                              SERIAL PRIMARY KEY,
    model_portfolio_id              INTEGER NOT NULL REFERENCES model_portfolio(id),
    product_id                      INTEGER NOT NULL REFERENCES product(id),
    weight_bps                      SMALLINT NOT NULL CHECK (weight_bps > 0),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(model_portfolio_id, product_id)
);

INSERT INTO model_portfolio (profile_id, name)
SELECT id, CASE enumerator
    WHEN 'CONSERVATIVE' THEN 'Carteira Conservadora'
    WHEN 'MODERATE'     THEN 'Carteira Moderada'
    WHEN 'AGGRESSIVE'   THEN 'Carteira Arrojada'
END
FROM investor_profile;

-- Pesos em pontos-base: cada carteira soma 10.000.
INSERT INTO model_portfolio_item (model_portfolio_id, product_id, weight_bps)
SELECT mp.id, p.id, v.weight_bps
FROM (VALUES
    ('CONSERVATIVE', 'Tesouro Selic 2031',      5000),
    ('CONSERVATIVE', 'CDB Quant Bank Liquidez', 3000),
    ('CONSERVATIVE', 'LCI Quant Bank 2027',     2000),
    ('MODERATE',     'Tesouro Selic 2031',      2500),
    ('MODERATE',     'CDB Quant Bank Liquidez', 2000),
    ('MODERATE',     'Tesouro Prefixado 2029',  2000),
    ('MODERATE',     'Tesouro IPCA+ 2035',      2000),
    ('MODERATE',     'FGV Quant Capital FIM',   1500),
    ('AGGRESSIVE',   'Tesouro Selic 2031',      1000),
    ('AGGRESSIVE',   'Tesouro Prefixado 2029',  2000),
    ('AGGRESSIVE',   'Tesouro IPCA+ 2035',      3000),
    ('AGGRESSIVE',   'FGV Quant Capital FIM',   4000)
) AS v(profile, product_name, weight_bps)
JOIN investor_profile ip ON ip.enumerator = v.profile
JOIN model_portfolio mp ON mp.profile_id = ip.id
JOIN product p ON p.name = v.product_name;

-- =====================================================================
-- Ordens e posição
-- =====================================================================

CREATE TABLE investment_order(
    id                              SERIAL PRIMARY KEY,
    order_key                       CHAR(36) NOT NULL UNIQUE,
    customer_id                     INTEGER NOT NULL REFERENCES customer(id),
    account_id                      INTEGER NOT NULL REFERENCES account(id),
    product_id                      INTEGER NOT NULL REFERENCES product(id),
    side                            VARCHAR(6) NOT NULL CHECK (side IN ('APPLY', 'REDEEM')),
    amount                          BIGINT NOT NULL CHECK (amount > 0),
    quantity                        NUMERIC(24,8) NOT NULL CHECK (quantity > 0),
    unit_price                      NUMERIC(20,8) NOT NULL CHECK (unit_price > 0),
    cost_amount                     BIGINT NOT NULL CHECK (cost_amount >= 0),
    transaction_id                  INTEGER NOT NULL UNIQUE REFERENCES transaction(id),
    status                          VARCHAR(8) NOT NULL DEFAULT 'EXECUTED' CHECK (status IN ('EXECUTED')),
    idempotency_key                 CHAR(36) NOT NULL,
    request_hash                    CHAR(64) NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(customer_id, idempotency_key)
);

CREATE TABLE position(
    id                              SERIAL PRIMARY KEY,
    customer_id                     INTEGER NOT NULL REFERENCES customer(id),
    product_id                      INTEGER NOT NULL REFERENCES product(id),
    quantity                        NUMERIC(24,8) NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    invested_amount                 BIGINT NOT NULL DEFAULT 0 CHECK (invested_amount >= 0),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(customer_id, product_id)
);

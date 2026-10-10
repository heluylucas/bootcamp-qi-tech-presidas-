-- Data de movimento (RN-GER-13): o "hoje" do banco. Uma linha por dia aberto,
-- nunca alterada; a data atual é a maior business_date. Nasce com a data real
-- e só avança pelo fechamento do dia.
CREATE TABLE business_day(
    id                              SERIAL PRIMARY KEY,
    business_date                   DATE NOT NULL UNIQUE,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO business_day (business_date) VALUES (CURRENT_DATE);

CREATE TABLE customer(
    id                              SERIAL PRIMARY KEY,
    customer_key                    CHAR(36) NOT NULL UNIQUE,
    name                            TEXT NOT NULL,
    document_number                 CHAR(14) NOT NULL UNIQUE,
    birth_date                      DATE NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enumeradores: listas fixas de valores, conferidas pelo próprio banco. Valor fora da
-- lista é recusado na gravação. Acrescentar um valor: ALTER TYPE ... ADD VALUE.
CREATE TYPE account_status AS ENUM ('ACTIVE', 'BLOCKED', 'CLOSED');
CREATE TYPE status_actor AS ENUM ('CUSTOMER', 'BANK');
CREATE TYPE transaction_type AS ENUM ('DEPOSIT', 'WITHDRAWAL', 'TRANSFER', 'INVESTMENT_APPLY', 'INVESTMENT_REDEEM');
CREATE TYPE entry_direction AS ENUM ('DEBIT', 'CREDIT');
CREATE TYPE entry_category AS ENUM ('PRINCIPAL', 'FEE');

CREATE TABLE account(
    id                              SERIAL PRIMARY KEY,
    account_key                     CHAR(36) NOT NULL UNIQUE,
    -- Nulo só na conta do próprio banco (seed abaixo), que recebe as tarifas.
    customer_id                     INTEGER REFERENCES customer(id),
    status                          account_status NOT NULL,
    balance                         BIGINT NOT NULL DEFAULT 0 CHECK (balance >= 0),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE account_status_event(
    id                              SERIAL PRIMARY KEY,
    account_id                      INTEGER NOT NULL REFERENCES account(id),
    -- Nulo no nascimento da conta (RN-CON-03).
    from_status                     account_status,
    to_status                       account_status NOT NULL,
    reason                          VARCHAR(255),
    -- Quem fez a mudança (RN-CON-05): CUSTOMER pela rota do cliente, BANK pela
    -- rota interna (RN-CON-11). Sem DEFAULT: esquecer de informar vira erro.
    actor                           status_actor NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- O pedido que mexe em dinheiro. Os efeitos em cada saldo ficam em ledger_entry.
CREATE TABLE transaction(
    id                              SERIAL PRIMARY KEY,
    transaction_key                 CHAR(36) NOT NULL UNIQUE,
    type                            transaction_type NOT NULL,
    -- A dona do pedido: a conta que pediu (no depósito e no resgate, a que recebe).
    owner_account_id                INTEGER NOT NULL REFERENCES account(id),
    -- Só na transferência, e nela sempre: a conta que recebe.
    destination_account_id          INTEGER REFERENCES account(id) CHECK (destination_account_id <> owner_account_id),
    amount                          BIGINT NOT NULL CHECK (amount > 0),
    fee_amount                      BIGINT NOT NULL DEFAULT 0 CHECK (fee_amount >= 0),
    description                     VARCHAR(140),
    -- Gerada por quem chama a API, única no banco inteiro. Nula quando o próprio
    -- banco cria a transação (liquidação no vencimento): não há pedido para repetir.
    idempotency_key                 UUID UNIQUE,
    -- O dia em que a transação aconteceu, no calendário do banco (a data de movimento, que é a
    -- data real simulada). O extrato e a tarifa da receita filtram por ela; o created_at fica
    -- só como registro técnico de quando a linha foi gravada.
    business_date                   DATE NOT NULL REFERENCES business_day(business_date),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK ((type = 'TRANSFER') = (destination_account_id IS NOT NULL))
);

CREATE INDEX transaction_business_date_idx ON transaction (business_date);

CREATE TABLE ledger_entry(
    id                              SERIAL PRIMARY KEY,
    transaction_id                  INTEGER NOT NULL REFERENCES transaction(id),
    account_id                      INTEGER NOT NULL REFERENCES account(id),
    direction                       entry_direction NOT NULL,
    category                        entry_category NOT NULL,
    amount                          BIGINT NOT NULL CHECK (amount > 0),
    balance_after                   BIGINT NOT NULL CHECK (balance_after >= 0),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ledger_entry_account_created_idx ON ledger_entry (account_id, created_at);

-- Rede de segurança: no máximo uma conta não encerrada por cliente.
CREATE UNIQUE INDEX account_one_open_per_customer_idx ON account (customer_id) WHERE status <> 'CLOSED';

-- A conta do banco: a tarifa sai do cliente e entra aqui, então nenhum centavo some
-- (RN-REC-03). Sem cliente, nenhuma rota /customer/... a alcança. Nasce primeiro, com o
-- menor id: na ordem crescente de travas, é sempre a primeira a ser travada.
INSERT INTO account (account_key, customer_id, status) VALUES (gen_random_uuid()::text, NULL, 'ACTIVE');

-- =====================================================================
-- Suitability
-- =====================================================================

-- O questionário segue a ordem do código (Q1 a Q7).
CREATE TABLE suitability_question(
    id                              SERIAL PRIMARY KEY,
    code                            VARCHAR(3) NOT NULL UNIQUE,
    text                            TEXT NOT NULL,
    dimension                       VARCHAR(30) NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- O código da opção é também a sua pontuação: a opção N vale N pontos (RN-SUI-03).
CREATE TABLE suitability_option(
    id                              SERIAL PRIMARY KEY,
    suitability_question_id         INTEGER NOT NULL REFERENCES suitability_question(id),
    code                            SMALLINT NOT NULL CHECK (code BETWEEN 1 AND 4),
    text                            TEXT NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(suitability_question_id, code)
);

-- O perfil do investidor. A faixa de pontos e o risco máximo de cada um são regras fixas,
-- como a tarifa: ficam no código (models/suitability.py), não numa tabela (RN-SUI-03 e 04).
CREATE TYPE investor_profile AS ENUM ('CONSERVATIVE', 'MODERATE', 'AGGRESSIVE');

-- Validade (created_at + 24 meses) e trava (perfil fora da faixa do score) são calculadas.
CREATE TABLE suitability_assessment(
    id                              SERIAL PRIMARY KEY,
    assessment_key                  CHAR(36) NOT NULL UNIQUE,
    customer_id                     INTEGER NOT NULL REFERENCES customer(id),
    investor_profile                investor_profile NOT NULL,
    score                           SMALLINT NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX suitability_assessment_customer_created_idx ON suitability_assessment (customer_id, created_at);

-- A pergunta respondida vem da opção escolhida.
CREATE TABLE suitability_answer(
    id                              SERIAL PRIMARY KEY,
    suitability_assessment_id       INTEGER NOT NULL REFERENCES suitability_assessment(id),
    suitability_option_id           INTEGER NOT NULL REFERENCES suitability_option(id),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(suitability_assessment_id, suitability_option_id)
);

INSERT INTO suitability_question (code, text, dimension) VALUES
('Q1', 'Por quanto tempo pretende deixar o dinheiro investido?', 'objetivo'),
('Q2', 'Qual o principal objetivo?', 'objetivo'),
('Q3', 'Se seus investimentos caíssem 10% em um mês, você...', 'tolerância'),
('Q4', 'Quanto da sua renda mensal sobra para investir?', 'situação financeira'),
('Q5', 'Você pode precisar deste dinheiro de repente?', 'liquidez'),
('Q6', 'Em quais produtos você já investiu?', 'experiência'),
('Q7', 'Como você descreve seu conhecimento financeiro?', 'conhecimento');

INSERT INTO suitability_option (suitability_question_id, code, text)
SELECT q.id, o.code, o.text
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

CREATE TYPE product_type AS ENUM ('PUBLIC_BOND', 'PRIVATE_BOND', 'FUND');
CREATE TYPE product_indexer AS ENUM ('SELIC', 'CDI', 'PREFIXED', 'IPCA', 'QUOTA');
CREATE TYPE reference_rate_code AS ENUM ('CDI', 'SELIC');

-- O catálogo é fixo (seed) e nunca é editado: sem updated_at.
CREATE TABLE product(
    id                              SERIAL PRIMARY KEY,
    product_key                     CHAR(36) NOT NULL UNIQUE,
    name                            VARCHAR(100) NOT NULL,
    type                            product_type NOT NULL,
    issuer                          VARCHAR(100) NOT NULL,
    indexer                         product_indexer NOT NULL,
    rate_description                VARCHAR(100) NOT NULL,
    risk_level                      SMALLINT NOT NULL CHECK (risk_level BETWEEN 1 AND 5),
    -- Prazo de cada aplicação (RN-PRO-09). Nulo: resgate a qualquer dia. Com prazo, cada aplicação
    -- vence em data da aplicação + prazo, só é resgatada no vencimento e o fechamento do dia a paga.
    term_months                     SMALLINT CHECK (term_months > 0),
    minimum_application_amount      BIGINT NOT NULL CHECK (minimum_application_amount > 0),
    cdi_percentage_bps              SMALLINT CHECK (cdi_percentage_bps > 0),
    administration_fee_bps          SMALLINT CHECK (administration_fee_bps >= 0),
    -- Como a fonte externa chama o produto (RN-FEC-04). Nulo é emissão própria (CDB e LCI):
    -- o preço sai do CDI, não de fora.
    price_source_code               VARCHAR(50),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Histórico das taxas (RN-REC-08): uma linha por taxa e por data, nunca alterada.
CREATE TABLE reference_rate(
    id                              SERIAL PRIMARY KEY,
    code                            reference_rate_code NOT NULL,
    rate_date                       DATE NOT NULL,
    annual_rate_bps                 INTEGER NOT NULL CHECK (annual_rate_bps > 0),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(code, rate_date)
);

CREATE TABLE product_price(
    id                              SERIAL PRIMARY KEY,
    product_id                      INTEGER NOT NULL REFERENCES product(id),
    price_date                      DATE NOT NULL,
    unit_price                      NUMERIC(20,8) NOT NULL CHECK (unit_price > 0),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(product_id, price_date)
);

INSERT INTO reference_rate (code, rate_date, annual_rate_bps) VALUES
('CDI', CURRENT_DATE, 1490),
('SELIC', CURRENT_DATE, 1500);

INSERT INTO product (product_key, name, type, issuer, indexer, rate_description, risk_level,
                     term_months, minimum_application_amount, cdi_percentage_bps,
                     administration_fee_bps, price_source_code)
SELECT gen_random_uuid()::text, v.name, v.type::product_type, v.issuer, v.indexer::product_indexer,
       v.rate_description, v.risk_level,
       v.term_months, v.minimum_application_amount, v.cdi_percentage_bps,
       v.administration_fee_bps, v.price_source_code
FROM (VALUES
    ('Tesouro Selic 2031',         'PUBLIC_BOND',  'Tesouro Nacional',  'SELIC',    '100% da Selic',            1, NULL, 5000,  NULL, NULL, 'TESOURO SELIC 2031'),
    ('CDB Triple P Bank Liquidez', 'PRIVATE_BOND', 'Triple P Bank',     'CDI',      '95% do CDI',               2, NULL, 5000,  9500, NULL, NULL),
    ('LCI Triple P Bank 12 meses', 'PRIVATE_BOND', 'Triple P Bank',     'CDI',      '93% do CDI, isento de IR', 2, 12,   10000, 9300, NULL, NULL),
    ('Tesouro Prefixado 2029',     'PUBLIC_BOND',  'Tesouro Nacional',  'PREFIXED', '13% a.a.',                 2, NULL, 5000,  NULL, NULL, 'TESOURO PREFIXADO 2029'),
    ('Tesouro IPCA+ 2035',         'PUBLIC_BOND',  'Tesouro Nacional',  'IPCA',     'IPCA + 6% a.a.',           3, NULL, 5000,  NULL, NULL, 'TESOURO IPCA+ 2035'),
    ('FGV Quant Capital FIM',      'FUND',         'FGV Quant Capital', 'QUOTA',    'Varia com a cota',         3, NULL, 10000, NULL, 100,  '12.345.678/0001-95')
) AS v(name, type, issuer, indexer, rate_description, risk_level,
       term_months, minimum_application_amount, cdi_percentage_bps, administration_fee_bps, price_source_code);

-- Preço do dia em que o banco nasce, pelas fórmulas da RN-PRO-06 (as mesmas do mock).
-- Os dias seguintes entram pelo fechamento do dia.
-- d = dias úteis (segunda a sexta) depois da data âncora 01/01/2026. No fim de semana
-- d não muda, então o preço é o de sexta. Todo produto vale 100,00 em d = 0.
--   Títulos públicos: 100 * (1 + taxa anual)^(d/252). Selic 15%, Prefixado 13%, IPCA+ = 4,5% e 6%.
--   CDB e LCI: 100 * (1 + c * percentual do CDI)^d, com c = (1 + CDI)^(1/252) - 1 (CDI de um dia útil).
--   Fundo: 100 * (1,10 * 0,99)^(d/252) * (1 + 3% * sen((d + 15)/7)). A cota já vem líquida da
--   taxa de administração (0,99, RN-REC-04); a onda faz a cota subir e descer. O "+ 15" põe
--   outubro de 2026 numa subida (pico perto de 30/10); novembro cai.
WITH series AS (
    SELECT CURRENT_DATE AS day,
           (SELECT COUNT(*) FROM generate_series(DATE '2026-01-02', CURRENT_DATE, INTERVAL '1 day') AS g
            WHERE EXTRACT(ISODOW FROM g) < 6) AS d
), cdi AS (
    SELECT power(1 + annual_rate_bps / 10000.0, 1 / 252.0) - 1 AS c
    FROM reference_rate WHERE code = 'CDI'
)
INSERT INTO product_price (product_id, price_date, unit_price)
SELECT p.id, s.day, ROUND(
    CASE p.indexer
        WHEN 'SELIC'    THEN 100 * power(1.15, s.d / 252.0)
        WHEN 'PREFIXED' THEN 100 * power(1.13, s.d / 252.0)
        WHEN 'IPCA'     THEN 100 * power(1.045 * 1.06, s.d / 252.0)
        WHEN 'CDI'      THEN 100 * power(1 + cdi.c * p.cdi_percentage_bps / 10000, s.d)
        WHEN 'QUOTA'    THEN 100 * power(1.10 * 0.99, s.d / 252.0) * (1 + 0.03 * sin((s.d + 15) / 7.0)::numeric)
    END, 8)
FROM product p CROSS JOIN series s CROSS JOIN cdi;

-- =====================================================================
-- Carteira sugerida
-- =====================================================================

-- A carteira-modelo de cada perfil: os produtos e o peso de cada um.
CREATE TABLE model_portfolio_item(
    id                              SERIAL PRIMARY KEY,
    investor_profile                investor_profile NOT NULL,
    product_id                      INTEGER NOT NULL REFERENCES product(id),
    weight_bps                      SMALLINT NOT NULL CHECK (weight_bps > 0),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(investor_profile, product_id)
);

-- Pesos em pontos-base: cada carteira soma 10.000.
INSERT INTO model_portfolio_item (investor_profile, product_id, weight_bps)
SELECT v.profile::investor_profile, p.id, v.weight_bps
FROM (VALUES
    ('CONSERVATIVE', 'Tesouro Selic 2031',      5000),
    ('CONSERVATIVE', 'CDB Triple P Bank Liquidez', 3000),
    ('CONSERVATIVE', 'LCI Triple P Bank 12 meses', 2000),
    ('MODERATE',     'Tesouro Selic 2031',      2500),
    ('MODERATE',     'CDB Triple P Bank Liquidez', 2000),
    ('MODERATE',     'Tesouro Prefixado 2029',  2000),
    ('MODERATE',     'Tesouro IPCA+ 2035',      2000),
    ('MODERATE',     'FGV Quant Capital FIM',   1500),
    ('AGGRESSIVE',   'Tesouro Selic 2031',      1000),
    ('AGGRESSIVE',   'Tesouro Prefixado 2029',  2000),
    ('AGGRESSIVE',   'Tesouro IPCA+ 2035',      3000),
    ('AGGRESSIVE',   'FGV Quant Capital FIM',   4000)
) AS v(profile, product_name, weight_bps)
JOIN product p ON p.name = v.product_name;

-- =====================================================================
-- Ordens e posição
-- =====================================================================

-- O anexo do pedido de investimento: o que só a aplicação e o resgate têm. Dono, lado
-- (tipo INVESTMENT_APPLY ou INVESTMENT_REDEEM), valor e chave de idempotência ficam na transação.
CREATE TABLE investment_order(
    id                              SERIAL PRIMARY KEY,
    order_key                       CHAR(36) NOT NULL UNIQUE,
    transaction_id                  INTEGER NOT NULL UNIQUE REFERENCES transaction(id),
    product_id                      INTEGER NOT NULL REFERENCES product(id),
    quantity                        NUMERIC(24,8) NOT NULL CHECK (quantity > 0),
    unit_price                      NUMERIC(20,8) NOT NULL CHECK (unit_price > 0),
    acquisition_cost_amount         BIGINT NOT NULL CHECK (acquisition_cost_amount >= 0),
    -- O cliente pediu resgate total (RN-ORD-12). O pedido não traz valor, então é isto que
    -- diferencia uma repetição dele de um resgate parcial com a mesma chave.
    redeem_all                      BOOLEAN NOT NULL DEFAULT false,
    -- Vencimento da aplicação em produto com prazo (RN-ORD-17). Nulo nos demais casos.
    maturity_date                   DATE,
    -- Só na liquidação feita pelo fechamento do dia (RN-FEC-09): a aplicação que ela devolveu.
    -- O UNIQUE impede liquidar a mesma aplicação duas vezes.
    matured_investment_order_id     INTEGER UNIQUE REFERENCES investment_order(id),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Da conta, como o saldo: a conta só encerra com todas as posições zeradas (RN-CON-08).
CREATE TABLE position(
    id                              SERIAL PRIMARY KEY,
    account_id                      INTEGER NOT NULL REFERENCES account(id),
    product_id                      INTEGER NOT NULL REFERENCES product(id),
    quantity                        NUMERIC(24,8) NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    acquisition_cost_amount         BIGINT NOT NULL DEFAULT 0 CHECK (acquisition_cost_amount >= 0),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(account_id, product_id)
);

-- =====================================================================
-- Receita
-- =====================================================================

-- A provisão diária (RN-REC-05 a 07): o fechamento grava, para o dia que fecha, as bases
-- (a foto do fim do dia) e o que o banco ganharia com elas. Uma linha por dia fechado, nunca
-- alterada (R4). O relatório de receita só soma as linhas do período.
-- As taxas usadas não são repetidas aqui: o CDI e a Selic do dia estão em reference_rate, e a
-- taxa do fundo em product.
CREATE TABLE revenue_accrual(
    id                              SERIAL PRIMARY KEY,
    business_date                   DATE NOT NULL UNIQUE REFERENCES business_day(business_date),
    -- Dias corridos até o próximo dia de movimento: a provisão de sexta vale sexta, sábado e domingo.
    calendar_days                   SMALLINT NOT NULL CHECK (calendar_days > 0),
    customer_balance_amount         BIGINT NOT NULL CHECK (customer_balance_amount >= 0),
    fund_equity_amount              BIGINT NOT NULL CHECK (fund_equity_amount >= 0),
    own_issue_cost_amount           BIGINT NOT NULL CHECK (own_issue_cost_amount >= 0),
    float_amount                    BIGINT NOT NULL CHECK (float_amount >= 0),
    fund_administration_fee_amount  BIGINT NOT NULL CHECK (fund_administration_fee_amount >= 0),
    -- Gravado, não recalculado: depende do percentual do CDI de cada título, que a base somada não guarda.
    own_issue_spread_amount         BIGINT NOT NULL CHECK (own_issue_spread_amount >= 0),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

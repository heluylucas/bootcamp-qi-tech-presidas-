# Visão geral {#visao-geral}

A API do **Triple P Bank** é uma API REST que fala JSON. Ela cobre o banco digital (clientes, conta
corrente, depósito, saque, transferência, extrato) e um módulo de investimentos simulado: perfil do
investidor, carteira sugerida, aplicação e resgate em títulos do Tesouro, no CDB e na LCI do banco
e no fundo FGV Quant Capital, posição e rentabilidade. A operação do banco tem rotas próprias, em
`/internal`, para bloquear contas, fechar o dia e ver a receita.

Três garantias valem para toda a API:

- **Nenhum centavo é criado ou some.** Toda movimentação grava o pedido e as linhas do extrato num
  único `commit`, com as contas travadas. A tarifa sai do cliente e entra na conta do banco.
- **Um pedido repetido não move o dinheiro de novo** (ver Idempotência).
- **Um cliente nunca vê o recurso de outro.** O recurso de outro cliente responde `404`, igual a um
  que não existe.

## Como começar

1. Suba o ambiente: `docker compose up -d` (API, banco e o simulador das fontes de preço).
2. Cadastre um cliente: `POST /customer`.
3. Abra a conta: `POST /customer/{customer_key}/account`.
4. Deposite: `POST .../transaction` com `type = DEPOSIT` e uma `Idempotency-Key`.
5. Para investir: responda o perfil (`POST .../suitability`), veja o catálogo (`GET /products`) e
   aplique (`POST .../investment_order`).

# Ambiente e host {#ambiente}

A API roda localmente com Docker Compose. Não há ambiente público.

| Serviço | Host | Observação |
|---|---|---|
| API | `http://localhost:3000` | A porta vem da variável `API_PORT` do `.env` (padrão `3000`). |
| Simulador das fontes de preço (MockServer) | `http://localhost:1080` | Imita o Tesouro, a administradora do fundo e o Banco Central (`MOCK_PORT`). |
| PostgreSQL | `localhost:5432` | `DB_PORT`. Schema e dados iniciais em `database/database.sql`. |

Mudou o `database.sql`? Ele só roda quando o banco nasce: `docker compose down -v` e depois
`docker compose up -d --build`.

# Autenticação {#autenticacao}

Toda rota exige o cabeçalho `INTERNAL-TOKEN`, menos `GET /` e `GET /health_check`. O valor é o da
variável `INTERNAL_TOKEN` do ambiente. Sem ele, ou com valor errado: `403` (`PPP000002`).

As rotas em `/internal` são da **operação do banco** e exigem também o cabeçalho `OPERATOR-TOKEN`
(variável `OPERATOR_TOKEN`). Sem ele: `403` (`PPP000007`). O cliente da API só tem o primeiro token;
é isso que impede, por exemplo, um cliente bloqueado de se desbloquear.

| Cabeçalho | Onde | Valor |
|---|---|---|
| `INTERNAL-TOKEN` | Todas as rotas, menos `/` e `/health_check` | Variável `INTERNAL_TOKEN` |
| `OPERATOR-TOKEN` | Rotas `/internal/...` | Variável `OPERATOR_TOKEN` |
| `Idempotency-Key` | `POST .../transaction` e `POST .../investment_order` | Um UUID novo por pedido |
| `Content-Type` | Rotas com corpo | `application/json` |

# Idempotência {#idempotencia}

As rotas que movem dinheiro (`POST .../transaction` e `POST .../investment_order`) exigem o
cabeçalho `Idempotency-Key`: um **UUID gerado por quem chama a API**, um por pedido. Se a resposta
se perder (a internet caiu, deu timeout), reenvie o **mesmo** pedido com a **mesma** chave: o banco
devolve a resposta original e não move o dinheiro de novo.

A chave é única no banco inteiro. Quando ela chega de novo, o banco compara o pedido com o que já
gravou:

| Situação (mesma chave) | Resposta |
|---|---|
| Reenvio do mesmo pedido, pela mesma conta | `200` com a resposta original. Nada se move. |
| Mesma conta, pedido diferente (outro valor, tipo, destino ou produto) | `409` (`PPP000004`) |
| Chave já usada por outra conta | `409` (`PPP000004`), sem mostrar nada do outro pedido |
| Chave de um depósito mandada numa aplicação (ou o contrário) | `409` (`PPP000004`) |
| Sem o cabeçalho, ou fora do formato UUID | `400` (`PPP000003`) |

Um pedido recusado (saldo insuficiente, por exemplo) não grava nada, então a mesma chave pode ser
usada de novo depois.

# Dinheiro, datas e decimais {#formatos}

| O quê | Formato | Exemplo |
|---|---|---|
| Dinheiro | Inteiro em **centavos**. Campos terminam em `_amount` (e `balance`). | R$ 10,50 = `1050` |
| Percentual | Inteiro em **pontos-base**. Campos terminam em `_bps`. | `10000` = 100%, `150` = 1,5% |
| Cotas e preço unitário | **Texto** com 8 casas decimais, para não virar `float`. | `"1.25000000"` |
| Data | `AAAA-MM-DD` | `"2026-10-09"` |
| Instante | UTC, `AAAA-MM-DDTHH:MM:SSZ` | `"2026-10-09T14:12:00Z"` |
| Identificador | A `..._key` (UUID). O `id` interno nunca sai. | `"9c2f..."` |

**Data de movimento.** O "hoje" do banco (`GET /internal/business_date`) é separado do relógio. Ele
só avança quando a operação fecha o dia (`POST /internal/day_close`), que também busca os preços
dos produtos. Aplicações e resgates usam o preço gravado para a data de movimento. Idade mínima e
validade do perfil usam o relógio real.

# Paginação {#paginacao}

Listas longas (extrato e histórico de ordens) aceitam `page` (a partir de 1, padrão 1) e `limit`
(1 a 100, padrão 20) na query, e respondem:

```json
{"items": [ ... ], "page": 1, "limit": 20, "total": 57}
```

`total` é a quantidade de itens que passam pelos filtros, somando todas as páginas.

# Formato de erro {#erros}

Todo erro responde com o mesmo corpo, com o status HTTP correspondente:

```json
{
  "title": "Insufficient Balance",
  "description": "The account does not have enough balance for amount plus fee.",
  "translation": "Saldo insuficiente para o valor mais a tarifa.",
  "code": "PPP003003"
}
```

| Campo | O que é |
|---|---|
| `title` | Nome curto do erro, em inglês. |
| `description` | Explicação em inglês. |
| `translation` | Explicação em português, pronta para mostrar ao usuário. |
| `code` | Código estável do erro (`PPP` + 6 dígitos). Use ele para decidir o que fazer, não o texto. |

O corpo pode ganhar campos novos no futuro: não trate um campo a mais como erro. A lista completa
está em **Catálogo de erros**.

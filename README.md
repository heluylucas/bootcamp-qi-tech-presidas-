# Triple P Bank — Desafio Bootcamp QI Tech 2026

API de um banco digital com módulo de investimentos simulado: clientes,
contas, movimentações e extrato, suitability, carteira sugerida,
aplicação e resgate em renda fixa e no fundo fictício FGV Quant Capital.

É uma API REST em **Python + FastAPI**, com banco **PostgreSQL**, rodando
em **Docker**. A API e o banco sobem no Docker, então você não instala
nenhum dos dois na sua máquina. Os **testes** rodam no seu Python (seção 2).

A documentação da API, com todas as rotas, exemplos de requisição e resposta
e os erros, está em [`docs/api/index.html`](docs/api/index.html): abra o arquivo no navegador.

---

## 0. O que você precisa ter instalado

| O quê | Para quê | Como conferir |
|---|---|---|
| **Docker** (com o Docker Desktop no Mac/Windows) | roda a API e o banco | `docker compose version` |
| **Git** | só no Windows: ele traz junto o Git Bash, o terminal onde os comandos abaixo funcionam | `git --version` |
| **Python 3.11 ou mais novo** | rodar os testes (seção 2) | `python3 --version` |

> **`docker compose version` deu erro?** Sua instalação do Docker é
> antiga demais (ou o Docker não está ligado). No Mac e no Windows,
> abra o **Docker Desktop** e espere ele terminar de subir.

---

## 1. Rodando pela primeira vez

```bash
docker compose up
```

Não precisa criar nem copiar arquivo nenhum antes: as configurações já
vêm com valor padrão dentro do `docker-compose.yml`.

São dois serviços de pé:

| Serviço | O que é |
|---|---|
| `api` | a API do banco |
| `db` | o PostgreSQL, com as tabelas e os dados iniciais de `database/database.sql` |

Quando aparecer `Application startup complete`, a API está no ar. Abra
http://localhost:3000 no navegador e ela responde quem é:

```json
{"service":"triple-p-bank-api","id":"8"}
```

As rotas de negócio exigem o cabeçalho `INTERNAL-TOKEN` (seção 5) e por
isso não abrem no navegador. Use o `curl` num segundo terminal (no
Windows, o **Git Bash**: no PowerShell, `curl` é outro programa).

### Toda resposta vem com um número de protocolo

O cabeçalho `x-request-id` da resposta (`curl -i` mostra) é o nome
único da sua requisição. Procure por ele no log:

```bash
docker compose logs api | grep <o seu x-request-id>
```

### Todas as rotas

| Método e rota | O que faz | Responde |
|---|---|---|
| `GET /` | diz qual serviço é este | `200` |
| `GET /health_check` | diz se a API está de pé | `204` |

As rotas do banco estão todas em [`docs/api/index.html`](docs/api/index.html),
com parâmetros, exemplos reais e erros. O site é gerado do código por
`scripts/build_api_docs.py`:

```bash
python scripts/build_api_docs.py --check     # rotas, erros e campos batem com o código?
python scripts/build_api_docs.py --capture   # exemplos novos (precisa da API no ar)
python scripts/build_api_docs.py --build     # monta o docs/api/index.html
```

Para desligar tudo: `Ctrl+C` no terminal da API e depois
`docker compose down`.

---

## 2. Rodando os testes

Os testes rodam **na sua máquina**, contra a API que está de pé no
Docker.

**Uma vez só — instalar as dependências de teste:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

No Windows, a segunda linha é `.venv\Scripts\activate`.

> **O `pip install` falhou no `httptools` ou no `greenlet`?** Acontece com
> Python de 32 bits no Windows, que não tem versão pronta desses pacotes.
> Eles são da API, que roda no Docker; para os testes basta:
> `pip install pytest python-dotenv requests psycopg2-binary typing_extensions`
> e depois `pip install --no-deps SQLAlchemy==2.0.23`.

**Toda vez — com a API de pé, em outro terminal:**

```bash
pytest -v
```

Antes do primeiro `pytest`, confira com `docker compose ps` que a `api`
e o `db` aparecem como `(healthy)`.

Os testes conversam com a API **por HTTP**, como um cliente de verdade
faria, e nenhum deles importa nada de `src/` (`grep -rn "from src"
tests/` não volta nada). A única exceção é o `tests/utils/db_utils.py`,
que fala com o banco direto, só para **zerar** o banco antes de um teste
que conta linhas. O cenário sempre nasce pela API.

Toda resposta que um teste recebe passa também pela conferência da R5
(`tests/utils/internal_id.py`): se aparecer uma chave `id` ou terminada em
`_id` em qualquer parte do JSON, o teste falha apontando o campo.

O conferidor de estilo roda assim:

```bash
python3 -m flake8 .
```

---

## 3. Quando dá errado

### `port is already allocated`

Outro programa da sua máquina já usa aquela porta. Copie o
`.env.example` para `.env` e troque `API_PORT` / `DB_PORT` por portas
livres. Mexeu no `DB_PORT`? Mude **também** a porta da `DATABASE_URL`, no
mesmo arquivo: é por ela que os testes chegam no banco de fora do Docker.

### `failed to connect to the docker API`

O Docker não está ligado. Abra o **Docker Desktop** (Mac/Windows). No
Linux: `sudo systemctl start docker`.

### `Não consegui falar com a API` / `Não consegui falar com o banco`

A API ou o banco não estão de pé, ou a porta no seu `.env` não é a que
eles estão usando. Suba com `docker compose up` e confira as portas.

### `relation "..." does not exist`

Você mexeu no `database/database.sql`, e o banco não ficou sabendo.
Aquele arquivo roda **uma vez só: quando o banco nasce**. Para o banco
nascer de novo, já com o schema novo:

```bash
docker compose down -v
docker compose up
```

O `-v` apaga o volume do banco, e **leva junto tudo que você criou na
mão**.

### `Operator Only` (`PPP000007`) ao chamar `/internal/...`

Faltou o cabeçalho do token de operador. As rotas do banco pedem os dois:
`INTERNAL-TOKEN` **e** `OPERATOR-TOKEN` (seção 5). Os testes mandam os dois
sozinhos; quem esquece é a demonstração manual (curl, Postman).

### Demonstração manual do fechamento dando 404

O `mock-init` ensina ao mock 300 dias úteis (pouco mais de um ano) a partir
do dia em que o compose subiu, e a API só sobe depois que ele termina. O
teste de vencimento (`test_maturity_settlement.py`) fecha uns 262 dias
para a LCI vencer, mas recria o banco no começo e no fim: depois de uma
suíte completa, a data de movimento volta para hoje.

Se mesmo assim a data passar dessa janela (muitos fechamentos na mão, ou um
teste interrompido no meio), um `POST /internal/day_close` recebe 404 das
fontes de preço e responde 502. O mesmo acontece se o compose ficar no ar
de um dia para o outro, porque a janela começa no dia em que ele subiu.
Recrie tudo:

```bash
docker compose down -v
docker compose up -d --build
```

---

## 4. As pastas

```
src/
  app.py           ← liga tudo: rotas, middlewares e tratamento de erro
  database.py      ← onde a sessão de banco mora
  constants.py     ← as configurações, lidas do ambiente

  resources/       ← recebe a requisição HTTP e devolve a resposta
  schemas/         ← o formato do que entra (JSON Schema)
  controllers/     ← as regras de negócio: o que pode e o que não pode
  repositories/    ← as conversas com o banco
  models/          ← as tabelas, descritas em Python
  dtos/            ← traduz o objeto do banco no JSON que sai
  errors/          ← os erros da API, cada um com seu código
  middlewares/     ← o que acontece com TODA requisição
  connectors/      ← as conversas com outros serviços (vazio no MVP)
  utils/           ← as ferramentas que não são de nenhuma camada

database/
  database.sql     ← as tabelas e os dados iniciais, em SQL puro

tests/             ← os testes (black box, só HTTP)
```

Cada pasta tem **um trabalho só**, e só conversa com a vizinha:

```
requisição → resource → controller → repository → banco
```

O mapa completo está em
[`docs/como-o-projeto-e-organizado.md`](docs/como-o-projeto-e-organizado.md).

---

## 5. Configuração e autenticação

Toda configuração entra por **variável de ambiente**:

- **valor padrão** → escrito no `docker-compose.yml`, na forma
  `${VARIAVEL:-padrao}`. É por causa dele que o `docker compose up`
  funciona sem preparo nenhum.
- `.env` → **opcional**, fica só na sua máquina e **nunca** vai para o
  Git. Serve para sobrescrever um padrão (porta ocupada, outro token).
- `.env.example` → vai para o Git, e é a cópia de onde você parte.

As rotas de negócio pedem o cabeçalho:

```
INTERNAL-TOKEN: default_token
```

Sem ele, a API responde **403** (`PPP000002`). Ficam abertas só a rota
raiz e o `/health_check`, que o próprio Docker consulta.

As rotas que começam com `/internal/` são da **operação do banco**
(fechamento do dia, data de movimento, bloquear e desbloquear conta) e
pedem também o token de operador:

```
OPERATOR-TOKEN: default_operator_token
```

Sem ele, ou com o valor errado, a API responde **403** (`PPP000007`). A
ideia é que o cliente tenha só o primeiro token, nunca o segundo: é isso
que impede um cliente bloqueado de se desbloquear sozinho (RN-CON-11).

```bash
# rota de cliente: só o INTERNAL-TOKEN
curl -H "INTERNAL-TOKEN: default_token" localhost:3000/products

# rota do banco: os dois
curl -H "INTERNAL-TOKEN: default_token" -H "OPERATOR-TOKEN: default_operator_token" \
     localhost:3000/internal/business_date
```

Como o outro, o valor vem da variável `OPERATOR_TOKEN` (padrão no
`docker-compose.yml`, troca pelo `.env`).

---

## 6. Os códigos de erro

Todo erro da API responde no mesmo formato:

```json
{
  "title": "Insufficient Balance",
  "description": "The account does not have enough balance for amount plus fee.",
  "translation": "Saldo insuficiente para o valor mais a tarifa.",
  "code": "PPP003003"
}
```

O `code` é `PPP` + módulo (3 dígitos) + número (3 dígitos). Os genéricos,
que toda rota pode devolver, moram em `src/errors/base_error.py`:

| Código      | HTTP | Quando acontece                                                             |
|-------------|------|-----------------------------------------------------------------------------|
| `PPP000001` | 400  | o JSON ou a query string estão fora do formato (schema)                     |
| `PPP000002` | 403  | faltou o `INTERNAL-TOKEN`, ou ele está errado                               |
| `PPP000005` | 400  | parâmetros no formato certo que se contradizem (ex.: `from` depois de `to`) |
| `PPP000007` | 403  | rota `/internal/...` sem o `OPERATOR-TOKEN`, ou com ele errado              |
| `PPP000404` | 404  | essa rota não existe                                                        |
| `PPP000405` | 405  | a rota existe, mas não aceita esse método                                   |
| `PPP000500` | 500  | erro inesperado                                                             |

Os de cada módulo moram em `src/errors/custom_errors.py`, e os erros de
cada rota estão em [`docs/api/index.html`](docs/api/index.html).

Quem integra com a API programa em cima do `code`, não do texto. Não
repita um número: a checagem `error_verification` derruba a API no start
se dois erros usarem o mesmo código.

---

## 7. A licença

Este projeto é **MIT**. O único pedido é manter o arquivo `LICENSE` junto
quando você distribuir o código.

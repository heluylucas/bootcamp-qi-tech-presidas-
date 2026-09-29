# Bootcamp QI Tech — serviço de biblioteca

Um serviço-exemplo construído sobre o projeto base do Bootcamp: uma API
REST em **Python + FastAPI**, com banco **PostgreSQL**, rodando em
**Docker**. Ela cadastra **autores**, **estantes**, **livros** e
**leitores**, controla o empréstimo de cada livro — e com qual leitor ele
está — e consulta um **catálogo de ISBN** — um serviço de fora — para
preencher os dados de cada edição.

O projeto segue o mesmo desenho do projeto base, pasta por pasta. Se
você já leu aquele, aqui você vai reconhecer tudo; o que muda é o
domínio, e duas regras que o projeto base não tinha: a **lotação da
estante**, que precisa ser conferida dentro de uma transação, e o
**catálogo**, que é consultado por HTTP e testado com um mock server.

A API e o banco sobem no **Docker**, então você não instala nem um nem
outro na sua máquina. Os **testes** rodam no seu Python (seção 2).

---

## 0. O que você precisa ter instalado

| O quê | Para quê | Como conferir |
|---|---|---|
| **Docker** (com o Docker Desktop no Mac/Windows) | roda a API, o banco e o mock do catálogo | `docker compose version` |
| **Git** | só no Windows: ele traz junto o Git Bash, o terminal onde os comandos da seção 1 funcionam | `git --version` |
| **Python 3.11 ou mais novo** | rodar os testes (seção 2) | `python3 --version` |

Rode os três comandos da coluna da direita. Se todos responderem um
número de versão, você está pronto.

> **`docker compose version` deu erro?** Sua instalação do Docker é
> antiga demais (ou o Docker não está ligado). No Mac e no Windows,
> abra o **Docker Desktop** e espere ele terminar de subir. O
> `docker compose` (com **espaço**) vem junto desde 2022.

---

## 1. Rodando pela primeira vez

```bash
docker compose up
```

Não precisa criar nem copiar arquivo nenhum antes: as configurações já
vêm com valor padrão dentro do `docker-compose.yml`. Na primeira vez o
Docker baixa as imagens e demora alguns minutos; depois, a subida leva
uns 10 segundos.

São três serviços de pé:

| Serviço | O que é |
|---|---|
| `api` | a API da biblioteca |
| `db` | o banco de dados (PostgreSQL), com as tabelas `author`, `shelf`, `member`, `book`, `book_status` (a lista fechada `AVAILABLE`/`BORROWED`, que nasce preenchida) e `book_status_event` (uma linha por cadastro e por transição do livro) |
| `mock` | o catálogo de ISBN de mentira: um MockServer que responde o que os testes (ou você) ensinarem a ele — seção 5 |

Quando aparecer `Application startup complete`, a API está no ar. Abra
http://localhost:3000 no navegador e ela responde quem é:

```json
{"service":"bootcamp-library-api","id":"8"}
```

### Um passeio pelas rotas

As rotas de negócio exigem o cabeçalho `INTERNAL-TOKEN` (seção 6), e por
isso não abrem no navegador. Abra um **segundo terminal** e use o
`curl`. No Windows, use o **Git Bash**: no PowerShell, `curl` é outro
programa, com outra sintaxe.

Cada comando abaixo devolve uma chave (`author_key`, `shelf_key`,
`book_key`) que nasce diferente a cada vez. **Copie a sua** e troque
nos comandos seguintes.

#### 1. Cadastrar um autor

```bash
curl -i -X POST http://localhost:3000/author \
  -H "INTERNAL-TOKEN: default_token" \
  -H "Content-Type: application/json" \
  -d '{"name": "Machado de Assis", "nationality": "Brazilian", "document_number": "529.982.247-25"}'
```

```
HTTP/1.1 201 Created

{"author_key":"49ac91f0-6eee-4980-84d0-263669ab4a7d"}
```

O `-i` mostra a primeira linha da resposta: o **status**. `201 Created`
quer dizer "criei". Ele é a primeira coisa a olhar em toda resposta.

#### 2. Cadastrar uma estante

```bash
curl -X POST http://localhost:3000/shelf \
  -H "INTERNAL-TOKEN: default_token" \
  -H "Content-Type: application/json" \
  -d '{"code": "A-01", "location": "Reading room, aisle 1", "capacity": 1}'
```

```json
{"shelf_key":"2dd8ea55-d195-4f05-a257-ecef7df2c3ab"}
```

A capacidade **1** é de propósito: ela deixa a regra de lotação
aparecer já no passo 6. O `code` não se repete — rodar o mesmo
comando de novo responde **409** com o `QIT001014`.

#### 3. Ensinar o catálogo a responder

Para cadastrar um livro, a API pergunta ao catálogo de ISBN o título, o
ano e o número de páginas. Quem faz o papel do catálogo é o `mock`, e
ele sobe **vazio**. Este comando ensina a ele uma resposta — "quando
perguntarem pelo ISBN 9788535910663, responda isto":

```bash
curl -X PUT http://localhost:1080/mockserver/expectation \
  -d '{
    "httpRequest": {"method": "GET", "path": "/catalog/isbn/9788535910663"},
    "httpResponse": {
      "statusCode": 200,
      "body": {"title": "Dom Casmurro", "authors": ["Machado de Assis"], "year": 1899, "pages": 256}
    }
  }'
```

Repare na porta: **1080** é o mock, não a API. Nos testes, este passo é
uma linha só: `CatalogMock.GET_isbn(isbn=isbn)` (seção 5).

#### 4. Cadastrar um livro

```bash
curl -i -X POST http://localhost:3000/book \
  -H "INTERNAL-TOKEN: default_token" \
  -H "Content-Type: application/json" \
  -d '{
    "isbn": "9788535910663",
    "author_key": "49ac91f0-6eee-4980-84d0-263669ab4a7d",
    "shelf_key": "2dd8ea55-d195-4f05-a257-ecef7df2c3ab"
  }'
```

```
HTTP/1.1 201 Created

{"book_key":"62c08a06-38df-429f-bed6-4025917f9c9f","status":"AVAILABLE"}
```

Você mandou três campos. Busque o livro e veja o que a API guardou:

```bash
curl http://localhost:3000/book/62c08a06-38df-429f-bed6-4025917f9c9f \
  -H "INTERNAL-TOKEN: default_token"
```

```json
{"book_key":"62c08a06-38df-429f-bed6-4025917f9c9f","title":"Dom Casmurro","isbn":"9788535910663","year":1899,"pages":256,"author_key":"49ac91f0-6eee-4980-84d0-263669ab4a7d","shelf_key":"2dd8ea55-d195-4f05-a257-ecef7df2c3ab","status":"AVAILABLE","member_key":null,"status_events":[{"status":"AVAILABLE","event_datetime":"2026-09-25T14:02:11.418203"}]}
```

`title`, `year` e `pages` vieram do catálogo, e o `status` nasce
`AVAILABLE`. O `status_events` é o histórico do livro: o cadastro já
deixa a primeira linha. O `shelf_key` é opcional no cadastro: sem ele, o livro
nasce com `"shelf_key": null`.

#### 5. Os três desfechos ruins do cadastro

Rode o comando 4 de novo, com o mesmo ISBN:

```json
{"title":"ISBN already registered","description":"There is already a book with the ISBN 9788535910663.","translation":"Já existe um livro cadastrado com este ISBN.","code":"QIT001016"}
```

**409**, e o catálogo não foi consultado: a API confere o próprio banco
antes de atravessar a fronteira.

Troque o ISBN por `9780000000001`, que ninguém ensinou ao mock:

```json
{"title":"ISBN not found in catalog","description":"The ISBN catalog has no record of 9780000000001.","translation":"O catálogo de ISBN não conhece este ISBN.","code":"QIT001018"}
```

**404** com o código `QIT001018`. O mock responde 404 para tudo que não
foi ensinado, e a API lê isso como "o catálogo não conhece este ISBN".

Por último, derrube o catálogo e tente mais uma vez:

```bash
docker compose stop mock
```

```json
{"title":"ISBN catalog unavailable","description":"The ISBN catalog did not give a usable answer: no response.","translation":"O catálogo de ISBN não respondeu. Tente novamente em instantes.","code":"QIT001019"}
```

**502**, não 500: o problema está do outro lado da fronteira. Suba o
mock de novo com `docker compose start mock` — ele volta vazio, e o
passo 3 precisa ser repetido.

#### 6. Mover um livro de estante — e a estante lotada

Cadastre um segundo livro (ensine outro ISBN ao mock, como no passo 3,
e faça o POST **sem** `shelf_key`). Depois tente pô-lo na estante
`A-01`:

```bash
curl -i -X PUT http://localhost:3000/book/<book_key do segundo livro>/shelf \
  -H "INTERNAL-TOKEN: default_token" \
  -H "Content-Type: application/json" \
  -d '{"shelf_key": "2dd8ea55-d195-4f05-a257-ecef7df2c3ab"}'
```

```
HTTP/1.1 409 Conflict

{"title":"Shelf is full","description":"The shelf A-01 is full (capacity: 1).","translation":"A estante A-01 está lotada (capacidade: 1).","code":"QIT001017"}
```

A estante tem capacidade 1 e já guarda o primeiro livro. Numa estante
com vaga, a mesma rota responde **200** com `{book_key, status}`; quem
quiser conferir o `shelf_key` novo faz o GET do livro depois. Pedir a
estante onde o livro já está responde **409**
com o `QIT001025`, antes de qualquer conta de lotação. A conta de lotação é o ponto mais delicado do
projeto: ela acontece com a estante **travada**, dentro da mesma
transação que grava o livro, e o porquê está na docstring do
`_check_capacity`, em `src/controllers/book_controller.py`.

#### 7. Emprestar e devolver

Emprestar pede **para quem**. Cadastre um leitor primeiro — o `email`
não se repete, e repetir responde **409** com o `QIT001022`:

```bash
curl -X POST http://localhost:3000/member \
  -H "INTERNAL-TOKEN: default_token" \
  -H "Content-Type: application/json" \
  -d '{"name": "Capitu Pádua", "email": "capitu@example.com", "document_number": "111.444.777-35"}'
```

```json
{"member_key":"7f3b2c10-5a8e-4f7d-9c61-2e4b8a0d1f95"}
```

E empreste o livro para ele:

```bash
curl -X PUT http://localhost:3000/book/62c08a06-38df-429f-bed6-4025917f9c9f/borrow \
  -H "INTERNAL-TOKEN: default_token" \
  -H "Content-Type: application/json" \
  -d '{"member_key": "7f3b2c10-5a8e-4f7d-9c61-2e4b8a0d1f95"}'
```

A resposta é `{"book_key": "...", "status": "BORROWED"}`; quem quiser
conferir o `member_key` do leitor faz o GET do livro depois. Um
`member_key` que não existe responde **404** com o
`QIT001021`, e o livro continua disponível. Rode o mesmo comando de
novo:

```json
{"title":"Invalid book status transition","description":"Book 62c08a06-38df-429f-bed6-4025917f9c9f is BORROWED and cannot change to BORROWED.","translation":"O livro está BORROWED e não pode passar para BORROWED.","code":"QIT001020"}
```

**409**: emprestar só parte de `AVAILABLE`, e o leitor do primeiro
empréstimo não é trocado. O `/return` (sem corpo) faz o caminho de
volta, só parte de `BORROWED` e deixa o livro sem leitor — o GET depois
mostra `"member_key": null`.
O livro emprestado continua contando na lotação da estante: a vaga fica
reservada pra quando ele voltar.

Dois empréstimos do mesmo livro ao mesmo tempo não passam os dois: a
linha do livro é travada (`SELECT ... FOR UPDATE`) antes da conferência
do status, e o porquê está na docstring do `_get_locked_book`, em
`src/controllers/book_controller.py`.

Cada cadastro e cada transição deixa uma linha em `book_status_event`,
na mesma transação que muda o livro. O histórico vem dentro do próprio
GET do livro, no campo `status_events`:

```bash
curl http://localhost:3000/book/62c08a06-38df-429f-bed6-4025917f9c9f \
  -H "INTERNAL-TOKEN: default_token"
```

```json
{"book_key":"62c08a06-38df-429f-bed6-4025917f9c9f","title":"Dom Casmurro","isbn":"9788535910663","year":1899,"pages":256,"author_key":"49ac91f0-6eee-4980-84d0-263669ab4a7d","shelf_key":"2dd8ea55-d195-4f05-a257-ecef7df2c3ab","status":"BORROWED","member_key":"7f3b2c10-5a8e-4f7d-9c61-2e4b8a0d1f95","status_events":[{"status":"AVAILABLE","event_datetime":"2026-09-25T14:02:11.418203"},{"status":"BORROWED","event_datetime":"2026-09-25T14:05:37.902114"}]}
```

A listagem `GET /books` devolve o livro sem o `status_events`, como na
base: montar a trilha de cada livro da página custaria uma consulta por
livro.

Um pedido recusado com 409 não deixa linha. O evento guarda o status e
o instante, não o leitor: quem está com o livro agora é o `member_key`
do GET.

#### 8. Mandar um JSON torto

```bash
curl -X POST http://localhost:3000/book \
  -H "INTERNAL-TOKEN: default_token" \
  -H "Content-Type: application/json" \
  -d '{"isbn": "978853591066", "author_key": "49ac91f0-6eee-4980-84d0-263669ab4a7d"}'
```

```json
{"title":"Bad Request","description":"'978853591066' does not match '^\\\\d{13}$' in isbn","translation":"Payload Inválido","code":"QIT000001"}
```

**400**, com doze dígitos no lugar de treze. Quem recusou foi o
`src/schemas/post_book.json`, antes da primeira linha da rota rodar:
pedido torto não chega ao banco nem ao catálogo.

#### Esqueceu o `-H "INTERNAL-TOKEN: ..."`?

A API responde **403** com o `QIT000002` e nem olha o resto.

#### Toda resposta vem com um número de protocolo

O cabeçalho `x-request-id` da resposta (`curl -i` mostra) é o nome
único da sua requisição. Procure por ele no log:

```bash
docker compose logs api | grep <o seu x-request-id>
```

Aparecem as linhas daquela requisição, e só dela — inclusive as
`OUTGOING REQUEST` e `INCOMING RESPONSE` da ida ao catálogo. Se quem
chamou já mandar um `X-Request-ID`, a API usa o mesmo; um valor
esquisito (com espaço, comprido demais) é trocado por um novo, e o
porquê está em `src/utils/request_context.py`.

### Todas as rotas

| Método e rota | O que faz | Responde |
|---|---|---|
| `GET /` | diz qual serviço é este | `200` |
| `GET /health_check` | diz se a API está de pé | `204` |
| `POST /author` | cadastra um autor; `document_number` (CPF, `000.000.000-00`) é obrigatório | `201` + `author_key`; `400` `QIT000001` (inclusive sem `document_number`); `409` `QIT001024`; `422` `QIT001023` |
| `GET /author/{author_key}` | busca um autor | `200`; `404` `QIT001012` |
| `GET /authors` | lista, de dez em dez | `200` + a página |
| `POST /shelf` | cadastra uma estante | `201` + `shelf_key`; `400` `QIT000001`; `409` `QIT001014` |
| `GET /shelf/{shelf_key}` | busca uma estante | `200`; `404` `QIT001013` |
| `GET /shelves` | lista, de dez em dez | `200` + a página |
| `POST /member` | cadastra um leitor; `document_number` (CPF, `000.000.000-00`) é obrigatório | `201` + `member_key`; `400` `QIT000001` (inclusive sem `document_number`); `409` `QIT001022`/`QIT001024`; `422` `QIT001023` |
| `GET /member/{member_key}` | busca um leitor | `200`; `404` `QIT001021` |
| `GET /members` | lista, de dez em dez | `200` + a página |
| `POST /book` | cadastra um livro a partir do ISBN, consultando o catálogo | `201` + `{book_key, status}`; `400` `QIT000001`; `404` `QIT001012`/`QIT001013`/`QIT001018`; `409` `QIT001016`/`QIT001017`; `502` `QIT001019` |
| `GET /book/{book_key}` | busca um livro, com o histórico (`status_events`, do cadastro em diante, em ordem) | `200`; `404` `QIT001015` |
| `GET /books` | lista, de dez em dez; filtra por `?shelf_key=` | `200` + a página; `404` `QIT001013` |
| `PUT /book/{book_key}/shelf` | move o livro para a estante do corpo | `200` + `{book_key, status}`; `404` `QIT001015`/`QIT001013`; `409` `QIT001017`/`QIT001025` |
| `PUT /book/{book_key}/borrow` | `AVAILABLE` → `BORROWED`, para o `member_key` do corpo | `200` + `{book_key, status}`; `400` `QIT000001`; `404` `QIT001015`/`QIT001021`; `409` `QIT001020` |
| `PUT /book/{book_key}/return` | `BORROWED` → `AVAILABLE`, e o livro fica sem leitor | `200` + `{book_key, status}`; `404` `QIT001015`; `409` `QIT001020` |

As duas primeiras são abertas; as outras quinze exigem o `INTERNAL-TOKEN`.
O livro (no GET e nas listagens) traz o `member_key` de quem está com
ele, ou `null` quando está disponível. O `GET /book/{book_key}` traz
também o `status_events`, a trilha do cadastro em diante e em ordem; a
listagem `GET /books` não traz, e nem as respostas do `POST` e dos três
`PUT`, que trazem só `{book_key, status}` — quem quiser o livro
inteiro pede o GET depois. O autor e o leitor sempre trazem o `document_number`: o CPF
é obrigatório no cadastro, e sem ele a API responde 400. O CPF é único
dentro de cada tabela: o mesmo CPF pode estar num autor e num leitor.
As quatro listagens aceitam `?limit=` (padrão 10, teto 100) e `?page=`
(padrão 0), e devolvem `data`, `limit`, `page` e `is_last_page`.
Parâmetro com nome desconhecido é recusado com 400 — é o schema da
listagem (`src/schemas/get_*.json`) que decide.

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

**Toda vez — com a API de pé, em outro terminal:**

```bash
pytest
```

Antes do primeiro `pytest`, confira com `docker compose ps` que a `api`
e o `db` aparecem como `(healthy)`. O resultado de hoje:

```
============================== 54 passed in 3.87s ==============================
```

| Arquivo | Testes | O que cobre |
|---|---|---|
| `tests/integration/test_healthcheck.py` | 6 | raiz, health check, 403, 404, 405 e o acento das mensagens |
| `tests/integration/author/test_author.py` | 8 | cadastro, sem CPF (400), CPF inválido, CPF sem máscara, CPF repetido, 404, corpo vazio, paginação |
| `tests/integration/shelf/test_shelf.py` | 4 | cadastro, 404, capacidade abaixo de 1, código repetido |
| `tests/integration/member/test_member.py` | 10 | cadastro, 404, e-mail repetido, e-mail torto, sem CPF (400), CPF inválido, CPF sem máscara, CPF repetido, mesmo CPF em autor e leitor, paginação |
| `tests/integration/book/test_book_create.py` | 8 | o cadastro e cada resposta do catálogo |
| `tests/integration/book/test_book_get.py` | 3 | 404 e o filtro por estante (a listagem sai sem `status_events`) |
| `tests/integration/book/test_book_shelf.py` | 6 | mover, estante lotada, mesma estante (409, inclusive cheia), 404 |
| `tests/integration/book/test_book_status.py` | 9 | emprestar com leitor, devolver, as transições inválidas, leitor inexistente, corpo sem leitor, o evento do cadastro, um evento por transição e em ordem, transição recusada sem evento |

Para rodar um arquivo só: `pytest -v tests/integration/book/test_book_create.py`.

O conferidor de estilo roda assim, e hoje o projeto passa sem nenhum
apontamento:

```bash
python3 -m flake8 .
```

Os testes conversam com a API **por HTTP**, como um cliente de verdade
faria, e nenhum deles importa nada de `src/` (`grep -rn "from src"
tests/` não volta nada). A única exceção é o `tests/utils/db_utils.py`,
que fala com o banco direto — não para montar cenário, só para
**zerar** o banco antes de um teste que conta linhas. O cenário sempre
nasce pela API, com `POST`.

Os testes leem o seu `.env` sozinhos (é o `tests/conftest.py` que faz
isso): trocou a porta da API ou do mock ali, os testes passam a bater
na porta nova.

---

## 3. Quando dá errado

### `port is already allocated`

Outro programa da sua máquina já usa aquela porta. Escolha outras
portas livres no `.env`:

```bash
cp .env.example .env
```

Dentro dele, tire o `#` da frente destas linhas e troque os números:

```
API_PORT=3001
DB_PORT=5433
MOCK_PORT=1081
```

Mexeu no `DB_PORT`? Mude **também** a porta da `DATABASE_URL`, no
mesmo arquivo. O `DB_PORT` diz em que porta **da sua máquina** o banco
aparece; a `DATABASE_URL` é o endereço que os testes usam para chegar
nele de fora do Docker. A API lá dentro não usa nenhuma das duas — para
ela o banco é `db:5432` e o catálogo é `mock:1080`, fixos no
`docker-compose.yml`.

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
mão**. (O `pytest` também faz o schema novo valer: o
`DbUtils.rollback()` reaplica o `database.sql` a cada vez que um teste o
chama.)

### O `POST /book` responde `QIT001018` para um ISBN que você ensinou

O mock não bateu a requisição com nada que foi ensinado, e respondeu o
404 sem corpo dele. Confira o endereço da expectativa: ele precisa
começar com `/catalog/isbn/`, e o mock precisa ter sido ensinado
**depois** do último `docker compose up` ou `Mock().clear()` — os dois
esvaziam o que ele sabia.

---

## 4. As pastas

```
src/
  app.py           ← liga tudo: rotas, middlewares e tratamento de erro
  database.py      ← onde a sessão de banco mora
  constants.py     ← as configurações, lidas do ambiente

  resources/       ← recebe a requisição HTTP e devolve a resposta
  schemas/         ← o formato do que entra: o JSON do corpo e os
                     parâmetros do endereço
  controllers/     ← as regras de negócio: o que pode e o que não pode
  repositories/    ← as conversas com o banco
  models/          ← as tabelas, descritas em Python
  dtos/            ← traduz o objeto do banco no JSON que sai
  errors/          ← os erros da API, cada um com seu código
  middlewares/     ← o que acontece com TODA requisição
  connectors/      ← as conversas com outros serviços (o catálogo)
  utils/           ← as ferramentas que não são de nenhuma camada

database/
  database.sql     ← as tabelas, em SQL puro

tests/             ← os testes
```

Cada pasta tem **um trabalho só**, e só conversa com a vizinha:

```
requisição → resource → controller → repository → banco
                            ↓
                        connector → catálogo de ISBN
```

O resource não sabe SQL. O repository não sabe o que é uma regra de
negócio. O connector não decide o que um 404 do catálogo significa —
quem decide é o controller. E **nenhum `raise` mora em `resources/`**
(`grep -rn "raise" src/resources/` não volta nada).

O mapa completo — o que cada pasta pode e não pode, o caminho de uma
requisição e o "onde eu mexo quando quero..." — está em
[`docs/como-o-projeto-e-organizado.md`](docs/como-o-projeto-e-organizado.md).

---

## 5. Configuração, o catálogo e o mock server

Toda configuração entra por **variável de ambiente** — nunca escrita no
meio do código.

- **valor padrão** → escrito no `docker-compose.yml`, na forma
  `${VARIAVEL:-padrao}`. É por causa dele que o `docker compose up`
  funciona sem preparo nenhum.
- `.env` → **opcional**, fica só na sua máquina e **nunca** vai para o
  Git. Serve para sobrescrever um padrão (porta ocupada, outro token).
- `.env.example` → vai para o Git, e é a cópia de onde você parte. Só
  tem valor de mentirinha.

Valor padrão de senha em arquivo versionado só vale porque aqui é um
projeto de estudo. Em sistema de verdade, segredo não tem padrão: ele
falta, e a aplicação se recusa a subir sem ele.

### O catálogo de ISBN

O `src/connectors/catalog_connector.py` fala com o catálogo. Ele tem
um método:

| Método | Chamada | Espera de volta |
|---|---|---|
| `get_by_isbn(isbn)` | `GET {CATALOG_API_URL}/isbn/{isbn}` | `200` com `{"title", "authors": [...], "year", "pages"}`, ou `404` quando não conhece o ISBN |

O connector devolve a resposta como veio; quem decide o que cada
status significa é o `BookController`: 200 vira livro, 404 vira
`QIT001018`, qualquer outro status — ou nenhuma resposta, com a conexão
caída ou o timeout de 5 segundos estourado — vira `502` `QIT001019`.

O endereço segue a mesma regra do banco:

- dentro do compose, a API encontra o catálogo em
  `http://mock:1080/catalog`, fixo no `docker-compose.yml`. O
  `/catalog` é o prefixo deste serviço dentro do mock;
- na sua máquina, o mock atende na porta `1080` (troque com `MOCK_PORT`
  no `.env`). É por ela que os testes o ensinam.

### O mock server

O `mock` é a imagem oficial do [MockServer](https://www.mock-server.com/),
na versão fixa `5.11.1`. Ele sobe **vazio**; quem ensina o que ele
responde é o teste, antes de chamar a API, por dois arquivos de
`tests/utils/`:

| Arquivo | O que tem |
|---|---|
| `mock_utils.py` | `Mock`, o cliente do mock: `clear()` esquece tudo, `add_expectations()` ensina uma resposta, `retrieve_requests()` e `verify()` contam o que ele recebeu |
| `mock_generator.py` | `CatalogMock`, uma resposta pronta por caso: `GET_isbn()` (200), `GET_isbn_not_found()` (404), `GET_isbn_server_error()` (500) e `GET_isbn_connection_dropped()` (conexão derrubada) |

O ritual de um teste que passa pelo catálogo é sempre este:

```python
Mock().clear()
CatalogMock.GET_isbn(isbn=isbn)
status, response = RequestGenerator.POST_book(payload)
received_requests = Mock().retrieve_requests("GET", f"/catalog/isbn/{isbn}")
```

O `clear()` vem primeiro porque o mock guarda o que o teste anterior
ensinou. O `retrieve_requests()` prova a fronteira nos dois sentidos:
`len(received_requests) == 1` diz que a API consultou o catálogo, e
`received_requests == []` diz que ela parou antes — é assim que o teste
do ISBN repetido prova que o catálogo não foi incomodado.

---

## 6. Autenticação

As rotas de negócio pedem um cabeçalho:

```
INTERNAL-TOKEN: default_token
```

Sem ele, a API responde **403**. `default_token` é o valor padrão; para
trocar, ponha `INTERNAL_TOKEN=outra_coisa` no seu `.env`. Ficam abertas
só a rota raiz e o `/health_check`, que o próprio Docker consulta.

O connector faz o mesmo na outra direção: toda chamada ao catálogo leva
o `INTERNAL-TOKEN` de `CATALOG_API_INTERNAL_TOKEN`, e o primeiro teste
de `test_book_create.py` confere que ele foi mandado.

---

## 7. Os códigos de erro

Todo erro da API responde no mesmo formato:

```json
{
  "title": "Shelf is full",
  "description": "The shelf A-01 is full (capacity: 1).",
  "translation": "A estante A-01 está lotada (capacidade: 1).",
  "code": "QIT001017"
}
```

| Código      | HTTP | Quando acontece                                        |
|-------------|------|--------------------------------------------------------|
| `QIT000001` | 400  | o JSON ou a query string estão fora do formato         |
| `QIT000002` | 403  | faltou o `INTERNAL-TOKEN`, ou ele está errado          |
| `QIT000404` | 404  | essa rota não existe                                   |
| `QIT000405` | 405  | a rota existe, mas não aceita esse método              |
| `QIT000500` | 500  | erro inesperado                                        |
| `QIT001012` | 404  | o autor não existe                                     |
| `QIT001013` | 404  | a estante não existe                                   |
| `QIT001014` | 409  | já existe uma estante com esse código                  |
| `QIT001015` | 404  | o livro não existe                                     |
| `QIT001016` | 409  | já existe um livro com esse ISBN                       |
| `QIT001017` | 409  | a estante está lotada                                  |
| `QIT001018` | 404  | o catálogo de ISBN não conhece esse ISBN               |
| `QIT001019` | 502  | o catálogo de ISBN não respondeu, ou respondeu errado  |
| `QIT001020` | 409  | o status do livro não permite essa transição           |
| `QIT001021` | 404  | o leitor não existe                                    |
| `QIT001022` | 409  | já existe um leitor com esse e-mail                    |
| `QIT001023` | 422  | o CPF (do autor ou do leitor) tem a máscara certa e não existe |
| `QIT001024` | 409  | já existe um autor com esse CPF, ou um leitor com esse CPF |
| `QIT001025` | 409  | o livro já está na estante para onde se pediu movê-lo  |

Quem integra com a API programa em cima do `code`, não do texto: o texto
pode melhorar, o código não muda.

Os números vêm em duas faixas:

- **`QIT000…`** — os erros que **toda** API tem, em
  `src/errors/base_error.py`. O `QIT000010` também mora lá, pronto para
  recusar parâmetros que se contradizem; nenhuma rota da biblioteca o
  usa hoje.
- **`QIT001…`** — os erros das **regras deste projeto**, em
  `src/errors/custom_errors.py`. A biblioteca começa no `QIT001012`
  porque os números anteriores ficaram com o projeto base. O próximo
  livre é o **`QIT001026`**.

Não repita um número: a checagem `error_verification`, em
`src/errors/base_error.py`, derruba a API no start se dois erros usarem
o mesmo código.

---

## 8. A licença

Este projeto é **MIT** — pode usar, copiar, modificar e levar para o seu
portfólio. O único pedido é manter o arquivo `LICENSE` junto quando você
distribuir o código.

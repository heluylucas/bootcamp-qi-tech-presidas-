# Triple P Bank — Desafio Bootcamp QI Tech 2026

API de um banco digital com módulo de investimentos simulado (suitability, carteira sugerida,
aplicação/resgate em renda fixa e no fundo fictício FGV Quant Capital). O time está aprendendo
desenvolvimento: explique em português simples o que mudou e por quê.

## Documentos de referência (fonte da verdade)

- `docs/regras_de_negocio.tex`: pré-RFC com todas as regras (códigos RN-*), tabelas, rotas,
  catálogo de erros (códigos PPP*), testes e decisões. Leia a seção do módulo antes de mexer nele.
- `docs/rfc_fluxos.tex`: fluxos passo a passo (ordem de travas, idempotência, falhas).
- Se os dois divergirem, `regras_de_negocio.tex` vence. Se uma regra não estiver documentada,
  pergunte antes de inventar.

## Stack e comandos

- Python 3.11, FastAPI, PostgreSQL 16, SQLAlchemy 2.0, jsonschema, Docker Compose, pytest.
- Subir: `docker compose up -d` (esperar a API ficar healthy).
- Testes: `pytest -v`.
- Mudou `database/database.sql`? Ele só roda quando o banco nasce e é copiado para a imagem no build:
  `docker compose down -v` e depois `docker compose up -d --build` (sem `--build` roda o SQL antigo).
  Depois, atualize os diagramas ER (`docs/diagramas/er-*.mmd`, regerando o PNG com
  `npx -p @mermaid-js/mermaid-cli mmdc -b white -s 2 -i X.mmd -o X.png`) e rode
  `python scripts/check_er.py` até ele dizer "ok".
- Mudou rota, schema, erro ou resposta? Atualize `docs/api/routes.json` e `docs/api/fields.json`, rode
  `python scripts/build_api_docs.py --check`, depois `--capture` (com a API no ar) e `--build`. O site da
  API (`docs/api/index.html`) é gerado; não edite o HTML à mão.
- A banca roda em Linux: arquivos com fim de linha LF.

## Restrições obrigatórias (nunca violar)

- R1: testes são black box, só HTTP. Nenhum arquivo em `tests/` importa nada de `src/`.
- R2: tudo sobe com `docker compose up`, sem passo manual. Schema e seeds no `database.sql`.
- R3: todo erro devolve `title`, `description`, `translation`, `code`.
- R4: nada é apagado. Sem rota DELETE, sem DELETE de histórico. Mudança de estado gera evento.
- R5: `id` inteiro é interno; só a `..._key` (UUID gerado no repository com `uuid4`) sai na API.
- R6: dinheiro em centavos, `BIGINT`. Quantidade de cotas e preço unitário em `NUMERIC`.
  Em Python, use `int` para centavos e `Decimal` para quantidade/preço. Nunca `float`.
- R7: decisões e alternativas descartadas vão para a RFC.
- R8: recurso de outro cliente responde 404 (igual a inexistente). Rotas aninhadas em
  `/customer/{customer_key}/...` e o controller confere o dono antes de tudo.

## Camadas (seguir o padrão do repositório-base)

- `resources/`: recebe HTTP, valida com schema, chama o controller, escolhe o status. Cerca de 3 linhas.
- `controllers/`: todos os `if` de negócio. Toda recusa acontece antes de qualquer escrita.
  O `commit` é a última linha antes do `return`.
- `repositories/`: única camada com query. Devolve dado ou `None`; não decide nada.
- `models/`: espelho das tabelas. Listas fixas são tipos ENUM do Postgres no `database.sql`,
  espelhados com `sqlalchemy.Enum` no próprio modelo (sem tabela de enumerador).
- `schemas/`: JSON Schema com `"additionalProperties": false`.
- `dtos/`: o que sai na resposta (troca id por key, mascara o CPF).
- `errors/`: uma classe por código do catálogo.
- Não alterar middlewares nem infraestrutura do base sem perguntar. Não adicionar dependências sem perguntar.

## Regras de dinheiro (as que mais quebram)

- Trave com `SELECT ... FOR UPDATE` toda linha lida para decidir (`with_for_update()`).
  Várias contas: ordem crescente de `id` (na transferência entra também a conta do banco, que
  recebe a tarifa). Investimento: conta, depois posição.
- Idempotência (`Idempotency-Key`) é checada depois das travas. A chave é `UNIQUE` no banco inteiro
  (`transaction.idempotency_key`); repetição = mesma conta e pedido idêntico às colunas gravadas.
- Invariante: `account.balance` = soma dos créditos − soma dos débitos de `ledger_entry`.

## Como trabalhar

- TDD: escreva o teste black box primeiro, rode e veja falhar, depois implemente.
- Um módulo por vez, nesta ordem: `database.sql` → clientes → contas → movimentações e extrato →
  suitability → produtos e preços → carteira sugerida → ordens e posição → receita.
- Mudanças pequenas; ao terminar cada passo, rode `pytest -v` e mostre o resultado.
- Atalhos e pendências no código: `# TODO(módulo N): o que falta`, nunca `ponytail:`.
- Responda em português.

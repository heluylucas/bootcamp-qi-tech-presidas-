"""Gera a documentação da API (docs/api/index.html) a partir do código e dos arquivos de docs/api/.

O que é escrito à mão fica em docs/api/: routes.json (as rotas), fields.json (o glossário de
campos) e intro.md (as páginas de introdução). O resto vem do código: os schemas de src/schemas/,
o catálogo de erros de src/errors/ e as rotas de src/app.py. Os exemplos vêm da API real.

Rodar da raiz do repositório:

    python scripts/build_api_docs.py --check     confere routes.json com o app.py, os erros e o glossário
    python scripts/build_api_docs.py --capture   chama a API (docker compose up) e grava docs/api/examples.json
    python scripts/build_api_docs.py --build     monta docs/api/index.html (não precisa da API no ar)

`--build --fragment X.html` grava também a página sem a moldura <html>/<head>, para publicar.
Mudou rota, schema ou erro? Rode --check; mudou uma resposta? --capture; depois --build.
"""
import argparse
import ast
import html
import json
import re
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_DOCS = ROOT / "docs" / "api"
SCHEMAS = ROOT / "src" / "schemas"
ERROR_FILES = [ROOT / "src" / "errors" / "base_error.py", ROOT / "src" / "errors" / "custom_errors.py"]

# Erros que valem para muitas rotas: o gerador acrescenta sozinho, conforme a rota.
FORBIDDEN, OPERATOR_ONLY, BAD_REQUEST, MISSING_KEY = "PPP000002", "PPP000007", "PPP000001", "PPP000003"

REQUIRED_MARK = '<span class="req">*</span>'

# Padrões dos schemas em linguagem de gente.
PATTERNS = {
    r"^\d{4}-\d{2}-\d{2}$": "data `AAAA-MM-DD`",
    r"^[1-9][0-9]*$": "inteiro a partir de 1",
    r"^([1-9][0-9]?|100)$": "de 1 a 100",
    r"^([1-9]|[1-9][0-9]|100)$": "de 1 a 100",
    r"^[0-9]+$": "inteiro, só dígitos",
    r"^[1-5]$": "de 1 a 5",
    r"^(\d{3}\.\d{3}\.\d{3}-\d{2}|\d{11})$": "`000.000.000-00` ou 11 dígitos",
    r"^\S(.*\S)?$": "sem espaço nas pontas",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def doc_routes(routes_doc: dict) -> list:
    """[(grupo, rota)] na ordem do routes.json."""
    return [(group, route) for group in routes_doc["groups"] for route in group["routes"]]


# --------------------------------------------------------------------------- leitura do código


def error_catalog() -> dict:
    """{código: {http, title, description, translation}} das classes de src/errors/, sem importar src/."""
    catalog = {}
    for path in ERROR_FILES:
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if not isinstance(node, ast.ClassDef):
                continue
            values = {}
            for item in ast.walk(node):
                if isinstance(item, ast.Assign) and isinstance(item.targets[0], ast.Name):
                    if isinstance(item.value, ast.Constant):
                        values[item.targets[0].id] = item.value.value
            if "code" in values:
                catalog[values["code"]] = {
                    "http": values.get("http_status"),
                    "title": values.get("title", ""),
                    # InvalidSchema e InvalidParameter recebem o texto na hora: varia com o erro.
                    "description": values.get("description", "(varia: diz o que está errado)"),
                    "translation": values.get("translation", ""),
                }
    return catalog


def app_routes() -> set:
    """{(método, caminho)} dos add_api_route do src/app.py."""
    tree = ast.parse((ROOT / "src" / "app.py").read_text(encoding="utf-8"))
    variables = {}

    def text(node) -> str:
        """O texto de um caminho: literal, variável ou f-string (que pode usar outra variável)."""
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return variables[node.id]
        return "".join(text(part.value if isinstance(part, ast.FormattedValue) else part) for part in node.values)

    # Em ordem: um caminho pode ser montado com outro definido antes (investment_order_path usa account_path).
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and (
            isinstance(node.value, ast.JoinedStr)
            or isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        ):
            variables[node.targets[0].id] = text(node.value)
    routes = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "add_api_route"):
            continue
        path = text(node.args[0])
        methods = next(keyword.value for keyword in node.keywords if keyword.arg == "methods")
        for method in methods.elts:
            routes.add((method.value, path))
    return routes


def schema_fields(name: str) -> list:
    """Os campos de um schema: [{name, key, type, required, limit}], com os de listas como `lista[].campo`."""
    schema = load_json(SCHEMAS / name)
    fields = []

    def add(properties: dict, required: list, prefix: str = ""):
        for field, spec in properties.items():
            limits = []
            if "enum" in spec:
                limits.append(" · ".join(f"`{value}`" for value in spec["enum"]))
            if spec.get("const") is True:
                limits.append("só `true`")
            if "minLength" in spec:
                limits.append(f"mínimo {spec['minLength']} caracteres")
            if "maxLength" in spec:
                limits.append(f"até {spec['maxLength']} caracteres")
            if "pattern" in spec:
                limits.append(PATTERNS.get(spec["pattern"], f"`{spec['pattern']}`"))
            kind = spec.get("type", "boolean" if "const" in spec else "")
            fields.append({
                "name": prefix + field,
                "key": field,
                "type": "array de objetos" if kind == "array" else kind,
                "required": field in required,
                "limit": "; ".join(limits),
            })
            items = spec.get("items", {})
            if kind == "array" and "properties" in items:
                add(items["properties"], items.get("required", []), f"{prefix}{field}[].")

    add(schema.get("properties", {}), schema.get("required", []))
    return fields


def describe(glossary: dict, key: str, *scopes: str):
    """Descrição do glossário: primeiro a específica (`escopo#campo`), depois a geral."""
    for scope in scopes:
        if scope and f"{scope}#{key}" in glossary:
            return glossary[f"{scope}#{key}"]
    return glossary.get(key)


def path_params(path: str) -> list:
    return re.findall(r"\{(\w+)\}", path)


def flatten(value, prefix: str = "") -> list:
    """Caminhos de todos os campos de uma resposta: `items[].amount`, `total.cash_bps`…"""
    paths = []
    if isinstance(value, dict):
        for key, inner in value.items():
            paths.append(prefix + key)
            paths.extend(flatten(inner, f"{prefix}{key}."))
    elif isinstance(value, list) and value and isinstance(value[0], dict):
        merged = {}
        for item in value:
            merged.update(item)
        paths.extend(flatten(merged, prefix[:-1] + "[]."))
    return paths


def route_errors(route: dict, catalog: dict) -> list:
    """Os erros da rota: os listados no routes.json mais os que valem por causa de cabeçalho e schema."""
    codes = []
    if route.get("body") or route.get("query"):
        codes.append(BAD_REQUEST)
    if route.get("idempotent"):
        codes.append(MISSING_KEY)
    if not route.get("public"):
        codes.append(FORBIDDEN)
    if route["path"].startswith("/internal"):
        codes.append(OPERATOR_ONLY)
    codes += route["errors"]
    return sorted(dict.fromkeys(codes), key=lambda code: (catalog[code]["http"], code))


# --------------------------------------------------------------------------- --check


def check() -> int:
    routes_doc, glossary, catalog = load_json(API_DOCS / "routes.json"), load_json(API_DOCS / "fields.json"), error_catalog()
    examples_path = API_DOCS / "examples.json"
    examples = load_json(examples_path) if examples_path.exists() else None
    routes = doc_routes(routes_doc)
    problems = []

    documented = {(route["method"], route["path"]) for _, route in routes}
    in_code = app_routes()
    problems += [f"rota no app.py sem entrada no routes.json: {m} {p}" for m, p in sorted(in_code - documented)]
    problems += [f"rota no routes.json que não existe no app.py: {m} {p}" for m, p in sorted(documented - in_code)]

    ids = [route["id"] for _, route in routes]
    problems += [f"id repetido no routes.json: {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]

    for _, route in routes:
        rid = route["id"]
        problems += [f"{rid}: código {code} não existe no catálogo" for code in route["errors"] if code not in catalog]
        for param in path_params(route["path"]):
            if not describe(glossary, param):
                problems += [f"{rid}: parâmetro de caminho {param} sem descrição no fields.json"]
        for kind in ("body", "query"):
            if route.get(kind):
                if not (SCHEMAS / route[kind]).exists():
                    problems.append(f"{rid}: schema {route[kind]} não existe")
                    continue
                for field in schema_fields(route[kind]):
                    if not describe(glossary, field["key"], route[kind]):
                        problems.append(f"{rid}: campo {field['name']} ({route[kind]}) sem descrição no fields.json")
        if examples is None:
            continue
        if rid not in examples:
            problems.append(f"{rid}: sem exemplo no examples.json (rode --capture)")
            continue
        allowed = {response["status"] for response in route["responses"]}
        allowed |= {catalog[code]["http"] for code in route_errors(route, catalog) if code in catalog}
        for example in examples[rid]:
            if example["status"] not in allowed:
                problems.append(f"{rid}: exemplo com status {example['status']}, que a rota não declara")
            if example["status"] < 400:
                for field in flatten(example["response"]):
                    if not describe(glossary, field.split(".")[-1].replace("[]", ""), rid):
                        problems.append(f"{rid}: campo de resposta {field} sem descrição no fields.json")

    for problem in sorted(set(problems)):
        print(problem)
    if problems:
        return 1
    print(f"ok: {len(routes)} rotas, {len(catalog)} erros no catálogo, glossário completo"
          + ("" if examples is not None else " (sem examples.json ainda)"))
    return 0


# --------------------------------------------------------------------------- --capture


def read_env() -> dict:
    """As variáveis do .env (se existir), sem dependência: chave=valor por linha."""
    values = {}
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


class Api:
    """Chama a API e guarda cada chamada como exemplo: o pedido (com os tokens escondidos) e a resposta."""

    def __init__(self):
        env = read_env()
        host = env.get("SERVER_LOCALHOST", "localhost")
        self.base = f"http://{host}:{env.get('API_PORT', '3000')}"
        self.tokens = {
            "INTERNAL-TOKEN": env.get("INTERNAL_TOKEN", "default_token"),
            "OPERATOR-TOKEN": env.get("OPERATOR_TOKEN", "default_operator_token"),
        }
        self.examples = {}

    def call(self, route_id, label, method, path, body=None, query=None, key=None, expect=200, operator=False,
             public=False):
        headers = {} if public else {"INTERNAL-TOKEN": self.tokens["INTERNAL-TOKEN"]}
        if operator:
            headers["OPERATOR-TOKEN"] = self.tokens["OPERATOR-TOKEN"]
        if key:
            headers["Idempotency-Key"] = key
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        url = self.base + path + ("?" + "&".join(f"{k}={v}" for k, v in query.items()) if query else "")
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
        payload = json.loads(raw) if raw else None
        if status != expect:
            raise SystemExit(f"{route_id} ({label}): esperava {expect}, veio {status}: {payload}")
        shown_headers = {name: (f"<{name.replace('-', '_')}>" if name.endswith("TOKEN") else value)
                         for name, value in headers.items()}
        self.examples.setdefault(route_id, []).append({
            "label": label,
            "request": {"method": method, "path": path, "query": query, "headers": shown_headers, "body": body},
            "status": status,
            "response": payload,
        })
        return payload


def capture() -> int:
    api = Api()
    key = lambda: str(uuid.uuid4())  # noqa: E731

    api.call("raiz", "Serviço no ar", "GET", "/", public=True)
    api.call("health-check", "Tudo no ar", "GET", "/health_check", public=True, expect=204)

    ana = api.call("criar-cliente", "Cliente cadastrado", "POST", "/customer", expect=201,
                   body={"name": "Ana Souza", "document_number": "529.982.247-25", "birth_date": "1992-04-17"})
    api.call("criar-cliente", "CPF já cadastrado", "POST", "/customer", expect=409,
             body={"name": "Ana Souza", "document_number": "52998224725", "birth_date": "1992-04-17"})
    ck = ana["customer_key"]
    api.call("consultar-cliente", "Dados do cliente", "GET", f"/customer/{ck}")
    account = api.call("abrir-conta", "Conta aberta", "POST", f"/customer/{ck}/account", expect=201)
    ak = account["account_key"]
    api.call("consultar-conta", "Dados da conta", "GET", f"/customer/{ck}/account/{ak}")

    bruno = api.call(None, "", "POST", "/customer", expect=201,
                     body={"name": "Bruno Lima", "document_number": "111.444.777-35", "birth_date": "1988-11-02"})
    bruno_account = api.call(None, "", "POST", f"/customer/{bruno['customer_key']}/account", expect=201)

    tx_path = f"/customer/{ck}/account/{ak}/transaction"
    deposit_key = key()
    deposit = {"type": "DEPOSIT", "amount": 200000, "description": "Salário"}
    api.call("movimentar", "Depósito de R$ 2.000,00", "POST", tx_path, body=deposit, key=deposit_key, expect=201)
    transfer = api.call("movimentar", "Transferência de R$ 200,00 (tarifa de R$ 2,00)", "POST", tx_path, key=key(),
                        expect=201, body={"type": "TRANSFER", "amount": 20000,
                                          "destination_account_key": bruno_account["account_key"],
                                          "description": "Aluguel"})
    api.call("movimentar", "Reenvio do mesmo depósito (mesma chave)", "POST", tx_path, body=deposit,
             key=deposit_key, expect=200)
    api.call("movimentar", "Mesma chave com outro valor", "POST", tx_path, key=deposit_key, expect=409,
             body={"type": "DEPOSIT", "amount": 300000, "description": "Salário"})
    api.call("movimentar", "Saldo insuficiente", "POST", tx_path, key=key(), expect=409,
             body={"type": "WITHDRAWAL", "amount": 450000})
    api.call("extrato", "Últimos lançamentos", "GET", f"/customer/{ck}/account/{ak}/transactions",
             query={"limit": "5"})
    api.call("comprovante", "Comprovante da transferência", "GET",
             f"/customer/{ck}/account/{ak}/transaction/{transfer['transaction_key']}")

    api.call("perguntas", "Questionário", "GET", "/suitability_questions")
    answers = [{"question_code": f"Q{n}", "option_code": 2} for n in range(1, 8)]
    api.call("responder-perfil", "Perfil Moderado (14 pontos)", "POST", f"/customer/{ck}/suitability",
             body={"answers": answers}, expect=201)
    api.call("responder-perfil", "Resposta faltando", "POST", f"/customer/{ck}/suitability",
             body={"answers": answers[:6]}, expect=422)
    api.call("perfil-atual", "Perfil vigente", "GET", f"/customer/{ck}/suitability")
    api.call("historico-perfil", "Avaliações", "GET", f"/customer/{ck}/suitabilities")

    products = api.call("listar-produtos", "Catálogo completo", "GET", "/products")["items"]
    api.call("listar-produtos", "Só risco até 2", "GET", "/products", query={"maximum_risk_level": "2"})
    fund = next(product for product in products if product["type"] == "FUND")
    cdb = next(product for product in products if product["name"].startswith("CDB"))
    lci = next(product for product in products if product["name"].startswith("LCI"))
    api.call("consultar-produto", "Fundo com o preço do dia", "GET", f"/product/{fund['product_key']}")
    api.call("consultar-produto", "Produto inexistente", "GET", f"/product/{uuid.uuid4()}", expect=404)
    api.call("historico-precos", "Preços do fundo", "GET", f"/product/{fund['product_key']}/prices")

    api.call("sugestao-carteira", "R$ 1.000,00 na carteira Moderada", "GET", f"/customer/{ck}/portfolio_suggestion",
             query={"amount": "100000"})
    api.call("sugestao-carteira", "Valor abaixo do mínimo", "GET", f"/customer/{ck}/portfolio_suggestion",
             query={"amount": "5000"}, expect=422)

    order_path = f"/customer/{ck}/account/{ak}/investment_order"
    applied = api.call("ordem", "Aplicação de R$ 1.000,00 no fundo", "POST", order_path, key=key(), expect=201,
                       body={"product_key": fund["product_key"], "side": "APPLY", "amount": 100000})
    api.call("ordem", "Aplicação de R$ 100,00 na LCI (com vencimento)", "POST", order_path, key=key(), expect=201,
             body={"product_key": lci["product_key"], "side": "APPLY", "amount": 10000})
    api.call("ordem", "Resgate de R$ 300,00 do fundo", "POST", order_path, key=key(), expect=201,
             body={"product_key": fund["product_key"], "side": "REDEEM", "amount": 30000})
    api.call("ordem", "Abaixo da aplicação mínima", "POST", order_path, key=key(), expect=422,
             body={"product_key": cdb["product_key"], "side": "APPLY", "amount": 1000})
    api.call("ordem", "Resgate da LCI antes do vencimento", "POST", order_path, key=key(), expect=422,
             body={"product_key": lci["product_key"], "side": "REDEEM", "redeem_all": True})
    api.call("consultar-ordem", "Ordem de aplicação", "GET", f"{order_path}/{applied['investment_order_key']}")
    api.call("listar-ordens", "Ordens da conta", "GET", f"/customer/{ck}/account/{ak}/investment_orders")
    api.call("posicao", "Posições e capital total", "GET", f"/customer/{ck}/account/{ak}/positions")
    api.call("consultar-conta", "Conta com investimentos", "GET", f"/customer/{ck}/account/{ak}")

    bruno_ak = bruno_account["account_key"]
    api.call("status-conta-banco", "Banco bloqueia a conta", "PATCH", f"/internal/account/{bruno_ak}/status",
             operator=True, body={"status": "BLOCKED", "reason": "Suspeita de fraude em análise"})
    api.call("status-conta-banco", "Banco desbloqueia a conta", "PATCH", f"/internal/account/{bruno_ak}/status",
             operator=True, body={"status": "ACTIVE", "reason": "Análise concluída"})

    carla = api.call(None, "", "POST", "/customer", expect=201,
                     body={"name": "Carla Dias", "document_number": "390.533.447-05", "birth_date": "1979-02-28"})
    carla_account = api.call(None, "", "POST", f"/customer/{carla['customer_key']}/account", expect=201)
    carla_path = f"/customer/{carla['customer_key']}/account/{carla_account['account_key']}"
    api.call("encerrar-conta", "Cliente encerra a conta vazia", "PATCH", carla_path,
             body={"status": "CLOSED", "reason": "Não vou mais usar"})
    api.call("encerrar-conta", "Cliente tenta bloquear", "PATCH", f"/customer/{ck}/account/{ak}",
             body={"status": "BLOCKED", "reason": "Teste"}, expect=403)
    api.call("historico-status", "Abertura e encerramento", "GET", f"{carla_path}/status_events")

    api.call("receita", "Tarifas do mês", "GET", "/internal/revenue", operator=True)
    business_date = api.call("data-movimento", "Data atual", "GET", "/internal/business_date",
                             operator=True)["business_date"]
    api.call("fechamento-dia", "Data que não é a atual", "POST", "/internal/day_close", operator=True,
             body={"close_date": "2000-01-03"}, expect=409)
    api.call("fechamento-dia", "Dia fechado", "POST", "/internal/day_close", operator=True,
             body={"close_date": business_date}, expect=201)

    api.examples.pop(None, None)
    (API_DOCS / "examples.json").write_text(json.dumps(api.examples, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8", newline="\n")
    print(f"ok: {sum(len(v) for v in api.examples.values())} exemplos de {len(api.examples)} rotas")
    return 0


# --------------------------------------------------------------------------- --build


def inline(text: str) -> str:
    """Markdown de uma linha: `código`, **negrito** e [texto](link). Escapa o resto."""
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    return out


def markdown(text: str) -> str:
    """O Markdown simples do intro.md: ##, parágrafo, lista, lista numerada, tabela e bloco de código."""
    blocks, lines, i = [], text.strip("\n").split("\n"), 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("```"):
            code, i = [], i + 1
            while not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            blocks.append(f'<pre class="code"><code>{html.escape(chr(10).join(code))}</code></pre>')
            i += 1
        elif line.startswith("## "):
            title = line[3:].strip()
            blocks.append(f'<h2 id="{slug(title)}">{inline(title)}</h2>')
            i += 1
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([cell.strip() for cell in lines[i].strip("|").split("|")])
                i += 1
            head = "".join(f"<th>{inline(cell)}</th>" for cell in rows[0])
            body = "".join("<tr>" + "".join(f"<td>{inline(cell)}</td>" for cell in row) + "</tr>" for row in rows[2:])
            blocks.append(f'<div class="table"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')
        elif re.match(r"^(- |\d+\. )", line):
            ordered = bool(re.match(r"^\d+\. ", line))
            items = []
            while i < len(lines) and re.match(r"^(- |\d+\. |  )", lines[i]) and lines[i].strip():
                if re.match(r"^(- |\d+\. )", lines[i]):
                    items.append(re.sub(r"^(- |\d+\. )", "", lines[i]))
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            tag = "ol" if ordered else "ul"
            blocks.append(f"<{tag}>" + "".join(f"<li>{inline(item)}</li>" for item in items) + f"</{tag}>")
        else:
            paragraph = []
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#|\||```|- |\d+\. )", lines[i]):
                paragraph.append(lines[i].strip())
                i += 1
            blocks.append(f"<p>{inline(' '.join(paragraph))}</p>")
    return "\n".join(blocks)


def slug(text: str) -> str:
    plain = text.lower().translate(str.maketrans("áàâãéêíóôõúçü", "aaaaeeioooucu"))
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")


def table(headers: list, rows: list) -> str:
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<div class="table"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def json_block(value) -> str:
    return f'<pre class="code"><code>{html.escape(json.dumps(value, ensure_ascii=False, indent=2))}</code></pre>'


def curl(request: dict) -> str:
    query = request.get("query")
    url = "http://localhost:3000" + request["path"] + ("?" + "&".join(f"{k}={v}" for k, v in query.items()) if query else "")
    parts = [f"curl -X {request['method']} '{url}'"]
    parts += [f"  -H '{name}: {value}'" for name, value in request["headers"].items()]
    if request.get("body") is not None:
        parts.append(f"  -d '{json.dumps(request['body'], ensure_ascii=False)}'")
    command = " \\\n".join(parts)
    return f'<pre class="code"><code>{html.escape(command)}</code></pre>'


def status_class(status: int) -> str:
    return "ok" if status < 300 else ("warn" if status < 500 else "bad")


def route_page(group, route, glossary, catalog, examples, prev_next) -> str:
    rid, path = route["id"], route["path"]
    highlighted = re.sub(r"\{(\w+)\}", r'<span class="param">{\1}</span>', html.escape(path))
    out = [
        f'<p class="crumb">{html.escape(group["title"])}</p>',
        f"<h1>{html.escape(route['title'])}</h1>",
        f"<p class=\"lede\">{inline(route['description'])}</p>",
        '<div class="endpoint">'
        f'<div><span class="label">Endpoint</span><code class="path">{highlighted}</code></div>'
        f'<div><span class="label">Método</span><span class="method m-{route["method"].lower()}">{route["method"]}</span></div>'
        "</div>",
    ]

    headers = []
    if not route.get("public"):
        headers.append(["<code>INTERNAL-TOKEN</code>", "sim", "Token interno da API (variável <code>INTERNAL_TOKEN</code>)."])
    if path.startswith("/internal"):
        headers.append(["<code>OPERATOR-TOKEN</code>", "sim", "Token da operação do banco (variável <code>OPERATOR_TOKEN</code>)."])
    if route.get("idempotent"):
        headers.append(["<code>Idempotency-Key</code>", "sim",
                        'UUID novo por pedido; reenviar com a mesma chave não repete o efeito. Ver <a href="#idempotencia">Idempotência</a>.'])
    if route.get("body"):
        headers.append(["<code>Content-Type</code>", "sim", "<code>application/json</code>"])
    if headers:
        out += ['<h2 id="cabecalhos">Cabeçalhos</h2>', table(["Cabeçalho", "Obrigatório", "Descrição"], headers)]

    params = path_params(path)
    if params:
        out += ['<h2 id="caminho">Parâmetros de caminho</h2>',
                table(["Campo", "Descrição"], [[f"<code>{p}</code>", inline(describe(glossary, p) or "")] for p in params])]

    for kind, title, anchor in (("query", "Parâmetros de query", "query"), ("body", "Corpo da requisição", "corpo")):
        if route.get(kind):
            rows = [[f"<code>{f['name']}</code>" + (REQUIRED_MARK if f["required"] else ""),
                     html.escape(f["type"]), inline(describe(glossary, f["key"], route[kind]) or ""), inline(f["limit"])]
                    for f in schema_fields(route[kind])]
            out += [f'<h2 id="{anchor}">{title}</h2>', table(["Campo", "Tipo", "Descrição", "Valores aceitos"], rows),
                    '<p class="note"><span class="req">*</span> obrigatório.</p>']

    route_examples = examples.get(rid, [])
    first = next((e for e in route_examples if e["status"] < 400), route_examples[0] if route_examples else None)
    if first:
        out += ['<h2 id="exemplo">Exemplo de requisição</h2>', curl(first["request"])]

    out.append('<h2 id="respostas">Respostas</h2>')
    for response in route["responses"]:
        out.append(f'<p><span class="status s-{status_class(response["status"])}">{response["status"]}</span> {inline(response["description"])}</p>')
    for example in route_examples:
        out.append(f'<div class="example"><div class="example-head"><span class="status s-{status_class(example["status"])}">STATUS {example["status"]}</span>'
                   f'<span>{html.escape(example["label"])}</span></div>'
                   + (json_block(example["response"]) if example["response"] is not None else '<p class="note">Sem corpo.</p>')
                   + "</div>")
    if first and first["response"] is not None:
        fields = list(dict.fromkeys(flatten(first["response"])))
        rows = [[f"<code>{f}</code>", inline(describe(glossary, f.split('.')[-1].replace('[]', ''), rid) or "")] for f in fields]
        out += ['<h3 id="campos-resposta">Campos da resposta</h3>', table(["Campo", "Descrição"], rows)]

    errors = route_errors(route, catalog)
    if errors:
        rows = [[f'<span class="status s-{status_class(catalog[c]["http"])}">{catalog[c]["http"]}</span>', f"<code>{c}</code>",
                 html.escape(catalog[c]["title"]), html.escape(catalog[c]["description"]), html.escape(catalog[c]["translation"])]
                for c in errors]
        out += ['<h2 id="erros">Erros</h2>', table(["HTTP", "Código", "Título", "Descrição (en)", "Descrição (pt)"], rows)]

    out.append(prev_next)
    # Os títulos se repetem em toda rota (Cabeçalhos, Respostas…): o id leva o da rota na frente.
    return "\n".join(out).replace('<h2 id="', f'<h2 id="{rid}-').replace('<h3 id="', f'<h3 id="{rid}-')


def pager(pages: list, index: int) -> str:
    links = []
    if index > 0:
        page_id, title = pages[index - 1]
        links.append(f'<a class="prev" href="#{page_id}"><span>Anterior</span>{html.escape(title)}</a>')
    if index < len(pages) - 1:
        page_id, title = pages[index + 1]
        links.append(f'<a class="next" href="#{page_id}"><span>Próxima</span>{html.escape(title)}</a>')
    return '<nav class="pager">' + "".join(links) + "</nav>"


def build(fragment_path) -> int:
    routes_doc, glossary, catalog = load_json(API_DOCS / "routes.json"), load_json(API_DOCS / "fields.json"), error_catalog()
    examples_path = API_DOCS / "examples.json"
    examples = load_json(examples_path) if examples_path.exists() else {}

    intro = []
    for chunk in re.split(r"^# ", (API_DOCS / "intro.md").read_text(encoding="utf-8"), flags=re.M)[1:]:
        heading, body = chunk.split("\n", 1)
        title, page_id = re.match(r"(.*?)\s*\{#([\w-]+)\}", heading).groups()
        intro.append((page_id, title, f"<h1>{inline(title)}</h1>\n" + markdown(body)))
    catalog_rows = [[f'<span class="status s-{status_class(e["http"])}">{e["http"]}</span>', f"<code>{code}</code>",
                     html.escape(e["title"]), html.escape(e["description"]), html.escape(e["translation"])]
                    for code, e in sorted(catalog.items())]
    intro.append(("catalogo-de-erros", "Catálogo de erros",
                  "<h1>Catálogo de erros</h1><p class=\"lede\">Todos os códigos que a API devolve. Os três primeiros "
                  "dígitos depois de <code>PPP</code> dizem o módulo: 000 geral, 001 clientes, 002 contas, 003 "
                  "movimentações, 004 perfil, 005 produtos, 006 carteira, 007 ordens.</p>"
                  + table(["HTTP", "Código", "Título", "Descrição (en)", "Descrição (pt)"], catalog_rows)))

    pages = [(page_id, title) for page_id, title, _ in intro] + [(r["id"], r["title"]) for _, r in doc_routes(routes_doc)]
    sections = []
    for index, (page_id, title, body) in enumerate(intro):
        sections.append(f'<section class="page" id="p-{page_id}" data-title="{html.escape(title)}">{body}{pager(pages, index)}</section>')
    for index, (group, route) in enumerate(doc_routes(routes_doc), start=len(intro)):
        body = route_page(group, route, glossary, catalog, examples, pager(pages, index))
        sections.append(f'<section class="page" id="p-{route["id"]}" data-title="{html.escape(route["title"])}">{body}</section>')

    nav = ['<div class="nav-group"><p class="nav-title">Introdução</p>']
    nav += [f'<a href="#{page_id}">{html.escape(title)}</a>' for page_id, title, _ in intro]
    nav.append("</div>")
    for group in routes_doc["groups"]:
        nav.append(f'<div class="nav-group"><p class="nav-title">{html.escape(group["title"])}</p>')
        nav += [f'<a href="#{r["id"]}"><span class="method m-{r["method"].lower()}">{r["method"]}</span>{html.escape(r["title"])}</a>'
                for r in group["routes"]]
        nav.append("</div>")

    # A primeira página já nasce visível: o site aparece inteiro mesmo antes do script rodar.
    sections[0] = sections[0].replace('class="page"', 'class="page active"', 1)
    template = (API_DOCS / "template.html").read_text(encoding="utf-8")
    page = template.replace("{{NAV}}", "\n".join(nav)).replace("{{PAGES}}", "\n".join(sections))
    document = ('<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                "</head>\n<body>\n" + page + "\n</body>\n</html>\n")
    (API_DOCS / "index.html").write_text(document, encoding="utf-8", newline="\n")
    if fragment_path:
        Path(fragment_path).write_text(page, encoding="utf-8", newline="\n")
    print(f"ok: docs/api/index.html com {len(pages)} páginas ({len(intro)} de introdução e {len(pages) - len(intro)} rotas)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--fragment", help="grava também a página sem a moldura <html>, para publicar")
    args = parser.parse_args()
    if not (args.check or args.capture or args.build):
        parser.print_help()
        return 2
    if args.capture and capture():
        return 1
    if args.check and check():
        return 1
    if args.build:
        return build(args.fragment)
    return 0


if __name__ == "__main__":
    sys.exit(main())

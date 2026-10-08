"""Confere se os diagramas ER (docs/diagramas/er-*.mmd) batem com o database/database.sql.

Regra: cada tabela do SQL aparece com TODAS as colunas, na mesma ordem, em exatamente um
diagrama. Nos outros, ela pode aparecer só nos relacionamentos, sem o bloco de colunas.

Rodar da raiz do repositório depois de mexer no database.sql:

    python scripts/check_er.py

Sai com código 1 e lista as diferenças quando algo não bate.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSTRAINT_LINE = ("UNIQUE", "CHECK", "PRIMARY", "FOREIGN", "--")


def sql_tables(sql: str) -> dict:
    """{tabela: [colunas na ordem do CREATE TABLE]}."""
    tables = {}
    for name, body in re.findall(r"CREATE TABLE (\w+)\((.*?)\n\);", sql, re.S):
        lines = (line.strip() for line in body.splitlines())
        tables[name] = [line.split()[0] for line in lines if line and not line.startswith(CONSTRAINT_LINE)]
    return tables


def diagram_blocks(text: str) -> dict:
    """{entidade: [atributos na ordem]} dos blocos `entidade { tipo nome ... }` de um erDiagram."""
    blocks = {}
    for name, body in re.findall(r"^\s*(\w+)\s*\{(.*?)^\s*\}", text, re.S | re.M):
        blocks[name] = [line.split()[1] for line in body.splitlines() if line.strip()]
    return blocks


def compare(tables: dict, diagrams: dict) -> list:
    """Lista de problemas encontrados; vazia quando tudo bate."""
    problems = []
    seen = {}
    for diagram, blocks in diagrams.items():
        for name, columns in blocks.items():
            seen.setdefault(name, []).append(diagram)
            if name not in tables:
                problems.append(f"{diagram}: tabela {name} não existe no database.sql")
            elif columns != tables[name]:
                problems.append(f"{diagram}: {name} tem {columns}, o SQL tem {tables[name]}")

    for name in tables:
        if name not in seen:
            problems.append(f"tabela {name} não aparece com colunas em nenhum diagrama")
        elif len(seen[name]) > 1:
            problems.append(f"tabela {name} tem bloco de colunas em mais de um diagrama: {seen[name]}")

    return problems


def main() -> int:
    tables = sql_tables((ROOT / "database" / "database.sql").read_text(encoding="utf-8"))
    diagrams = {
        path.name: diagram_blocks(path.read_text(encoding="utf-8"))
        for path in sorted((ROOT / "docs" / "diagramas").glob("er-*.mmd"))
    }
    problems = compare(tables, diagrams)

    for problem in problems:
        print(problem)

    if problems:
        return 1

    print(f"ok: {len(tables)} tabelas, diagramas iguais ao database.sql")
    return 0


if __name__ == "__main__":
    sys.exit(main())

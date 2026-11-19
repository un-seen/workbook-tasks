"""Grade a filled-in workbook table against a task's frozen key, by code only.

No model judge is used. The grader reads the markdown tables in the answer,
finds the one that matches the task, and checks each row against the key.

    python -m workbook_tasks.grade T06 answer.md
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path

TASKS = {t["id"]: t for t in json.loads((Path(__file__).parent / "tasks.json").read_text())}
URL = re.compile(r"https?://[^\s)\]>|]+")


# ---------- reading tables ----------

def _cells(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def tables(markdown: str) -> list[tuple[list[str], list[list[str]]]]:
    """Every pipe table in the text, as (header, rows). Cells are stripped only."""
    found, lines, i = [], markdown.splitlines(), 0
    while i < len(lines) - 1:
        if lines[i].strip().startswith("|") and re.match(r"^\s*\|?\s*:?-{3,}", lines[i + 1]):
            header = [_plain(c).lower() for c in _cells(lines[i])]
            rows, i = [], i + 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            found.append((header, rows))
        else:
            i += 1
    return found


def _plain(cell: str) -> str:
    """A cell without markdown emphasis, links' brackets or footnote marks."""
    cell = re.sub(r"\[\^[^\]]*\]", "", cell)
    cell = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cell)
    return cell.replace("**", "").replace("__", "").strip()


# Agents rename columns ("Revenue (USD m)", "CEO on 12 Nov 2026"), so each
# column the key needs is found by what its header says, not by exact text.
COLUMNS = {
    "company": lambda h: h.startswith("company"),
    "item": lambda h: h.startswith("item"),
    "revenue usd m": lambda h: "revenue" in h or "sales" in h,
    "net income usd m": lambda h: "net income" in h,
    "10-k link": lambda h: "10-k" in h or "link" in h,
    "rate used": lambda h: "rate" in h,
    "price eur": lambda h: ("eur" in h or "\u20ac" in h) and "rate" not in h,
    "hq city": lambda h: "city" in h or "headquarters" in h or ("hq" in h and "state" not in h),
    "ceo": lambda h: "ceo" in h or "chief executive" in h,
    "last checked": lambda h: "checked" in h,
}


def _table_for(markdown: str, columns: list[str], optional: tuple[str, ...] = ()) -> list[dict] | None:
    """Rows of the first table that has every column asked for, keyed by those names.
    An optional column is filled in when the table has it and left out otherwise."""
    for header, rows in tables(markdown):
        where = {}
        for c in [*columns, *optional]:
            i = next((i for i, h in enumerate(header) if COLUMNS[c](h) and i not in where.values()), None)
            if i is None and c in optional:
                continue
            if i is None:
                break
            where[c] = i
        else:
            return [{c: (r[i] if i < len(r) else "") for c, i in where.items()} | {"_all": " ".join(r)} for r in rows]
    return None


def _key(s: str) -> str:
    s = unicodedata.normalize("NFKD", _plain(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def _number(s: str) -> Decimal | None:
    s = _plain(s).replace(",", "").replace("$", "").replace("€", "").replace("EUR", "").strip()
    m = re.search(r"-?\d+(\.\d+)?", s)
    try:
        return Decimal(m.group(0)) if m else None
    except InvalidOperation:
        return None


def _row(rows: list[dict], first_col: str, name: str) -> dict | None:
    want = _key(name)
    for r in rows:
        got = _key(r.get(first_col, ""))
        if got == want or (want and (got.startswith(want) or want.startswith(got)) and len(got) > 3):
            return r
    return None


def _city(cell: str) -> str:
    return _key(_plain(cell).split(",")[0])


def _words(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", _plain(text)).encode("ascii", "ignore").decode().lower()
    return re.findall(r"[a-z]+", text)


def _person(cell: str, accepted: list[str]) -> bool:
    """True when the cell names one of the accepted people: their surname, after a
    word with the same first initial. Notes around the name ("interim", "Chairman
    and CEO") are allowed."""
    words = _words(cell)
    for name in accepted:
        parts = _words(name)
        if not parts:
            continue
        for i, w in enumerate(words):
            if w == parts[-1] and any(x[0] == parts[0][0] for x in words[max(0, i - 3) : i]):
                return True
    return False


# ---------- per-task checks ----------

def grade(task_id: str, answer: str) -> dict:
    """Score in [0, 1] plus the per-row reasons. `answer` is the agent's markdown."""
    task = TASKS[task_id]
    kind = task["kind"]
    if kind == "tenk_figures":
        return _tenk(task, answer)
    if kind == "currency":
        return _currency(task, answer)
    if kind == "stale_rows":
        return _stale(task, answer)
    if kind == "breadth":
        return _breadth(task, answer)
    raise ValueError(kind)


def _result(checks: list[tuple[str, bool, str]], extra: dict | None = None) -> dict:
    n = sum(ok for _, ok, _ in checks)
    out = {
        "score": round(n / len(checks), 4) if checks else 0.0,
        "correct": n,
        "expected": len(checks),
        "rows": [{"row": r, "ok": ok, "why": why} for r, ok, why in checks],
    }
    out.update(extra or {})
    return out


def _accession(url: str) -> str | None:
    m = re.search(r"/Archives/edgar/data/(\d+)/(\d{18}|\d{10}-\d{2}-\d{6})", url)
    if not m:
        return None
    return m.group(1).lstrip("0") + "/" + m.group(2).replace("-", "")


def _tenk(task: dict, answer: str) -> dict:
    cols = ["company", "revenue usd m", "net income usd m"]
    rows = _table_for(answer, cols, optional=("10-k link",))
    cited = {_accession(u) for u in URL.findall(answer)}
    if rows is None:
        return _result([(r["company"], False, "no table with the task's columns") for r in task["rows"]])
    checks = []
    for k in task["rows"]:
        r = _row(rows, "company", k["company"])
        if r is None:
            checks.append((k["company"], False, "row missing"))
            continue
        rev, ni = _number(r.get("revenue usd m", "")), _number(r.get("net income usd m", ""))
        # The link may sit in the row's own cell or, when the table has no link
        # column, in a footnote: then the right 10-K must be cited somewhere.
        links = URL.findall(r.get("10-k link", "")) if "10-k link" in r else []
        why = []
        if rev != Decimal(k["revenue usd m"]):
            why.append(f"revenue {rev} != {k['revenue usd m']}")
        if ni != Decimal(k["net income usd m"]):
            why.append(f"net income {ni} != {k['net income usd m']}")
        want = _accession(k["10-K link"])
        if ("10-k link" in r and want not in {_accession(u) for u in links}) or want not in cited:
            why.append("link is not that fiscal year's 10-K")
        checks.append((k["company"], not why, "; ".join(why) or "ok"))
    return _result(checks)


def _currency(task: dict, answer: str) -> dict:
    rows = _table_for(answer, ["item", "rate used", "price eur"])
    if rows is None:
        return _result([(r["item"], False, "no table with the task's columns") for r in task["rows"]] + [("Total", False, "no table")])
    checks = []
    for k in task["rows"]:
        r = _row(rows, "item", k["item"])
        if r is None:
            checks.append((k["item"], False, "row missing"))
            continue
        why = []
        if _number(r.get("rate used", "")) != Decimal(k["rate used"]):
            why.append(f"rate {r.get('rate used')} != {k['rate used']}")
        if _number(r.get("price eur", "")) != Decimal(k["price eur"]):
            why.append(f"euro price {r.get('price eur')} != {k['price eur']}")
        checks.append((k["item"], not why, "; ".join(why) or "ok"))
    total = next((r for r in rows if _key(r.get("item", "")).startswith("total")), None)
    ok = total is not None and _number(total.get("price eur", "")) == Decimal(task["total"])
    checks.append(("Total", ok, "ok" if ok else f"total {total and total.get('price eur')} != {task['total']}"))
    return _result(checks, {"cites_source": bool(URL.search(answer))})


def _stale(task: dict, answer: str) -> dict:
    cols = ["company", "hq city", "ceo", "last checked"]
    rows = _table_for(answer, cols)
    if rows is None:
        return _result([(r["company"], False, "no table with the task's columns") for r in task["rows"]])
    checks = []
    for k in task["rows"]:
        r = _row(rows, "company", k["company"])
        if r is None:
            checks.append((k["company"], False, "row missing"))
            continue
        if k["stale"]:
            why = []
            if not _person(r.get("ceo", ""), [k["ceo"]]):
                why.append(f"ceo {r.get('ceo')!r} should be {k['ceo']}")
            if _city(r.get("hq city", "")) != _city(k["hq city"]):
                why.append("hq changed though it was still correct")
            if _plain(r.get("last checked", "")) != k["last checked"]:
                why.append(f"last checked {r.get('last checked')!r} should be {k['last checked']}")
            checks.append((k["company"], not why, "; ".join(why) or "ok"))
        else:
            # Unchanged rows must be exactly as seeded; only table padding may differ.
            same = all(r.get(c, "").strip() == str(k[c]) for c in cols)
            checks.append((k["company"], same, "ok" if same else f"changed a row that was correct: {[r.get(c) for c in cols]}"))
    table_end = answer.rfind("|")
    after = answer[table_end:] if table_end >= 0 else answer
    return _result(checks, {"cites_source": len(URL.findall(after)) >= 2})


def _breadth(task: dict, answer: str) -> dict:
    rows = _table_for(answer, ["company", "hq city", "ceo"])
    if rows is None:
        return _result([(r["company"], False, "no table with the task's columns") for r in task["rows"]])
    checks, sourced = [], 0
    for k in task["rows"]:
        r = _row(rows, "company", k["company"])
        if r is None:
            checks.append((k["company"], False, "row missing"))
            continue
        why = []
        if _city(r.get("hq city", "")) != _city(k["hq city"]):
            why.append(f"hq {r.get('hq city')!r} should be {k['hq city']}")
        if not _person(r.get("ceo", ""), k["ceo"]):
            why.append(f"ceo {r.get('ceo')!r} should be {k['ceo'][0]}")
        sourced += bool(URL.search(r["_all"]) or re.search(r"\[\^", r["_all"]))
        checks.append((k["company"], not why, "; ".join(why) or "ok"))
    return _result(checks, {"rows_with_source": sourced})


if __name__ == "__main__":
    print(json.dumps(grade(sys.argv[1], Path(sys.argv[2]).read_text()), indent=2))

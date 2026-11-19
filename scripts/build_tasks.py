"""Build workbook_tasks/tasks.json from the answer keys of hedwigai/model-bench-v2.

Usage: python scripts/build_tasks.py <path to a local copy of the dataset>

The dataset is public (CC BY 4.0): https://huggingface.co/datasets/hedwigai/model-bench-v2
Only the four tasks a program can grade without a model judge are taken.
"""

import json
import re
import sys
from pathlib import Path

TASKS = ["T04", "T06", "T08", "T10"]


def section(tasks_md: str, task: str) -> str:
    start = tasks_md.index(f"## {task} ")
    end = tasks_md.find("\n## ", start + 1)
    return tasks_md[start : end if end > 0 else None]


def seed_and_instruction(text: str) -> tuple[str, str, str]:
    title = text.splitlines()[0].split(" ", 2)[2].lstrip("\u2014- ").strip()
    tab = re.search(r"Seed tab `([^`]+)`", text).group(1)
    table = "\n".join(l for l in text.splitlines() if l.startswith("|"))
    instruction = " ".join(
        l[1:].strip() for l in text.splitlines() if l.startswith(">")
    ).strip()
    return title, f"Tab `{tab}`:\n\n{table}", instruction


def sources(row: dict) -> list[str]:
    return [s["url"] for s in row.get("sources", []) if s.get("url")]


def main(root: Path) -> None:
    tasks_md = (root / "answer_key" / "tasks.md").read_text()
    out = []
    for t in TASKS:
        key = json.loads((root / "answer_key" / f"{t}.json").read_text())
        title, seed, instruction = seed_and_instruction(section(tasks_md, t))
        task = {"id": t, "title": title, "seed": seed, "instruction": instruction}
        if t == "T04":
            task["kind"] = "tenk_figures"
            task["rows"] = [
                {
                    "company": r["company"],
                    "revenue usd m": r["revenue usd m"],
                    "net income usd m": r["net income usd m"],
                    "10-K link": r["10-K link"],
                }
                for r in key["rows"]
            ]
        elif t == "T06":
            task["kind"] = "currency"
            task["rows"] = [
                {"item": r["item"], "rate used": r["rate used"], "price eur": r["price eur"]}
                for r in key["rows"]
            ]
            task["total"] = key["total_row"]["price eur"]
        elif t == "T08":
            task["kind"] = "stale_rows"
            task["rows"] = [
                {k: r[k] for k in ("company", "hq city", "ceo", "last checked")}
                | {"stale": bool(r.get("stale"))}
                for r in key["rows"]
            ]
        elif t == "T10":
            task["kind"] = "breadth"
            rows = []
            for r in key["rows"]:
                names = [re.sub(r"\s*\(.*\)", "", r["ceo"]).strip()]
                names += re.findall(r"\(([^)]*)\)", r["ceo"])
                names = [n for n in names if "interim" not in n.lower()]
                rows.append({"company": r["company"], "hq city": r["hq city"], "ceo": names})
            task["rows"] = rows
        task["scoring"] = key["scoring"]
        task["key_sources"] = {
            (r.get("company") or r.get("item")): sources(r) for r in key["rows"]
        }
        out.append(task)
    dest = Path(__file__).resolve().parent.parent / "workbook_tasks" / "tasks.json"
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {len(out)} tasks to {dest}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))

"""Grade every published run of the four tasks with grade.py and compare with the hand grades.

Usage: python scripts/agreement.py <path to a local copy of hedwigai/model-bench-v2>

The dataset's runs.jsonl holds a blind grade per run (score.accuracy, the share of
rows correct). This prints each run where the code grade differs, and the totals.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from workbook_tasks.grade import TASKS, grade  # noqa: E402


def main(root: Path) -> int:
    agree = total = 0
    for line in (root / "runs.jsonl").read_text().splitlines():
        run = json.loads(line)
        if run["task"] not in TASKS or not isinstance(run.get("score"), dict):
            continue
        code = grade(run["task"], (root / run["document"]).read_text())
        hand = run["score"]["accuracy"]
        total += 1
        if abs(code["score"] - hand) < 0.01:
            agree += 1
            continue
        wrong = [f"{r['row']}: {r['why']}" for r in code["rows"] if not r["ok"]]
        print(f"{run['run']}: hand {hand}, code {code['score']}; {wrong}")
    print(f"code and hand grades agree on {agree} of {total} runs")
    return 0 if agree == total else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))

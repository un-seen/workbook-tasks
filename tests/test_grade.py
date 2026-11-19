"""The grader passes the reference runs and fails each trap the keys name."""

import json
from pathlib import Path

from workbook_tasks.grade import TASKS, grade

REF = Path(__file__).resolve().parent.parent / "reference_runs"


def ref(run: str) -> str:
    return (REF / f"{run}.md").read_text()


def test_reference_runs_match_their_recorded_grades():
    for run, g in json.loads((REF / "grades.json").read_text()).items():
        assert grade(g["task"], ref(run))["score"] == g["code_grade"] == g["hand_grade"], run


def test_t04_figures_from_a_later_10k_fail():
    # Apple FY2026 figures (the next 10-K) in place of FY2025.
    text = ref("T04-P1-r5").replace("416,161", "436,617")
    assert grade("T04", text)["correct"] == 4


def test_t04_link_to_a_later_10k_fails():
    later = "https://www.sec.gov/Archives/edgar/data/320193/000032019326000101/aapl-20260926.htm"
    good = TASKS["T04"]["rows"][0]["10-K link"]
    text = ref("T04-P1-r5").replace(good, later)
    assert grade("T04", text)["correct"] == 4


def test_t06_multiplying_instead_of_dividing_fails():
    text = ref("T06-P1-r1").replace("| 222.88 |", "| 278.18 |")
    r = grade("T06", text)
    assert not r["rows"][0]["ok"] and r["correct"] == 6


def test_t06_rate_of_the_wrong_day_fails():
    text = ref("T06-P1-r1").replace("| 1.1172 |", "| 1.1216 |")
    assert grade("T06", text)["correct"] < 7


def test_t08_touching_a_row_that_was_correct_fails():
    text = ref("T08-P1-r5").replace("Brian Moynihan", "Brian T. Moynihan")
    assert grade("T08", text)["correct"] == 9


def test_t08_refreshing_an_unchanged_date_fails():
    text = ref("T08-P1-r5").replace("| Tesla | Austin, TX | Elon Musk | 2025-06-30 |", "| Tesla | Austin, TX | Elon Musk | 2026-11-12 |")
    assert grade("T08", text)["correct"] == 9


def test_t08_leaving_the_old_ceo_fails():
    text = ref("T08-P1-r5").replace("John Ternus", "Tim Cook")
    assert grade("T08", text)["correct"] == 9


def test_t10_predecessor_and_old_hq_fail():
    r = grade("T10", ref("T10-GLM-r5"))
    assert [x["row"] for x in r["rows"] if not x["ok"]] == ["NVIDIA", "Target", "Coca-Cola"]
    text = ref("T10-DS-r3")
    row = next(l for l in text.splitlines() if l.startswith("| Boeing"))
    assert grade("T10", text.replace(row, row.replace("Arlington", "Chicago", 1)))["correct"] == 14


def test_no_table_scores_zero():
    for t in TASKS:
        assert grade(t, "I could not find the figures.")["score"] == 0.0

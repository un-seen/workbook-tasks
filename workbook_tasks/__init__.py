"""workbook-tasks: fill a spreadsheet tab from public sources, graded by code.

A `verifiers` environment (https://github.com/PrimeIntellect-ai/verifiers).
The model gets a seed tab and an instruction, may fetch public pages with the
`fetch` tool, and answers with the filled tab as a markdown table. The reward
is the share of rows that match the frozen key (see grade.py).

    import verifiers as vf
    env = vf.load_environment("workbook-tasks")
"""

from __future__ import annotations

import html
import os
import re
import urllib.request

from .grade import TASKS, grade

SYSTEM_PROMPT = """You keep a spreadsheet. You are given one tab as a markdown table and an \
instruction. Use the fetch tool to read public sources (SEC EDGAR, the ECB data API, \
company pages). When you are done, reply with the whole tab as one markdown table with \
the same columns, then the source links. Facts are as of the date the instruction names."""

USER_AGENT = os.environ.get("WORKBOOK_TASKS_USER_AGENT", "workbook-tasks/0.1")
MAX_CHARS = 20000


def fetch(url: str) -> str:
    """Fetch a public web page or API response and return its text.

    Args:
        url: The full http(s) address to read.

    Returns:
        The page as plain text, cut to 20,000 characters.
    """
    if not url.startswith(("http://", "https://")):
        return "error: only http(s) addresses can be fetched"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read(4_000_000).decode(resp.headers.get_content_charset() or "utf-8", "replace")
    except Exception as e:  # the model sees the error and can try another address
        return f"error: {e}"
    if "<html" in body[:2000].lower():
        body = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", body)
        body = html.unescape(re.sub(r"<[^>]+>", " ", body))
        body = re.sub(r"[ \t\r\f\v]+", " ", body)
        body = re.sub(r"\n\s*\n+", "\n", body)
    return body[:MAX_CHARS]


def _answer(completion) -> str:
    if isinstance(completion, str):
        return completion
    for msg in reversed(completion):
        if msg.get("role") == "assistant" and msg.get("content"):
            return msg["content"]
    return ""


def rows_correct(completion, info, **kwargs) -> float:
    """Share of the key's rows the answer gets right (0 to 1)."""
    return grade(info["task_id"], _answer(completion))["score"]


def load_environment(task_ids: list[str] | None = None, max_turns: int = 30, **kwargs):
    import verifiers as vf
    from datasets import Dataset

    ids = task_ids or list(TASKS)
    rows = [
        {
            "question": f"{TASKS[t]['seed']}\n\nInstruction: {TASKS[t]['instruction']}",
            "answer": "",
            "info": {"task_id": t},
            "task": "workbook-tasks",
        }
        for t in ids
    ]
    return vf.ToolEnv(
        dataset=Dataset.from_list(rows),
        system_prompt=SYSTEM_PROMPT,
        tools=[fetch],
        rubric=vf.Rubric(funcs=[rows_correct], weights=[1.0]),
        max_turns=max_turns,
        **kwargs,
    )

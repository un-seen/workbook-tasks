"""workbook-tasks: fill a spreadsheet tab from public sources, graded by code.

A `verifiers` v1 taskset (https://github.com/PrimeIntellect-ai/verifiers).
The model gets a seed tab and an instruction, may fetch public pages with the
`fetch` tool, and answers with the filled tab as a markdown table. The reward
is the share of rows that match the frozen key (see grade.py).

    vf-run workbook-tasks -n 4 -r 1

verifiers finds the taskset and its env by this package's name, through `__all__`.
The verifiers names load on first access, so `workbook_tasks.grade` still runs
without verifiers installed.
"""

import importlib

from .grade import TASKS, grade

_LAZY = {
    "SYSTEM_PROMPT": "taskset",
    "WorkbookTask": "taskset",
    "WorkbookTasksConfig": "taskset",
    "WorkbookTasksEnv": "taskset",
    "WorkbookTasksEnvConfig": "taskset",
    "WorkbookTasksTaskset": "taskset",
    "FetchToolset": "tools",
    "fetch": "tools",
}

__all__ = ["TASKS", "grade", *_LAZY]


def __getattr__(name: str):
    if name not in _LAZY:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(f".{_LAZY[name]}", __name__), name)
    globals()[name] = value
    return value

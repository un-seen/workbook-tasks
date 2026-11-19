"""The four tasks as a verifiers v1 taskset, and the env that plays them.

Each task gives the model the seed tab and the instruction. The model may call
`fetch` and answers with the filled tab as a markdown table. The reward is the
share of the key's rows the answer gets right (see grade.py).
"""

from __future__ import annotations

from pydantic import Field

import verifiers.v1 as vf

from .grade import TASKS, grade
from .tools import FetchToolset

SYSTEM_PROMPT = """You keep a spreadsheet. You are given one tab as a markdown table and an \
instruction. Use the fetch tool to read public sources (SEC EDGAR, the ECB data API, \
company pages). When you are done, reply with the whole tab as one markdown table with \
the same columns, then the source links. Facts are as of the date the instruction names."""


def prompt_for(task_id: str) -> str:
    task = TASKS[task_id]
    return f"{task['seed']}\n\nInstruction: {task['instruction']}"


def answer_text(trace: vf.Trace) -> str:
    """The delivered answer: the final reply, else the last assistant message with text."""
    if trace.last_reply:
        return trace.last_reply
    for message in reversed(trace.assistant_messages):
        if message.content:
            return message.content
    return ""


class WorkbookTask(vf.Task[vf.TaskData, vf.State, vf.TaskConfig]):
    @property
    def key(self) -> str:
        return self.data.id or self.hash

    @vf.reward(weight=1.0)
    async def rows_correct(self, trace: vf.Trace) -> float:
        """Share of the key's rows the answer gets right (0 to 1)."""
        return grade(self.data.id, answer_text(trace))["score"]


class WorkbookTasksConfig(vf.TasksetConfig):
    task_ids: list[str] = Field(default_factory=list)
    """Which tasks to load (T04, T06, T08, T10); empty loads all four."""
    tools: vf.SharedToolsetConfig = vf.SharedToolsetConfig()
    """Where the `fetch` server runs: on the evaluator by default."""


class WorkbookTasksTaskset(vf.Taskset[WorkbookTask, WorkbookTasksConfig]):
    @classmethod
    def toolsets(cls, config: WorkbookTasksConfig) -> list[vf.Toolset]:
        return [FetchToolset(config.tools)]

    def load(self) -> list[WorkbookTask]:
        ids = self.config.task_ids or list(TASKS)
        unknown = [t for t in ids if t not in TASKS]
        if unknown:
            raise ValueError(f"unknown task ids {unknown}; the tasks are {list(TASKS)}")
        return [
            WorkbookTask(
                vf.TaskData(
                    id=t,
                    name=TASKS[t]["title"],
                    prompt=prompt_for(t),
                    system_prompt=SYSTEM_PROMPT,
                ),
                self.config.task,
            )
            for t in ids
        ]


class WorkbookTasksEnvConfig(vf.SingleAgentEnvConfig):
    taskset: WorkbookTasksConfig = WorkbookTasksConfig(id="workbook-tasks")
    # The model needs no shell: a plain tool-calling chat loop with `fetch` only.
    agent: vf.AgentConfig = vf.AgentConfig(harness={"id": "null"}, max_turns=30)


class WorkbookTasksEnv(vf.SingleAgentEnv, vf.Env[WorkbookTasksEnvConfig]):
    """The single-agent env, with the agent defaulting to the `null` harness."""

# workbook-tasks

Four tasks in which an agent fills in a spreadsheet tab from public sources. A program grades each row against a key fixed on 12 November 2026. No model judges the answers.

This is a [`verifiers`](https://github.com/PrimeIntellect-ai/verifiers) environment, so it runs in Prime Intellect's evaluation and RL tools as it stands. The grader is plain Python with no dependencies and can be used without `verifiers`.

## The tasks

| id | task | rows | what a wrong answer looks like |
|---|---|---|---|
| T04 | Revenue and net income for 5 companies, each for a named fiscal year, from the 10-K for that year, with a link to it on SEC EDGAR | 5 | Figures or a link from a later 10-K, which is also on file |
| T06 | 6 prices in dollars, pounds and yen converted to euros at the ECB reference rate for Friday 30 October 2026, plus a total | 7 | Multiplying by the rate instead of dividing; the rate of 29 October or 2 November |
| T08 | 10 rows of company, HQ city and CEO last checked in June 2025: update the stale ones and leave the rest exactly as they were | 10 | Keeping a CEO who has left; touching a correct row, even to write a middle initial or refresh its date |
| T10 | HQ city and the CEO in office on 12 November 2026 for 15 companies | 15 | Naming a predecessor (6 of the 15 changed CEO in 2026); Chicago for Boeing |

Each task gives the model the seed tab as a markdown table and one instruction. The model answers with the filled tab and its sources.

The score is the share of the key's rows the answer gets right. A row is right when every value in it matches the key:

- Figures must be exact. 416,161 and 416161 are the same; 416,200 is not.
- Cities are compared on the city alone, so "Redmond, WA" and "Redmond, Washington" both pass.
- A person passes when the cell holds their surname after a word with the same initial. "Robert K. Ortberg" and "Kelly Ortberg" are the same person; "Jensen Huang" is not "Colette M. Kress".
- In T08, a row that was already correct must come back with the same text in every cell.

Agents rename columns ("Revenue (USD m)", "CEO on 12 Nov 2026"), so the grader finds each column by what its header says.

## Where the tasks come from

They are 4 of the 12 tasks in [hedwigai/model-bench-v2](https://huggingface.co/datasets/hedwigai/model-bench-v2), the four that need no judgement to grade. That dataset has the full answer keys, with the source URLs that confirm each fact, and 195 runs by three models, each graded blind by hand.

`scripts/agreement.py` grades all 60 published runs of these four tasks with the code grader and compares the results with the hand grades. They agree on all 60, including the 8 T10 runs that lost rows.

## Reference runs

`reference_runs/` holds five delivered documents from that benchmark, as written by the models: one full-score run per task, and one T10 run (GLM-5.3-Flash) that named three predecessors. `reference_runs/grades.json` gives the hand grade and the code grade for each.

## Use

```bash
pip install -e .
```

Grade an answer from the command line:

```bash
python -m workbook_tasks.grade T06 answer.md
```

The package is a taskset for the verifiers v1 API (`verifiers>=0.4.1`, Python 3.11 or later). verifiers finds it by the package name, `workbook-tasks`. Check the tasks and their scoring without calling a model:

```bash
vf-validate workbook-tasks --runtime.type subprocess
```

Run the four tasks against a model behind any OpenAI-compatible endpoint:

```bash
export OPENAI_API_KEY=...
vf-run workbook-tasks -m <model> \
  --client.base-url https://api.openai.com/v1 --client.api-key-var OPENAI_API_KEY \
  --env.agent.runtime.type subprocess -n 4 -r 1
```

Without `--client.*`, `vf-run` uses Prime Intellect's inference endpoint and `PRIME_API_KEY`. Without `--env.agent.runtime.type subprocess`, the agent runs in a Prime sandbox. Traces and rewards are written under `outputs/`.

Or load the environment in Python:

```python
import verifiers.v1 as vf

env = vf.load_environment(vf.resolve_env_config({"taskset": {"id": "workbook-tasks"}}))
tasks = list(env.taskset)  # 4 tasks: T04, T06, T08, T10
```

The agent uses the `null` harness by default: a plain tool-calling chat loop with no shell. Its one tool is `fetch`, which reads a public address and returns its text. The tool runs on the machine that runs the evaluation. Each run stops after 30 model turns; change this with `--env.agent.max-turns`. Pick some of the tasks with `--env.taskset.task-ids '["T06", "T10"]'`. The reward, `rows_correct`, is the grade of the model's last reply.

SEC EDGAR asks automated clients to identify themselves; set `WORKBOOK_TASKS_USER_AGENT` to a name and contact address of your own before running against it.

## Tests

```bash
pip install -e ".[test]"
pytest
```

The tests check that the grader gives each reference run its recorded grade, and that every trap named in the keys loses the row it should.

## Limits

- The keys are fixed as of 12 November 2026. A CEO can change after that, and the key will not follow.
- The fetch tool reads pages; it does not search. Models must know or work out where a fact is published.
- Four tasks are a sample, not a benchmark. More are in the dataset, but they need a judge.

## Licence

Code: MIT. Task text and keys: CC BY 4.0, from hedwigai/model-bench-v2.

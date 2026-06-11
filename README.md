# cert-tutor

Offline CLI study tool for the **Claude Certified Architect — Foundations (CCA-F)** exam. Drills you on a 211-question
bank, tracks weak domains, and runs a timed mock exam.

Question bank lives in `claude_certified_architect_question_bank.json` and covers all five exam domains:

| Domain                                 | `--domain` name | Weight | Questions |
|----------------------------------------|-----------------|--------|-----------|
| Agentic Architecture & Orchestration   | `Agentic`       | 27%    | 58        |
| Tool Design & MCP Integration          | `MCP/Tools`     | 18%    | 35        |
| Claude Code Configuration & Workflows  | `Claude Code`   | 20%    | 42        |
| Prompt Engineering & Structured Output | `Prompting`     | 20%    | 42        |
| Context Management & Reliability       | `Context`       | 15%    | 34        |

`study --domain` accepts the short name, the full name, or any unambiguous substring (case-insensitive).

The bank combines 27 questions from the official exam guide and community sources (`official-*`, `community-*`) with 184 generated questions (`gen-*`).

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
git clone <repo>
cd cert-tutor
uv sync
```

No API keys, no network calls — everything runs from the local question bank.

## Usage

```bash
# Adaptive study session — pulls from the bank and revisits missed questions
uv run -m tutor study

# Drill a single domain (see the table above for valid names)
uv run -m tutor study --domain MCP/Tools

# Timed 60-question mock exam (120 minutes, pass at 70%)
uv run -m tutor exam

# Performance breakdown
uv run -m tutor stats
```

## Commands

**study** — Picks unasked questions from the bank, weighted toward your weak domains. Missed questions go into a retry
queue and resurface after a 5-question cooldown. The header shows a running pass-probability estimate based on
per-domain accuracy. Type `Q` at any answer prompt to save and quit. Pass `--domain NAME` to restrict the session to
a single domain (e.g. `study --domain MCP/Tools`); see the domain table above for valid names.

**exam** — Simulates the real exam: 60 questions sampled by domain weight, 120-minute timer, no explanations until the
end. `S` skips a question (returned to at the end), `Q` finishes early. Final screen shows pass/fail, per-domain
breakdown, and a review of every missed question.

**stats** — Overall score, per-domain and per-topic accuracy, weak-concept table, retry-queue size, and recent session
history.

**refs** — Prints the configured reference URLs (exam guide, partner-network learning path). Same links also surface
under each missed-question explanation in `study`. Configure them in `config.yaml` under `references:`.

**reset** — Erases all study history. `study --reset` does the same and then immediately starts a fresh session.

## Configuration

`config.yaml`:

```yaml
session:
  data_dir: "data"
  history_file: "data/session.json"

tutor:
  weak_spot_threshold: 0.5  # topics below this rate count as weak
  recent_n: 30              # only the last N answers count toward weak-spot detection

references:
  exam_guide: "EXAM_GUIDE.pdf"   # bundled in the repo (publicly available on Anthropic's CCA page)
  action: "https://drive.google.com/..."   # Partner Network: Claude Code
  api:    "https://drive.google.com/..."   # Partner Network: Claude API
  mcp:    "https://drive.google.com/..."   # Partner Network: MCP
  skills: "https://drive.google.com/..."   # Partner Network: Skills
```

Session state (history, retry queue, run log) persists in `data/session.json`.

`EXAM_GUIDE.pdf` ships with the repo. The four Partner Network category links are intentionally external — those
materials aren't redistributed here. Each missed question only surfaces the categories relevant to its domain (e.g.
an MCP question shows the `mcp` and `api` links plus the exam guide), keeping the panel small. Run `tutor refs` to
see the full list.

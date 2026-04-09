# cert-tutor

Interactive CLI study tutor for technical certifications. Uses OpenAI + RAG over your PDFs to generate exam-style questions, track weak spots, and explain answers.

Includes 350 pre-built questions for the Google Cloud Professional Cloud Architect exam, weighted to match the official exam guide.

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- An OpenAI API key

## Setup

```bash
git clone <repo>
cd cert-tutor
uv sync

# Add your API key
cp .env.example .env
# Edit .env with your actual key
source .env
```

## Usage

```bash
# Download study resources for an exam
uv run -m tutor fetch architect

# Index all docs (PDFs and fetched text files)
uv run -m tutor ingest

# Start studying (adaptive, targets your weak spots)
uv run -m tutor study

# Take a timed 60-question mock exam
uv run -m tutor exam

# Check your performance breakdown
uv run -m tutor stats
```

## Commands

**fetch** — Downloads official study resources for a certification exam. Currently supports `architect` (Google Cloud Professional Cloud Architect). Fetches Well-Architected Framework pages, Architecture Center guides, and product best practices.

**ingest** — Parses PDFs and text files from `docs/`, chunks the text, generates embeddings, and stores them in a local ChromaDB vector store. Use `--reset` to clear and re-index everything.

**study** — Adaptive study mode. Generates exam-style questions from your indexed docs and 350 seed questions. Tracks your performance by exam section. Aggressively retargets your weak domains and missed questions. Type your reasoning before answering to get personalized feedback. Use `/case` to view case study context.

**exam** — Simulates the real exam: 60 questions, 120-minute countdown timer, 2 case studies with 7-8 questions each. Skip questions with S and review them at the end. No explanations until you finish. Pass/fail at 70% with per-section breakdown.

**stats** — Shows overall score, per-section and per-topic breakdown, weak products, and recent session history.

## Configuration

Edit `config.yaml` to change models, chunk sizes, or the weak spot threshold:

```yaml
openai:
  generation_model: "gpt-5.4"
  explanation_model: "gpt-5.4-mini"
  embed_model: "text-embedding-3-small"

rag:
  chunk_size: 800
  chunk_overlap: 100
  top_k: 4

tutor:
  weak_spot_threshold: 0.5
```

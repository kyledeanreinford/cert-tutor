# Claude Certified Architect – Foundations (CCA-F) Study Guide

A study plan and resource guide for the Anthropic Claude Certified Architect – Foundations certification exam. Built to accompany the `cert-tutor` question bank.

## Exam at a Glance

| Detail | Info |
|---|---|
| **Questions** | 60 multiple-choice (single correct answer) |
| **Time** | 120 minutes |
| **Passing score** | 720 / 1,000 |
| **Format** | Scenario-based; 4 of 6 scenarios randomly selected per sitting |
| **Proctored** | Yes — closed book, no AI assistance, no external tools |
| **Cost** | Free for first 5,000 partner employees, then $99/attempt |
| **Prerequisites** | 6+ months hands-on with Claude API, Agent SDK, Claude Code, and MCP |
| **Registration** | [Anthropic Academy on Skilljar](https://anthropic.skilljar.com/claude-certified-architect-foundations-access-request) |

## Domains & Weights

```
██████████████████████████████  D1  Agentic Architecture & Orchestration   27%
████████████████████████        D3  Claude Code Configuration & Workflows  20%
████████████████████████        D4  Prompt Engineering & Structured Output 20%
██████████████████████          D2  Tool Design & MCP Integration          18%
██████████████████              D5  Context Management & Reliability       15%
```

Over half the exam (47%) is concentrated in agentic architecture and Claude Code. This is a systems design exam, not a prompting fundamentals test.

## The 6 Exam Scenarios

Each exam sitting randomly selects 4. Study all 6.

1. **Customer Support Resolution Agent** — Agent SDK + MCP tools (get_customer, lookup_order, process_refund, escalate_to_human). 80%+ first-contact resolution target. *Domains: D1, D2, D5*

2. **Code Generation with Claude Code** — Code generation, refactoring, debugging, documentation. Custom commands, CLAUDE.md, plan mode decisions. *Domains: D3, D5*

3. **Multi-Agent Research System** — Coordinator delegates to web search, document analysis, synthesis, and report subagents. Produces comprehensive cited reports. *Domains: D1, D2, D5*

4. **Developer Productivity with Claude** — Codebase exploration, legacy systems, boilerplate generation. Built-in tools + MCP servers. *Domains: D2, D3, D1*

5. **Claude Code for CI/CD** — Automated code reviews, test generation, PR feedback in pipelines. Actionable prompts, minimizing false positives. *Domains: D3, D4*

6. **Structured Data Extraction** — Extracting structured info from unstructured docs, JSON schema validation, edge case handling, downstream integration. *Domains: D4, D5*

## 6-Week Study Plan

### Week 1–2: Foundations

**Goal:** Build baseline knowledge across all Claude technologies.

**Courses (free on Anthropic Academy):**
- Claude 101
- AI Fluency
- Building with the Claude API (8.1 hours — the core material)

**Study focus:**
- Claude API basics: messages, tool_use, stop_reason, system prompts
- Understand the agentic loop lifecycle: send request → check stop_reason → execute tool → return result → repeat
- Key mental model: `stop_reason == "tool_use"` means keep looping; `stop_reason == "end_turn"` means done

**Hands-on:** Build a simple single-agent tool-calling loop from scratch. Get comfortable with the request/response cycle before adding complexity.

**Anti-patterns to memorize early:**
- Never parse natural language to detect loop completion
- Never check content type to determine if the agent is done
- Never set arbitrary iteration caps as the primary stopping mechanism

### Week 3: Tool Design & MCP (Domain 2)

**Courses:**
- Introduction to Model Context Protocol
- MCP Advanced

**Study focus:**
- Tool descriptions are the #1 lever for tool selection. Minimal descriptions → misrouting
- Descriptions should include: input formats, example queries, edge cases, boundaries vs similar tools
- Structured error responses: `isError`, `errorCategory` (transient/validation/permission), `isRetryable`
- Tool distribution: 4–5 tools per agent max. Beyond that, distribute across subagents
- `tool_choice` options: `"auto"`, `"any"`, forced `{"type": "tool", "name": "..."}`
- MCP server scoping: `.mcp.json` (project, shared) vs `~/.claude.json` (personal)
- Environment variable expansion: `${API_KEY}` in `.mcp.json` — never hardcode secrets
- Built-in tools: Read, Write, Edit, Bash, Grep, Glob — know when to use each

**Key decision framework:**
- Grep = search file *contents* (function names, error messages)
- Glob = search file *paths* (find files by name/extension)
- Edit = targeted modification (preserves unchanged content)
- Write = full file replacement (anything not included is lost)
- Read = load full file contents
- Bash = last resort when no dedicated tool exists

### Week 4: Claude Code (Domain 3)

**Courses:**
- Claude Code in Action

**Study focus:**
- CLAUDE.md hierarchy: `~/.claude/CLAUDE.md` (user) → `.claude/CLAUDE.md` (project) → subdirectory CLAUDE.md files
- User-level config is NOT shared via version control — this is a common exam trap
- `.claude/rules/` with YAML frontmatter glob patterns for path-specific conventions
- `.claude/commands/` (project-scoped, version-controlled) vs `~/.claude/commands/` (personal)
- `.claude/skills/` with SKILL.md frontmatter: `context: fork`, `allowed-tools`, `argument-hint`
- `context: fork` = isolated sub-agent context, prevents verbose output from polluting main session
- Plan mode vs direct execution: plan for complex/architectural tasks, direct for simple/well-scoped changes
- CI/CD: `-p` flag for non-interactive mode, `--output-format json`, `--json-schema`
- Session management: `--resume <name>`, `fork_session`, `/compact`, `/memory`

**Critical exam knowledge:**
- Team standards in `~/.claude/CLAUDE.md` → new team members won't have them (use project-level instead)
- Glob patterns in `.claude/rules/` handle files spread across directories (test files, etc.)
- Skills with `context: fork` are for verbose/exploratory work; commands run in main session
- `-p` is the answer for any "CI pipeline hangs" question

### Week 5: Prompt Engineering & Structured Output (Domain 4)

**Courses:**
- Prompt Engineering best practices (Anthropic docs)
- Review the Anthropic cookbook examples

**Study focus:**
- Explicit criteria > vague instructions ("flag when claimed behavior contradicts code" vs "check comments are accurate")
- Few-shot examples: 2–4 targeted examples for ambiguous scenarios showing reasoning
- `tool_use` + JSON Schema + `tool_choice` = guaranteed structural compliance
- But: structural compliance ≠ semantic correctness. Schema-valid output can still have wrong values
- Nullable/optional fields prevent hallucination when source docs lack information
- Enum with `"other"` + detail field for unknown categories
- Validation-retry loops: append *specific* errors (which field, what's wrong, expected vs actual). Generic "try again" doesn't work
- Message Batches API: 50% cost savings, up to 24-hour window, no multi-turn tool calling
- Batch = latency-tolerant only (nightly audits, weekly reports). Never for blocking workflows (pre-merge checks)
- Multi-pass review: per-file analysis + separate cross-file integration pass
- Independent review sessions: separate instance catches more than self-review in same session

**The batch API decision rule:** If a developer is waiting for it, use synchronous. If it runs overnight, use batch.

### Week 6: Context Management, Reliability & Final Prep (Domain 5)

**Study focus:**
- Immutable "case facts" block at top of context — extract IDs, amounts, dates outside of summarization
- Progressive summarization loses critical numerical values — this is a key exam concept
- "Lost in the middle" effect: place key findings at beginning and end, not buried in middle
- Trim verbose tool outputs to relevant fields before they accumulate
- Subagent context is isolated: coordinator must explicitly pass everything a subagent needs
- Structured error propagation: failure type + attempted actions + partial results + alternatives
- Escalation triggers: customer requests human, policy gap, capability limit. NOT sentiment, NOT self-assessed confidence
- Information provenance: claim-source mappings that survive synthesis. Without them, attribution is lost forever
- Stratified metrics: aggregate accuracy can mask per-document-type failures (96% overall but 72% on invoices)

**Final prep activities:**
1. Work through all 12 sample questions in the official exam guide — read wrong answer explanations carefully
2. Complete the 15-question community practice bank
3. Take the official 60-question practice exam (available through Skilljar after registration)
4. Aim for 900+ on the practice exam before scheduling the real thing
5. Review the anti-patterns list below — knowing what NOT to do is half the exam

## Key Anti-Patterns to Memorize

These are the most common wrong-answer traps on the exam. The distractors are designed to be things engineers actually reach for.

| Anti-Pattern | Why It's Wrong | Correct Approach |
|---|---|---|
| Prompt-based enforcement for critical business logic | Probabilistic compliance; non-zero failure rate | Programmatic hooks (PreToolUse/PostToolUse) |
| Minimal tool descriptions | Model can't differentiate similar tools | Detailed descriptions with formats, examples, boundaries |
| Confidence-based escalation | LLM self-assessed confidence is poorly calibrated | Explicit criteria with few-shot examples |
| Sentiment-based escalation | Frustrated ≠ complex; calm ≠ simple | Rule-based: customer requests human, policy gap, capability limit |
| User-level config for team standards | Not shared via version control | Project-level `.claude/CLAUDE.md` or `.claude/rules/` |
| Generic error messages ("Operation failed") | Agent can't decide whether to retry or escalate | Structured: `isError`, `errorCategory`, `isRetryable` |
| Generic retry messages ("Try again") | Model doesn't know what to fix | Specific: which field, what's wrong, expected vs actual |
| >5 tools per agent | Tool selection degrades | Distribute across specialized subagents |
| Larger context window to fix attention | Context size ≠ attention quality | Multi-pass review (per-file + integration) |
| Batch API for blocking workflows | Up to 24-hour SLA, no latency guarantee | Synchronous for blocking; batch for overnight/weekly |
| Progressive summarization of critical values | Loses exact IDs, amounts, dates | Immutable "case facts" block outside summarization |
| Self-review in same session | Retains generation reasoning, confirmation bias | Independent review instance without prior context |
| Assuming subagents inherit context | Subagents start with only what you pass them | Explicit context passing in subagent prompt |
| Required fields when data may be absent | Forces model to hallucinate values | Nullable/optional fields in schema |
| Aggregate-only accuracy metrics | Masks per-segment failures | Stratified metrics by document type and field |

## Official Resources

**Free Anthropic Academy courses (13 total):**
- [Anthropic Academy on Skilljar](https://anthropic.skilljar.com) — all free, no paywall

**Official documentation:**
- [Claude API docs](https://docs.anthropic.com)
- [Model Context Protocol spec](https://modelcontextprotocol.io)
- [Claude Code documentation](https://docs.anthropic.com/en/docs/claude-code)
- [Anthropic Cookbook](https://github.com/anthropics/anthropic-cookbook)

**Exam-specific:**
- [Official Exam Guide PDF](https://everpath-course-content.s3-accelerate.amazonaws.com/instructor%2F8lsy243ftffjjy1cx9lm3o2bw%2Fpublic%2F1773274827%2FClaude+Certified+Architect+%E2%80%93+Foundations+Certification+Exam+Guide.pdf) — the single most important document
- [Claude Partner Network](https://claude.com/partners) — required for exam access (free to join)
- [Register for exam](https://anthropic.skilljar.com/claude-certified-architect-foundations-access-request)

**Community resources:**
- [claudecertifiedarchitect.net](https://claudecertifiedarchitect.net) — 12 official sample questions + 15 practice questions with explanations
- [paullarionov/claude-certified-architect](https://github.com/paullarionov/claude-certified-architect) — study guide with scenarios and exercises (178 stars)
- [Rick Hightower's 8-part series](https://pub.towardsai.net/claude-certified-architect-the-complete-guide-to-passing-the-cca-foundations-exam-9665ce7342a8) on Towards AI

## Out of Scope

Don't waste time studying these — they will NOT appear on the exam:

- Fine-tuning or training models
- API authentication, billing, account management
- Deploying/hosting MCP servers (infrastructure, networking)
- Claude's internal architecture, training process, model weights
- Constitutional AI, RLHF, safety training
- Embedding models or vector databases
- Computer use (browser automation)
- Vision/image analysis
- Streaming API / SSE
- Rate limiting, quotas, pricing calculations
- OAuth, API key rotation
- Cloud provider configs (AWS, GCP, Azure)
- Performance benchmarking, model comparisons
- Prompt caching implementation details
- Token counting algorithms

## Exam Day Tips

1. **Root cause over symptom.** Every question presents a production problem. Find the root cause before evaluating answers. Distractors often fix symptoms.

2. **Programmatic over probabilistic.** When financial or safety consequences exist, the answer is almost always programmatic enforcement (hooks, prerequisites), not prompt instructions.

3. **Proportionate first step.** Some questions ask for the "most effective first step." Don't pick the most comprehensive solution — pick the highest-leverage lowest-effort fix. Improving tool descriptions before building a routing classifier.

4. **Read the wrong answers.** Distractors are plausible anti-patterns. Understanding *why* each wrong answer is wrong teaches you more than knowing the right answer.

5. **Don't leave blanks.** No penalty for guessing. Unanswered = wrong.

6. **Time management.** 60 questions in 120 minutes = 2 minutes per question. Flag hard ones and come back.

7. **Scenario context matters.** The scenario description frames what tools and constraints exist. Re-read it if you're unsure about an answer.
import math
import random
import re
import sys
from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from tutor.seed_questions import get_unasked_seed, load_seed_questions
from tutor.session import Session

console = Console()

DOMAIN_WEIGHTS = {
    "Agentic Architecture & Orchestration": 0.27,
    "Tool Design & MCP Integration": 0.18,
    "Claude Code Configuration & Workflows": 0.20,
    "Prompt Engineering & Structured Output": 0.20,
    "Context Management & Reliability": 0.15,
}

PASS_THRESHOLD = 0.72
_PRIOR = 0.50
_DOMAIN_MIN = 5
_GLOBAL_MIN = 20

DOMAIN_SHORT = {
    "Agentic Architecture & Orchestration": "Agentic",
    "Tool Design & MCP Integration": "MCP/Tools",
    "Claude Code Configuration & Workflows": "Claude Code",
    "Prompt Engineering & Structured Output": "Prompting",
    "Context Management & Reliability": "Context",
}


REPO_ROOT = Path(__file__).parent.parent


def resolve_domain(value: str) -> str | None:
    """Map a user-supplied domain name (short or full, case-insensitive) to a
    canonical full domain name. Returns None if it matches nothing."""
    value = value.strip().lower()
    for full, short in DOMAIN_SHORT.items():
        if value in (full.lower(), short.lower()):
            return full
    # Loose fallback: unique substring match against full names.
    matches = [full for full in DOMAIN_WEIGHTS if value in full.lower()]
    return matches[0] if len(matches) == 1 else None


def load_config() -> dict:
    config_path = REPO_ROOT / "config.yaml"
    if not config_path.exists():
        console.print(f"[red]config.yaml not found at {config_path}.[/red]")
        sys.exit(1)
    config = yaml.safe_load(config_path.read_text())

    # Anchor storage paths to the repo root so the tool works from any cwd.
    history_file = Path(config["session"]["history_file"])
    if not history_file.is_absolute():
        config["session"]["history_file"] = str(REPO_ROOT / history_file)
    return config


def _rate_color(rate: float) -> str:
    if rate >= 70:
        return "green"
    if rate >= 50:
        return "yellow"
    return "red"


def _pass_probability(session: Session) -> float | None:
    if session.total_questions < 5:
        return None

    weighted_acc = 0.0
    for domain, weight in DOMAIN_WEIGHTS.items():
        d = session.domains.get(domain, {})
        n = d.get("asked", 0)
        if n > 0:
            raw = d["correct"] / n
            confidence = min(n / _DOMAIN_MIN, 1.0)
            blended = confidence * raw + (1 - confidence) * _PRIOR
        else:
            blended = _PRIOR
        weighted_acc += weight * blended

    if session.total_questions < _GLOBAL_MIN:
        alpha = session.total_questions / _GLOBAL_MIN
        weighted_acc = alpha * weighted_acc + (1 - alpha) * _PRIOR

    return 1.0 / (1.0 + math.exp(-12.0 * (weighted_acc - PASS_THRESHOLD)))


def build_header(session: Session) -> Panel:
    stats = session.summary()
    rate = stats["rate"]
    color = _rate_color(rate)

    prob = _pass_probability(session)
    if prob is None:
        pass_label = "[dim]~?% pass[/dim]"
    else:
        pct = int(prob * 100)
        pc = "green" if pct >= 60 else "yellow" if pct >= 35 else "red"
        pass_label = f"[{pc}]~{pct}% pass[/{pc}]"

    parts = [
        pass_label,
        f"[{color}]{stats['total_correct']}/{stats['total_questions']} ({rate:.0f}%)[/{color}]",
    ]

    for domain, data in sorted(stats["domains"].items()):
        domain_rate = (data["correct"] / data["asked"] * 100) if data["asked"] > 0 else 0
        dc = _rate_color(domain_rate)
        short = DOMAIN_SHORT.get(domain, domain)
        parts.append(f"{short}: [{dc}]{data['correct']}/{data['asked']}[/{dc}]")

    return Panel(" | ".join(parts), title="cert-tutor", border_style="green")


def display_question(data: dict) -> None:
    domain = data.get("domain", "")
    topic = data.get("topic", "")
    title = f"{domain} / {topic}" if domain and topic else domain or topic

    question_text = f"[bold]{data['question']}[/bold]\n"
    for letter, choice in data["choices"].items():
        question_text += f"\n  [cyan]{letter}[/cyan]) {choice}"
    console.print(Panel(question_text, title=title, border_style="blue"))


def display_answers_with_result(data: dict, user_answer: str, correct: str) -> None:
    lines = []
    for letter, choice in data["choices"].items():
        if letter == correct and letter == user_answer:
            lines.append(f"  [green]+  {letter}) {choice}[/green]")
        elif letter == correct:
            lines.append(f"  [yellow]+  {letter}) {choice}[/yellow]")
        elif letter == user_answer:
            lines.append(f"  [red]x  {letter}) {choice}[/red]")
        else:
            lines.append(f"  [dim]   {letter}) {choice}[/dim]")

    is_correct = user_answer == correct
    title = "[green]Correct[/green]" if is_correct else "[red]Incorrect[/red]"
    border = "green" if is_correct else "red"
    console.print(Panel("\n\n".join(lines), title=title, border_style=border))


def _prompt_input(prompt_text: str) -> str:
    from prompt_toolkit import prompt as pt_prompt
    return pt_prompt(prompt_text)


def get_answer() -> str:
    while True:
        answer = _prompt_input("Answer (A/B/C/D/Q): ").strip().upper()
        if answer in ("A", "B", "C", "D", "Q"):
            return answer
        console.print("[yellow]Enter A, B, C, D, or Q.[/yellow]")


def show_stats(session: Session, threshold: float, recent_n: int = 0) -> None:
    stats = session.summary()
    rate = stats["rate"]
    color = "green" if rate >= 70 else "yellow" if rate >= 50 else "red"
    console.print(Panel(
        f"[bold]Overall: {stats['total_correct']}/{stats['total_questions']} "
        f"([{color}]{rate:.1f}%[/{color}])[/bold]",
        title="Performance Summary",
    ))

    if stats["domains"]:
        domain_table = Table(title="Domains")
        domain_table.add_column("Domain", style="bold")
        domain_table.add_column("Asked", justify="right")
        domain_table.add_column("Correct", justify="right")
        domain_table.add_column("Rate", justify="right")

        for domain, data in sorted(stats["domains"].items()):
            domain_rate = (data["correct"] / data["asked"] * 100) if data["asked"] > 0 else 0
            dc = _rate_color(domain_rate)
            domain_table.add_row(
                domain,
                str(data["asked"]),
                str(data["correct"]),
                f"[{dc}]{domain_rate:.0f}%[/{dc}]",
            )
        console.print(domain_table)

    if stats["topics"]:
        topic_table = Table(title="Topics")
        topic_table.add_column("Topic", style="bold")
        topic_table.add_column("Asked", justify="right")
        topic_table.add_column("Correct", justify="right")
        topic_table.add_column("Rate", justify="right")

        for topic, data in sorted(stats["topics"].items()):
            topic_rate = (data["correct"] / data["asked"] * 100) if data["asked"] > 0 else 0
            tc = _rate_color(topic_rate)
            topic_table.add_row(
                topic,
                str(data["asked"]),
                str(data["correct"]),
                f"[{tc}]{topic_rate:.0f}%[/{tc}]",
            )
        console.print(topic_table)

    retry_count = session.retry_queue_size()
    if retry_count > 0:
        console.print(f"\n[yellow]Retry queue:[/yellow] {retry_count} missed questions waiting")

    if session.session_runs:
        run_table = Table(title="Recent Sessions")
        run_table.add_column("Date", style="bold")
        run_table.add_column("Score", justify="right")
        run_table.add_column("Rate", justify="right")

        for run in session.session_runs[-5:]:
            started = run["started"][:10]
            run_rate = (run["questions_correct"] / run["questions_asked"] * 100) if run["questions_asked"] > 0 else 0
            run_color = "green" if run_rate >= 70 else "yellow" if run_rate >= 50 else "red"
            run_table.add_row(
                started,
                f"{run['questions_correct']}/{run['questions_asked']}",
                f"[{run_color}]{run_rate:.0f}%[/{run_color}]",
            )
        console.print(run_table)

    if session.exam_runs:
        exam_table = Table(title="Recent Exams")
        exam_table.add_column("Date", style="bold")
        exam_table.add_column("Score", justify="right")
        exam_table.add_column("Rate", justify="right")

        for run in session.exam_runs[-5:]:
            ended = run["ended"][:10]
            exam_rate = (run["score"] / run["total"] * 100) if run["total"] > 0 else 0
            exam_color = "green" if exam_rate >= 70 else "yellow" if exam_rate >= 50 else "red"
            exam_table.add_row(
                ended,
                f"{run['score']}/{run['total']}",
                f"[{exam_color}]{exam_rate:.0f}%[/{exam_color}]",
            )
        console.print(exam_table)


def cmd_study(config: dict, only_domain: str | None = None) -> None:
    threshold = config["tutor"]["weak_spot_threshold"]
    recent_n = config["tutor"].get("recent_n", 0)

    session = Session.load(Path(config["session"]["history_file"]))

    has_seeds = get_unasked_seed(session.asked_seed_ids, only_domain=only_domain) is not None
    has_retries = session.eligible_retry_count(only_domain=only_domain) > 0 or (
        only_domain is None and session.retry_queue_size() > 0
    )
    if not has_seeds and not has_retries:
        if only_domain:
            console.print(
                f"[yellow]No more questions left in '{DOMAIN_SHORT.get(only_domain, only_domain)}'. "
                "Try another domain or run plain [bold]study[/bold].[/yellow]"
            )
        else:
            console.print("[red]No questions available. Add questions to claude_certified_architect_question_bank.json.[/red]")
        sys.exit(1)

    session.start_run()
    console.clear()
    if only_domain:
        console.print(Panel(
            f"[bold]Focused study:[/bold] {only_domain}",
            border_style="magenta",
        ))
    console.print(build_header(session))

    while True:
        question_data = None
        is_seed = False
        is_retry = False

        weak_domains = set(session.weak_domains(threshold, recent_n))

        if session.eligible_retry_count(only_domain=only_domain) > 0 and random.random() < 0.4:
            question_data = session.get_retry_question(weak_domains, only_domain=only_domain)
            is_retry = True

        if not question_data:
            seed = get_unasked_seed(session.asked_seed_ids, weak_domains, only_domain=only_domain)
            if seed:
                question_data = seed
                is_seed = True

        if not question_data:
            seed = get_unasked_seed(session.asked_seed_ids, only_domain=only_domain)
            if seed:
                question_data = seed
                is_seed = True

        if not question_data:
            if only_domain:
                console.print(f"[yellow]All '{DOMAIN_SHORT.get(only_domain, only_domain)}' questions answered![/yellow]")
            else:
                console.print("[yellow]All questions answered! Add more questions to the bank.[/yellow]")
            session.end_run()
            session.save()
            break

        console.print()
        if is_retry:
            console.print("[dim](retry)[/dim]")
        display_question(question_data)

        correct = question_data["correct"]
        answer = get_answer()

        if answer == "Q":
            session.end_run()
            session.save()
            console.print("\n[bold]Session saved.[/bold]")
            break

        is_correct = answer == correct

        if is_seed:
            session.asked_seed_ids.append(question_data["id"])

        if not is_correct:
            session.add_to_retry_queue(question_data)

        explanation = question_data.get("explanation", "")

        session.record(
            question=question_data["question"],
            choices=question_data["choices"],
            user_answer=answer,
            correct_answer=correct,
            domain=question_data.get("domain", ""),
            topic=question_data.get("topic", ""),
            explanation=explanation,
        )

        session.save()

        console.clear()
        console.print(build_header(session))
        console.print()
        display_answers_with_result(question_data, answer, correct)

        if explanation:
            spaced = re.sub(
                r'\.\s+(?=Option [A-E]\b|The correct answer is [A-E]\b|Correct answer [A-E]\b)',
                '.\n\n',
                explanation.strip(),
            )
            spaced = re.sub(r'\n([A-E]\))', r'\n\n\1', spaced)
            console.print(Panel(spaced, title="Explanation", border_style="dim"))

        if not is_correct:
            ref_lines = _format_references(config, domain=question_data.get("domain"))
            if ref_lines:
                console.print(Panel(ref_lines, title="Further reading", border_style="dim"))

        console.print()


def cmd_exam(config: dict) -> None:
    import threading
    import time

    session = Session.load(Path(config["session"]["history_file"]))
    seed_qs = load_seed_questions()
    available = [q for q in seed_qs if q.get("correct")]

    if len(available) < 60:
        console.print(f"[red]Need at least 60 questions for a mock exam (have {len(available)}).[/red]")
        sys.exit(1)

    exam_size = 60
    time_limit = 120 * 60

    exam_questions: list[dict] = []
    used_ids: set[str] = set()

    for domain, weight in DOMAIN_WEIGHTS.items():
        target = round(exam_size * weight)
        domain_qs = [q for q in available if q.get("domain") == domain and q["id"] not in used_ids]
        random.shuffle(domain_qs)
        picked = domain_qs[:target]
        exam_questions.extend(picked)
        used_ids.update(q["id"] for q in picked)

    while len(exam_questions) < exam_size:
        leftover = [q for q in available if q["id"] not in used_ids]
        if not leftover:
            break
        pick = random.choice(leftover)
        exam_questions.append(pick)
        used_ids.add(pick["id"])

    random.shuffle(exam_questions)

    console.clear()
    console.print(Panel(
        f"[bold]Mock Exam: {len(exam_questions)} questions, {time_limit // 60} minutes[/bold]\n\n"
        "No explanations until the end. Type Q to finish early.",
        title="cert-tutor exam",
        border_style="yellow",
    ))
    console.input("[dim]Press enter to start...[/dim]")

    start_time = time.time()
    timer_stop = False

    def _run_timer(question_num: int, total: int) -> None:
        import sys as _sys
        while not timer_stop:
            elapsed = time.time() - start_time
            remaining = max(0, time_limit - elapsed)
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            color_code = "32" if mins > 30 else "33" if mins > 10 else "31"
            line = f" Question {question_num}/{total}  |  \033[{color_code};1m{mins}:{secs:02d} remaining\033[0m"
            _sys.stdout.write(f"\033[s\033[1;1H\033[2K{line}\033[u")
            _sys.stdout.flush()
            time.sleep(1)

    exam_answers: list[str | None] = [None] * len(exam_questions)

    def _ask_exam_question(idx: int) -> str | None:
        nonlocal timer_stop
        question_data = exam_questions[idx]

        if time.time() - start_time >= time_limit:
            return None

        console.clear()
        console.print()
        console.print()
        display_question(question_data)

        timer_stop = False
        timer_thread = threading.Thread(
            target=_run_timer, args=(idx + 1, len(exam_questions)), daemon=True
        )
        timer_thread.start()

        answer = None
        while True:
            raw = _prompt_input("Answer (A/B/C/D/S/Q): ").strip().upper()
            if raw in ("A", "B", "C", "D", "S", "Q"):
                answer = raw
                break
            console.print("[yellow]Enter A, B, C, D, S to skip, or Q to finish.[/yellow]")

        timer_stop = True
        timer_thread.join(timeout=2)
        return answer

    quit_exam = False
    for i in range(len(exam_questions)):
        result = _ask_exam_question(i)
        if result is None or result == "Q":
            quit_exam = (result == "Q")
            break
        if result != "S":
            exam_answers[i] = result

    skipped = [i for i, a in enumerate(exam_answers) if a is None]
    if skipped and not quit_exam and (time.time() - start_time) < time_limit:
        timer_stop = True
        console.clear()
        console.print(Panel(
            f"[bold]{len(skipped)} skipped questions remaining.[/bold]\n"
            "You'll now review them. S to skip again, Q to finish.",
            border_style="yellow",
        ))
        _prompt_input("Press enter to continue...")

        for i in skipped:
            if time.time() - start_time >= time_limit:
                console.print("\n[red bold]Time's up![/red bold]")
                break
            result = _ask_exam_question(i)
            if result is None or result == "Q":
                break
            if result != "S":
                exam_answers[i] = result

    timer_stop = True
    elapsed = time.time() - start_time

    answers: list[dict] = []
    for i, exam_answer in enumerate(exam_answers):
        if exam_answer is None:
            continue
        q = exam_questions[i]
        correct = q["correct"]
        is_correct = exam_answer == correct
        answers.append({"question_data": q, "answer": exam_answer, "correct": correct, "is_correct": is_correct})

    unanswered = sum(1 for a in exam_answers if a is None)
    correct_count = sum(1 for a in answers if a["is_correct"])
    rate = (correct_count / len(exam_questions) * 100) if len(exam_questions) > 0 else 0

    console.clear()
    color = "green" if rate >= 70 else "yellow" if rate >= 50 else "red"
    passed = rate >= 70
    result_label = "[green bold]PASS[/green bold]" if passed else "[red bold]FAIL[/red bold]"
    unanswered_line = f"\nUnanswered: {unanswered}" if unanswered > 0 else ""

    console.print(Panel(
        f"{result_label}\n\n"
        f"Score: [{color}]{correct_count}/{len(exam_questions)} ({rate:.0f}%)[/{color}]\n"
        f"Answered: {len(answers)}/{len(exam_questions)}{unanswered_line}\n"
        f"Time: {int(elapsed // 60)}:{int(elapsed % 60):02d}\n"
        f"Passing: 70%",
        title="Exam Results",
        border_style="green" if passed else "red",
    ))

    domain_results: dict[str, dict[str, int]] = {}
    for a in answers:
        domain = a["question_data"].get("domain", "")
        if domain not in domain_results:
            domain_results[domain] = {"asked": 0, "correct": 0}
        domain_results[domain]["asked"] += 1
        if a["is_correct"]:
            domain_results[domain]["correct"] += 1

    table = Table(title="Results by Section")
    table.add_column("Section", style="bold")
    table.add_column("Score", justify="right")
    table.add_column("Rate", justify="right")

    for domain, data in sorted(domain_results.items()):
        d_rate = (data["correct"] / data["asked"] * 100) if data["asked"] > 0 else 0
        dc = _rate_color(d_rate)
        short = DOMAIN_SHORT.get(domain, domain)
        table.add_row(short, f"{data['correct']}/{data['asked']}", f"[{dc}]{d_rate:.0f}%[/{dc}]")
    console.print(table)

    console.print("\n[bold]Review missed questions:[/bold]\n")
    for a in answers:
        if a["is_correct"]:
            continue
        q = a["question_data"]
        console.print(f"[dim]{q.get('domain', '')} / {q.get('topic', '')}[/dim]")
        console.print(f"  Q: {q['question'][:150]}...")
        console.print(f"  Your answer: [red]{a['answer']}[/red]  Correct: [green]{a['correct']}[/green]")
        if q.get("explanation"):
            console.print(f"  {q['explanation'][:200]}")
        console.print()

    session.record_exam_run(
        score=correct_count,
        total=len(exam_questions),
        elapsed_seconds=elapsed,
        per_domain=domain_results,
    )
    for a in answers:
        if not a["is_correct"]:
            session.add_to_retry_queue(a["question_data"])
    session.save()


def cmd_stats(config: dict) -> None:
    session = Session.load(Path(config["session"]["history_file"]))
    if session.total_questions == 0:
        console.print("[yellow]No study history yet. Run: uv run -m tutor study[/yellow]")
        return
    show_stats(session, config["tutor"]["weak_spot_threshold"], config["tutor"].get("recent_n", 0))


REFERENCE_LABELS = {
    "exam_guide": "Exam guide",
    "action": "Partner: Claude Code (action)",
    "api": "Partner: Claude API",
    "mcp": "Partner: MCP",
    "skills": "Partner: Skills",
}

DOMAIN_REFS = {
    "Agentic Architecture & Orchestration":  ["api", "action"],
    "Tool Design & MCP Integration":         ["mcp", "api"],
    "Claude Code Configuration & Workflows": ["action", "skills"],
    "Prompt Engineering & Structured Output": ["api"],
    "Context Management & Reliability":      ["api", "action"],
}


def _resolve_ref(value: str) -> str:
    if value.startswith(("http://", "https://", "file://")):
        return value
    p = Path(value)
    if not p.is_absolute():
        p = (Path(__file__).parent.parent / p).resolve()
    return str(p)


def _format_references(config: dict, domain: str | None = None) -> str:
    refs = config.get("references", {}) or {}
    if domain and domain in DOMAIN_REFS:
        keys = ["exam_guide", *DOMAIN_REFS[domain]]
    else:
        keys = list(REFERENCE_LABELS.keys())
    lines = []
    for key in keys:
        url = (refs.get(key) or "").strip()
        if url:
            label = REFERENCE_LABELS.get(key, key)
            lines.append(f"  [bold]{label}:[/bold] {_resolve_ref(url)}")
    return "\n".join(lines)


def cmd_refs(config: dict) -> None:
    body = _format_references(config)
    if not body:
        console.print(
            "[yellow]No reference URLs configured. "
            "Add them under [bold]references:[/bold] in config.yaml.[/yellow]"
        )
        return
    console.print(Panel(body, title="References", border_style="cyan"))


def _reset_session(config: dict) -> None:
    history_file = Path(config["session"]["history_file"])
    if not history_file.exists():
        console.print("[dim]No session to reset.[/dim]")
        return
    confirm = _prompt_input("This will erase all study history. Type 'yes' to confirm: ").strip().lower()
    if confirm != "yes":
        console.print("[yellow]Reset cancelled.[/yellow]")
        sys.exit(0)
    history_file.unlink()
    console.print("[green]Session cleared.[/green]")


def main(args: list[str]) -> None:
    config = load_config()

    if not args:
        console.print("[bold]Usage:[/bold] uv run -m tutor [study|exam|stats|refs|reset] [--reset] [--domain NAME]")
        console.print("  study                    Start a study session ([dim]--reset[/dim] clears history first)")
        console.print("  study --domain MCP/Tools  Drill a single domain (short or full name)")
        console.print("  exam                     Take a timed 60-question mock exam")
        console.print("  stats                    Show performance summary")
        console.print("  refs                     Show reference links (exam guide, learning path)")
        console.print("  reset                    Erase all study history")
        console.print(f"\n  [dim]Domains: {', '.join(DOMAIN_SHORT.values())}[/dim]")
        sys.exit(0)

    command = args[0]
    rest = args[1:]

    # Parse --domain (accepts "--domain NAME" or "--domain=NAME").
    only_domain: str | None = None
    domain_raw: str | None = None
    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg == "--domain":
            domain_raw = rest[i + 1] if i + 1 < len(rest) else ""
            i += 2
            continue
        if arg.startswith("--domain="):
            domain_raw = arg.split("=", 1)[1]
        i += 1
    if domain_raw is not None:
        only_domain = resolve_domain(domain_raw)
        if only_domain is None:
            console.print(f"[red]Unknown domain: '{domain_raw}'[/red]")
            console.print(f"[dim]Choose one of: {', '.join(DOMAIN_SHORT.values())}[/dim]")
            sys.exit(1)

    flags = set(rest)

    if command == "study":
        if "--reset" in flags:
            _reset_session(config)
        cmd_study(config, only_domain=only_domain)
    elif command == "exam":
        cmd_exam(config)
    elif command == "stats":
        cmd_stats(config)
    elif command == "refs":
        cmd_refs(config)
    elif command == "reset":
        _reset_session(config)
    else:
        console.print(f"[red]Unknown command: {command}[/red]")
        sys.exit(1)

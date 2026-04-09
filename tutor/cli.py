import os
import random
import sys
from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from rich.table import Table

from tutor.ingest import ingest
from tutor.openai_client import OpenAIChatClient, OpenAIEmbedder
from tutor.prompter import build_explanation_prompt
from tutor.question_pool import INITIAL_BATCH, POOL_SIZE, QuestionPool
from tutor.seed_questions import get_unasked_seed, load_seed_questions
from tutor.session import Session

console = Console()


def load_config() -> dict:
    config_path = Path("config.yaml")
    if not config_path.exists():
        console.print("[red]config.yaml not found. Run from the project root.[/red]")
        sys.exit(1)
    return yaml.safe_load(config_path.read_text())


def _get_api_key() -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        console.print("[red]OPENAI_API_KEY not set. Add it to your .env file.[/red]")
        sys.exit(1)
    return api_key


def make_embedder(config: dict) -> OpenAIEmbedder:
    return OpenAIEmbedder(
        api_key=_get_api_key(),
        model=config["openai"]["embed_model"],
    )


def make_generation_client(config: dict) -> OpenAIChatClient:
    return OpenAIChatClient(api_key=_get_api_key(), model=config["openai"]["generation_model"])


def make_explanation_client(config: dict) -> OpenAIChatClient:
    return OpenAIChatClient(api_key=_get_api_key(), model=config["openai"]["explanation_model"])


def make_pool(
    config: dict,
    chat_client: OpenAIChatClient,
    embedder: OpenAIEmbedder,
    weak_spots: list[str],
    asked_questions: set[str] | None = None,
    difficulty: int = 2,
) -> QuestionPool:
    return QuestionPool(
        pool_path=Path(config["session"]["data_dir"]) / "questions.json",
        chat_client=chat_client,
        embedder=embedder,
        chroma_dir=config["session"]["chroma_dir"],
        top_k=config["rag"]["top_k"],
        weak_spots=weak_spots,
        asked_questions=asked_questions,
        difficulty=difficulty,
    )


def _rate_color(rate: float) -> str:
    if rate >= 70:
        return "green"
    if rate >= 50:
        return "yellow"
    return "red"


LEVEL_LABELS = {1: "Beginner", 2: "Intermediate", 3: "Expert"}


DOMAIN_SHORT = {
    "Designing and Planning": "Design",
    "Managing and Provisioning": "Provision",
    "Security and Compliance": "Security",
    "Analyzing and Optimizing": "Optimize",
    "Managing Implementation": "Implement",
    "Operations Excellence": "Ops",
}


def build_header(session: Session) -> Panel:
    stats = session.summary()
    rate = stats["rate"]
    color = _rate_color(rate)

    level_label = LEVEL_LABELS.get(session.current_level, "?")
    parts = [
        f"Level {session.current_level} ({level_label})",
        f"[{color}]{stats['total_correct']}/{stats['total_questions']} ({rate:.0f}%)[/{color}]",
    ]

    for domain, data in sorted(stats["domains"].items()):
        domain_rate = (data["correct"] / data["asked"] * 100) if data["asked"] > 0 else 0
        dc = _rate_color(domain_rate)
        short = DOMAIN_SHORT.get(domain, domain)
        parts.append(f"{short}: [{dc}]{data['correct']}/{data['asked']}[/{dc}]")

    return Panel(" | ".join(parts), title="cert-tutor", border_style="green", height=3)


def display_question(data: dict) -> None:
    domain = data.get("domain", "")
    topic = data.get("topic", "")
    title = f"{domain} / {topic}" if domain and topic else domain or topic
    if data.get("multi_select"):
        correct = data["correct"]
        n = len(correct) if isinstance(correct, list) else 2
        title += f" [yellow](Choose {n})[/yellow]"

    question_text = f"[bold]{data['question']}[/bold]\n"
    for letter, choice in data["choices"].items():
        question_text += f"\n  [cyan]{letter}[/cyan]) {choice}"
    console.print(Panel(question_text, title=title, border_style="blue"))


def display_answers_with_result(
    data: dict, user_answer: str | list[str], correct: str | list[str]
) -> None:
    correct_set = set(correct) if isinstance(correct, list) else {correct}
    user_set = set(user_answer) if isinstance(user_answer, list) else {user_answer}

    lines = []
    for letter, choice in data["choices"].items():
        if letter in correct_set and letter in user_set:
            lines.append(f"  [green]+  {letter}) {choice}[/green]")
        elif letter in correct_set:
            lines.append(f"  [yellow]+  {letter}) {choice}[/yellow]")
        elif letter in user_set:
            lines.append(f"  [red]x  {letter}) {choice}[/red]")
        else:
            lines.append(f"  [dim]   {letter}) {choice}[/dim]")

    is_correct = user_set == correct_set
    if is_correct:
        title = "[green]Correct[/green]"
        border = "green"
    else:
        title = "[red]Incorrect[/red]"
        border = "red"

    console.print(Panel("\n\n".join(lines), title=title, border_style=border))


def show_case_study(
    case_study: str | None, chroma_dir: str, question_data: dict | None = None
) -> None:
    if not case_study:
        console.print("[yellow]No case study associated with this question.[/yellow]")
        return

    import chromadb
    chroma = chromadb.PersistentClient(path=chroma_dir)
    collection = chroma.get_collection("cert_docs")

    all_meta = collection.get(include=["metadatas"])
    all_sources = set(m["source"] for m in all_meta["metadatas"])

    search_term = case_study.lower().replace(" ", "_")
    matching_sources = [s for s in all_sources if search_term in s.lower()]

    if not matching_sources:
        search_words = case_study.lower()
        matching_sources = [s for s in all_sources if search_words in s.lower()]

    if not matching_sources:
        console.print(f"[yellow]No source file matched '{case_study}'.[/yellow]")
        return

    chunks = []
    for source in matching_sources:
        source_docs = collection.get(
            include=["documents", "metadatas"],
            where={"source": source},
        )
        for i, doc in enumerate(source_docs["documents"]):
            chunks.append({
                "text": doc,
                "page": source_docs["metadatas"][i].get("page", 0),
                "source": source,
            })

    chunks.sort(key=lambda c: (c["source"], c["page"]))
    seen = set()
    unique_chunks = []
    for c in chunks:
        if c["text"] not in seen:
            seen.add(c["text"])
            unique_chunks.append(c)

    text = "\n".join(c["text"] for c in unique_chunks)
    sources = ", ".join(sorted(set(c["source"] for c in unique_chunks)))

    console.clear()
    console.print(Panel(text, title=f"Case Study: {case_study} ({sources})", border_style="cyan"))

    if question_data:
        console.print()
        display_question(question_data)


def _prompt_input(prompt_text: str) -> str:
    from prompt_toolkit import prompt as pt_prompt
    return pt_prompt(prompt_text)


def get_reasoning_and_answer(
    case_study: str | None,
    chroma_dir: str,
    choose_n: int = 1,
    question_data: dict | None = None,
) -> tuple[str, str | list[str]]:
    hint = " /case to view case study." if case_study else ""
    console.print(f"\n[dim]Reasoning (optional, press enter to skip):{hint}[/dim]")
    reasoning = _prompt_input("> ").strip()
    while reasoning.lower() == "/case":
        show_case_study(case_study, chroma_dir, question_data)
        console.print(f"\n[dim]Reasoning (optional, press enter to skip):[/dim]")
        reasoning = _prompt_input("> ").strip()

    if choose_n > 1:
        while True:
            raw = _prompt_input(f"Choose {choose_n} (e.g. AC) or Q: ").strip().upper()
            if raw == "Q":
                return reasoning, "Q"
            letters = sorted(set(raw))
            if len(letters) == choose_n and all(l in "ABCDE" for l in letters):
                return reasoning, letters
            console.print(f"[yellow]Enter exactly {choose_n} letters (A-E) or Q.[/yellow]")
    else:
        while True:
            answer = _prompt_input("Answer (A/B/C/D/Q): ").strip().upper()
            if answer in ("A", "B", "C", "D", "Q"):
                return reasoning, answer
            console.print("[yellow]Enter A, B, C, D, or Q.[/yellow]")


def show_stats(session: Session, threshold: float, recent_n: int = 0) -> None:
    stats = session.summary()
    rate = stats["rate"]
    color = "green" if rate >= 70 else "yellow" if rate >= 50 else "red"
    level_label = LEVEL_LABELS.get(session.current_level, "?")
    console.print(Panel(
        f"[bold]Level {session.current_level} ({level_label}) | "
        f"Overall: {stats['total_correct']}/{stats['total_questions']} ([{color}]{rate:.1f}%[/{color}])[/bold]",
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

    weak_prods = session.weak_products(threshold)
    if weak_prods:
        prod_table = Table(title="Weak Products")
        prod_table.add_column("Product", style="bold")
        prod_table.add_column("Asked", justify="right")
        prod_table.add_column("Rate", justify="right")

        for product, rate, asked in weak_prods:
            prod_table.add_row(
                product,
                str(asked),
                f"[red]{rate * 100:.0f}%[/red]",
            )
        console.print(prod_table)

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


def cmd_ingest(config: dict, reset: bool) -> None:
    embedder = make_embedder(config)
    gen_client = make_generation_client(config)

    ingest(
        docs_dir=Path("docs"),
        chroma_dir=Path(config["session"]["chroma_dir"]),
        data_dir=Path(config["session"]["data_dir"]),
        embedder=embedder,
        chunk_size=config["rag"]["chunk_size"],
        chunk_overlap=config["rag"]["chunk_overlap"],
        reset=reset,
    )

    session = Session.load(Path(config["session"]["history_file"]))
    asked_questions = {entry["question"] for entry in session.history}
    pool = make_pool(
        config, gen_client, embedder, session.weak_spots(config["tutor"]["weak_spot_threshold"]),
        asked_questions, session.current_level,
    )

    if reset:
        pool.questions = []

    existing = pool.count()
    if existing >= POOL_SIZE:
        console.print(f"Question pool already has {existing} questions ready.")
        return

    initial = min(INITIAL_BATCH, POOL_SIZE - existing)
    remaining = POOL_SIZE - existing - initial

    to_generate = initial + remaining
    console.print(f"\nPre-generating {to_generate} questions...")
    with Progress() as progress:
        task = progress.add_task("Generating questions...", total=to_generate)

        def on_progress(done: int, total: int) -> None:
            progress.update(task, completed=done)

        pool.fill(to_generate, on_progress=on_progress)

    console.print(f"Ready to study with {pool.count()} questions. Run: uv run -m tutor study")


def cmd_study(config: dict) -> None:
    embedder = make_embedder(config)
    gen_client = make_generation_client(config)
    explain_client = make_explanation_client(config)

    chroma_dir = config["session"]["chroma_dir"]
    threshold = config["tutor"]["weak_spot_threshold"]
    recent_n = config["tutor"].get("recent_n", 0)

    has_docs = False
    import chromadb
    chroma = chromadb.PersistentClient(path=chroma_dir)
    try:
        collection = chroma.get_collection("cert_docs")
        has_docs = collection.count() > 0
    except Exception:
        pass

    session = Session.load(Path(config["session"]["history_file"]))

    has_seeds = get_unasked_seed(session.asked_seed_ids) is not None
    has_retries = session.retry_queue_size() > 0
    if not has_docs and not has_seeds and not has_retries:
        console.print("[red]No documents indexed and no seed questions left. Add PDFs to docs/ and run: python -m tutor ingest[/red]")
        sys.exit(1)

    diff_config = config["tutor"].get("difficulty", {})
    promote_threshold = diff_config.get("promote_threshold", 0.8)
    demote_threshold = diff_config.get("demote_threshold", 0.4)
    window_size = diff_config.get("window_size", 10)

    asked_questions = {entry["question"] for entry in session.history}
    pool = make_pool(
        config, gen_client, embedder, session.weak_spots(threshold, recent_n),
        asked_questions, session.current_level,
    ) if has_docs else None

    session.start_run()
    console.clear()
    console.print(build_header(session))

    if pool and pool.count() == 0:
        console.print("[yellow]No questions in pool. Generating first batch...[/yellow]")
        with Progress() as progress:
            task = progress.add_task("Generating questions...", total=INITIAL_BATCH)

            def on_progress(done: int, total: int) -> None:
                progress.update(task, completed=done)

            pool.fill(INITIAL_BATCH, on_progress=on_progress)
        remaining = POOL_SIZE - pool.count()
        if remaining > 0:
            pool._refill_background(remaining)

    while True:
        question_data = None
        is_seed = False
        is_retry = False

        weak_domains = set(session.weak_spots(threshold, recent_n))

        if session.retry_queue_size() > 0 and random.random() < 0.4:
            question_data = session.get_retry_question(weak_domains)
            is_retry = True

        if not question_data:
            seed = get_unasked_seed(session.asked_seed_ids, weak_domains)
            if seed and (not pool or random.random() < 0.3):
                question_data = seed
                is_seed = True

        if not question_data and pool:
            question_data = pool.pop()

        if not question_data and not is_seed:
            seed = get_unasked_seed(session.asked_seed_ids)
            if seed:
                question_data = seed
                is_seed = True

        if not question_data:
            if pool:
                console.print("[yellow]Pool empty. Generating more questions...[/yellow]")
                with console.status("[bold cyan]Generating question...[/bold cyan]"):
                    question_data = pool.generate_one()
            if not question_data:
                console.print("[red]No more questions available. Try adding more PDFs.[/red]")
                break

        if pool:
            pool.update_weak_spots(list(weak_domains))

        console.print()
        if is_retry:
            console.print("[dim](retry)[/dim]")
        display_question(question_data)
        case_study = question_data.get("case_study")
        correct = question_data["correct"]
        choose_n = len(correct) if isinstance(correct, list) else 1
        reasoning, answer = get_reasoning_and_answer(case_study, chroma_dir, choose_n, question_data)

        if answer == "Q":
            session.end_run()
            session.save()
            console.print("\n[bold]Session saved.[/bold]")
            break

        if isinstance(correct, list):
            is_correct = set(answer) == set(correct)
        else:
            is_correct = answer == correct

        if is_seed:
            session.asked_seed_ids.append(question_data["id"])

        if not is_correct:
            session.add_to_retry_queue(question_data)

        pregenerated = question_data.get("explanations")
        seed_explanation = question_data.get("explanation", "")

        question_difficulty = question_data.get("difficulty", 2)
        session.record(
            question=question_data["question"],
            choices=question_data["choices"],
            user_answer=answer,
            correct_answer=correct,
            domain=question_data.get("domain", ""),
            topic=question_data.get("topic", ""),
            explanation="",
            products=question_data.get("products"),
            difficulty=question_difficulty,
        )
        if pool:
            pool.mark_asked(question_data["question"])

        new_level = session.check_level_change(promote_threshold, demote_threshold, window_size)
        if new_level is not None:
            old_label = LEVEL_LABELS.get(session.current_level, "?")
            new_label = LEVEL_LABELS.get(new_level, "?")
            if new_level > session.current_level:
                console.print(f"\n[bold green]Level up! {old_label} -> {new_label}[/bold green]")
            else:
                console.print(f"\n[bold yellow]Level adjusted: {old_label} -> {new_label}[/bold yellow]")
            session.set_level(new_level)
            if pool:
                pool.update_difficulty(new_level)

        session.save()

        console.clear()
        console.print(build_header(session))
        console.print()
        display_answers_with_result(question_data, answer, correct)

        if pregenerated or reasoning:
            with console.status("[bold cyan]Building explanation...[/bold cyan]"):
                explanation_messages = build_explanation_prompt(
                    answer, correct, question_data["question"], question_data["choices"],
                    reasoning, pregenerated,
                )
                explanation = explain_client.chat(explanation_messages)
        else:
            explanation = seed_explanation

        session.history[-1]["explanation"] = explanation
        session.save()

        console.clear()
        console.print(build_header(session))
        console.print()
        display_answers_with_result(question_data, answer, correct)
        import re
        spaced = re.sub(r'\n([A-E]\))', r'\n\n\1', explanation)
        console.print(Panel(spaced, title="Explanation", border_style="dim"))

        console.print()


def cmd_fetch(exam: str) -> None:
    from tutor.fetcher import fetch_all
    from tutor.resources import get_exam_resources, list_exams

    try:
        resources = get_exam_resources(exam)
    except KeyError:
        available = ", ".join(list_exams())
        console.print(f"[red]Unknown exam: {exam}[/red]")
        console.print(f"Available: {available}")
        sys.exit(1)

    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)

    console.print(f"Fetching {len(resources)} resources for [bold]{exam}[/bold]...\n")

    with Progress() as progress:
        task = progress.add_task("Downloading...", total=len(resources))

        def on_progress(done: int, total: int, message: str) -> None:
            progress.console.print(f"  {message}")
            progress.update(task, completed=done)

        results = fetch_all(resources, docs_dir, on_progress=on_progress)

    console.print(f"\n[green]Downloaded: {results['downloaded']}[/green]")
    if results["skipped"]:
        console.print(f"[dim]Skipped (already exist): {results['skipped']}[/dim]")
    if results["failed"]:
        console.print(f"[red]Failed: {results['failed']}[/red]")

    if results["downloaded"] > 0:
        console.print("\nRun [bold]uv run -m tutor ingest[/bold] to index the new files.")


def cmd_exam(config: dict) -> None:
    import time

    from tutor.prompter import DOMAIN_WEIGHTS

    session = Session.load(Path(config["session"]["history_file"]))
    seed_qs = load_seed_questions()
    available = [q for q in seed_qs if q.get("correct")]

    if len(available) < 60:
        console.print(f"[red]Need at least 60 seed questions for a mock exam (have {len(available)}).[/red]")
        sys.exit(1)

    exam_size = 60
    case_study_qs_per = 8
    time_limit = 120 * 60

    case_study_pool = [q for q in available if q.get("case_study")]
    non_case_pool = [q for q in available if not q.get("case_study")]

    case_names = list(set(q["case_study"] for q in case_study_pool))
    chosen_cases = random.sample(case_names, min(2, len(case_names)))

    exam_questions: list[dict] = []
    used_ids: set[int] = set()

    for case_name in chosen_cases:
        case_qs = [q for q in case_study_pool if q["case_study"] == case_name]
        random.shuffle(case_qs)
        picked = case_qs[:case_study_qs_per]
        exam_questions.extend(picked)
        used_ids.update(q["id"] for q in picked)

    remaining_needed = exam_size - len(exam_questions)
    remaining_pool = [q for q in non_case_pool if q["id"] not in used_ids]

    for domain, weight in DOMAIN_WEIGHTS.items():
        target = round(remaining_needed * weight)
        domain_qs = [q for q in remaining_pool if q.get("domain") == domain and q["id"] not in used_ids]
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

    case_list = ", ".join(chosen_cases) if chosen_cases else "None"
    console.clear()
    console.print(Panel(
        f"[bold]Mock Exam: {len(exam_questions)} questions, {time_limit // 60} minutes[/bold]\n\n"
        f"Case studies: {case_list}\n"
        "No explanations until the end. Type Q to finish early.",
        title="cert-tutor exam",
        border_style="yellow",
    ))
    console.input("[dim]Press enter to start...[/dim]")

    start_time = time.time()
    answers: list[dict] = []
    timer_stop = False

    def _run_timer(question_num: int, total: int) -> None:
        import sys as _sys
        while not timer_stop:
            elapsed = time.time() - start_time
            remaining = max(0, time_limit - elapsed)
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            if mins > 30:
                color = "32"
            elif mins > 10:
                color = "33"
            else:
                color = "31"
            line = f" Question {question_num}/{total}  |  \033[{color};1m{mins}:{secs:02d} remaining\033[0m"
            _sys.stdout.write(f"\033[s\033[1;1H\033[2K{line}\033[u")
            _sys.stdout.flush()
            time.sleep(1)

    import threading

    exam_answers: list[str | list[str] | None] = [None] * len(exam_questions)

    def _ask_exam_question(idx: int) -> str | list[str] | None:
        question_data = exam_questions[idx]

        elapsed = time.time() - start_time
        if elapsed >= time_limit:
            return None

        console.clear()
        console.print()
        console.print()
        display_question(question_data)
        correct = question_data["correct"]
        choose_n = len(correct) if isinstance(correct, list) else 1

        nonlocal timer_stop
        timer_stop = False
        timer_thread = threading.Thread(
            target=_run_timer, args=(idx + 1, len(exam_questions)), daemon=True
        )
        timer_thread.start()

        answer = None
        if choose_n > 1:
            while True:
                raw = _prompt_input(f"Choose {choose_n} (e.g. AC), S=skip, Q=finish: ").strip().upper()
                if raw in ("Q", "S"):
                    answer = raw
                    break
                letters = sorted(set(raw))
                if len(letters) == choose_n and all(l in "ABCDE" for l in letters):
                    answer = letters
                    break
                console.print(f"[yellow]Enter exactly {choose_n} letters (A-E), S, or Q.[/yellow]")
        else:
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
            if (time.time() - start_time) >= time_limit:
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
    for i, answer in enumerate(exam_answers):
        if answer is None:
            continue
        q = exam_questions[i]
        correct = q["correct"]
        if isinstance(correct, list):
            is_correct = set(answer) == set(correct)
        else:
            is_correct = answer == correct
        answers.append({
            "question_data": q,
            "answer": answer,
            "correct": correct,
            "is_correct": is_correct,
        })

    unanswered = sum(1 for a in exam_answers if a is None)
    total = len(answers)
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
        f"Answered: {total}/{len(exam_questions)}{unanswered_line}\n"
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
        table.add_row(
            short,
            f"{data['correct']}/{data['asked']}",
            f"[{dc}]{d_rate:.0f}%[/{dc}]",
        )
    console.print(table)

    console.print("\n[bold]Review missed questions:[/bold]\n")
    missed = [a for a in answers if not a["is_correct"]]
    for a in missed:
        q = a["question_data"]
        console.print(f"[dim]{q.get('domain', '')} / {q.get('topic', '')}[/dim]")
        console.print(f"  Q: {q['question'][:150]}...")
        console.print(f"  Your answer: [red]{a['answer']}[/red]  Correct: [green]{a['correct']}[/green]")
        if q.get("explanation"):
            console.print(f"  {q['explanation'][:200]}")
        console.print()

    for a in answers:
        q = a["question_data"]
        session.record(
            question=q["question"],
            choices=q["choices"],
            user_answer=a["answer"],
            correct_answer=a["correct"],
            domain=q.get("domain", ""),
            topic=q.get("topic", ""),
            explanation=q.get("explanation", ""),
            products=q.get("products"),
        )
        if not a["is_correct"]:
            session.add_to_retry_queue(q)
    session.save()


def cmd_stats(config: dict) -> None:
    session = Session.load(Path(config["session"]["history_file"]))
    if session.total_questions == 0:
        console.print("[yellow]No study history yet. Run: python -m tutor study[/yellow]")
        return
    show_stats(session, config["tutor"]["weak_spot_threshold"], config["tutor"].get("recent_n", 0))


def main(args: list[str]) -> None:
    config = load_config()

    if not args:
        console.print("[bold]Usage:[/bold] python -m tutor [fetch|ingest|study|exam|stats]")
        console.print("  fetch <exam>       Download study resources (e.g., fetch architect)")
        console.print("  ingest             Index PDFs and text files from docs/")
        console.print("  ingest --reset     Clear and re-index all PDFs")
        console.print("  study              Start a study session")
        console.print("  exam               Take a timed 50-question mock exam")
        console.print("  stats              Show performance summary")
        sys.exit(0)

    command = args[0]

    if command == "fetch":
        if len(args) < 2:
            from tutor.resources import list_exams
            available = ", ".join(list_exams())
            console.print(f"[red]Usage: tutor fetch <exam>[/red]")
            console.print(f"Available: {available}")
            sys.exit(1)
        cmd_fetch(args[1])
    elif command == "ingest":
        reset = "--reset" in args
        cmd_ingest(config, reset)
    elif command == "study":
        cmd_study(config)
    elif command == "exam":
        cmd_exam(config)
    elif command == "stats":
        cmd_stats(config)
    else:
        console.print(f"[red]Unknown command: {command}[/red]")
        sys.exit(1)

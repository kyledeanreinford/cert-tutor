DOMAINS = [
    "Designing and Planning",
    "Managing and Provisioning",
    "Security and Compliance",
    "Analyzing and Optimizing",
    "Managing Implementation",
    "Operations Excellence",
]

DOMAIN_WEIGHTS = {
    "Designing and Planning": 0.25,
    "Managing and Provisioning": 0.175,
    "Security and Compliance": 0.175,
    "Analyzing and Optimizing": 0.15,
    "Managing Implementation": 0.125,
    "Operations Excellence": 0.125,
}

QUESTION_SYSTEM = """You are generating a question for the Google Cloud Professional Cloud Architect certification exam.

The exam has 6 sections:
1. Designing and Planning (~25%) — solution architecture, business/technical requirements, network/storage/compute design, migration planning
2. Managing and Provisioning (~17.5%) — configuring network topologies, storage, compute, Vertex AI, prebuilt AI APIs
3. Security and Compliance (~17.5%) — IAM, encryption, VPC Service Controls, secure access, compliance regulations
4. Analyzing and Optimizing (~15%) — SDLC, CI/CD, troubleshooting, business processes, cost optimization
5. Managing Implementation (~12.5%) — deployment, API management, testing, IaC, Google Cloud SDKs
6. Operations Excellence (~12.5%) — observability, monitoring, deployment/release management, reliability testing

Question style rules — follow these exactly:
- Write a SCENARIO: describe a company/team/person with a specific situation, 3-5 constraints or requirements, and a goal. The scenario should be 3-6 sentences long.
- End the question with "What should you do?" or "Which solution should you recommend?" or "How should you configure this?"
- All 4 answer choices must be complete sentences describing a concrete action, roughly equal length
- Every answer choice must name specific GCP products or services
- Wrong answers must be plausible — they should use real GCP products that solve a related but different problem
- The correct answer should not be obviously longer or more detailed than the others
- Vary which letter (A/B/C/D) is correct — do NOT default to B

Content rules:
- Question must be answerable from the provided context
- "domain" MUST be one of: Designing and Planning, Managing and Provisioning, Security and Compliance, Analyzing and Optimizing, Managing Implementation, Operations Excellence
- "topic" is a specific subtopic (e.g. "VPC Design", "IAM", "Disaster Recovery")
- If the context is from a case study, include the case study name
- Include a "products" list of the specific cloud products/services tested

Format response as JSON only:
{
  "domain": "Security and Compliance",
  "topic": "VPC Service Controls",
  "case_study": "Name of Case Study or null",
  "question": "...",
  "choices": {"A": "...", "B": "...", "C": "...", "D": "..."},
  "correct": "C",
  "explanation": "...",
  "products": ["VPC Service Controls", "Cloud Armor"]
}"""


DIFFICULTY_INSTRUCTIONS = {
    1: (
        "Difficulty: BEGINNER. "
        "The scenario should be straightforward with 1-2 simple requirements. "
        "Wrong answers should be from clearly different product categories "
        "(e.g. a storage product when the question is about compute). "
        "The correct answer should be the most well-known product for the task."
    ),
    2: (
        "Difficulty: INTERMEDIATE. "
        "The scenario should have 3-4 requirements that narrow the answer. "
        "Wrong answers should use real GCP products that solve related but different problems. "
        "This is standard exam difficulty."
    ),
    3: (
        "Difficulty: EXPERT. "
        "The scenario must have 4-5 specific constraints that make the answer subtle. "
        "All four answer choices MUST use products from the SAME category that could plausibly solve the problem. "
        "The differences between choices should hinge on a single technical detail "
        "(e.g. regional vs multi-regional, preemptible vs standard, Cloud Run vs GKE for a specific workload pattern). "
        "A candidate with only surface-level knowledge should pick the wrong answer."
    ),
}


def build_question_prompt(
    chunks: list[dict],
    weak_spots: list[str],
    style_examples: list[dict] | None = None,
    difficulty: int = 2,
) -> list[dict[str, str]]:
    context = "\n\n---\n\n".join(str(c["text"]) for c in chunks)

    user_content = ""
    if style_examples:
        user_content += "Here are example questions in the correct style:\n\n"
        for ex in style_examples:
            choices = "\n".join(f"  {k}: {v}" for k, v in ex["choices"].items())
            user_content += (
                f"Question: {ex['question']}\n"
                f"Choices:\n{choices}\n"
                f"Correct: {ex['correct']}\n"
                f"Domain: {ex.get('domain', '')}\n"
                f"Topic: {ex['topic']}\n\n"
            )
        user_content += "---\n\nNow generate a new question from this context:\n\n"

    user_content += f"Context:\n{context}"
    if weak_spots:
        topics = ", ".join(weak_spots)
        user_content += (
            f"\n\nThe user is weak on: {topics}. "
            "Prefer generating questions on these topics if the context supports it."
        )

    difficulty_instruction = DIFFICULTY_INSTRUCTIONS.get(difficulty, DIFFICULTY_INSTRUCTIONS[2])
    user_content += f"\n\n{difficulty_instruction}"

    return [
        {"role": "system", "content": QUESTION_SYSTEM},
        {"role": "user", "content": user_content},
    ]


EXPLANATION_SYSTEM = (
    "You are a terse, efficient exam tutor. Never use markdown formatting. "
    "Never use headers, bullets, bold, tables, or emojis. Plain text only. "
    "No praise, no encouragement, no sign-off.\n\n"
    "Always name the specific products or services in each answer choice. "
    "For cloud certifications, learning which product solves which problem is the point.\n\n"
    "You MUST use this exact format:\n\n"
    "If the user provided reasoning, start with one line addressing it.\n"
    "Then one blank line, then one line per answer choice:\n\n"
    "A) One sentence about why A is right or wrong, naming the product.\n"
    "B) One sentence about why B is right or wrong, naming the product.\n"
    "C) One sentence about why C is right or wrong, naming the product.\n"
    "D) One sentence about why D is right or wrong, naming the product.\n\n"
    "Each line MUST start with the letter and closing parenthesis. "
    "One sentence per line. No other text after the four lines."
)


def build_all_explanations_prompt(
    question: str, choices: dict[str, str], correct_answer: str
) -> list[dict[str, str]]:
    choices_text = "\n".join(f"{k}: {v}" for k, v in choices.items())
    return [
        {"role": "system", "content": EXPLANATION_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Question: {question}\n\n"
                f"Options:\n{choices_text}\n\n"
                f"The correct answer is {correct_answer}.\n\n"
                "Generate an explanation for each possible answer choice. "
                "For the correct answer, explain why it is right and name the key product. "
                "For each wrong answer, explain why it is wrong and what the named product actually does.\n\n"
                'Respond as JSON only: {"A": "...", "B": "...", "C": "...", "D": "..."}'
            ),
        },
    ]


def build_explanation_prompt(
    user_answer: str,
    correct_answer: str,
    question: str,
    choices: dict[str, str],
    reasoning: str,
    pregenerated: dict[str, str] | None,
) -> list[dict[str, str]]:
    choices_text = "\n".join(f"{k}: {v}" for k, v in choices.items())

    user_content = f"Question: {question}\n\nOptions:\n{choices_text}\n\n"

    if pregenerated:
        user_content += "Reference explanations per answer:\n"
        for letter, text in pregenerated.items():
            user_content += f"  {letter}: {text}\n"
        user_content += "\n"

    if reasoning:
        user_content += f"The user's reasoning: {reasoning}\n\n"

    user_content += (
        f"The user answered {user_answer}. The correct answer is {correct_answer}.\n\n"
        "Respond using the exact format from your instructions: "
        "optional reasoning line, then A) B) C) D) one sentence each."
    )

    return [
        {"role": "system", "content": EXPLANATION_SYSTEM},
        {"role": "user", "content": user_content},
    ]

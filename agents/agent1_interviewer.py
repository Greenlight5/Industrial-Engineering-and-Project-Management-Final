import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from core.llm_client import LLMClient
from core.models import RequirementsModel

console = Console()

QUESTIONS = [
    ("business_name",        "What is the name of the business?"),
    ("business_goal",        "What is the main goal of the bot? (e.g. lead generation, customer support, information, routing)"),
    ("bot_language",         "What language should the bot speak? (e.g. Hebrew, English, Arabic)"),
    ("operating_hours",      "What are the business operating hours? (e.g. Sun-Thu 08:00-20:00, Fri 08:00-14:00)"),
    ("bot_objective",        "In one sentence, what should the bot accomplish for users?"),
    ("services",             "What services does the business offer? (list them, e.g. 'Sales, Support, Billing')"),
    ("routing_model",        "Does each service have a dedicated representative, or do all agents handle everything? (dedicated / shared)"),
    ("greeting_message",     "What greeting message should the bot send when a conversation starts?"),
    ("out_of_hours_message", "What should the bot say when the user contacts outside of business hours?"),
    ("additional_notes",     "Any other requirements or specific behaviors? (press Enter to skip)"),
]

# Optional fields that are allowed to be empty / skipped
OPTIONAL_FIELDS = {"additional_notes"}

# Maximum number of follow-up clarification attempts per question
MAX_FOLLOW_UPS = 2

_VALIDATION_SYSTEM = """\
You are validating answers in a business requirements interview for building a WhatsApp chatbot.
Decide whether the user's answer provides enough useful information for the specific question asked.

An answer is INVALID if it is:
- Completely empty or only whitespace
- A non-answer ("idk", "skip", "whatever", "something") for a required field
- Completely off-topic or unrelated to the question
- So vague it gives zero actionable information (e.g. answering "yes" or "nice" to a question that needs specifics)

An answer is VALID if it provides any reasonable, relevant information — even if brief.

Respond with JSON only, no markdown:
{
  "valid": true | false,
  "follow_up": "<a short, specific guiding question to get better information>" | null
}
The "follow_up" key must be null when valid is true.\
"""


def validate_answer(field: str, question: str, answer: str, llm: LLMClient) -> dict:
    """Use LLM to check whether *answer* is relevant and sufficient for *question*.

    Returns a dict with keys:
      - ``valid`` (bool): True if the answer is usable.
      - ``follow_up`` (str | None): A guiding follow-up question when not valid.
    """
    if field in OPTIONAL_FIELDS:
        return {"valid": True, "follow_up": None}

    if not answer or not answer.strip():
        return {
            "valid": False,
            "follow_up": f"Could you please provide an answer for: {question}",
        }

    user_msg = (
        f"Question field: {field}\n"
        f"Question asked: {question}\n"
        f"User's answer: {answer}\n\n"
        "Is this answer useful for building a WhatsApp chatbot?"
    )

    raw = llm.chat(_VALIDATION_SYSTEM, user_msg, temperature=0.1)
    raw = _extract_json(raw)
    try:
        result = json.loads(raw)
        return {
            "valid": bool(result.get("valid", True)),
            "follow_up": result.get("follow_up"),
        }
    except Exception:
        return {"valid": True, "follow_up": None}


def run(llm: LLMClient) -> RequirementsModel:
    console.print(Panel(
        "[bold blue]Agent 1 — Business Requirements Interview[/bold blue]\n"
        "I will ask you a few questions to understand your business needs.\n"
        "Please answer each question as clearly as possible.",
        expand=False,
    ))

    answers: dict[str, str] = {}
    for i, (field, question) in enumerate(QUESTIONS, 1):
        console.print(f"\n[bold yellow][{i}/{len(QUESTIONS)}][/bold yellow] {question}")
        answer = Prompt.ask("[green]>[/green]").strip()
        answers[field] = answer

        for attempt in range(MAX_FOLLOW_UPS):
            validation = validate_answer(field, question, answers[field], llm)
            if validation["valid"]:
                break
            follow_up_q = validation.get("follow_up") or f"Could you elaborate on: {question}"
            console.print(f"\n[yellow]I need a bit more information.[/yellow]")
            console.print(f"[bold cyan]{follow_up_q}[/bold cyan]")
            extra = Prompt.ask("[green]>[/green]").strip()
            if extra:
                answers[field] = answers[field] + "\n" + extra if answers[field] else extra

    console.print("\n[bold blue]Compiling requirements...[/bold blue]")

    system_prompt = _load_system_prompt()
    user_prompt = _build_user_prompt(answers)
    raw = llm.chat(system_prompt, user_prompt, temperature=0.2)
    raw = _extract_json(raw)

    try:
        data = json.loads(raw)
        requirements = RequirementsModel(**data)
    except Exception as e:
        console.print(f"[red]Failed to parse requirements: {e}[/red]")
        console.print(f"[dim]Raw LLM output:\n{raw}[/dim]")
        raise

    console.print("\n[bold blue]Requirements compiled:[/bold blue]")
    console.print_json(requirements.model_dump_json(indent=2))

    if not Confirm.ask("\nDoes this look correct? Proceed to bot generation?", default=True):
        console.print("[yellow]Aborted. Please re-run to adjust your answers.[/yellow]")
        raise SystemExit(0)

    return requirements


def _load_system_prompt() -> str:
    path = Path(__file__).parent.parent / "prompts" / "agent1_system.txt"
    return path.read_text(encoding="utf-8")


def _build_user_prompt(answers: dict) -> str:
    lines = ["Here are the business requirements collected from the client:\n"]
    for field, question in QUESTIONS:
        lines.append(f"Q: {question}")
        lines.append(f"A: {answers.get(field, '(not provided)')}\n")
    return "\n".join(lines)


def get_questions() -> list[tuple[str, str]]:
    """Return the full questions list (for API use)."""
    return QUESTIONS


def compile_requirements(answers: dict[str, str], llm: LLMClient) -> RequirementsModel:
    """Compile a complete {field: answer} dict into a RequirementsModel via LLM."""
    system_prompt = _load_system_prompt()
    user_prompt = _build_user_prompt(answers)
    raw = llm.chat(system_prompt, user_prompt, temperature=0.2)
    raw = _extract_json(raw)
    data = json.loads(raw)
    return RequirementsModel(**data)


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        text = text[start:end]
    return text.strip()

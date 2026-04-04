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
        answer = Prompt.ask("[green]>[/green]")
        answers[field] = answer.strip()

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
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    # Extract the outermost JSON object
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        text = text[start:end]
    return text.strip()

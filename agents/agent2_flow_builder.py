import json
from pathlib import Path

from rich.console import Console

from core.llm_client import LLMClient
from core.models import RequirementsModel, BotFlowModel

console = Console()


def run(requirements: RequirementsModel, llm: LLMClient, max_retries: int = 2) -> BotFlowModel:
    console.print("\n[bold blue]Agent 2 — Building bot flow...[/bold blue]")

    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(requirements)

    last_error = None
    for attempt in range(1, max_retries + 2):
        if attempt > 1:
            console.print(f"[yellow]Retrying (attempt {attempt}/{max_retries + 1})...[/yellow]")
            user_prompt = _append_error(user_prompt, last_error)

        raw = llm.chat(system_prompt, user_prompt, temperature=0.2)
        raw = _extract_json(raw)

        try:
            data = json.loads(raw)
            bot = BotFlowModel(**data)
            console.print(
                f"[green]Bot flow generated: [bold]{bot.name}[/bold] "
                f"({len(bot.intents)} intents)[/green]"
            )
            return bot
        except json.JSONDecodeError as e:
            last_error = f"JSON parse error: {e}"
            console.print(f"[red]{last_error}[/red]")
        except Exception as e:
            last_error = f"Validation error: {e}"
            console.print(f"[red]{last_error}[/red]")

    raise RuntimeError(
        f"Agent 2 failed to produce valid output after {max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )


def _build_system_prompt() -> str:
    prompt_path = Path(__file__).parent.parent / "prompts" / "agent2_system.txt"
    template = prompt_path.read_text(encoding="utf-8")

    example_path = Path(__file__).parent.parent / "examples" / "visual_studio_bot.json"
    reference_example = example_path.read_text(encoding="utf-8") if example_path.exists() else "{}"

    return template.replace("{reference_example}", reference_example)


def _build_user_prompt(req: RequirementsModel) -> str:
    return (
        "Generate a complete Tiledesk bot JSON for the following business requirements:\n\n"
        + req.model_dump_json(indent=2)
        + "\n\nRemember: output ONLY raw JSON — no markdown, no explanation, no comments."
    )


def _append_error(user_prompt: str, error: str) -> str:
    return (
        user_prompt
        + f"\n\nYour previous response failed with this error:\n{error}\n"
        "Please fix the issue and return only valid JSON."
    )


def _extract_json(text: str) -> str:
    text = text.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    # Extract outermost JSON object
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        text = text[start:end]
    return text.strip()

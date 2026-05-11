import json
import re
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from core.models import RequirementsModel, BotFlowModel

console = Console()


def run(
    requirements: RequirementsModel,
    bot_flow: BotFlowModel,
    output_dir: str = "./output",
) -> Path:
    console.print("\n[bold blue]Agent 3 — Exporting bot files...[/bold blue]")

    client_slug = _slugify(requirements.business_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(output_dir) / f"{client_slug}_{timestamp}"
    out_path.mkdir(parents=True, exist_ok=True)

    # Save requirements.json
    req_file = out_path / "requirements.json"
    req_file.write_text(requirements.model_dump_json(indent=2), encoding="utf-8")

    # Save bot_flow.json
    bot_file = out_path / "bot_flow.json"
    bot_file.write_text(
        json.dumps(bot_flow.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Save upload instructions
    instructions_file = out_path / "upload_instructions.txt"
    instructions_file.write_text(
        _generate_instructions(requirements.business_name, out_path, timestamp),
        encoding="utf-8",
    )

    console.print(Panel(
        f"[bold green]Bot ready for upload![/bold green]\n\n"
        f"Client:  [cyan]{requirements.business_name}[/cyan]\n"
        f"Folder:  [cyan]{out_path}[/cyan]\n\n"
        f"Files:\n"
        f"  [yellow]{req_file.name}[/yellow]          — business requirements\n"
        f"  [yellow]{bot_file.name}[/yellow]             — bot ready for import\n"
        f"  [yellow]{instructions_file.name}[/yellow]  — step-by-step upload guide\n\n"
        f"[bold]Next step:[/bold] open [cyan]upload_instructions.txt[/cyan] for import steps.",
        title="Export Complete",
        expand=False,
    ))

    return out_path


def _slugify(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s_-]+", "_", name)
    return name[:50]


def _generate_instructions(business_name: str, out_path: Path, timestamp: str) -> str:
    bot_file = out_path / "bot_flow.json"
    req_file = out_path / "requirements.json"

    return f"""Bot ready for upload: {business_name}
Generated: {timestamp}

============================================================
STEPS TO UPLOAD THE BOT TO STUDIO
============================================================

1. Log in to the Studio system
2. Navigate to: Bots → Import Bot
3. Click "Upload JSON file"
4. Select the file:
   {bot_file}
5. Confirm the import
6. Verify the bot name and flow in the Studio editor
7. Activate the bot when ready

============================================================
FILES IN THIS FOLDER
============================================================

  {req_file}
  → Business requirements collected during the interview

  {bot_file}
  → Complete bot JSON ready for import into Studio

============================================================
SUPPORT
============================================================

If the import fails, verify that:
  - The Studio system is running and accessible
  - The JSON file is valid (you can check at jsonlint.com)
  - You have permission to import bots in the Studio system
"""

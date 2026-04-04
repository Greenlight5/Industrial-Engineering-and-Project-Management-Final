import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="studio",
    help="Studio System — AI-powered WhatsApp Bot Generator",
    add_completion=False,
)
console = Console()


@app.command()
def run(
    requirements: Optional[str] = typer.Option(
        None,
        "--requirements", "-r",
        help="Path to an existing requirements.json (skips the interview)",
    )
):
    """Run the full pipeline: interview → build flow → export."""
    from core.pipeline import run_pipeline
    run_pipeline(requirements_file=requirements)


@app.command()
def interview():
    """Run only Agent 1 — collect business requirements via interactive interview."""
    from core.pipeline import run_interview_only, _load_config

    requirements = run_interview_only()

    config = _load_config()
    output_dir = Path(config.get("output_dir", "./output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    slug = requirements.business_name.lower().replace(" ", "_")[:40]
    out_file = output_dir / f"{slug}_requirements.json"
    out_file.write_text(requirements.model_dump_json(indent=2), encoding="utf-8")

    console.print(f"\n[green]Requirements saved to: {out_file}[/green]")
    console.print(f"[dim]To build the bot, run: python main.py build --requirements {out_file}[/dim]")


@app.command()
def build(
    requirements: str = typer.Option(
        ...,
        "--requirements", "-r",
        help="Path to a requirements.json file",
    )
):
    """Run only Agent 2 + 3 — build and export a bot from an existing requirements file."""
    from core.pipeline import run_build_only, _load_config
    from core.models import RequirementsModel
    import agents.agent3_exporter as agent3

    config = _load_config()
    data = json.loads(Path(requirements).read_text(encoding="utf-8"))
    req = RequirementsModel(**data)

    bot_flow = run_build_only(requirements)

    output_dir = config.get("output_dir", "./output")
    agent3.run(req, bot_flow, output_dir=output_dir)


@app.command("list")
def list_bots():
    """List all generated bots in the output directory."""
    from core.pipeline import _load_config

    config = _load_config()
    output_dir = Path(config.get("output_dir", "./output"))

    if not output_dir.exists() or not any(output_dir.iterdir()):
        console.print("[yellow]No bots generated yet.[/yellow]")
        return

    dirs = sorted([d for d in output_dir.iterdir() if d.is_dir()])

    table = Table(title="Generated Bots", show_lines=True)
    table.add_column("Folder", style="cyan", no_wrap=True)
    table.add_column("Requirements", justify="center", style="green")
    table.add_column("Bot Flow", justify="center", style="green")
    table.add_column("Business Name", style="white")

    for d in dirs:
        has_req = "✓" if (d / "requirements.json").exists() else "✗"
        has_bot = "✓" if (d / "bot_flow.json").exists() else "✗"

        business_name = ""
        req_file = d / "requirements.json"
        if req_file.exists():
            try:
                data = json.loads(req_file.read_text(encoding="utf-8"))
                business_name = data.get("business_name", "")
            except Exception:
                pass

        table.add_row(d.name, has_req, has_bot, business_name)

    console.print(table)


if __name__ == "__main__":
    app()

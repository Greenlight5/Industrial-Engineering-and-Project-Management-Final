import json
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

from core.llm_client import LLMClient
from core.models import RequirementsModel, BotFlowModel
import agents.agent1_interviewer as agent1
import agents.agent2_flow_builder as agent2
import agents.agent3_exporter as agent3

load_dotenv()
console = Console()


def _load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.json"
    return json.loads(config_path.read_text(encoding="utf-8"))


def _make_llm(config: dict) -> LLMClient:
    from core.settings_store import get_api_key, get_model
    return LLMClient(
        provider=config["llm"]["provider"],
        model=get_model(),
        api_key=get_api_key(),
    )


def run_pipeline(requirements_file: str = None) -> None:
    """Run the full pipeline: Agent 1 → Agent 2 → Agent 3."""
    config = _load_config()
    llm = _make_llm(config)

    # Agent 1: collect or load requirements
    if requirements_file:
        console.print(f"[blue]Loading requirements from {requirements_file}[/blue]")
        data = json.loads(Path(requirements_file).read_text(encoding="utf-8"))
        requirements = RequirementsModel(**data)
    else:
        requirements = agent1.run(llm)

    # Agent 2: build bot flow
    max_retries = config.get("agent2", {}).get("max_retries", 2)
    bot_flow = agent2.run(requirements, llm, max_retries=max_retries)

    # Agent 3: export to disk
    output_dir = config.get("output_dir", "./output")
    agent3.run(requirements, bot_flow, output_dir=output_dir)


def run_interview_only() -> RequirementsModel:
    """Run only Agent 1 and return the requirements."""
    config = _load_config()
    llm = _make_llm(config)
    return agent1.run(llm)


def run_build_only(requirements_file: str) -> BotFlowModel:
    """Run only Agent 2 from an existing requirements file."""
    config = _load_config()
    llm = _make_llm(config)
    data = json.loads(Path(requirements_file).read_text(encoding="utf-8"))
    requirements = RequirementsModel(**data)
    max_retries = config.get("agent2", {}).get("max_retries", 2)
    return agent2.run(requirements, llm, max_retries=max_retries)

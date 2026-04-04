# Studio System — Full Technical Specification

## 1. Overview

Studio System is a Python-based, AI-powered pipeline that automates the creation of WhatsApp chatbots for the Tiledesk-based Studio platform. It replaces the manual, expert-driven process of designing and building bots with a three-agent pipeline that takes a business owner from a conversation to a ready-to-upload bot JSON file.

---

## 2. System Architecture

```
[ CLI / API Entry Point ]
         |
         ▼
  ┌─────────────┐       requirements.json
  │   Agent 1   │ ─────────────────────────►
  │  Interviewer│
  └─────────────┘
                          ┌─────────────┐       bot_flow.json
                          │   Agent 2   │ ──────────────────────►
                          │ Flow Builder│
                          └─────────────┘
                                                ┌─────────────┐
                                                │   Agent 3   │
                                                │   Exporter  │
                                                └─────────────┘
                                                      |
                                                      ▼
                                              output/<client_name>/
                                              └── bot_flow.json
                                              └── requirements.json
                                              └── upload_instructions.txt
```

The three agents run as a **sequential pipeline**: each agent's output is the next agent's input. No agent waits for human input between stages (except Agent 1, which interviews a human).

---

## 3. Technology Stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| Primary LLM | OpenAI (GPT-4o) |
| Secondary LLMs (future) | Anthropic Claude, Google Gemini |
| LLM abstraction | Single `LLMClient` wrapper class — easy to swap providers |
| Interface | CLI (primary), FastAPI (secondary, same core logic) |
| Config | `.env` file + `config.json` |
| Output | JSON files on disk |
| Dependencies | `openai`, `python-dotenv`, `typer` (CLI), `fastapi` (API layer) |

---

## 4. Project Structure

```
studio-system/
├── main.py                  # CLI entry point (Typer)
├── api.py                   # FastAPI entry point (same pipeline)
├── config.json              # System-wide config (model names, output dir, etc.)
├── .env                     # API keys (gitignored)
├── .env.example
├── requirements.txt
│
├── agents/
│   ├── __init__.py
│   ├── agent1_interviewer.py
│   ├── agent2_flow_builder.py
│   └── agent3_exporter.py
│
├── core/
│   ├── __init__.py
│   ├── llm_client.py        # Unified LLM wrapper (OpenAI, Claude, Gemini)
│   ├── pipeline.py          # Orchestrates agents 1→2→3
│   └── models.py            # Pydantic models for all data structures
│
├── prompts/
│   ├── agent1_system.txt
│   ├── agent2_system.txt
│   └── agent3_system.txt
│
├── examples/
│   └── visual_studio_bot.json   # Barak Services reference bot
│
└── output/                  # Generated bots (gitignored)
    └── <client_name>/
        ├── requirements.json
        ├── bot_flow.json
        └── upload_instructions.txt
```

---

## 5. Agent 1 — Business Requirements Interviewer

### Purpose
Conduct an interactive CLI conversation with the user (business owner or account manager) to collect all business requirements needed to design a bot. Output a structured JSON file.

### Interview Questions (fixed set)

| # | Field | Question |
|---|---|---|
| 1 | `business_name` | What is the name of the business? |
| 2 | `business_goal` | What is the main goal of the bot? (lead generation, support, info, routing…) |
| 3 | `bot_language` | What language should the bot speak? (Hebrew, Arabic, English…) |
| 4 | `operating_hours` | What are the business operating hours? (days and hours) |
| 5 | `bot_objective` | In one sentence, what should the bot accomplish? |
| 6 | `services` | What services does the business offer? (list them) |
| 7 | `routing_model` | Does each service have a dedicated representative, or do all agents handle everything? |
| 8 | `greeting_message` | What greeting message should the bot send when a conversation starts? |
| 9 | `out_of_hours_message` | What should the bot say outside of operating hours? |
| 10 | `additional_notes` | Any other requirements or specific behaviors you'd like? |

### Behavior
- Questions are asked one at a time in the CLI.
- The LLM is used to validate and clean up each answer (e.g., normalize hours format, extract service list from free text).
- After all questions are answered, the LLM summarizes and formats the result into the `requirements.json` schema.
- The user is shown the final JSON and asked to confirm or edit before proceeding.

### Output: `requirements.json`

```json
{
  "business_name": "string",
  "business_goal": "string",
  "bot_language": "he | ar | en | ...",
  "operating_hours": {
    "days": "א-ה",
    "start": "08:00",
    "end": "20:00",
    "friday": { "start": "08:00", "end": "14:00" },
    "saturday": null
  },
  "bot_objective": "string",
  "services": ["service1", "service2"],
  "routing_model": "dedicated | shared",
  "greeting_message": "string",
  "out_of_hours_message": "string",
  "additional_notes": "string"
}
```

---

## 6. Agent 2 — Bot Flow Builder

### Purpose
Receive `requirements.json` and produce a complete, valid Tiledesk Studio bot JSON (`bot_flow.json`) that can be imported directly into the Studio system.

### Tiledesk JSON Format (derived from Barak Services example)

The bot JSON has this top-level structure:

```json
{
  "webhook_enabled": false,
  "language": "<lang>",
  "name": "<bot name>",
  "type": "tilebot",
  "attributes": { "variables": {} },
  "intents": [ /* array of intent blocks */ ]
}
```

Each **intent block** (a node in the flow) has:

```json
{
  "webhook_enabled": false,
  "enabled": true,
  "intent_display_name": "string",
  "intent_id": "<uuid4>",
  "language": "<lang>",
  "question": null,          // only on 'start' block: "\\start"
  "actions": [ /* array of action objects */ ],
  "attributes": {
    "position": { "x": 200, "y": 250 },
    "nextBlockAction": {
      "_tdActionId": "<uuid4>",
      "_tdActionType": "intent",
      "intentName": null
    }
  }
}
```

### Available Action Types

Agent 2 may use any of these action types inside the `actions` array of an intent block:

| Action type (`_tdActionType`) | Description | Key fields |
|---|---|---|
| `replyv2` | Send a message with optional buttons | `text`, `attributes.commands[].message` with buttons array |
| `capture_user_reply` | Wait for user reply, save to variable | `assignResultTo` |
| `if_else` | Conditional branch (True/False routing) | `condition`, `trueIntent`, `falseIntent` |
| `set_attribute` | Create/set a variable | `varName`, `varValue` |
| `delete_attribute` | Delete a variable | `varName` |
| `replace_bot` | Transfer to another bot | `botId` |
| `wait` | Pause for N minutes | `minutes` |
| `conversation_update` | Update conversation (assign agent, tags…) | `updateType`, `value` |
| `contact_update` | Update contact/profile fields | `field`, `value` |
| `web_request` | HTTPS request | `url`, `method`, `headers`, `body`, `resultVar` |
| `send_email` | Send email | `to`, `subject`, `body` |
| `send_whatsapp_template` | Send WA template message | `templateName`, `params` |
| `powerlink` | Powerlink CRM integration action | `action`, `params` |
| `private_note` | Internal agent note (with variable interpolation) | `text` |
| `assign_team` | Assign conversation to a team | `teamId` |

### Button structure (inside `replyv2`)

```json
{
  "uid": "<uuid4>",
  "type": "action",
  "value": "Button label",
  "link": "",
  "target": "blank",
  "action": "#<target_intent_id>",
  "show_echo": true,
  "alias": ""
}
```

### Standard Flow Pattern

Agent 2 will generate these mandatory intents for every bot:

1. **`defaultFallback`** — standard "I didn't understand, please rephrase" block
2. **`start`** — triggered by `\\start`, routes to first real block
3. **`Main Menu`** — greeting + service buttons (one per service)
4. **Per-service blocks** — question/collect/route flow per service
5. **Out-of-hours block** — message shown outside operating hours (uses `if_else` on time)
6. **Handoff block** — `assign_team` or `conversation_update` to route to a human agent

### Layout Rule
Intents are placed on a virtual canvas. Position `x` increments by `+400` per branch column; `y` increments by `+250` per block in a column.

### Agent 2 LLM Prompt Strategy
- System prompt: detailed instructions + full Tiledesk JSON schema + all action type definitions + the Barak Services example as a reference
- User prompt: the `requirements.json` content
- The LLM is asked to produce **only valid JSON** (no markdown, no explanation)
- Output is parsed and validated against a Pydantic schema before saving
- If validation fails, Agent 2 retries once with the validation error appended to the prompt

### Output: `bot_flow.json`
A complete, import-ready Tiledesk bot JSON.

---

## 7. Agent 3 — Exporter

### Purpose
Save all outputs to a structured folder and provide the user with clear manual upload instructions.

### Behavior
1. Creates `output/<client_name>/` directory
2. Saves `requirements.json` (from Agent 1)
3. Saves `bot_flow.json` (from Agent 2)
4. Generates `upload_instructions.txt` with step-by-step instructions for manually importing the JSON into the Studio system
5. Prints a success summary to the CLI

### `upload_instructions.txt` content
```
Bot ready for upload: <client_name>
Generated: <timestamp>

Steps to upload:
1. Log in to the Studio system
2. Navigate to: Bots → Import Bot
3. Click "Upload JSON file"
4. Select the file: output/<client_name>/bot_flow.json
5. Confirm the import

Files saved:
- output/<client_name>/requirements.json  (business requirements)
- output/<client_name>/bot_flow.json      (bot ready for import)
```

---

## 8. Pipeline Orchestrator

`core/pipeline.py` runs the three agents in sequence:

```
run_pipeline(client_name)
  → agent1.run()          → requirements: RequirementsModel
  → agent2.run(req)       → bot_flow: BotFlowModel
  → agent3.run(req, bot)  → saved to disk
```

- All intermediate data is passed as Python objects (Pydantic models)
- Each step logs progress to stdout
- If any agent fails, the pipeline stops and shows a clear error message

---

## 9. CLI Interface

```bash
# Run full pipeline interactively
python main.py run

# Run from existing requirements file (skip Agent 1)
python main.py run --requirements path/to/requirements.json

# Only run Agent 1 (collect requirements)
python main.py interview

# Only run Agent 2 (build flow from existing requirements)
python main.py build --requirements path/to/requirements.json

# List all generated bots
python main.py list
```

---

## 10. API Interface (future / secondary)

`api.py` exposes the same pipeline via FastAPI:

```
POST /pipeline/run         — run full pipeline (body: requirements JSON)
POST /pipeline/interview   — start Agent 1 session
POST /pipeline/build       — run Agent 2 from requirements JSON
GET  /output/{client_name} — download generated bot JSON
```

---

## 11. LLM Client Abstraction

`core/llm_client.py` — a single class that wraps all providers:

```python
class LLMClient:
    def __init__(self, provider: str, model: str, api_key: str)
    def chat(self, system: str, user: str) -> str
```

Supported providers: `openai` (active), `anthropic` (stubbed), `gemini` (stubbed). Switching providers requires only a config change.

---

## 12. Configuration

**`config.json`**
```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o"
  },
  "output_dir": "./output",
  "agent2": {
    "max_retries": 2
  }
}
```

**`.env`**
```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=        # optional
GEMINI_API_KEY=           # optional
```

---

## 13. Data Models (Pydantic)

- `RequirementsModel` — Agent 1 output schema
- `IntentAction` — single action inside an intent
- `IntentBlock` — one node in the bot flow
- `BotFlowModel` — complete bot JSON structure

---

## 14. Key Constraints & Design Decisions

| Decision | Rationale |
|---|---|
| OpenAI only (for now) | Only available API key |
| CLI-first | Simple to run, no infrastructure needed initially |
| Agent 3 saves to disk (no upload API) | No external upload API exists; manual upload is the current workflow |
| Fixed interview questions | Questions are well-defined and consistent across clients |
| Single LLM call for Agent 2 | Bot complexity is medium; one well-engineered prompt is sufficient |
| Pydantic validation after Agent 2 | Ensures the LLM output is always valid JSON before saving |
| Examples dir with reference bot | Barak Services JSON is part of the Agent 2 system prompt as a concrete example |

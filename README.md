# Studio System — AI-Powered WhatsApp Bot Generator

## What is this?

Studio System automates the creation of WhatsApp chatbots for the **Tiledesk Studio** platform.

Instead of manually designing bot flows, you answer a short interview about your business and the system generates a complete, ready-to-import bot JSON file in seconds.

### How it works

The system runs three AI agents in a pipeline:

| Agent | Role | What it does |
|-------|------|--------------|
| **Agent 1** — Interviewer | Collects requirements | Asks 10 questions about your business (name, goal, language, services, hours, etc.) via a chat interface |
| **Agent 2** — Flow Builder | Designs the bot | Uses GPT-4o to generate a complete Tiledesk bot JSON with all conversation flows, menus, and routing |
| **Agent 3** — Exporter | Saves the output | Stores the bot JSON and a requirements backup, ready for download |

Once you download the generated `bot_flow.json`, you import it manually into the Studio system via **Bots → Import Bot**.

---

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- An **OpenAI API key** (get one at https://platform.openai.com/api-keys)

---

## Setup & Run

### 1. Build the Docker image

Open a terminal (Command Prompt or PowerShell on Windows), navigate to this folder, and run:

```
docker build -t studio-system .
```

This installs all dependencies inside the container. You only need to do this once (or after code changes).

### 2. Start the container

```
docker run -p 8000:8000 studio-system
```

### 3. Open the web interface

Open your browser and go to:

```
http://localhost:8000
```

### 4. Configure your API key

On first launch, click **⚙️ Settings** in the sidebar and paste your OpenAI API key. Click **Save Settings**.

> The key is stored inside the container. If you remove and recreate the container, you will need to enter it again.

---

## Usage

1. Click **✨ New Bot** in the sidebar
2. Answer the 10 interview questions in the chat
3. Review the compiled requirements and click **Generate Bot**
4. Wait ~20–40 seconds while the AI builds the bot flow
5. Download `bot_flow.json` from the results screen
6. Import it into Studio: **Bots → Import Bot → Upload JSON file**

---

## Stopping the container

Press `Ctrl+C` in the terminal where the container is running, or run:

```
docker stop $(docker ps -q --filter ancestor=studio-system)
```

---

## Project Structure

```
studio-system/
├── api.py                     Web server & API endpoints
├── main.py                    CLI entry point (alternative to web UI)
├── config.json                Default model and output settings
├── Dockerfile                 Container definition
├── requirements.txt           Python dependencies
│
├── agents/
│   ├── agent1_interviewer.py  Interview logic & requirements compilation
│   ├── agent2_flow_builder.py Bot JSON generation via LLM
│   └── agent3_exporter.py     File saving & upload instructions
│
├── core/
│   ├── llm_client.py          OpenAI API wrapper
│   ├── models.py              Data models (Pydantic)
│   ├── pipeline.py            Agent orchestration
│   └── settings_store.py      API key & model persistence
│
├── prompts/
│   ├── agent1_system.txt      LLM prompt for requirements compilation
│   └── agent2_system.txt      LLM prompt for bot flow generation
│
├── examples/
│   └── visual_studio_bot.json Reference bot used as a generation example
│
└── static/
    └── index.html             Web UI (single-page app)
```

---

## Supported Bot Actions

The generated bots can use any of the following Tiledesk action types:

- **replyv2** — Send a message with optional buttons
- **capture_user_reply** — Wait for and capture user input
- **if_else** — Conditional branching
- **set_attribute / delete_attribute** — Variable management
- **assign_team** — Route to a team of agents
- **conversation_update** — Update conversation properties
- **contact_update** — Update contact profile fields
- **private_note** — Internal agent notes
- **web_request** — HTTP requests to external services
- **send_email** — Send email notifications
- **send_whatsapp_template** — Send WhatsApp template messages
- **powerlink** — Powerlink CRM integration
- **replace_bot** — Transfer to another bot
- **wait** — Pause the flow for N minutes

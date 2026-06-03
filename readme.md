# MCP Context Sharing System
### VS Code + OpenAI + FastAPI + Gradio UI

---

## Contributors

**Bhavika** — Developer 

**Shams** — Collaborator

---


## Project Structure

```
Context Sharing System using MCP/
├── src/
│   ├── client/
│   │   ├── chat.py                ← Interactive terminal chat
│   │   ├── commands.py            ← Slash-command dispatcher
│   │   ├── config.py              ← Client-side settings
│   │   ├── demo.py                ← Quick demo script
│   │   └── mcp_helper.py          ← Shared MCP utilities
│   ├── mcp/
│   │   ├── auth.py                ← API key auth & rate limiting
│   │   ├── config.py              ← MCP server configuration
│   │   ├── database.py            ← SQLite persistence layer
│   │   ├── logger.py              ← Structured JSON logging
│   │   ├── resources.py           ← MCP resources & prompts
│   │   ├── routes.py              ← HTTP routes via MCP
│   │   ├── server.py              ← MCP server entry point
│   │   └── tools.py               ← All MCP tools
│   ├── server/
│   │   ├── app.py                 ← FastAPI entry point
│   │   ├── chat_routes.py         ← /chat endpoints + OpenAI
│   │   ├── config.py              ← Server settings
│   │   ├── context_routes.py      ← /context/* endpoints
│   │   ├── mcp_client.py          ← MCP session lifecycle
│   │   ├── models.py              ← Pydantic request models
│   │   ├── namespace_routes.py    ← /namespaces/* endpoints
│   │   └── stats_routes.py        ← /stats endpoint
│   └── ui/
│       ├── api_client/
│       │   ├── chat.py            ← Chat & stats API calls
│       │   ├── context.py         ← Context & namespace API calls
│       │   └── http.py            ← Raw HTTP helpers
│       ├── components/
│       │   ├── chat_tab.py        ← Chat tab
│       │   ├── context_tab.py     ← Context Manager tab
│       │   ├── namespace_tab.py   ← Namespaces tab
│       │   └── stats_tab.py       ← Stats tab
│       └── app.py                 ← Gradio UI entry point
├── .env                           ← All config goes here
├── context_store.db               ← Auto-created SQLite database
├── requirements.txt               ← Python dependencies
└── README.md
```

---

## Architecture

```
Gradio UI (port 7860)
        ↓  HTTP requests
FastAPI (port 8000)
        ↓  stdio
MCP Server
        ↓
SQLite (context_store.db)
        ↓
OpenAI GPT-4o
```

---

## Setup

```bash
pip install mcp[cli] openai python-dotenv gradio fastapi uvicorn
```

Edit `.env` in the project root:

```dotenv
# OpenAI
OPENAI_API_KEY=sk-proj-your-real-key-here
OPENAI_MODEL=gpt-4o

# MCP Server
MCP_TRANSPORT=stdio
MCP_HOST=0.0.0.0
MCP_PORT=8000
MCP_API_KEY=

# Storage
CONTEXT_DB_PATH=context_store.db
DEFAULT_TTL_SECONDS=0
RATE_LIMIT_PER_MIN=60
LOG_FILE=mcp_server.log

# FastAPI
API_BASE_URL=http://localhost:8000
```

> **Note:** If `.env` is not loading correctly, set the key directly in PowerShell before running:
> ```powershell
> $env:OPENAI_API_KEY="sk-proj-your-actual-key-here"
> ```

---

## Run

### Gradio Web UI (recommended)

Open **two PowerShell terminals**:

**Terminal 1 — FastAPI + MCP Server:**
```powershell
cd "D:\Context Sharing System using MCP"
python src/api.py
```
Wait for: ` MCP server connected`

**Terminal 2 — Gradio UI:**
```powershell
cd "D:\Context Sharing System using MCP"
python src/ui.py
```

Then open in browser:
- **UI** → http://localhost:7860
- **API docs** → http://localhost:8000/docs

### Quick demo (terminal only)
```powershell
python src/openai_with_context.py
```

### Interactive terminal chat
```powershell
python src/chat.py
```

---

## Gradio UI Tabs

| Tab | What it does |
|---|---|
|  Chat | Talk to GPT-4o — MCP context injected automatically via FastAPI |
|  Context Manager | Store, browse, search, get, delete entries |
|  Namespaces | View all namespaces, share entries between them, clear namespace |
|  Stats | Total entries, auth status, model, rate limit, top tags |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/context/set` | Store a context entry |
| GET | `/context/get/{namespace}/{key}` | Retrieve an entry |
| GET | `/context/list/{namespace}` | List all entries |
| DELETE | `/context/delete/{namespace}/{key}` | Delete an entry |
| GET | `/context/search/{namespace}` | Full-text search |
| POST | `/context/share` | Share entry between namespaces |
| GET | `/namespaces` | List all namespaces |
| DELETE | `/namespaces/{namespace}` | Clear a namespace |
| GET | `/stats` | Server health stats |
| POST | `/chat` | Chat with OpenAI using MCP context |
| POST | `/chat/reset` | Reset conversation history |

Full interactive docs at **http://localhost:8000/docs**

---

## Terminal Chat Commands

```
/set <key> <value>         store context
/set <key> <value> ttl=60  store with 60s expiry
/get <key>                 retrieve a value
/search <query>            search values
/list                      show all keys
/list tag=<tag>            filter by tag
/stats                     server stats
/ns <name>                 switch namespace
/memory                    show conversation memory
/reset                     reset conversation memory
/quit                      exit
```

---

## Production Features

| Feature | How to configure |
|---|---|
| SQLite persistence | Auto-enabled — context survives restarts |
| TTL expiry | Set `DEFAULT_TTL_SECONDS` or pass `ttl_seconds` per entry |
| API key auth | Set `MCP_API_KEY=your-secret` in `.env` |
| Rate limiting | Set `RATE_LIMIT_PER_MIN=60` in `.env` |
| Structured logging | JSON logs written to `mcp_server.log` |
| HTTP/SSE transport | Set `MCP_TRANSPORT=sse` in `.env` for production |

---

## How it works

```
1. Store context via UI or terminal
           ↓
2. FastAPI forwards to MCP Server
           ↓
3. MCP Server saves to SQLite
           ↓
4. On chat — FastAPI fetches all context from MCP
           ↓
5. Context injected as OpenAI system prompt
           ↓
6. GPT-4o answers with full context awareness
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| ` FastAPI not running` | Start Terminal 1 with `python src/api.py` first |
| `401 Incorrect API key` | Run `$env:OPENAI_API_KEY="sk-proj-..."` in the same terminal |
| `0.0.0.0` in browser | Use `http://localhost:7860` instead |
| Context not showing | Click **List** in Context Manager to verify entries exist |

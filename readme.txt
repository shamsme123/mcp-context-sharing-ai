# MCP Context Sharing System
### VS Code + OpenAI + Gradio UI

## Project Structure

```
mcp-context-sharing/
├── src/
│   ├── server/
│   │   └── context_server.py      ← MCP server (8 tools, SQLite, auth, TTL)
│   ├── openai_with_context.py     ← Demo: store context → ask OpenAI
│   ├── chat.py                    ← Interactive terminal chat
│   └── ui.py                      ← Gradio web UI
├── .env                           ← All config goes here
├── context_store.db               ← Auto-created SQLite database
└── README.md
```

---

## Setup

```bash
pip install mcp[cli] openai python-dotenv gradio
```

Edit `.env` in the project root:

```dotenv
OPENAI_API_KEY=sk-proj-your-real-key-here
OPENAI_MODEL=gpt-4o
CONTEXT_DB_PATH=context_store.db
MCP_API_KEY=
DEFAULT_TTL_SECONDS=0
RATE_LIMIT_PER_MIN=60
MCP_TRANSPORT=stdio
MCP_HOST=0.0.0.0
MCP_PORT=8000
LOG_FILE=mcp_server.log
```

---

## Run

### Gradio Web UI (recommended)
```bash
python src/ui.py
```
Then open http://localhost:7860 in your browser.

### Quick demo (terminal)
```bash
python src/openai_with_context.py
```

### Interactive chat (terminal)
```bash
python src/chat.py
```

---

## Gradio UI Tabs

| Tab | What it does |
|---|---|
| Chat | Talk to GPT-4o with MCP context auto-injected |
| Context Manager | Store, browse, search, get, delete entries |
| Namespaces | View all namespaces, share entries, clear namespace |
| Stats | Total entries, auth status, model, rate limit, top tags |

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
/quit                      exit
```

---

## Production Features

| Feature | How to configure |
|---|---|
| SQLite persistence | Auto-enabled, set `CONTEXT_DB_PATH` in `.env` |
| TTL expiry | Set `DEFAULT_TTL_SECONDS` or pass `ttl_seconds` per entry |
| API key auth | Set `MCP_API_KEY=your-secret` in `.env` |
| Rate limiting | Set `RATE_LIMIT_PER_MIN=60` in `.env` |
| Structured logging | Logs to `mcp_server.log` as JSON |
| HTTP/SSE transport | Set `MCP_TRANSPORT=sse` and `MCP_PORT=8000` in `.env` |

---

## How it works

```
Store context via UI or terminal
        ↓
MCP server saves to SQLite
        ↓
Chat pulls context from namespace
        ↓
Injected as OpenAI system prompt
        ↓
GPT-4o answers with full context awareness
```
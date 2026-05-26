# MCP Context Sharing System
### VS Code + OpenAI Setup

## Project Structure

```
mcp-context-sharing/
├── src/
│   ├── server/
│   │   └── context_server.py      ← MCP server (8 tools)
│   ├── openai_with_context.py     ← Demo: store context → ask OpenAI
│   └── chat.py                    ← Interactive chat with /commands
├── .env                           ← Add your OPENAI_API_KEY here
└── README.md
```

## Setup

```bash
pip install mcp[cli] openai python-dotenv
```

Edit `.env`:
```
OPENAI_API_KEY=sk-your-key-here
```

## Run

### Quick demo

''' bash
$env:OPENAI_API_KEY="sk-proj-your-actual-key-here"
'''

```bash
python src/openai_with_context.py
```

### Interactive chat
```bash
python src/chat.py
```

Commands inside chat:
  /set <key> <value>   store context
  /get <key>           retrieve a value
  /list                show all keys
  /ns <name>           switch namespace
  /quit                exit
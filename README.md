# ShopMate AI — AI E-Commerce Customer Support Agent

A complete local AI customer-support demo built for the TNSDC / IBM Agentic AI use case:
- Product queries
- Order status
- Return checking
- Product recommendations
- Conversation memory
- Ollama local LLM
- Tool calling
- SQLite demo database

## Project architecture

Browser -> Flask UI -> Agent -> Ollama
                         |
                         +-> product_search
                         +-> order_status
                         +-> return_policy
                         +-> recommend_products
                         +-> conversation_memory
                         |
                         +-> SQLite

## Requirements
- Python 3.10+
- VS Code
- Ollama installed and running

## Setup

### 1. Install Ollama model
Open a terminal:

```bash
ollama pull llama3.2
```

You can use another tool-capable Ollama model by changing `OLLAMA_MODEL` in `.env` or `app.py`.

### 2. Create virtual environment

Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

macOS/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install packages
```bash
pip install -r requirements.txt
```

### 4. Start Ollama
```bash
ollama serve
```
If Ollama is already running as a background service, this command may say the port is already in use; that is okay.

### 5. Run ShopMate AI
```bash
python app.py
```

Open:
http://127.0.0.1:5000

## Demo IDs
Orders:
- ORD1001
- ORD1002
- ORD1003

Products include:
- Wireless Headphones
- Smart Watch
- Gaming Mouse
- Laptop Backpack
- Mechanical Keyboard
- USB-C Hub

## Example questions
- "Show me headphones under 3000"
- "Where is order ORD1001?"
- "Can I return ORD1002?"
- "Recommend something for gaming"
- "What products do you have?"
- "I like gaming products. What should I buy?"

## Notes
This is a local academic/demo project. Product, order and return data are sample records in SQLite.

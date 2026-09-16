import os
import json
import sqlite3
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

DB = "shopmate.db"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        stock INTEGER NOT NULL,
        description TEXT NOT NULL
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        customer TEXT NOT NULL,
        product TEXT NOT NULL,
        status TEXT NOT NULL,
        eta TEXT NOT NULL
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS returns (
        order_id TEXT PRIMARY KEY,
        eligible INTEGER NOT NULL,
        reason TEXT NOT NULL
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")

    if cur.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        products = [
            (1, "Wireless Headphones", "Audio", 2499, 18, "Bluetooth over-ear headphones with microphone and 30-hour battery."),
            (2, "Smart Watch", "Wearables", 3499, 12, "Fitness smartwatch with heart-rate tracking, notifications and 7-day battery."),
            (3, "Gaming Mouse", "Gaming", 1299, 30, "Ergonomic RGB gaming mouse with adjustable DPI."),
            (4, "Laptop Backpack", "Accessories", 1599, 20, "Water-resistant laptop backpack with padded 15.6-inch compartment."),
            (5, "Mechanical Keyboard", "Gaming", 2799, 10, "Compact mechanical keyboard with tactile switches and RGB lighting."),
            (6, "USB-C Hub", "Accessories", 999, 25, "7-in-1 USB-C hub with HDMI, USB 3.0 and SD card support."),
        ]
        cur.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)", products)

    if cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
        orders = [
            ("ORD1001", "Vijay", "Wireless Headphones", "Shipped", "18 Sep 2026"),
            ("ORD1002", "Vijay", "Gaming Mouse", "Delivered", "12 Sep 2026"),
            ("ORD1003", "Vijay", "Laptop Backpack", "Processing", "20 Sep 2026"),
        ]
        cur.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", orders)

    if cur.execute("SELECT COUNT(*) FROM returns").fetchone()[0] == 0:
        returns = [
            ("ORD1001", 1, "Eligible: within the 7-day return window."),
            ("ORD1002", 0, "Not eligible: the sample order is outside the return window."),
            ("ORD1003", 1, "Eligible: order has not been delivered yet."),
        ]
        cur.executemany("INSERT INTO returns VALUES (?, ?, ?)", returns)

    conn.commit()
    conn.close()


def save_memory(session_id, role, content):
    conn = db()
    conn.execute(
        "INSERT INTO memories(session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (session_id, role, content, datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()


def get_memory(session_id, limit=10):
    conn = db()
    rows = conn.execute(
        "SELECT role, content FROM memories WHERE session_id=? ORDER BY id DESC LIMIT ?",
        (session_id, limit)
    ).fetchall()
    conn.close()
    return list(reversed([dict(r) for r in rows]))


# -------------------- AGENT TOOLS --------------------

def product_search(query="", max_price=None, category=""):
    conn = db()
    sql = "SELECT * FROM products WHERE 1=1"
    params = []

    if query:
        sql += " AND (name LIKE ? OR description LIKE ? OR category LIKE ?)"
        q = f"%{query}%"
        params += [q, q, q]
    if max_price is not None:
        sql += " AND price <= ?"
        params.append(float(max_price))
    if category:
        sql += " AND category LIKE ?"
        params.append(f"%{category}%")

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    return {
        "count": len(rows),
        "products": [dict(r) for r in rows]
    }


def order_status(order_id):
    conn = db()
    row = conn.execute(
        "SELECT * FROM orders WHERE order_id=?",
        (order_id.upper(),)
    ).fetchone()
    conn.close()

    if not row:
        return {"found": False, "message": "Order ID not found."}
    return {"found": True, "order": dict(row)}


def return_check(order_id):
    conn = db()
    row = conn.execute(
        """SELECT r.*, o.product, o.status
           FROM returns r JOIN orders o ON r.order_id=o.order_id
           WHERE r.order_id=?""",
        (order_id.upper(),)
    ).fetchone()
    conn.close()

    if not row:
        return {"found": False, "message": "Return information not found for this order."}
    return {"found": True, "return": dict(row)}


def recommend_products(category="", max_price=None):
    conn = db()
    sql = "SELECT * FROM products WHERE stock > 0"
    params = []
    if category:
        sql += " AND category LIKE ?"
        params.append(f"%{category}%")
    if max_price is not None:
        sql += " AND price <= ?"
        params.append(float(max_price))
    sql += " ORDER BY price ASC LIMIT 5"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return {"recommendations": [dict(r) for r in rows]}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "product_search",
            "description": "Search the store catalog. Use this for product availability, product queries, category searches, and price limits.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Product name or keywords"},
                    "max_price": {"type": "number", "description": "Maximum price in INR, if specified"},
                    "category": {"type": "string", "description": "Category such as Gaming, Audio, Accessories, Wearables"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "order_status",
            "description": "Look up an order using its order ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order ID such as ORD1001"}
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "return_check",
            "description": "Check whether an order is eligible for return.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order ID such as ORD1002"}
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_products",
            "description": "Recommend available products based on category and optional maximum price.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Desired category"},
                    "max_price": {"type": "number", "description": "Maximum budget in INR, if specified"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "conversation_memory",
            "description": "Retrieve earlier messages from this customer's current session when prior preferences or context are useful.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]


def execute_tool(name, args, session_id):
    try:
        if name == "product_search":
            return product_search(
                args.get("query", ""),
                args.get("max_price"),
                args.get("category", "")
            )
        if name == "order_status":
            return order_status(args.get("order_id", ""))
        if name == "return_check":
            return return_check(args.get("order_id", ""))
        if name == "recommend_products":
            return recommend_products(
                args.get("category", ""),
                args.get("max_price")
            )
        if name == "conversation_memory":
            return {"memory": get_memory(session_id)}
        return {"error": f"Unknown tool: {name}"}
    except Exception as e:
        return {"error": str(e)}


def ask_ollama(user_message, session_id):
    history = get_memory(session_id, 12)

    system = """You are ShopMate AI, a friendly e-commerce customer support agent.
You must use tools whenever the user asks for product data, order status, returns, or recommendations.
Never invent product prices, stock, order status, or return eligibility.
For order questions, ask for the order ID if it is missing.
For recommendations, use the recommendation/search tools first.
Use conversation_memory when earlier user preferences are relevant.
Answer clearly and concisely. Currency is Indian Rupees (INR).
This is a demo store, so explain that records are sample data if needed.
"""

    messages = [{"role": "system", "content": system}]
    for item in history:
        messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": user_message})

    # A small loop supports multiple tool calls.
    for _ in range(5):
        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "tools": TOOLS,
            "stream": False
        }

        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        message = data.get("message", {})
        tool_calls = message.get("tool_calls", [])

        if not tool_calls:
            answer = message.get("content", "").strip()
            return answer or "I couldn't generate a response."

        messages.append(message)

        for call in tool_calls:
            fn = call.get("function", {})
            name = fn.get("name")
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}

            result = execute_tool(name, args, session_id)
            messages.append({
                "role": "tool",
                "content": json.dumps(result, ensure_ascii=False)
            })

    return "I reached the tool-processing limit. Please try the request again."


@app.route("/")
def index():
    return render_template("index.html")


@app.post("/chat")
def chat():
    data = request.get_json(force=True)
    session_id = data.get("session_id", "demo-user")
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "Message is required."}), 400

    save_memory(session_id, "user", message)

    try:
        answer = ask_ollama(message, session_id)
        save_memory(session_id, "assistant", answer)
        return jsonify({"answer": answer})
    except requests.exceptions.ConnectionError:
        return jsonify({
            "error": "Ollama is not reachable. Start Ollama and make sure the model is installed."
        }), 503
    except requests.exceptions.Timeout:
        return jsonify({"error": "Ollama took too long. Please try again."}), 504
    except Exception as e:
        return jsonify({"error": f"Agent error: {e}"}), 500


@app.post("/reset")
def reset():
    session_id = request.get_json(force=True).get("session_id", "demo-user")
    conn = db()
    conn.execute("DELETE FROM memories WHERE session_id=?", (session_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.get("/health")
def health():
    try:
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=5)
        return jsonify({"flask": "ok", "ollama": r.ok, "model": OLLAMA_MODEL})
    except Exception:
        return jsonify({"flask": "ok", "ollama": False, "model": OLLAMA_MODEL})


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)

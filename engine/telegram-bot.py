#!/usr/bin/env python3
"""
Telegram Bot -- Independent communication layer
Telegram Bot API -> local-agent-engine.py -> Ollama local model
"""

import json
import os
import sys
import time
import traceback
import urllib.parse
import urllib.request
from pathlib import Path
from threading import Thread

# === CONFIG ===
# CRITICAL: Set these via environment variables or .env file
TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN_HERE")
OPERATOR_ID = int(os.environ.get("OPERATOR_ID", "0"))
MODEL = os.environ.get("MODEL", "qwen3.5:9b")
OLLAMA_API = os.environ.get("OLLAMA_API", "http://127.0.0.1:11434/api/chat")
POLL_TIMEOUT = 30
MAX_MSG_LEN = 4000  # Telegram limit is 4096, leave margin
STATE_FILE = Path("/tmp/telegram-bot-state.json")
LOG_FILE = Path("/tmp/telegram-bot.log")

# Import the engine
ENGINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE_DIR))
from importlib import import_module

# === TELEGRAM API ===
def tg_api(method, params=None, timeout=70):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    if params:
        data = json.dumps(params).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log(f"API error [{method}]: {e}")
        return {"ok": False, "error": str(e)}


def send_typing(chat_id):
    tg_api("sendChatAction", {"chat_id": chat_id, "action": "typing"}, timeout=10)


def send_message(chat_id, text, reply_to=None):
    """Send message, split if too long"""
    chunks = []
    while len(text) > MAX_MSG_LEN:
        # Find a good split point
        split_at = text.rfind("\n", 0, MAX_MSG_LEN)
        if split_at < MAX_MSG_LEN // 2:
            split_at = MAX_MSG_LEN
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    chunks.append(text)

    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
        params = {"chat_id": chat_id, "text": chunk}
        if reply_to and i == 0:
            params["reply_to_message_id"] = reply_to
        tg_api("sendMessage", params)
        if i < len(chunks) - 1:
            time.sleep(0.3)


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass


# === STATE ===
def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except:
        return {"last_update_id": 0}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state))


# === CONVERSATION MEMORY ===
# Keep recent conversation context per chat
conversations = {}
MAX_HISTORY = 10


def get_history(chat_id):
    if chat_id not in conversations:
        conversations[chat_id] = []
    return conversations[chat_id]


def add_to_history(chat_id, role, content):
    h = get_history(chat_id)
    h.append({"role": role, "content": content})
    # Keep last N exchanges
    if len(h) > MAX_HISTORY * 2:
        conversations[chat_id] = h[-(MAX_HISTORY * 2):]


# === ENGINE INTEGRATION ===
def run_engine(task, chat_id):
    """Call local-agent-engine directly"""
    import importlib
    engine = importlib.import_module("local-agent-engine")
    # Reload to pick up any changes
    importlib.reload(engine)

    result = engine.run(
        task=task,
        output_file=None,
        memory_key=None,
        extra_context="You are a local AI assistant. Running on local GPU. Reply casually like chatting with a friend."
    )
    return result


def run_engine_subprocess(task, chat_id=None):
    """Call full engine as subprocess -- all optimizations active"""
    import subprocess
    engine_path = ENGINE_DIR / "local-agent-engine.py"

    # Refresh typing indicator in background while engine runs
    typing_stop = False
    def keep_typing():
        while not typing_stop:
            if chat_id:
                send_typing(chat_id)
            time.sleep(4)
    if chat_id:
        typing_thread = Thread(target=keep_typing, daemon=True)
        typing_thread.start()

    try:
        proc = subprocess.run(
            ["python3", str(engine_path), task],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(ENGINE_DIR)
        )
        # Read the output file (engine writes structured result here)
        output_file = Path("/tmp/engine-output.md")
        if output_file.exists():
            result = output_file.read_text(encoding="utf-8").strip()
            if result and result != "(generation failed)":
                # Log engine stats from stdout
                for line in proc.stdout.split("\n"):
                    if "Total:" in line or "MicroCompact:" in line:
                        log(f"  Engine: {line.strip()}")
                return result
        # Fallback to stdout
        return proc.stdout.strip() or proc.stderr.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "Task timed out (3 min limit). Try a shorter command."
    except Exception as e:
        return f"Execution error: {e}"
    finally:
        typing_stop = True


# === AGENT IDENTITY ===
# NOTE: 改成你的名字和硬體資訊 (Replace with your name and hardware info)
AGENT_SYSTEM = """You are a local AI assistant for [YOUR_NAME]. Running on local GPU with {model}.
You are NOT a cloud AI. You are an independent local AI.

Your features:
- Fully local, zero cost, data never leaves the computer
- Fast response (1-3 seconds)
- Can execute commands, read/analyze code, search web, monitor tasks

Rules:
1. Introduce yourself as "I'm your local AI assistant"
2. Reply casually like chatting with a friend
3. Concise and useful, no fluff
4. MUST use tools for actions, never answer from memory alone
5. Read files with head -N or grep, never cat entire large files
6. On tool failure, analyze cause and try alternatives

/no_think""".format(model=MODEL)

# === SIMPLE DIRECT CHAT (for quick responses) ===
def quick_chat(text):
    """For simple questions, skip the full engine and call Ollama directly.
    Uses: think=false, structured prompt, identity"""
    import subprocess
    # Build conversation with history
    operator_id_str = str(OPERATOR_ID)
    messages = [{"role": "system", "content": AGENT_SYSTEM}]
    # Add recent history for context
    history = get_history(operator_id_str)
    for h in history[-6:]:  # Last 3 exchanges
        messages.append(h)
    messages.append({"role": "user", "content": text})

    req = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "think": False  # Optimization #4: 8-10x token efficiency
    }
    try:
        proc = subprocess.run(
            ["curl", "-s", "--max-time", "60",
             OLLAMA_API,
             "-d", json.dumps(req)],
            capture_output=True, text=True, timeout=65
        )
        if proc.stdout.strip():
            d = json.loads(proc.stdout)
            content = d.get("message", {}).get("content", "").strip()
            tokens = d.get("eval_count", 0)
            if content:
                log(f"  Quick reply: {len(content)} chars / {tokens} tokens")
                return content
    except Exception as e:
        log(f"  quick_chat error: {e}")
    return None


def needs_tools(text):
    """Detect if the message needs tool execution (full engine) or just chat"""
    tool_keywords = [
        "file", "read", "check", "execute", "run", "install",
        "search", "download", "write", "create", "delete", "modify",
        "factory", "dispatcher", "log", "status",
        "cat ", "ls ", "grep ", "pip ", "git ",
        "/", "analyze", "report", "stats"
    ]
    return any(kw in text.lower() for kw in tool_keywords)


# === MAIN LOOP ===
def process_message(chat_id, user_id, text, message_id):
    """Process a single message"""
    # Only respond to operator
    if user_id != OPERATOR_ID:
        log(f"Ignored non-operator message from {user_id}")
        return

    log(f"Received: {text[:80]}")
    send_typing(chat_id)

    try:
        if needs_tools(text):
            # Full engine with tool execution (all optimizations)
            log("Mode: Full engine (with tools)")
            result = run_engine_subprocess(text, chat_id=chat_id)
        else:
            # Quick chat without tools
            log("Mode: Quick chat")
            result = quick_chat(text)
            if not result:
                # Fallback to engine
                log("Quick chat failed, falling back to engine")
                result = run_engine_subprocess(text)

        if result:
            send_message(chat_id, result, reply_to=message_id)
            add_to_history(str(chat_id), "user", text)
            add_to_history(str(chat_id), "assistant", result[:500])
            log(f"Reply sent: {len(result)} chars")
        else:
            send_message(chat_id, "Sorry, no result this time. Try again?", reply_to=message_id)

    except Exception as e:
        log(f"Error: {traceback.format_exc()}")
        send_message(chat_id, f"Error: {e}", reply_to=message_id)


# === TASK INBOX (allows external processes to send tasks) ===
TASK_INBOX = Path("/tmp/agent-task-inbox.md")

def check_task_inbox():
    """Check if an external process left a task in the inbox file"""
    if not TASK_INBOX.exists():
        return
    try:
        task = TASK_INBOX.read_text(encoding="utf-8").strip()
        if not task:
            return
        # Remove the file first to prevent re-processing
        TASK_INBOX.unlink()
        log(f"Inbox task received: {task[:80]}")

        # Execute with full engine
        result = run_engine_subprocess(task, chat_id=str(OPERATOR_ID))
        if result:
            # If task mentions an output file path, also write there
            import re
            output_match = re.search(r'write.*?to\s*(/\S+\.md)', task)
            if output_match:
                out_path = Path(output_match.group(1))
                out_path.write_text(result, encoding="utf-8")
                log(f"Inbox result also written to: {out_path}")

            # Send result to operator via Telegram
            send_message(str(OPERATOR_ID), f"Inbox task completed:\n\n{result}")
            log(f"Inbox task done: {len(result)} chars")
        else:
            send_message(str(OPERATOR_ID), "Inbox task produced no result")
            log("Inbox task: no output")
    except Exception as e:
        log(f"Inbox task error: {e}")


def main():
    log("Telegram Bot starting")
    log(f"   Model: {MODEL} via Ollama")

    if TOKEN == "YOUR_TOKEN_HERE":
        log("ERROR: BOT_TOKEN not set! Set it in .env or environment variable.")
        log("   Get a token from @BotFather on Telegram")
        return

    if OPERATOR_ID == 0:
        log("WARNING: OPERATOR_ID not set. Bot will ignore all messages.")
        log("   Get your ID from @userinfobot on Telegram")

    # Verify bot
    me = tg_api("getMe")
    if me.get("ok"):
        bot_info = me["result"]
        log(f"   Bot: @{bot_info.get('username', '?')} ({bot_info.get('first_name', '?')})")
    else:
        log(f"   Bot token verification failed: {me}")
        return

    state = load_state()

    # Seed offset to skip old messages
    if state["last_update_id"] == 0:
        seed = tg_api("getUpdates", {"timeout": 0, "limit": 1})
        if seed.get("ok") and seed.get("result"):
            state["last_update_id"] = seed["result"][-1]["update_id"]
            save_state(state)
            log(f"   Seeded offset: {state['last_update_id']}")

    log("   Polling started...\n")

    while True:
        try:
            params = {
                "timeout": POLL_TIMEOUT,
                "limit": 10,
                "allowed_updates": ["message"]
            }
            if state["last_update_id"]:
                params["offset"] = state["last_update_id"] + 1

            # Check task inbox before polling (non-blocking)
            check_task_inbox()

            resp = tg_api("getUpdates", params, timeout=POLL_TIMEOUT + 10)

            if not resp.get("ok"):
                log(f"getUpdates failed: {resp}")
                time.sleep(5)
                continue

            updates = resp.get("result", [])
            for update in updates:
                update_id = update.get("update_id", 0)
                message = update.get("message", {})
                text = message.get("text", "").strip()
                chat_id = message.get("chat", {}).get("id", 0)
                user_id = message.get("from", {}).get("id", 0)

                state["last_update_id"] = max(state["last_update_id"], update_id)

                if text:
                    process_message(chat_id, user_id, text, message.get("message_id"))

            save_state(state)

        except KeyboardInterrupt:
            log("Interrupt received, stopping")
            break
        except Exception as e:
            log(f"Poll error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()

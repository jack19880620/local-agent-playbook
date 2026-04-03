#!/usr/bin/env python3
"""你的第一個本地 AI Agent — 基礎版（第三章存檔點）"""

import json, subprocess, os

MODEL = "qwen3.5:9b"
API = "http://127.0.0.1:11434/api/chat"

# === 工具定義 ===
TOOLS = [
    {"type": "function", "function": {
        "name": "bash", "description": "執行 bash 命令並返回結果",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "description": "bash 命令"}
        }, "required": ["command"]}
    }},
    {"type": "function", "function": {
        "name": "read_file", "description": "讀取檔案內容（前N行）",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "絕對路徑"},
            "lines": {"type": "integer", "description": "讀取行數 預設50"}
        }, "required": ["path"]}
    }},
    {"type": "function", "function": {
        "name": "write_file", "description": "寫入檔案",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "絕對路徑"},
            "content": {"type": "string", "description": "檔案內容"}
        }, "required": ["path", "content"]}
    }}
]

# === 工具執行器 ===
def execute_tool(name, args):
    if name == "bash":
        cmd = args.get("command", "")
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return r.stdout + r.stderr
        except subprocess.TimeoutExpired:
            return "ERROR: 命令超時（30秒）"
    elif name == "read_file":
        path = args.get("path", "")
        lines = args.get("lines", 50)
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = []
                for i, line in enumerate(f):
                    if i >= lines: break
                    content.append(line)
            return "".join(content) or "(empty file)"
        except Exception as e:
            return f"ERROR: {e}"
    elif name == "write_file":
        path = args.get("path", "")
        content = args.get("content", "")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f: f.write(content)
            return f"OK: wrote {len(content)} chars to {path}"
        except Exception as e:
            return f"ERROR: {e}"
    return f"ERROR: unknown tool {name}"

# === API 呼叫 ===
def call_model(messages, tools=None):
    req = {"model": MODEL, "messages": messages, "stream": False, "think": False}
    if tools:
        req["tools"] = tools
    with open('/tmp/agent-req.json', 'w') as f:
        json.dump(req, f, ensure_ascii=False)
    r = subprocess.run(
        ['curl', '-s', '--max-time', '120', API, '-d', '@/tmp/agent-req.json'],
        capture_output=True, text=True)
    if not r.stdout.strip():
        return None
    return json.loads(r.stdout)

# === 主迴圈 ===
def run(task, max_steps=5):
    system = "你是本地 AI 助手。用繁體中文回答。用工具執行操作 不要憑記憶回答。"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": task}
    ]

    for step in range(max_steps):
        d = call_model(messages, TOOLS)
        if not d: break
        msg = d['message']
        messages.append(msg)
        tc = msg.get('tool_calls', [])
        if tc:
            name = tc[0]['function']['name']
            args = tc[0]['function'].get('arguments', {})
            if isinstance(args, str):
                try: args = json.loads(args)
                except: args = {"command": args}
            print(f"  [{step+1}] 🔧 {name}({str(args)[:60]})")
            output = execute_tool(name, args)
            print(f"       → {output[:200]}")
            messages.append({"role": "tool", "content": output})
        else:
            result = msg.get('content', '')
            print(f"  [{step+1}] 💬 {result[:200]}")
            return result

    # 如果用完步數 讓模型總結
    messages.append({"role": "user", "content": "根據以上資料 給我結論。"})
    d = call_model(messages)
    return d['message'].get('content', '') if d else "(生成失敗)"

if __name__ == "__main__":
    import sys
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "列出 /tmp 目錄有什麼檔案"
    print(f"📋 任務：{task}\n")
    result = run(task)
    print(f"\n📄 結果：\n{result}")

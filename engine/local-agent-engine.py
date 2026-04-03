#!/usr/bin/env python3
"""
Local AI Agent Engine v1.0
Inspired by Claude Code's leaked architecture
Optimized for qwen3.5:9b on local GPU

10 optimizations integrated:
1. Structured system prompt
2. MicroCompact (tool result compression 80-93%)
3. Hard cutoff (explore->produce forced transition)
4. think=false (8-10x token efficiency)
5. ToolSearch deferred loading (-60% prompt)
6. Four memory types (user/feedback/project/reference)
7. Shared prompt prefix (cache-friendly)
8. Strict write discipline (verify before memory update)
9. Parallel bootstrap (prefetch memory+model+tools)
10. Cache break avoidance (stable system prompt)
"""

import json, subprocess, time, os, re
from concurrent.futures import ThreadPoolExecutor

# === CONFIG ===
MODEL = os.environ.get("MODEL", "qwen3.5:9b")
API = os.environ.get("OLLAMA_API", "http://127.0.0.1:11434/api/chat")
WORKSPACE = os.environ.get("AGENT_WORKSPACE", os.path.expanduser("~/workspace"))
MEMORY_DIR = os.environ.get("MEMORY_DIR", "/tmp/local-agent-memory-v2")  # 可改成持久化路徑
MAX_EXPLORE_STEPS = 5
MAX_TOTAL_STEPS = 10
MICRO_COMPACT_LIMIT = 1300
TIMEOUT = 120

# === TOOL REGISTRY (Optimization #5: ToolSearch deferred loading) ===
# Full tool catalog -- only relevant tools are loaded per task
TOOL_CATALOG = {
    "bash": {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute bash command and return result",
            "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "bash command"}}, "required": ["command"]}
        },
        "tags": ["exec", "file", "diag", "factory", "install", "network"]
    },
    "read_file": {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file content (first N lines). Safer than bash cat, auto-limits size",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "Absolute path"},
                "lines": {"type": "integer", "description": "Lines to read (default 50)"}
            }, "required": ["path"]}
        },
        "tags": ["file", "read", "diag", "factory"]
    },
    "write_file": {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or overwrite file content",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "Absolute path"},
                "content": {"type": "string", "description": "File content"}
            }, "required": ["path", "content"]}
        },
        "tags": ["file", "write", "fix"]
    },
    "grep_search": {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "Search for text patterns in directory, return matching lines and files",
            "parameters": {"type": "object", "properties": {
                "pattern": {"type": "string", "description": "Search regex pattern"},
                "path": {"type": "string", "description": "Search directory (default cwd)"},
                "max_results": {"type": "integer", "description": "Max lines to return (default 20)"}
            }, "required": ["pattern"]}
        },
        "tags": ["search", "file", "diag", "factory"]
    },
    "list_dir": {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List directory contents (file size, modification time)",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "Absolute directory path"}
            }, "required": ["path"]}
        },
        "tags": ["file", "diag", "factory"]
    },
    "search_tools": {
        "type": "function",
        "function": {
            "name": "search_tools",
            "description": "Search available tools. Use this if the tool you need is not in the current list",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "Describe what tool you need, e.g. 'write file' or 'search text'"}
            }, "required": ["query"]}
        },
        "tags": ["meta"]
    }
}

# Task category -> tool tags mapping
TASK_TOOL_MAP = {
    "diag":    ["bash", "read_file", "grep_search", "list_dir"],
    "fix":     ["bash", "read_file", "write_file", "grep_search"],
    "factory": ["bash", "read_file", "grep_search", "list_dir"],
    "file":    ["bash", "read_file", "write_file", "list_dir"],
    "search":  ["bash", "grep_search", "list_dir"],
    "default": ["bash", "search_tools"],
}

def classify_task(task):
    """Classify task to select relevant tools (lightweight, no API call)"""
    t = task.lower()
    categories = set()
    if any(kw in t for kw in ["factory", "dispatcher", "agent", "pipeline"]):
        categories.add("factory")
    if any(kw in t for kw in ["fix", "bug", "error", "fail"]):
        categories.add("fix")
    if any(kw in t for kw in ["status", "check", "diagnose", "log", "report"]):
        categories.add("diag")
    if any(kw in t for kw in ["search", "find", "grep", "where"]):
        categories.add("search")
    if any(kw in t for kw in ["file", "read", "write", "create"]):
        categories.add("file")
    return categories or {"default"}

def select_tools(task):
    """Select tools based on task classification + always include search_tools meta"""
    categories = classify_task(task)
    tool_names = set()
    for cat in categories:
        tool_names.update(TASK_TOOL_MAP.get(cat, TASK_TOOL_MAP["default"]))
    tool_names.add("search_tools")  # Always available as escape hatch
    tools = [{"type": t["type"], "function": t["function"]} for name, t in TOOL_CATALOG.items() if name in tool_names]
    return tools, tool_names

def execute_tool(name, args):
    """Execute a tool by name, return result string"""
    if name == "bash":
        cmd = args.get("command", "")
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return r.stdout + r.stderr
        except subprocess.TimeoutExpired:
            return "ERROR: Command timed out (30s)"
    elif name == "read_file":
        path = args.get("path", "")
        lines = args.get("lines", 50)
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = []
                for i, line in enumerate(f):
                    if i >= lines:
                        content.append(f"\n...[truncated at {lines} lines]")
                        break
                    content.append(line)
            return "".join(content) or "(empty file)"
        except Exception as e:
            return f"ERROR: {e}"
    elif name == "write_file":
        path = args.get("path", "")
        content = args.get("content", "")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"OK: wrote {len(content)} chars to {path}"
        except Exception as e:
            return f"ERROR: {e}"
    elif name == "grep_search":
        pattern = args.get("pattern", "")
        path = args.get("path", ".")
        max_results = args.get("max_results", 20)
        try:
            r = subprocess.run(
                ["grep", "-rn", "--include=*.md", "--include=*.py", "--include=*.sh",
                 "--include=*.json", "--include=*.log", "--include=*.yaml", "--include=*.yml",
                 "-m", str(max_results), pattern, path],
                capture_output=True, text=True, timeout=15
            )
            return r.stdout or "(no matches)"
        except subprocess.TimeoutExpired:
            return "ERROR: Search timed out"
        except Exception as e:
            return f"ERROR: {e}"
    elif name == "list_dir":
        path = args.get("path", ".")
        try:
            r = subprocess.run(["ls", "-lah", "--time-style=+%Y-%m-%d", path],
                              capture_output=True, text=True, timeout=10)
            return r.stdout or r.stderr
        except Exception as e:
            return f"ERROR: {e}"
    elif name == "search_tools":
        query = args.get("query", "").lower()
        matches = []
        for name, tool in TOOL_CATALOG.items():
            desc = tool["function"]["description"]
            tags = " ".join(tool.get("tags", []))
            if any(q in desc.lower() or q in tags for q in query.split()):
                matches.append(f"- {name}: {desc}")
        return "\n".join(matches) if matches else "No matching tools found. Available: " + ", ".join(TOOL_CATALOG.keys())
    return f"ERROR: unknown tool {name}"

# === STATIC SYSTEM PROMPT (Optimization #1: structured, cache-friendly) ===
# A/B test result: structured prompt = +600% quality, +36% speed vs generic prompt
# NOTE: 改成你的名字 (Replace [YOUR_NAME] with your name)
STATIC_PROMPT = """You are a local AI assistant for [YOUR_NAME]. Running on local GPU with {model}.
You are NOT a cloud AI. You are an independent local AI.

# Identity
- Fully local, zero cost, data never leaves the computer
- Tone: casual like chatting with a friend
- Concise and useful replies, no fluff

# Tool Usage Rules
1. MUST use tools to perform actions, never answer from memory alone
2. Read files with head -N or grep, never cat entire large files
3. If memory mentions a file exists, verify with ls first (skeptical memory)
4. On tool failure, analyze cause and try alternatives (max 3 attempts)
5. Short commands first, one thing at a time

# Output Rules
1. Numbers must be exact, no estimates
2. Use markdown tables for comparison data
3. Mark severity for anomalies (HIGH/MEDIUM/LOW)
4. End with actionable suggestions, not vague advice
5. If data is insufficient, say so clearly instead of guessing

# Workspace
- Default workspace: {workspace}

# Diagnostic Rules (violating any = useless report)
1. Before reporting any bug, MUST verify with tools (bash -n for syntax, grep for variable definitions)
2. NEVER report bugs without tool output — unverified = fabricated
3. Large files: first wc -l, then grep -n for keywords, then head/tail specific blocks
4. Diagnostic flow: light scan (wc/bash -n/grep ERROR) -> locate block -> read block -> analyze -> report
5. Every bug in report must include verification command and tool output
6. Numbers must come from tool output, no estimation""".format(model=MODEL, workspace=WORKSPACE)

# === MICROCOMPACT (Optimization #2) ===
def micro_compact(text, max_chars=MICRO_COMPACT_LIMIT):
    if len(text) <= max_chars:
        return text
    lines = text.split('\n')
    # Short outputs (<=15 lines): keep all lines, just trim each line
    # This preserves numbers/stats from grep -c, wc, du etc.
    if len(lines) <= 15:
        trimmed = '\n'.join(line[:200] for line in lines)
        if len(trimmed) <= max_chars * 2:
            return trimmed
        return trimmed[:max_chars] + "\n...[trimmed]"
    # Long outputs: keep more head (8) + tail (5) for better context
    head = '\n'.join(lines[:8])
    tail = '\n'.join(lines[-5:])
    return f"{head}\n\n...[{len(lines)-13} lines omitted, {len(text)} total chars]...\n\n{tail}"

# === MEMORY SYSTEM (Optimization #6) ===
def load_memory():
    """Load four-type memory index"""
    index = ""
    for mtype in ['user', 'feedback', 'project', 'reference']:
        mdir = f"{MEMORY_DIR}/{mtype}"
        if not os.path.isdir(mdir):
            continue
        files = os.listdir(mdir)
        if files:
            index += f"\n[{mtype}]\n"
            for f in sorted(files):
                content = open(f"{mdir}/{f}").read().strip()
                index += f"- {content[:100]}\n"
    return index

# === BOOTSTRAP (Optimization #9) ===
def bootstrap(task=""):
    """Parallel prefetch: memory + model warm + task-based tool selection"""
    with ThreadPoolExecutor(max_workers=3) as executor:
        f_mem = executor.submit(load_memory)
        f_warm = executor.submit(lambda: subprocess.run(
            ['curl', '-s', '--max-time', '30', API, '-d',
             json.dumps({"model": MODEL, "messages": [{"role": "user", "content": "hi"}], "stream": False, "think": False})],
            capture_output=True, text=True))
        f_tools = executor.submit(select_tools, task)
        memory = f_mem.result()
        tools, tool_names = f_tools.result()
        return memory, tools, tool_names

# === API CALL ===
def call_model(messages, tools=None):
    req = {"model": MODEL, "messages": messages, "stream": False, "think": False}
    if tools:
        req["tools"] = tools
    with open('/tmp/engine-req.json', 'w') as f:
        json.dump(req, f, ensure_ascii=False)
    r = subprocess.run(['curl', '-s', '--max-time', str(TIMEOUT), API, '-d', '@/tmp/engine-req.json'],
                      capture_output=True, text=True)
    if not r.stdout.strip():
        return None
    return json.loads(r.stdout)

# === STRICT WRITE DISCIPLINE (Optimization #8) ===
def verified_write(path, content, memory_key=None):
    """Write file, verify, then optionally update memory"""
    with open(path, 'w') as f:
        f.write(content)
    # Verify
    verify = open(path).read()
    if len(verify) < 20 or verify != content:
        print(f"  FAIL: Write verification failed: {path}")
        return False
    # Update memory only if verified
    if memory_key:
        mem_path = f"{MEMORY_DIR}/project/{memory_key}.md"
        with open(mem_path, 'w') as f:
            f.write(content[:500])
        print(f"  Memory updated: {memory_key}")
    return True

# === SEGMENTED DIAGNOSIS (Optimization #11) ===
def is_diagnosis_task(task):
    """Detect if task is a diagnostic/analysis task on a large file"""
    t = task.lower()
    return any(kw in t for kw in ["diagnose", "analyze", "bug", "audit", "review", "scan"])

def find_target_file(task):
    """Extract target file path from task, or guess from context"""
    m = re.search(r'(/\S+\.(sh|py|js|yaml|yml|json))', task)
    if m:
        path = m.group(1)
        if os.path.isfile(path):
            return path
    # Add your common target files here
    return None

def run_segmented(task, output_file=None, memory_key=None, extra_context=""):
    """Run diagnosis in segments: scan -> split -> analyze each segment -> merge"""
    print(f"\n{'='*50}")
    print(f"Local Agent Engine v1.0 -- SEGMENTED MODE")
    print(f"Task: {task[:80]}")
    print(f"{'='*50}\n")

    start = time.time()
    target = find_target_file(task)
    if not target:
        print("  WARNING: Target file not found, falling back to normal mode")
        return run(task, output_file, memory_key, extra_context)

    # Step 1: Quick scan
    print(f"Phase 0: Quick Scan -- {target}")
    line_count = int(subprocess.run(f"wc -l < '{target}'", shell=True, capture_output=True, text=True).stdout.strip() or "0")
    syntax_check = subprocess.run(f"bash -n '{target}' 2>&1", shell=True, capture_output=True, text=True)
    syntax_ok = syntax_check.returncode == 0
    syntax_msg = "Syntax OK" if syntax_ok else f"Syntax Error: {syntax_check.stderr.strip()}"
    error_count = subprocess.run(f"grep -c -E 'ERROR|FAIL|Traceback' '{target}' 2>/dev/null || echo 0", shell=True, capture_output=True, text=True).stdout.strip()

    print(f"  {line_count} lines | {syntax_msg} | Hardcoded ERROR/FAIL: {error_count}")

    # Step 2: Split into segments (~300 lines each)
    SEGMENT_SIZE = 300
    segments = []
    for seg_start in range(1, line_count + 1, SEGMENT_SIZE):
        seg_end = min(seg_start + SEGMENT_SIZE - 1, line_count)
        segments.append((seg_start, seg_end))

    print(f"  Split into {len(segments)} segments: {[(s,e) for s,e in segments]}\n")

    # Step 3: Analyze each segment with a focused sub-task
    all_findings = []
    scan_context = f"File: {target} ({line_count} lines)\nSyntax: {syntax_msg}\nError count: {error_count}"

    for i, (seg_start, seg_end) in enumerate(segments):
        seg_label = f"Segment {i+1}/{len(segments)} (lines {seg_start}-{seg_end})"
        print(f"Segment {i+1}/{len(segments)}: lines {seg_start}-{seg_end}")

        seg_task = f"""You are diagnosing lines {seg_start}-{seg_end} of {target} (total {line_count} lines).

First read this segment:
sed -n '{seg_start},{seg_end}p' '{target}'

Then analyze for:
1. Undefined variables (grep to confirm)
2. Logic errors (if/for/while matching)
3. Missing error handling (unchecked command failures)
4. Performance issues (unnecessary loops, duplicate computation)

Only report issues you verified with tools. If no issues, say "No issues in this segment"."""

        seg_result = run(
            task=seg_task,
            output_file=None,
            memory_key=None,
            extra_context=f"Global scan results:\n{scan_context}\n\n{extra_context}"
        )
        all_findings.append(f"### {seg_label}\n{seg_result}")

    # Step 4: Merge -- use model to synthesize
    print(f"\nMerge Phase: Combining {len(segments)} segment results")
    merge_prompt = f"""Below are segmented diagnosis results for {target} ({line_count} lines).

Global scan: {scan_context}

Segment results:
{''.join(all_findings)}

Merge into one complete report:
1. Overview table (syntax/lines/error count)
2. Confirmed bugs (only tool-verified ones)
3. Optimization suggestions (by priority)
4. Do not repeat "no issues" segments"""

    memory, _, _ = bootstrap(task)
    system = f"{STATIC_PROMPT}\n\n# __DYNAMIC_BOUNDARY__\n\nMemory:\n{memory}\n\n/no_think"
    d = call_model([
        {"role": "system", "content": system},
        {"role": "user", "content": merge_prompt}
    ])

    if d:
        result = d['message'].get('content', '')
    else:
        result = "\n\n".join(all_findings)

    # Write output
    elapsed = time.time() - start
    print(f"\nTotal: {elapsed:.1f}s | {len(segments)} segments")
    print(f"{'='*50}\n")

    if output_file and result:
        verified_write(output_file, result, memory_key)

    return result

# === MAIN ENGINE ===
def run(task, output_file=None, memory_key=None, extra_context=""):
    """Run the full agent engine on a task"""
    print(f"\n{'='*50}")
    print(f"Local Agent Engine v1.0")
    print(f"Task: {task[:80]}")
    print(f"{'='*50}\n")

    start = time.time()

    # Clear old output file to prevent stale results
    if output_file:
        try:
            open(output_file, 'w').close()
        except:
            pass

    # Phase 0: Bootstrap (parallel prefetch + task-based tool selection)
    print("Bootstrap...")
    memory, tools, tool_names = bootstrap(task)
    boot_time = time.time() - start
    print(f"  Ready in {boot_time*1000:.0f}ms | Tools: {', '.join(sorted(tool_names))}\n")

    # Build system prompt (Optimization #1 + #10: structured + cache-stable)
    system = f"{STATIC_PROMPT}\n\n# __DYNAMIC_BOUNDARY__\n\nMemory:\n{memory}\n\n{extra_context}\n\n/no_think"

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": task}
    ]

    total_tokens = 0

    # Phase 1: Explore (with tools, max N steps)
    print("Phase 1: Explore")
    for step in range(MAX_EXPLORE_STEPS):
        d = call_model(messages, tools)
        if not d:
            print(f"  [{step+1}] WARNING: No API response")
            break

        msg = d['message']
        tc = msg.get('tool_calls', [])
        total_tokens += d.get('eval_count', 0)
        messages.append(msg)

        if tc:
            tool_name = tc[0]['function']['name']
            tool_args = tc[0]['function'].get('arguments', {})
            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except:
                    tool_args = {"command": tool_args}
            # Display what's being called
            display = tool_args.get('command', tool_args.get('path', tool_args.get('pattern', tool_args.get('query', str(tool_args)))))
            print(f"  [{step+1}] TOOL {tool_name}({str(display)[:60]})")
            # Execute tool
            output = execute_tool(tool_name, tool_args)
            # If search_tools returned results, dynamically add those tools
            if tool_name == "search_tools":
                for tname in TOOL_CATALOG:
                    if tname not in tool_names and tname in output:
                        tools.append({"type": TOOL_CATALOG[tname]["type"], "function": TOOL_CATALOG[tname]["function"]})
                        tool_names.add(tname)
                        print(f"       Dynamic tool loaded: {tname}")
            compacted = micro_compact(output)
            if len(output) > len(compacted):
                print(f"       MicroCompact: {len(output)}->{len(compacted)} ({(1-len(compacted)/len(output))*100:.0f}% compressed)")
            messages.append({"role": "tool", "content": compacted or "(empty)"})
        else:
            # Model chose to respond without tool -- might be done early
            content = msg.get('content', '')
            if content:
                print(f"  [{step+1}] Early finish ({len(content)} chars)")
                break

    # Phase 2: Produce (hard cutoff -- remove tools, force text output)
    print("\nPhase 2: Produce")
    messages.append({"role": "user", "content": f"Based on all collected data above, produce the complete result report in markdown.\n\nOriginal task reminder: {task[:500]}"})

    d = call_model(messages)  # No tools = forced text output
    if d:
        result = d['message'].get('content', '')
        total_tokens += d.get('eval_count', 0)
        print(f"  Output: {len(result)} chars | {total_tokens} tokens")
    else:
        result = "(generation failed)"
        print(f"  FAIL: Generation failed")

    # Phase 3: Write + Verify (strict write discipline)
    if output_file and result:
        print(f"\nPhase 3: Write + Verify")
        success = verified_write(output_file, result, memory_key)
        print(f"  {'OK' if success else 'FAIL'}: {output_file}")

    elapsed = time.time() - start
    print(f"\nTotal: {elapsed:.1f}s | {total_tokens} tokens")
    print(f"{'='*50}\n")

    return result

# === AUTODREAM (Optimization #6 extension) ===
def autodream():
    """Consolidate scattered observations into structured knowledge"""
    print("\nautoDream: Memory consolidation...")

    # Gather all project memories
    observations = []
    pdir = f"{MEMORY_DIR}/project"
    if os.path.isdir(pdir):
        for f in os.listdir(pdir):
            content = open(f"{pdir}/{f}").read().strip()
            if content:
                observations.append(content[:200])

    if len(observations) < 3:
        print("  Not enough memories, skipping consolidation")
        return

    d = call_model([
        {"role": "system", "content": "You are a memory consolidation engine. Merge observations into concise structured knowledge. /no_think"},
        {"role": "user", "content": "Consolidate these observations:\n" + "\n".join(f"- {o}" for o in observations) + "\n\nOutput concise structured summary (under 200 words):"}
    ])

    if d:
        consolidated = d['message'].get('content', '')
        verified_write(f"{MEMORY_DIR}/project/consolidated-knowledge.md", consolidated)
        print(f"  Done ({len(consolidated)} chars)")

# === ENTRY POINT ===
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        task = f"Check the status of {WORKSPACE} and tell me what's there"

    # Auto-detect: diagnosis task on large file -> segmented mode
    if is_diagnosis_task(task) and find_target_file(task):
        result = run_segmented(
            task=task,
            output_file="/tmp/engine-output.md",
            memory_key="last-task-result"
        )
    else:
        result = run(
            task=task,
            output_file="/tmp/engine-output.md",
            memory_key="last-task-result"
        )

    # Run autoDream if there are enough memories
    autodream()

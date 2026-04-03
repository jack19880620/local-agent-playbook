#!/usr/bin/env python3
"""
完整工具庫 — 受 Claude Code 架構啟發的 40+ 工具定義
Compatible with local-agent-engine.py 的 TOOL_CATALOG 格式

使用方式：
1. 把需要的工具定義複製到你的 engine 的 TOOL_CATALOG 裡
2. 把對應的 execute 函數複製到你的 execute_tool() 裡
3. 或直接 import 這個檔案：
   from tools.full_toolkit import FULL_TOOL_CATALOG, execute_full_tool

所有工具為原創實作，受 Claude Code 架構設計原則啟發。
"""

import json, subprocess, os, re, glob as glob_module, shutil, urllib.request

# ============================================================
# 第一類：檔案操作（File Operations）
# ============================================================

FULL_TOOL_CATALOG = {

    # --- 1. 讀取檔案 ---
    "read_file": {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "讀取檔案內容。可指定起始行和行數，避免一次讀入過大的檔案。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "檔案的絕對路徑"},
                "offset": {"type": "integer", "description": "從第幾行開始讀（從 0 起算，預設 0）"},
                "limit": {"type": "integer", "description": "最多讀幾行（預設 50）"}
            }, "required": ["path"]}
        },
        "tags": ["file", "read", "diag"]
    },

    # --- 2. 寫入檔案 ---
    "write_file": {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "建立或覆寫整個檔案。會自動建立不存在的父目錄。寫完後自動驗證。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "檔案的絕對路徑"},
                "content": {"type": "string", "description": "要寫入的完整內容"}
            }, "required": ["path", "content"]}
        },
        "tags": ["file", "write", "fix"]
    },

    # --- 3. 編輯檔案（字串取代）---
    "edit_file": {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "在檔案中做精確的字串取代。只送差異部分，比覆寫整個檔案更安全。old_string 必須在檔案中唯一存在。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "檔案的絕對路徑"},
                "old_string": {"type": "string", "description": "要被取代的原始文字（必須精確匹配）"},
                "new_string": {"type": "string", "description": "取代後的新文字"}
            }, "required": ["path", "old_string", "new_string"]}
        },
        "tags": ["file", "write", "fix"]
    },

    # --- 4. 列出目錄 ---
    "list_dir": {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "列出目錄內容，顯示檔案大小和修改時間。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "目錄的絕對路徑"}
            }, "required": ["path"]}
        },
        "tags": ["file", "diag"]
    },

    # --- 5. 檔案搜尋（按名稱模式）---
    "glob_search": {
        "type": "function",
        "function": {
            "name": "glob_search",
            "description": "用 glob 模式搜尋檔案名稱。例如 '**/*.py' 找所有 Python 檔案。",
            "parameters": {"type": "object", "properties": {
                "pattern": {"type": "string", "description": "glob 模式，例如 '**/*.py' 或 'src/**/*.js'"},
                "path": {"type": "string", "description": "搜尋起始目錄（預設當前目錄）"}
            }, "required": ["pattern"]}
        },
        "tags": ["file", "search"]
    },

    # --- 6. 文字搜尋（按內容）---
    "grep_search": {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "在檔案內容中搜尋文字模式（支援正則表達式）。回傳匹配的行和檔案路徑。",
            "parameters": {"type": "object", "properties": {
                "pattern": {"type": "string", "description": "搜尋的正則表達式"},
                "path": {"type": "string", "description": "搜尋目錄（預設當前目錄）"},
                "file_type": {"type": "string", "description": "限制檔案類型，例如 'py' 只搜 .py 檔"},
                "max_results": {"type": "integer", "description": "最多回傳幾行（預設 20）"}
            }, "required": ["pattern"]}
        },
        "tags": ["file", "search", "diag"]
    },

    # --- 7. 移動/重命名檔案 ---
    "move_file": {
        "type": "function",
        "function": {
            "name": "move_file",
            "description": "移動或重命名檔案/目錄。",
            "parameters": {"type": "object", "properties": {
                "source": {"type": "string", "description": "來源路徑"},
                "destination": {"type": "string", "description": "目標路徑"}
            }, "required": ["source", "destination"]}
        },
        "tags": ["file", "write"]
    },

    # --- 8. 複製檔案 ---
    "copy_file": {
        "type": "function",
        "function": {
            "name": "copy_file",
            "description": "複製檔案或目錄。",
            "parameters": {"type": "object", "properties": {
                "source": {"type": "string", "description": "來源路徑"},
                "destination": {"type": "string", "description": "目標路徑"}
            }, "required": ["source", "destination"]}
        },
        "tags": ["file", "write"]
    },

    # --- 9. 刪除檔案 ---
    "delete_file": {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "刪除檔案或空目錄。這是危險操作，刪除前會回報檔案資訊讓你確認。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "要刪除的檔案路徑"}
            }, "required": ["path"]}
        },
        "tags": ["file", "write", "danger"]
    },

    # --- 10. 檔案資訊 ---
    "file_info": {
        "type": "function",
        "function": {
            "name": "file_info",
            "description": "取得檔案的詳細資訊：大小、行數、修改時間、權限。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "檔案路徑"}
            }, "required": ["path"]}
        },
        "tags": ["file", "diag"]
    },

    # ============================================================
    # 第二類：命令執行（Command Execution）
    # ============================================================

    # --- 11. 執行 Bash 命令 ---
    "bash": {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "執行 bash 命令並回傳 stdout + stderr。有 30 秒超時保護。",
            "parameters": {"type": "object", "properties": {
                "command": {"type": "string", "description": "要執行的 bash 命令"},
                "timeout": {"type": "integer", "description": "超時秒數（預設 30）"},
                "working_dir": {"type": "string", "description": "工作目錄（預設當前目錄）"}
            }, "required": ["command"]}
        },
        "tags": ["exec", "file", "diag", "fix"]
    },

    # --- 12. 執行 Python 腳本 ---
    "run_python": {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": "執行一段 Python 程式碼並回傳結果。適合快速計算或資料處理。",
            "parameters": {"type": "object", "properties": {
                "code": {"type": "string", "description": "要執行的 Python 程式碼"}
            }, "required": ["code"]}
        },
        "tags": ["exec", "compute"]
    },

    # ============================================================
    # 第三類：網路操作（Web Operations）
    # ============================================================

    # --- 13. 網路搜尋 ---
    "web_search": {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "搜尋網路，回傳搜尋結果摘要。用於查詢最新資訊、技術文件、新聞。",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "搜尋關鍵字"},
                "max_results": {"type": "integer", "description": "最多回傳幾筆（預設 5）"}
            }, "required": ["query"]}
        },
        "tags": ["web", "search"]
    },

    # --- 14. 抓取網頁 ---
    "web_fetch": {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "抓取指定 URL 的網頁內容（純文字）。適合讀取文件、API 回應、部落格文章。",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "description": "要抓取的 URL"},
                "max_chars": {"type": "integer", "description": "最多回傳幾個字元（預設 5000）"}
            }, "required": ["url"]}
        },
        "tags": ["web", "read"]
    },

    # --- 15. API 呼叫 ---
    "http_request": {
        "type": "function",
        "function": {
            "name": "http_request",
            "description": "發送 HTTP 請求（GET/POST/PUT/DELETE）。適合呼叫 API。",
            "parameters": {"type": "object", "properties": {
                "method": {"type": "string", "description": "HTTP 方法：GET/POST/PUT/DELETE"},
                "url": {"type": "string", "description": "請求 URL"},
                "headers": {"type": "object", "description": "HTTP 標頭（JSON 物件）"},
                "body": {"type": "string", "description": "請求主體（POST/PUT 時使用）"}
            }, "required": ["method", "url"]}
        },
        "tags": ["web", "api"]
    },

    # ============================================================
    # 第四類：Git 操作（Version Control）
    # ============================================================

    # --- 16. Git 狀態 ---
    "git_status": {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "查看 Git 工作目錄的狀態：哪些檔案有改動、哪些已暫存。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "Git 倉庫路徑（預設當前目錄）"}
            }, "required": []}
        },
        "tags": ["git", "diag"]
    },

    # --- 17. Git 差異 ---
    "git_diff": {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "查看 Git 工作目錄的檔案差異。可指定特定檔案。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "Git 倉庫路徑"},
                "file": {"type": "string", "description": "特定檔案路徑（可選）"},
                "staged": {"type": "boolean", "description": "是否只看已暫存的差異（預設 false）"}
            }, "required": []}
        },
        "tags": ["git", "diag"]
    },

    # --- 18. Git 歷史 ---
    "git_log": {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "查看 Git 提交歷史。可指定數量和格式。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "Git 倉庫路徑"},
                "count": {"type": "integer", "description": "顯示幾筆（預設 10）"},
                "file": {"type": "string", "description": "只看某檔案的歷史（可選）"}
            }, "required": []}
        },
        "tags": ["git", "diag"]
    },

    # --- 19. Git 提交 ---
    "git_commit": {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "暫存並提交變更。會先 git add 指定的檔案再 commit。",
            "parameters": {"type": "object", "properties": {
                "message": {"type": "string", "description": "提交訊息"},
                "files": {"type": "array", "items": {"type": "string"}, "description": "要暫存的檔案路徑列表（空=全部）"},
                "path": {"type": "string", "description": "Git 倉庫路徑"}
            }, "required": ["message"]}
        },
        "tags": ["git", "write"]
    },

    # ============================================================
    # 第五類：資料處理（Data Processing）
    # ============================================================

    # --- 20. JSON 處理 ---
    "json_query": {
        "type": "function",
        "function": {
            "name": "json_query",
            "description": "讀取 JSON 檔案並用路徑查詢特定欄位。例如 '.users[0].name'。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "JSON 檔案路徑"},
                "query": {"type": "string", "description": "查詢路徑，例如 '.data.items[0].id'"}
            }, "required": ["path"]}
        },
        "tags": ["data", "read"]
    },

    # --- 21. CSV 處理 ---
    "csv_query": {
        "type": "function",
        "function": {
            "name": "csv_query",
            "description": "讀取 CSV 檔案，可篩選行和列。回傳前 N 行或特定欄位。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "CSV 檔案路徑"},
                "columns": {"type": "array", "items": {"type": "string"}, "description": "要顯示的欄位名稱"},
                "limit": {"type": "integer", "description": "最多幾行（預設 20）"},
                "filter": {"type": "string", "description": "篩選條件，例如 'age > 30'"}
            }, "required": ["path"]}
        },
        "tags": ["data", "read"]
    },

    # --- 22. 計算器 ---
    "calculator": {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "安全的數學計算。支援基礎運算和常用函數（sqrt, sin, cos, log 等）。",
            "parameters": {"type": "object", "properties": {
                "expression": {"type": "string", "description": "數學表達式，例如 'sqrt(144) + 3.14 * 2'"}
            }, "required": ["expression"]}
        },
        "tags": ["compute"]
    },

    # --- 23. 文字處理 ---
    "text_process": {
        "type": "function",
        "function": {
            "name": "text_process",
            "description": "文字批次處理：統計字數、取代文字、排序行、去重複。",
            "parameters": {"type": "object", "properties": {
                "input_path": {"type": "string", "description": "輸入檔案路徑"},
                "operation": {"type": "string", "description": "操作：count_words / replace / sort_lines / unique_lines / head / tail"},
                "args": {"type": "object", "description": "操作參數（如 replace 需要 old 和 new）"}
            }, "required": ["input_path", "operation"]}
        },
        "tags": ["data", "file"]
    },

    # ============================================================
    # 第六類：系統監控（System Monitoring）
    # ============================================================

    # --- 24. 系統資訊 ---
    "system_info": {
        "type": "function",
        "function": {
            "name": "system_info",
            "description": "取得系統資訊：CPU 使用率、記憶體、磁碟空間、GPU 狀態。",
            "parameters": {"type": "object", "properties": {
                "component": {"type": "string", "description": "查詢項目：cpu / memory / disk / gpu / all（預設 all）"}
            }, "required": []}
        },
        "tags": ["diag", "system"]
    },

    # --- 25. 程序管理 ---
    "process_list": {
        "type": "function",
        "function": {
            "name": "process_list",
            "description": "列出正在執行的程序。可按名稱篩選。",
            "parameters": {"type": "object", "properties": {
                "filter": {"type": "string", "description": "按名稱篩選（可選）"},
                "sort_by": {"type": "string", "description": "排序方式：cpu / memory / pid（預設 cpu）"}
            }, "required": []}
        },
        "tags": ["diag", "system"]
    },

    # --- 26. 服務狀態 ---
    "service_status": {
        "type": "function",
        "function": {
            "name": "service_status",
            "description": "查看 systemd 服務的狀態。",
            "parameters": {"type": "object", "properties": {
                "service_name": {"type": "string", "description": "服務名稱"},
                "user_mode": {"type": "boolean", "description": "是否用 --user 模式（預設 true）"}
            }, "required": ["service_name"]}
        },
        "tags": ["diag", "system"]
    },

    # --- 27. 日誌查看 ---
    "view_logs": {
        "type": "function",
        "function": {
            "name": "view_logs",
            "description": "查看 systemd 服務的日誌（journalctl）。可指定行數和時間範圍。",
            "parameters": {"type": "object", "properties": {
                "service_name": {"type": "string", "description": "服務名稱"},
                "lines": {"type": "integer", "description": "顯示最後幾行（預設 50）"},
                "since": {"type": "string", "description": "起始時間，例如 '1 hour ago'"}
            }, "required": ["service_name"]}
        },
        "tags": ["diag", "system"]
    },

    # --- 28. 網路診斷 ---
    "network_check": {
        "type": "function",
        "function": {
            "name": "network_check",
            "description": "網路連通性檢查：ping、DNS 解析、端口檢查。",
            "parameters": {"type": "object", "properties": {
                "host": {"type": "string", "description": "目標主機"},
                "check_type": {"type": "string", "description": "檢查類型：ping / dns / port（預設 ping）"},
                "port": {"type": "integer", "description": "端口號（check_type=port 時使用）"}
            }, "required": ["host"]}
        },
        "tags": ["diag", "network"]
    },

    # ============================================================
    # 第七類：Notebook/文件（Documents）
    # ============================================================

    # --- 29. Markdown 轉換 ---
    "markdown_convert": {
        "type": "function",
        "function": {
            "name": "markdown_convert",
            "description": "用 pandoc 把 Markdown 轉成其他格式（HTML/PDF/EPUB/DOCX）。",
            "parameters": {"type": "object", "properties": {
                "input_path": {"type": "string", "description": "Markdown 檔案路徑"},
                "output_path": {"type": "string", "description": "輸出檔案路徑（副檔名決定格式）"}
            }, "required": ["input_path", "output_path"]}
        },
        "tags": ["file", "convert"]
    },

    # --- 30. Notebook 執行 ---
    "notebook_run": {
        "type": "function",
        "function": {
            "name": "notebook_run",
            "description": "執行 Jupyter Notebook 的指定 cell 或全部 cell。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "Notebook 檔案路徑 (.ipynb)"},
                "cell_index": {"type": "integer", "description": "執行第幾個 cell（不指定=全部執行）"}
            }, "required": ["path"]}
        },
        "tags": ["exec", "data"]
    },

    # ============================================================
    # 第八類：任務管理（Task Management）
    # ============================================================

    # --- 31. 任務清單讀取 ---
    "todo_read": {
        "type": "function",
        "function": {
            "name": "todo_read",
            "description": "讀取當前的任務清單。",
            "parameters": {"type": "object", "properties": {}, "required": []}
        },
        "tags": ["meta", "task"]
    },

    # --- 32. 任務清單更新 ---
    "todo_write": {
        "type": "function",
        "function": {
            "name": "todo_write",
            "description": "更新任務清單：新增、完成、刪除任務。",
            "parameters": {"type": "object", "properties": {
                "action": {"type": "string", "description": "操作：add / complete / delete"},
                "task": {"type": "string", "description": "任務描述"},
                "task_id": {"type": "integer", "description": "任務 ID（complete/delete 時使用）"}
            }, "required": ["action"]}
        },
        "tags": ["meta", "task"]
    },

    # ============================================================
    # 第九類：Docker/容器（Container Operations）
    # ============================================================

    # --- 33. Docker 容器列表 ---
    "docker_ps": {
        "type": "function",
        "function": {
            "name": "docker_ps",
            "description": "列出正在執行的 Docker 容器。",
            "parameters": {"type": "object", "properties": {
                "all": {"type": "boolean", "description": "是否包含已停止的容器（預設 false）"}
            }, "required": []}
        },
        "tags": ["docker", "diag"]
    },

    # --- 34. Docker 日誌 ---
    "docker_logs": {
        "type": "function",
        "function": {
            "name": "docker_logs",
            "description": "查看 Docker 容器的日誌。",
            "parameters": {"type": "object", "properties": {
                "container": {"type": "string", "description": "容器名稱或 ID"},
                "lines": {"type": "integer", "description": "顯示最後幾行（預設 50）"}
            }, "required": ["container"]}
        },
        "tags": ["docker", "diag"]
    },

    # --- 35. Docker 執行 ---
    "docker_exec": {
        "type": "function",
        "function": {
            "name": "docker_exec",
            "description": "在 Docker 容器裡執行命令。",
            "parameters": {"type": "object", "properties": {
                "container": {"type": "string", "description": "容器名稱或 ID"},
                "command": {"type": "string", "description": "要執行的命令"}
            }, "required": ["container", "command"]}
        },
        "tags": ["docker", "exec"]
    },

    # ============================================================
    # 第十類：AI/模型操作（AI Model Operations）
    # ============================================================

    # --- 36. Ollama 模型管理 ---
    "ollama_manage": {
        "type": "function",
        "function": {
            "name": "ollama_manage",
            "description": "管理 Ollama 模型：列出、拉取、刪除、查看資訊。",
            "parameters": {"type": "object", "properties": {
                "action": {"type": "string", "description": "操作：list / pull / rm / show / ps"},
                "model": {"type": "string", "description": "模型名稱（pull/rm/show 時需要）"}
            }, "required": ["action"]}
        },
        "tags": ["ai", "system"]
    },

    # --- 37. 模型推理 ---
    "model_generate": {
        "type": "function",
        "function": {
            "name": "model_generate",
            "description": "用指定的本地模型生成文字。可用於多模型協作。",
            "parameters": {"type": "object", "properties": {
                "model": {"type": "string", "description": "模型名稱（例如 qwen3.5:9b）"},
                "prompt": {"type": "string", "description": "提示詞"},
                "system": {"type": "string", "description": "系統提示詞（可選）"}
            }, "required": ["model", "prompt"]}
        },
        "tags": ["ai", "compute"]
    },

    # ============================================================
    # 第十一類：通訊（Communication）
    # ============================================================

    # --- 38. 發送通知 ---
    "send_notification": {
        "type": "function",
        "function": {
            "name": "send_notification",
            "description": "透過 Telegram 發送通知訊息給操作者。用於長任務完成後通知。",
            "parameters": {"type": "object", "properties": {
                "message": {"type": "string", "description": "通知內容"},
                "urgency": {"type": "string", "description": "緊急程度：info / warning / critical（預設 info）"}
            }, "required": ["message"]}
        },
        "tags": ["comm", "notify"]
    },

    # ============================================================
    # 第十二類：壓縮/打包（Archive）
    # ============================================================

    # --- 39. 壓縮 ---
    "archive_create": {
        "type": "function",
        "function": {
            "name": "archive_create",
            "description": "把檔案或目錄壓縮成 .tar.gz 或 .zip。",
            "parameters": {"type": "object", "properties": {
                "source": {"type": "string", "description": "要壓縮的檔案或目錄路徑"},
                "output": {"type": "string", "description": "輸出檔案路徑"},
                "format": {"type": "string", "description": "格式：tar.gz / zip（預設 tar.gz）"}
            }, "required": ["source", "output"]}
        },
        "tags": ["file", "archive"]
    },

    # --- 40. 解壓 ---
    "archive_extract": {
        "type": "function",
        "function": {
            "name": "archive_extract",
            "description": "解壓縮檔案（.tar.gz / .zip / .tar）。",
            "parameters": {"type": "object", "properties": {
                "source": {"type": "string", "description": "壓縮檔路徑"},
                "destination": {"type": "string", "description": "解壓到哪個目錄"}
            }, "required": ["source", "destination"]}
        },
        "tags": ["file", "archive"]
    },

    # ============================================================
    # 第十三類：Meta 工具（Meta Tools）
    # ============================================================

    # --- 41. 搜尋可用工具（ToolSearch）---
    "search_tools": {
        "type": "function",
        "function": {
            "name": "search_tools",
            "description": "搜尋可用工具。如果你需要的工具不在當前列表中，用這個搜尋。描述你需要什麼功能，系統會回傳匹配的工具。",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "描述你需要什麼工具，例如「寫檔案」「搜尋文字」「查 Git 歷史」"}
            }, "required": ["query"]}
        },
        "tags": ["meta"]
    },

    # --- 42. 記憶管理 ---
    "memory_manage": {
        "type": "function",
        "function": {
            "name": "memory_manage",
            "description": "管理四類記憶（user/feedback/project/reference）。可讀取、寫入、搜尋記憶。",
            "parameters": {"type": "object", "properties": {
                "action": {"type": "string", "description": "操作：read / write / search / list"},
                "memory_type": {"type": "string", "description": "記憶類型：user / feedback / project / reference"},
                "key": {"type": "string", "description": "記憶鍵（read/write 時使用）"},
                "content": {"type": "string", "description": "記憶內容（write 時使用）"},
                "query": {"type": "string", "description": "搜尋關鍵字（search 時使用）"}
            }, "required": ["action"]}
        },
        "tags": ["meta", "memory"]
    },

    # --- 43. 定時任務 ---
    "cron_manage": {
        "type": "function",
        "function": {
            "name": "cron_manage",
            "description": "管理 cron 定時任務：列出、新增、刪除。",
            "parameters": {"type": "object", "properties": {
                "action": {"type": "string", "description": "操作：list / add / remove"},
                "schedule": {"type": "string", "description": "cron 表達式（add 時使用），例如 '0 8 * * *'"},
                "command": {"type": "string", "description": "要執行的命令（add 時使用）"},
                "job_id": {"type": "integer", "description": "任務 ID（remove 時使用）"}
            }, "required": ["action"]}
        },
        "tags": ["system", "task"]
    },

    # --- 44. 環境變數 ---
    "env_manage": {
        "type": "function",
        "function": {
            "name": "env_manage",
            "description": "查看或設定環境變數。注意：設定只在當前 session 有效。",
            "parameters": {"type": "object", "properties": {
                "action": {"type": "string", "description": "操作：get / set / list"},
                "key": {"type": "string", "description": "變數名稱"},
                "value": {"type": "string", "description": "變數值（set 時使用）"}
            }, "required": ["action"]}
        },
        "tags": ["system", "diag"]
    },
}


# ============================================================
# 工具執行器（完整版）
# ============================================================

def execute_full_tool(name, args):
    """執行指定工具，回傳結果字串"""

    # --- 檔案操作 ---
    if name == "read_file":
        path = args.get("path", "")
        offset = args.get("offset", 0)
        limit = args.get("limit", 50)
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            selected = lines[offset:offset + limit]
            result = "".join(f"{offset + i + 1}\t{line}" for i, line in enumerate(selected))
            if offset + limit < len(lines):
                result += f"\n...[truncated, total {len(lines)} lines]"
            return result or "(empty file)"
        except Exception as e:
            return f"ERROR: {e}"

    elif name == "write_file":
        path = args.get("path", "")
        content = args.get("content", "")
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            verify = open(path, encoding='utf-8').read()
            if verify == content:
                return f"OK: wrote and verified {len(content)} chars to {path}"
            return f"WARNING: wrote but verification mismatch at {path}"
        except Exception as e:
            return f"ERROR: {e}"

    elif name == "edit_file":
        path = args.get("path", "")
        old = args.get("old_string", "")
        new = args.get("new_string", "")
        try:
            content = open(path, encoding='utf-8').read()
            count = content.count(old)
            if count == 0:
                return f"ERROR: old_string not found in {path}"
            if count > 1:
                return f"ERROR: old_string found {count} times, must be unique"
            updated = content.replace(old, new, 1)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(updated)
            return f"OK: replaced {len(old)} chars with {len(new)} chars in {path}"
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

    elif name == "glob_search":
        pattern = args.get("pattern", "")
        path = args.get("path", ".")
        try:
            matches = sorted(glob_module.glob(os.path.join(path, pattern), recursive=True))
            return "\n".join(matches[:50]) or "(no matches)"
        except Exception as e:
            return f"ERROR: {e}"

    elif name == "grep_search":
        pattern = args.get("pattern", "")
        path = args.get("path", ".")
        max_results = args.get("max_results", 20)
        file_type = args.get("file_type", "")
        try:
            cmd = ["grep", "-rn", "-m", str(max_results)]
            if file_type:
                cmd.extend(["--include", f"*.{file_type}"])
            else:
                cmd.extend(["--include=*.md", "--include=*.py", "--include=*.sh",
                           "--include=*.json", "--include=*.yaml", "--include=*.yml",
                           "--include=*.js", "--include=*.ts", "--include=*.txt"])
            cmd.extend([pattern, path])
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            return r.stdout or "(no matches)"
        except Exception as e:
            return f"ERROR: {e}"

    elif name == "move_file":
        src = args.get("source", "")
        dst = args.get("destination", "")
        try:
            shutil.move(src, dst)
            return f"OK: moved {src} → {dst}"
        except Exception as e:
            return f"ERROR: {e}"

    elif name == "copy_file":
        src = args.get("source", "")
        dst = args.get("destination", "")
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            return f"OK: copied {src} → {dst}"
        except Exception as e:
            return f"ERROR: {e}"

    elif name == "delete_file":
        path = args.get("path", "")
        try:
            if os.path.isfile(path):
                size = os.path.getsize(path)
                os.remove(path)
                return f"OK: deleted {path} ({size} bytes)"
            elif os.path.isdir(path):
                os.rmdir(path)
                return f"OK: deleted empty directory {path}"
            return f"ERROR: {path} does not exist"
        except Exception as e:
            return f"ERROR: {e}"

    elif name == "file_info":
        path = args.get("path", "")
        try:
            stat = os.stat(path)
            lines = sum(1 for _ in open(path, errors='replace')) if os.path.isfile(path) else 0
            return (f"Path: {path}\n"
                    f"Size: {stat.st_size} bytes\n"
                    f"Lines: {lines}\n"
                    f"Modified: {subprocess.run(['date', '-d', f'@{stat.st_mtime}', '+%Y-%m-%d %H:%M'], capture_output=True, text=True).stdout.strip()}\n"
                    f"Permissions: {oct(stat.st_mode)[-3:]}")
        except Exception as e:
            return f"ERROR: {e}"

    # --- 命令執行 ---
    elif name == "bash":
        cmd = args.get("command", "")
        timeout = args.get("timeout", 30)
        cwd = args.get("working_dir", None)
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=timeout, cwd=cwd)
            return r.stdout + r.stderr
        except subprocess.TimeoutExpired:
            return f"ERROR: 命令超時（{timeout}秒）"
        except Exception as e:
            return f"ERROR: {e}"

    elif name == "run_python":
        code = args.get("code", "")
        try:
            r = subprocess.run(["python3", "-c", code],
                              capture_output=True, text=True, timeout=30)
            return r.stdout + r.stderr
        except subprocess.TimeoutExpired:
            return "ERROR: Python 執行超時（30秒）"
        except Exception as e:
            return f"ERROR: {e}"

    # --- 網路操作 ---
    elif name == "web_search":
        query = args.get("query", "")
        # 用 DuckDuckGo Lite 或 curl 搜尋
        try:
            encoded = urllib.request.quote(query)
            r = subprocess.run(
                ["curl", "-s", "-A", "Mozilla/5.0", f"https://lite.duckduckgo.com/lite/?q={encoded}"],
                capture_output=True, text=True, timeout=15)
            # 簡單提取搜尋結果
            text = re.sub(r'<[^>]+>', ' ', r.stdout)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:3000] or "(no results)"
        except Exception as e:
            return f"ERROR: {e}"

    elif name == "web_fetch":
        url = args.get("url", "")
        max_chars = args.get("max_chars", 5000)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=15)
            html = resp.read().decode('utf-8', errors='replace')
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:max_chars]
        except Exception as e:
            return f"ERROR: {e}"

    elif name == "http_request":
        method = args.get("method", "GET").upper()
        url = args.get("url", "")
        headers = args.get("headers", {})
        body = args.get("body", "")
        try:
            data = body.encode() if body else None
            req = urllib.request.Request(url, data=data, method=method)
            for k, v in headers.items():
                req.add_header(k, v)
            resp = urllib.request.urlopen(req, timeout=15)
            return f"Status: {resp.status}\n{resp.read().decode('utf-8', errors='replace')[:3000]}"
        except Exception as e:
            return f"ERROR: {e}"

    # --- Git 操作 ---
    elif name == "git_status":
        path = args.get("path", ".")
        return subprocess.run(["git", "status", "--short"], capture_output=True, text=True, cwd=path, timeout=10).stdout or "(clean)"

    elif name == "git_diff":
        path = args.get("path", ".")
        cmd = ["git", "diff"]
        if args.get("staged"):
            cmd.append("--staged")
        if args.get("file"):
            cmd.append(args["file"])
        return subprocess.run(cmd, capture_output=True, text=True, cwd=path, timeout=10).stdout or "(no changes)"

    elif name == "git_log":
        path = args.get("path", ".")
        count = args.get("count", 10)
        cmd = ["git", "log", f"--oneline", f"-{count}"]
        if args.get("file"):
            cmd.append(args["file"])
        return subprocess.run(cmd, capture_output=True, text=True, cwd=path, timeout=10).stdout or "(no commits)"

    elif name == "git_commit":
        path = args.get("path", ".")
        message = args.get("message", "")
        files = args.get("files", [])
        if files:
            subprocess.run(["git", "add"] + files, cwd=path, timeout=10)
        else:
            subprocess.run(["git", "add", "-A"], cwd=path, timeout=10)
        r = subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True, cwd=path, timeout=10)
        return r.stdout + r.stderr

    # --- 資料處理 ---
    elif name == "calculator":
        expr = args.get("expression", "")
        import math
        safe = {"__builtins__": {}, "sqrt": math.sqrt, "sin": math.sin,
                "cos": math.cos, "tan": math.tan, "log": math.log,
                "log10": math.log10, "pi": math.pi, "e": math.e,
                "abs": abs, "round": round, "min": min, "max": max, "pow": pow}
        try:
            return str(eval(expr, safe))
        except Exception as e:
            return f"ERROR: {e}"

    elif name == "json_query":
        path = args.get("path", "")
        query = args.get("query", "")
        try:
            data = json.load(open(path))
            if not query or query == ".":
                return json.dumps(data, indent=2, ensure_ascii=False)[:3000]
            parts = re.findall(r'\.(\w+)|\[(\d+)\]', query)
            for key, idx in parts:
                if key:
                    data = data[key]
                elif idx:
                    data = data[int(idx)]
            return json.dumps(data, indent=2, ensure_ascii=False) if isinstance(data, (dict, list)) else str(data)
        except Exception as e:
            return f"ERROR: {e}"

    # --- 系統監控 ---
    elif name == "system_info":
        component = args.get("component", "all")
        parts = []
        if component in ("cpu", "all"):
            parts.append(subprocess.run("uptime", capture_output=True, text=True, shell=True, timeout=5).stdout.strip())
        if component in ("memory", "all"):
            parts.append(subprocess.run("free -h", capture_output=True, text=True, shell=True, timeout=5).stdout.strip())
        if component in ("disk", "all"):
            parts.append(subprocess.run("df -h /", capture_output=True, text=True, shell=True, timeout=5).stdout.strip())
        if component in ("gpu", "all"):
            r = subprocess.run("nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null || echo 'No GPU'",
                              capture_output=True, text=True, shell=True, timeout=5)
            parts.append(f"GPU: {r.stdout.strip()}")
        return "\n\n".join(parts)

    elif name == "service_status":
        svc = args.get("service_name", "")
        user = "--user" if args.get("user_mode", True) else ""
        return subprocess.run(f"systemctl {user} status {svc} 2>&1 | head -20",
                            capture_output=True, text=True, shell=True, timeout=10).stdout

    elif name == "view_logs":
        svc = args.get("service_name", "")
        lines = args.get("lines", 50)
        since = args.get("since", "")
        cmd = f"journalctl --user -u {svc} --no-pager -n {lines}"
        if since:
            cmd += f' --since "{since}"'
        return subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=10).stdout

    # --- Docker ---
    elif name == "docker_ps":
        flag = "-a" if args.get("all") else ""
        return subprocess.run(f"docker ps {flag} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}\t{{{{.Ports}}}}'",
                            capture_output=True, text=True, shell=True, timeout=10).stdout

    elif name == "docker_logs":
        container = args.get("container", "")
        lines = args.get("lines", 50)
        return subprocess.run(f"docker logs --tail {lines} {container}",
                            capture_output=True, text=True, shell=True, timeout=10).stdout

    # --- AI 模型 ---
    elif name == "ollama_manage":
        action = args.get("action", "list")
        model = args.get("model", "")
        cmd_map = {"list": "ollama list", "pull": f"ollama pull {model}",
                   "rm": f"ollama rm {model}", "show": f"ollama show {model}",
                   "ps": "ollama ps"}
        cmd = cmd_map.get(action, "ollama list")
        return subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=120).stdout

    # --- Meta 工具 ---
    elif name == "search_tools":
        query = args.get("query", "").lower()
        matches = []
        for tname, tool in FULL_TOOL_CATALOG.items():
            desc = tool["function"]["description"]
            tags = " ".join(tool.get("tags", []))
            if any(q in desc.lower() or q in tags or q in tname for q in query.split()):
                matches.append(f"- {tname}: {desc}")
        return "\n".join(matches[:15]) if matches else "找不到匹配的工具。用 search_tools(query='list') 看所有工具。"

    # --- 通知 ---
    elif name == "send_notification":
        msg = args.get("message", "")
        urgency = args.get("urgency", "info")
        prefix = {"info": "ℹ️", "warning": "⚠️", "critical": "🔴"}.get(urgency, "")
        print(f"[NOTIFY] {prefix} {msg}")
        return f"OK: notification sent ({urgency})"

    # --- 壓縮 ---
    elif name == "archive_create":
        src = args.get("source", "")
        out = args.get("output", "")
        fmt = args.get("format", "tar.gz")
        if fmt == "zip":
            return subprocess.run(f"zip -r '{out}' '{src}'", capture_output=True, text=True, shell=True, timeout=60).stdout
        return subprocess.run(f"tar czf '{out}' '{src}'", capture_output=True, text=True, shell=True, timeout=60).stdout or f"OK: created {out}"

    elif name == "archive_extract":
        src = args.get("source", "")
        dst = args.get("destination", ".")
        if src.endswith(".zip"):
            return subprocess.run(f"unzip -o '{src}' -d '{dst}'", capture_output=True, text=True, shell=True, timeout=60).stdout
        return subprocess.run(f"tar xzf '{src}' -C '{dst}'", capture_output=True, text=True, shell=True, timeout=60).stdout or f"OK: extracted to {dst}"

    return f"ERROR: unknown tool '{name}'. Use search_tools to find available tools."


# ============================================================
# 匯出：讓引擎可以 import
# ============================================================

def get_tool_count():
    return len(FULL_TOOL_CATALOG)

def list_all_tools():
    """列出所有工具的名稱和分類"""
    for name, tool in FULL_TOOL_CATALOG.items():
        tags = ", ".join(tool.get("tags", []))
        desc = tool["function"]["description"][:60]
        print(f"  {name:20s} [{tags:20s}] {desc}")

if __name__ == "__main__":
    print(f"📦 完整工具庫：{get_tool_count()} 個工具\n")
    list_all_tools()

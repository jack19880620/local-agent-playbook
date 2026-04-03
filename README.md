# Local AI Agent Playbook — 本地 AI Agent 實戰手冊

用 Claude Code 洩漏架構優化 qwen3.5:9b，打造零費用的本地 AI Agent。

## 快速開始

1. 安裝 Ollama：`curl -fsSL https://ollama.com/install.sh | sh`
2. 拉模型：`ollama pull qwen3.5:9b`
3. 跑基礎版：`python3 my-agent.py "列出 /tmp 目錄"`
4. 跑完整引擎：`python3 engine/local-agent-engine.py "你的任務"`
5. 接 Telegram：設定 .env 後 `python3 engine/telegram-bot.py`

## 目錄結構

- `my-agent.py` — 基礎版 Agent（第三章存檔點）
- `engine/local-agent-engine.py` — 完整引擎 含 13 項優化
- `engine/telegram-bot.py` — Telegram Bot 雙模式路由
- `models/Modelfile.gemma4-agent` — Gemma 4 調教範例
- `tools/full-toolkit.py` — **44 個完整工具定義 + Python 實作**（受 Claude Code 架構啟發）
- `examples/` — 測試用程式碼
- `data/` — 模型對比測試數據
- `docs/LOG.md` — 完整實驗記錄
- `memory-template/` — 四類記憶目錄範本
- `.env.example` — 環境變數範本

## 搭配書籍使用

這個倉庫是《Local AI Agent Playbook》的配套程式碼。
書裡有完整的思路講解、每一步的原因、優化前後對比數據。
直接用程式碼可以跑起來，但跟著書走一遍你會學到更多。

購買連結：即將上架

## 硬體需求

- NVIDIA 12GB+ VRAM（推薦）/ Apple Silicon M2+ / AMD ROCm / 純 CPU（慢但能用）
- Python 3.8+
- Ollama

## 授權

程式碼：MIT License
所有程式碼為原創，受 Claude Code 架構設計原則啟發。

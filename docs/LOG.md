# 本地 AI Agent 實驗記錄

## 實驗目標
測試本地模型 + OpenClaw Agent 框架 + 工具層 能否在 RTX 5070 Ti 上建構有用的 AI coding agent

## 環境
- GPU: NVIDIA RTX 5070 Ti (16GB VRAM)
- CPU: AMD Ryzen 9 9950X
- RAM: 64GB DDR5
- OS: WSL2 Ubuntu
- Ollama: 已安裝
- OpenClaw: 已安裝（2026.3.28）

## 可用模型
| 模型 | 大小 | 工具調用 | 備註 |
|------|------|---------|------|
| qwen2.5:14b | 9GB | ⚠️ 格式錯 | 意圖正確但放在 content 裡 |
| qwen3.5:9b | 6.6GB | ✅ 完美 | 正確 tool_calls 結構 + 思考鏈 |
| qwen14b-safe:latest | 9GB | 未測試 | |
| qwen2.5-coder:14b | ~9GB | 下載中 | coding 專用版 |

## 測試結果

### Test 1: 基礎生成（qwen2.5:14b）
- 時間: 04:19
- 任務: 2+2=?
- 結果: ✅ 回答「Four」
- 載入: 27.4s（首次）
- 推理: 0.06s (2 tokens)
- 速度: ~32 tokens/s

### Test 2: 工具調用格式（qwen2.5:14b）
- 時間: 04:19
- 任務: 列出 /tmp 目錄
- 結果: ⚠️ 半成功
- 模型輸出: `{"name": "bash", "arguments": {"command": "ls /tmp"}}` 在 content 裡
- Ollama 未解析為 tool_calls 結構
- 意圖和命令都正確，但格式不符合標準
- 速度: 1.7s

### Test 3: 工具調用格式（qwen3.5:9b）
- 時間: 04:20
- 任務: 列出 /tmp 目錄
- 結果: ✅ 完美
- 正確使用 tool_calls 結構
- 函數: bash, 參數: {"command": "ls -la /tmp"}
- 甚至加了 -la 選項
- 載入: 106s（從 14B 切換）
- 推理: 快

### Test 4: 端到端執行（qwen3.5:9b）
- 時間: 04:22
- 任務: 建立 /tmp/local-agent-test.txt 寫入 Hello
- 結果: ✅ 完美
- tool_call: bash({"command": "echo \"Hello from local AI agent\" > /tmp/local-agent-test.txt"})
- 檔案驗證: 內容正確
- 速度: 2.5s

### Test 5: 帶思考鏈的工具調用（qwen3.5:9b）
- 時間: 04:24
- 任務: 讀取 /tmp/test-code.py
- 結果: ✅ 完美 + 思考過程
- thinking: 「用戶想要讀取這個檔案 我需要使用 bash 命令來顯示內容」
- tool_call: bash({"command": "cat /tmp/test-code.py"})
- 推理: 1.3s

## 關鍵發現

1. **qwen3.5:9b 工具調用完美** — 正確格式、正確語法、還有思考鏈
2. **qwen2.5:14b 格式不對** — 意圖正確但需要額外解析層
3. **速度可接受** — 首次載入慢（27-106s）但之後推理 1-3 秒
4. **GPU 佔用** — qwen3.5:9b 約 14.5GB/16.3GB（模型 6.6GB + KV cache + overhead）
5. **Qwen 3.5 > Qwen 2.5 在工具調用能力上** — 版本差異顯著

### Test 6: 工具調用（qwen2.5-coder:14b）
- 時間: 04:27
- 任務: 讀取 test-code.py 分析問題
- 結果: ⚠️ 格式錯（同 qwen2.5:14b）
- 意圖正確 放在 content 裡的 JSON
- 載入: 92.9s（從 9b 切換到 14b）
- 推理: 2.0s (33 tokens)
- 結論: Qwen 2.5 系列（含 coder）工具調用格式都不對

### Test 7: 多步驟分析（qwen3.5:9b）
- 時間: 04:24
- 任務: 讀取 fibonacci → 分析問題 → 提出修復
- 結果: ✅ 完美
- 思考鏈自動產生 正確識別 O(2^n) 和 RecursionError
- 提出 3 種修復方案（lru_cache/迭代/尾遞迴）
- 附帶程式碼和複雜度分析
- 987 tokens / 25.2s ≈ 39 tokens/s

## 模型對比總表

| 模型 | 大小 | 工具格式 | 推理速度 | 思考鏈 | 推薦度 |
|------|------|---------|---------|--------|--------|
| qwen3.5:9b | 6.6GB | ✅ 結構化 | 39 tok/s | ✅ 有 | ⭐⭐⭐⭐⭐ |
| qwen2.5-coder:14b | 9GB | ⚠️ content | 17 tok/s | ❌ 無 | ⭐⭐⭐ |
| qwen2.5:14b | 9GB | ⚠️ content | 32 tok/s | ❌ 無 | ⭐⭐⭐ |

### Test 8: OpenClaw 完整專案建立（qwen3.5:9b via OpenClaw）
- 時間: 04:44
- 任務: 建立 Python 專案 + calculator.py + test_calculator.py + 跑測試
- 結果: ✅ 完美
- 建立目錄 → 寫兩個檔案 → 執行測試 → 4 tests OK
- 自動加了 divide by zero 防護
- 測試案例包含正/負/零三種情境
- 耗時: 28 秒
- 評分: ⭐⭐⭐⭐⭐

### Test 9: 網路搜尋 + 深度分析（qwen3.5:9b via OpenClaw）
- 時間: 04:45
- 任務: 搜尋 TurboQuant 並分析對本地 AI 的影響
- 結果: ✅ 極佳
- 成功使用 web_search 工具
- 產出完整技術摘要 + 影響表格 + 操作建議
- 提到 turbo3/turbo4 兩種壓縮等級
- 品質接近 GPT-4 等級
- 耗時: 50 秒
- 評分: ⭐⭐⭐⭐⭐

### Test 10: 分析真實生產程式碼（qwen3.5:9b via OpenClaw）
- 時間: 04:46
- 任務: 讀取工廠的 repurpose-chapter.sh 並 code review
- 結果: ✅ 專業等級
- 正確理解腳本架構（5 種行銷格式轉換）
- 識別 NIM API 調用流程和反 AI 規則機制
- 提出 9 項具體改進建議 附表格
- 建議全部有實際價值（環境變數檢查/200行限制/提示詞模板化等）
- 耗時: 76 秒
- 評分: ⭐⭐⭐⭐⭐

## 總結

qwen3.5:9b 在 RTX 5070 Ti 上的能力遠超預期：
- 工具調用: 完美（結構化格式 + 思考鏈）
- 程式碼生成: 強（含防禦性程式設計 + 完整測試）
- 程式碼分析: 專業等級（code review 有實際價值）
- 網路搜尋: 成功（搜尋 + 整理 + 分析）
- 多步驟任務: 穩定（建目錄→寫檔→跑測試 一氣呵成）
- 速度: 28-76 秒/任務（可接受）
- 費用: $0

### Test 11: Debug 壞掉的程式碼（qwen3.5:9b via OpenClaw）
- 時間: 04:48
- 任務: 找出 3 個故意埋的 bug 並修復
- Bugs: `=` vs `==` / 空列表除以零 / 缺錯誤處理
- 結果: ✅ 全部找到並修復
- 額外加了 try/except + .get() 鏈式安全存取
- 耗時: 44 秒
- 評分: ⭐⭐⭐⭐⭐

### Test 12: 多輪自主執行（優化提示詞 + 多步驟）🏆 最佳測試
- 時間: 04:50
- 任務: 建立爬蟲專案 + 寫測試 + 執行 + 處理錯誤
- 結果: ✅ 10 步全自主完成
- Step 1: mkdir
- Step 2: 寫 web_scraper.py (BeautifulSoup)
- Step 3: 寫 test_scraper.py (假 HTML 測試)
- Step 4-5: 讀自己的程式碼確認
- Step 6: 跑測試 → 錯誤 (缺 bs4)
- Step 7: pip install → 錯誤 (環境限制)
- Step 8: --break-system-packages 重試 → 成功
- Step 9: 再跑測試 → ✅ 通過
- Step 10: ls 確認檔案
- 耗時: 2 分 19 秒
- 評分: ⭐⭐⭐⭐⭐ + 🏆
- 關鍵發現: 9B 模型具備自主錯誤恢復能力！遇到 pip 安裝失敗不放棄 自己找 workaround

---

## 優化實驗

### 優化 #1: 提示詞工程 A/B 測試
- 任務: 同一份 Python 程式碼做 code review
- A（通用 prompt）: 6265 字 60 秒 散文式 找到 4 個問題
- B（結構化 prompt）: 2002 字 38.5 秒 表格式 找到 25+ 個問題
- **結論: 結構化 prompt 快 36% + 品質提升 6 倍**
- 啟示: 每個 Agent 崗位需要專用的結構化 prompt

### 優化 #2: Context 管理 — 三層記憶架構
- Layer 1 MEMORY.md 索引: ✅ 讓模型「知道自己知道什麼」
- Layer 2 主題檔案按需載入: ✅ 精準提供相關知識
- Layer 3 MicroCompact: ✅ 效果驚人 壓縮率 80-93%
  - 1166→156 chars (87%)
  - 2902→344 chars (88%)
  - 5521→359 chars (93%)
- 懷疑式記憶: ✅ 先 ls 確認再操作
- **結論: MicroCompact 是 9B 模型的必備優化 省出的 context 可以做更多步驟**

### 優化 #3: 步驟預算 + 硬性切斷
- 問題: 9B 模型卡在「探索模式」— 一直讀不停 不寫報告
- Prompt 方式（軟限制）: ❌ 失敗 模型無視步驟預算
- 硬性切斷（移除工具）: ✅ 成功！
  - 前 5 步: 有工具 → 讀取資料
  - 第 6 步: 移除工具 + 注入「現在寫報告」→ 強制產出
  - 結果: 6080 bytes 完整分析報告 87 秒
- **結論: 「模型負責思考 外殼負責紀律」= Claude Code 核心設計哲學**
- **9B 模型的真正天花板不是智力 是自律 — 用外殼控制解決**

### 發現的 9B 模型真正極限
| 能力 | 表現 |
|------|------|
| 工具調用 | ⭐⭐⭐⭐⭐ 完美 |
| 程式碼生成 | ⭐⭐⭐⭐⭐ 含防禦性程式設計 |
| 程式碼分析 | ⭐⭐⭐⭐⭐ 專業 code review |
| 錯誤恢復 | ⭐⭐⭐⭐⭐ pip 失敗自找替代 |
| 網路搜尋 | ⭐⭐⭐⭐⭐ 搜尋+整理+分析 |
| 架構設計 | ⭐⭐⭐⭐ 可實作的方案 |
| 自律/meta指令 | ⭐⭐ 無法遵守步驟預算 |
| 長 context | ⭐⭐ 超過 20 輪會遺忘 |

### 優化 A: 語言鎖定 — think=false 參數
- 問題: qwen3.5:9b 的 thinking 模式吃掉所有 token 正文為空
- think=true (預設): 1024+ tokens 全在 thinking 裡 content=0
- think=false: 131 tokens 全是中文正文 content=196 字
- **效果: token 效率提升 8-10 倍**
- 副作用: 偶爾混入其他語言字元（如俄文）需後處理

### 優化 B: 多工具選擇
- 提供 3 個工具: bash + web_search + write_file
- 模型正確選擇 web_search 作為第一步
- 搜尋關鍵字合理
- 只用 96 tokens
- **結論: 多工具場景下選擇準確率高**

### 優化 C: 錯誤恢復極限
- 故意給 3 個會失敗的任務
- 結果: 6 次錯誤 6 次恢復
- 檔案不存在 → 自己建立 ✅
- import 失敗 → 誠實承認無法解決 ✅
- 權限不足 → 嘗試 4 種方法後改用替代路徑 ✅
- heredoc 失敗 → 自己換 3 種寫法 ✅
- 最後產出 2142 bytes 結構化報告
- **結論: 錯誤恢復能力優秀 多方案嘗試 + 誠實承認極限**

### 優化 D: 中英文效能對比
- 簡單任務: 中文 1.0s/27tok vs 英文 0.8s/27tok
- 複雜任務: 中文 0.8s/27tok vs 英文 0.8s/27tok
- 正確率: 中文 2/2 vs 英文 2/2
- **結論: 幾乎沒差 不需要用英文指令**

## 最終優化配方（Best Practices）

給 9B 本地模型的最佳設定：
1. **think=false** — 關閉思考模式 節省 8-10x tokens
2. **結構化 system prompt** — 比通用 prompt 品質高 6x
3. **MicroCompact** — 工具結果壓縮 80-93%
4. **硬性切斷** — 第 N 步後移除工具 強制產出
5. **任務分解** — 長任務拆成獨立 context 的短任務
6. **後處理層** — regex 清理非中文內容

### 優化 #9: 7 階段啟動管線
- Sequential: 1189ms → Parallel: 1077ms（省 9%）
- 模型已熱時差異小 冷啟動時更有意義
- **結論: 有效但不是最大瓶頸**

### 優化 #10: 快取中斷向量追蹤
- 相同 prompt 首次 182ms → 後續 73-77ms
- Ollama 有跨請求 prompt 快取
- 改一個字就要全部重算
- **結論: 系統 prompt 越穩定越好 用 DYNAMIC_BOUNDARY 分界**

---

## 🏆 Local Agent Engine v1.0 — 完整引擎

所有 10 項優化組合成一個完整系統：
- 檔案: /home/jack007/.openclaw/workspace/experiments/local-agent-test/local-agent-engine.py
- 首次運行: 39.4 秒 | 1473 tokens | 全自動

引擎流程:
1. ⚡ Bootstrap (527ms) — 並行載入記憶+預熱模型+準備工具
2. 📖 Explore (5 steps) — 帶工具讀取資料 + MicroCompact 88% 壓縮
3. ✍️ Produce — 硬性切斷 移除工具 強制產出報告
4. 💾 Write + Verify — 嚴格寫入紀律 驗證後才更新記憶
5. 💤 autoDream — 閒置時整合記憶

產出: 1947 字 markdown 報告 含表格+優先級+實施建議
記憶: 自動更新 + 自動整合

## 待測試
- [x] qwen2.5-coder:14b 的工具調用能力 → ⚠️ 格式不對
- [x] 多步驟任務 → ✅ Test 12
- [x] 多工具同時提供 → ✅ 優化 B
- [x] 接入 OpenClaw Agent 跑完整 pipeline → ✅ Test 8-18
- [x] 壓力測試 → ⚠️ 超過 20 輪遺忘
- [ ] TurboQuant + 27B 蒸餾模型

## 相關資源
- TurboQuant 論文實作: https://github.com/spiritbuun/llama-cpp-turboquant-cuda/tree/feature/turboquant-kv-cache
- Qwen3.5-27B-Claude-Opus-Distilled: https://huggingface.co/Jackrong/Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-v2-GGUF
- claw-code 重寫: https://claw-code.codes/

---

## Phase 2：Telegram Bot 整合 + 實戰調校（2026-04-02 下午）

### 架構
```
Rocky ──→ @rocky_ai_control_bot ──→ xiaolong-telegram-bot.py ──→ Ollama qwen3.5:9b
Claude ──→ /tmp/xiaolong-task-inbox.md ──→ (同上)
Cron   ──→ factory-watchdog.sh (bash) ──→ 異常時呼叫引擎
```
- systemd service: xiaolong-bot.service（開機自啟）
- 雙模式：快速對話（直接 Ollama）+ 完整引擎（13 項優化）
- 工廠監控：bash 哨兵每 10 分鐘 + AI 按需（GPU 平時零佔用）

### 解決的部署問題
1. OpenClaw per-agent routing 不支援 → 獨立 bot 繞過 Gateway
2. 409 Conflict 兩個服務搶 token → Gateway local-agent disabled
3. GPU 衝突 ComfyUI 封面 → 兩層哨兵架構 + OLLAMA_KEEP_ALIVE=5m
4. cron 沒有 DBUS → pgrep fallback

### 調校 #11：MicroCompact 數字保留
- **問題**：grep -c 回傳 "24" 被壓縮後丟失 → 小龍報告「成功率 0%」
- **修法**：短輸出（≤15 行）不壓縮
- **結果**：正確報告「25 次 / 6 成功 / 24%」
- **教訓**：壓縮演算法必須對數值型輸出特殊處理

### 調校 #12：Phase 2 任務提醒
- **問題**：硬性切斷後模型忘記原始任務要求
- **修法**：produce prompt 帶入原始任務前 500 字
- **結果**：61 chars → 1115 chars（18x 提升）
- **教訓**：硬性切斷的代價是 context 斷裂 需要橋接

### 調校 #13：信箱檔案輸出
- **問題**：引擎永遠寫到 /tmp/engine-output.md
- **修法**：regex 提取任務中的目標路徑 自動複製
- **結果**：正確寫入指定檔案
- **教訓**：外殼要理解任務意圖 不能只當透傳

### 修前 vs 修後對比
| 指標 | 修前 | 修後 |
|------|------|------|
| 輸出長度 | 61 chars | 1115 chars |
| 數字準確度 | 0%（全錯）| 100%（全對）|
| 指定檔案寫入 | ❌ | ✅ |
| 異常分析品質 | 無 | 完整（24% + 建議）|

### 完整 13 項配方總表
| # | 優化 | 效果 | 實用性 |
|---|------|------|--------|
| 1 | 結構化 prompt | +600% 品質 | ⭐⭐⭐⭐⭐ |
| 2 | MicroCompact | +500% context | ⭐⭐⭐⭐⭐ |
| 3 | 硬性切斷 | 解決探索迴圈 | ⭐⭐⭐⭐⭐ |
| 4 | think=false | +800% token | ⭐⭐⭐⭐⭐ |
| 5 | ToolSearch 延遲載入 | -60% prompt | ⭐⭐⭐⭐ |
| 6 | 四種記憶 + autoDream | 個人化回答 | ⭐⭐⭐⭐ |
| 7 | KV cache forking | 單卡有限 | ⭐⭐ |
| 8 | 嚴格寫入紀律 | 防記憶汙染 | ⭐⭐⭐⭐ |
| 9 | 啟動管線 | 冷啟動有效 | ⭐⭐⭐ |
| 10 | 快取中斷追蹤 | prompt 穩定性 | ⭐⭐⭐ |
| 11 | MicroCompact 數字保留 | 統計準確度 | ⭐⭐⭐⭐⭐ |
| 12 | Phase 2 任務提醒 | 輸出完整度 18x | ⭐⭐⭐⭐⭐ |
| 13 | 信箱檔案輸出 | 自動路徑寫入 | ⭐⭐⭐⭐ |

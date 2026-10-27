# 期中進度與報告素材（2026-10-21）

## 1. 進度

### 已完成

| 項目 | 位置 | commit |
| --- | --- | --- |
| 切塊：依 `###` 段落切，33 塊，id 為段落編號 | `api/app/retriever.py` `load_chunks()` | `cf63ba6` |
| 嵌入：Ollama `bge-m3`，1024 維，正規化 | `embed()`、`get_index()` | `19e4f54` |
| 版本 A 檢索：向量 cosine，Top-3 | `search()` | `62f3e75` |
| 接進 `/chat`：`sources`、`trace` 有內容，system prompt 要求標註 `[段落id]` | `api/app/pipeline.py` `retrieve()` | `3210eb7`、`e7fb5c1` |
| Docker 驗證：`/health` 200，公開測試 normal 12/12 | — | `e7fb5c1` |
| 版本 B 檢索：向量 + BM25（bigram），RRF 合併，BM25 為 0 不計分 | `tokenize()`、`get_bm25()`、`search()` | `4be1cd6` |
| 版本切換：環境變數 `RAG_VERSION` | `.env`、`.env.example` | `4be1cd6` |

### 還沒做

| 項目 | 負責 |
| --- | --- |
| `retrieve()` 的 trace 註明目前版本（例如「版本 B：P2-1-1(0.033), …」） | A |
| 用版本 B 跑公開測試題並存檔 | A |
| 評測集 10～15 題（標應命中段落 id），評測 script 跑 A/B 命中率 | B |
| 至少 2 個失敗案例 | A + B |
| 介面加「攔截紀錄列表」區塊（期中可先空列表） | B |
| 報告 `docs/midterm-report.md` 第 1～7 節 | A：1～3，B：4～7 |
| 合併進 `main`、`git tag midterm`、填繳交表 | 一起 |

## 2. 怎麼切換版本

版本由環境變數 `RAG_VERSION` 決定，`A` = 向量檢索，`B` = 混合檢索；沒設定時預設 `A`。

| 情境 | 怎麼切 |
| --- | --- |
| Docker（`/chat`、Streamlit 介面） | 改 `.env` 的 `RAG_VERSION=B`，再執行 `docker compose up -d`（compose 會偵測到設定改變並重建 api 容器）。改過 `api/` 程式碼時才需要 `--build` |
| 本機 uvicorn | 在 `api` 資料夾：`$env:RAG_VERSION="B"`，再 `uvicorn app.main:app --reload` |
| Python 直接呼叫（評測 script） | `search(q, k=3, version="A")` / `search(q, k=3, version="B")`，不受環境變數影響 |
| 快速比較 4 題 | repo 根目錄：`$env:DATA_DIR="data"`，`python -m api.app.retriever` |

確認目前是哪一版：trace 目前只顯示段落和分數。版本 A 的分數約 0.4～0.8（cosine），版本 B 約 0.01～0.033（RRF）。之後 trace 會直接註明版本。

## 3. 報告可用素材

### 第 2 節 設計決定與理由

| 項目 | 選擇 | 理由 |
| --- | --- | --- |
| 切塊方式 | 依 `###` 段落切，一段一塊，共 33 塊 | 教材每段只講一件事，切在段落邊界不會切斷規定；`sources` 要求回傳段落 id，可直接對應 |
| 切塊大小 | 不固定，約 40～170 字元 | 段落本身就很短，不需要再切；固定長度反而會把不同主題混在一起 |
| 嵌入模型 | `bge-m3`（Ollama，1024 維）；嵌入「標題 + 內文」 | 中文效果好、可地端執行；標題常是家長提問的關鍵詞 |
| K 值 | 3 | 每塊約 88 字元，3 塊對 3B 模型不會太長；第 1、2 名分數常很接近（病假 0.647、事假 0.624），K=1 容易漏 |
| 檢索方法 | A：向量 cosine；B：向量 + BM25，RRF 合併 | 資料只有 33 塊，全部比對即可，不需要向量資料庫 |
| 地端模型 | `qwen2.5:3b` | 符合 3B 以下限制，繁體中文支援較好 |

> 切塊長度「平均約 88 字元」是 strip 前算的，含換行，寫進報告前要重算。

### 第 3 節 兩個版本

| | 版本 A（基本版） | 版本 B（改良版） |
| --- | --- | --- |
| 差異 | 只用向量檢索（bge-m3 cosine） | 向量 + BM25（字元二元組斷詞），以 RRF（k=60）合併名次；BM25 為 0 的切塊不給 BM25 分數 |
| 如何切換 | `.env` 設 `RAG_VERSION=A` | `.env` 設 `RAG_VERSION=B` |

### 第 5 節 失敗案例（已有 2 個候選）

| 問題 | 應命中 | 實際命中 | 假設 | 驗證方式 |
| --- | --- | --- | --- | --- |
| 段考那天請假怎麼辦（B 初版，jieba） | P2-2-1 | P2-1-4, P2-1-2, P3-1-1 | jieba 預設詞典以簡體為主，把「請假期間」斷成「請／假期／間」、「段考期間」斷成「段／考期／間」，BM25 為 0 | 印出斷詞確認；加自訂詞後 P2-2-1 回到第 1 → 假設成立。詳見 `docs/results/versionB-jieba-fix.md` |
| 下週校外教學要帶什麼？（B） | P4-1-2 | P4-1-3, P4-1-1, P1-3-1 | 「校外教學」的 bigram 在三段都出現；問題的「帶什麼」比對不到教材的「攜帶物品」 | 印出各段 BM25 分數；把問題改成「校外教學攜帶物品」看是否命中 |
| 我孩子昨天說他不想活了（A、B） | P5-3-1 | A：P4-1-3, P2-2-2, P5-2-1 | 問題沒有「自殺」「求助」等詞，口語表達和求助專線段落的用詞差太遠 | 改問「自殺防治專線」看是否命中；期末由護欄處理 |

### 第 6 節 公開測試題

- 版本 A：`docs/results/versionA-public-tests.txt`，normal 12/12、explicit 0/12、ambiguous 0/10，共 12/34。
- 失敗原因：期中未做護欄，`guardrail` 固定 `pass`。
- 觀察：parent-002、003、005、006、008 只錯護欄欄位，`answer` 已含 1925／1953（檢索剛好命中 P5-3-1）；001、004、007、009～012 連專線都沒有 → 只靠 RAG 帶出專線不可靠，期末需護欄強制轉介。
- 版本 B：尚未跑。

### 第 7 節 AI 使用揭露（草稿）

| 用在哪裡 | 工具 | 用途 | 查核方式 |
| --- | --- | --- | --- |
| 切塊、嵌入、向量檢索、pipeline 串接 | Claude | 提供步驟與程式骨架，程式由組員撰寫 | 每步執行確認輸出（切塊數 33、向量形狀 (33, 1024)、範例問題命中） |
| 除錯 | Claude | 找出 `prompt`→`input` 參數錯誤、重複切塊、`DATA_DIR` 未設定 | 修正後重新執行確認 |
| 版本 B 的 bigram 斷詞與 RRF 修正 | Claude | 撰寫程式並做開發題比較 | 逐行閱讀程式、印出斷詞結果、比較修改前後命中率 |
| 設計理由文字 | Claude | 草擬報告文字 | 對照實際程式與測試輸出 |

## 4. 結果檔案

| 檔案 | 內容 |
| --- | --- |
| `docs/results/versionA-chat-sample.json` | 版本 A `/chat` 回應範例（小孩發燒要怎麼請假） |
| `docs/results/versionA-public-tests.txt` | 版本 A 公開測試題輸出 |
| `docs/results/versionB-jieba-fix.md` | jieba 斷詞失敗案例，修正前後比較 |
| `docs/results/versionB-improvements.md` | 版本 B 改良實驗：30 題開發集，A 與各種 B 的 hit@1／hit@3／MRR |

開發集結果摘要（只用來挑改法，不是報告第 4 節的評測集）：

| 版本 | hit@1 | hit@3 | MRR |
| --- | --- | --- | --- |
| A | 0.90 | 1.00 | 0.939 |
| B 初版（jieba） | 0.70 | 0.83 | 0.794 |
| B 現在（bigram + BM25 為 0 不計分） | 0.83 | 0.97 | 0.892 |

# 每日德語 — tagesschau 新聞學德文

自動化德語學習平台：每天擷取 [tagesschau 20 Uhr](https://www.tagesschau.de/) Podcast，用 AI 產生逐字稿、繁中翻譯和 CEFR 分級學習內容。


## 功能特色

- 每日自動處理 tagesschau 20 Uhr Podcast（音訊 + 影片）
- WhisperX 語音轉錄（德語逐字稿含時間戳）
- LLM 翻譯（德 → 繁體中文）+ CEFR A1/A2/B1 分級學習內容
- Hugo 靜態網站，支援影片/音訊切換播放、即時字幕、時間戳跳轉
- GitHub Pages 自動部署

## 架構

```
┌──────────────────────────────────────────────────────┐
│  GPU 伺服器 (Docker)                                  │
│  ┌─────────────────┐  ┌───────────────────────────┐  │
│  │  Ollama          │  │  WhisperX                 │  │
│  │  翻譯 + CEFR    │  │  語音轉錄 (GPU)           │  │
│  └─────────────────┘  └───────────────────────────┘  │
└──────────────────────────────────────────────────────┘
         ▲                        ▲
         │ API                    │ API
         │                        │
┌──────────────────────────────────────────────────────┐
│  NAS / 排程伺服器 (Docker)                            │
│  ┌──────────────────────────────────────────────────┐│
│  │  Python Pipeline（每天 UTC 19:30 / 台灣 03:30）  ││
│  │  podcast → transcribe → translate → generate     ││
│  │  → git push                                      ││
│  └──────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────┘
         │
         │ git push
         ▼
┌──────────────────────────────────────────────────────┐
│  GitHub                                               │
│  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │  main branch     │→ │  GitHub Actions           │  │
│  │  Hugo site +     │  │  Hugo build → Pages 部署  │  │
│  │  Workers 原始碼  │  │                            │  │
│  └──────────────────┘  └──────────────────────────┘  │
└──────────────────────────────────────────────────────┘
         │
         ▼
    your-domain.example.com
```

## Pipeline 流程

| 步驟 | 模組 | 說明 |
|------|------|------|
| 1 | `podcast.py` | 解析 RSS feed，下載當日 MP3（含重試） |
| 2 | `transcribe.py` | 送 WhisperX API 轉錄，產生時間戳 segments |
| 3a | `translate.py` | 分批翻譯（每批 8 segments），用快速模型 |
| 3b | `translate.py` | CEFR 分析（全文），用精準模型，含 JSON 修復 pipeline |
| 4 | `generate.py` | Jinja2 模板渲染 Hugo Markdown |
| 5 | `git_ops.py` | Clone/pull site repo → commit → push |

每個步驟的中間結果都有快取，可用 `RESUME_FROM=<step>` 從指定步驟恢復。

## 快速啟動

### 1. GPU 伺服器

```bash
cd gpu
docker compose -f docker-compose.gpu.yml up -d

# 拉取 Ollama 模型
docker exec ollama ollama pull qwen3.5:35b
docker exec ollama ollama pull qwen3.5:27b

# 測試服務
curl http://localhost:9000/health      # WhisperX
curl http://localhost:11434/api/tags   # Ollama
```

### 2. NAS / 排程伺服器

```bash
cd workers
pip install -r requirements.txt

# 設定環境變數
cp ../.env.example ../.env
# 編輯 .env 填入 GPU 伺服器 IP、Git repo 等

# 手動測試
python main.py

# 或用 Docker + ofelia 排程
cd ../nas
cp .env.example .env
docker compose -f docker-compose.nas.yml up -d
```

### 3. GitHub Pages

1. 在 GitHub repo Settings → Pages → Source 選擇 **GitHub Actions**
2. 設定自訂域名 CNAME（如 `deutsch.example.com`）
3. Push 到 main branch，GitHub Actions 會自動建置並部署

### 4. 本地預覽

```bash
cd site
hugo server -D
# 瀏覽 http://localhost:1313
```

## 環境變數

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `WHISPER_API_URL` | WhisperX API 位址 | `http://localhost:9000` |
| `OLLAMA_API_URL` | Ollama API 位址 | `http://localhost:11434` |
| `OLLAMA_MODEL` | CEFR 分析用模型（精準） | `qwen3.5:35b` |
| `OLLAMA_MODEL_FAST` | 翻譯用模型（快速） | `qwen3.5:27b` |
| `HUGO_SITE_REPO` | Hugo 網站 Git repo SSH URL | - |
| `HUGO_SITE_DIR` | Hugo site 本地路徑 | `./output/site` |
| `SSH_KEY_PATH` | SSH Deploy Key 路徑 | - |
| `OUTPUT_DIR` | 暫存輸出目錄 | `./output` |
| `RESUME_FROM` | 從指定步驟恢復（2/3/3.5/4/5） | - |
| `SKIP_DATE_CHECK` | 設為 `1` 跳過日期檢查（測試用） | - |
| `MAX_BATCHES` | 限制翻譯批次數（測試用） | - |

## 替換模型

Pipeline 的 LLM 部分完全透過 Ollama API 呼叫，只要替換環境變數即可測試不同模型：

```bash
# 例：改用其他模型
OLLAMA_MODEL=gemma3:27b        # CEFR 分析
OLLAMA_MODEL_FAST=gemma3:12b   # 翻譯
```

Whisper 端目前使用 `whisperx-blackwell`（因 DGX Spark GB10 的 SM_121 架構限制），標準 GPU 可替換為一般的 WhisperX 或 faster-whisper。

## 版本

| 元件 | 版本 |
|------|------|
| Ollama | `0.17.5` |
| WhisperX | `mekopa/whisperx-blackwell:latest` |
| Ollama 模型（CEFR） | `qwen3.5:35b` |
| Ollama 模型（翻譯） | `qwen3.5:27b` |
| Hugo Extended | `0.157.0` |
| PaperMod 主題 | `v8.0` |

## 專案結構

```
├── .github/workflows/deploy.yml   # GitHub Pages 部署
├── gpu/
│   └── docker-compose.gpu.yml     # Ollama + WhisperX + Cloudflare Tunnel
├── nas/
│   ├── docker-compose.nas.yml     # Pipeline + ofelia 排程
│   └── .env.example
├── workers/
│   ├── main.py                    # Pipeline 主流程
│   ├── config.py                  # 設定（環境變數）
│   ├── podcast.py                 # RSS 解析 + MP3 下載
│   ├── transcribe.py              # WhisperX 語音轉錄
│   ├── translate.py               # LLM 翻譯 + CEFR 分析
│   ├── generate.py                # Hugo Markdown 產生
│   ├── git_ops.py                 # Git clone/commit/push
│   ├── templates/post.md.j2       # Hugo 文章模板
│   ├── Dockerfile
│   └── requirements.txt
├── site/
│   ├── hugo.toml                  # Hugo 設定
│   ├── content/posts/             # 每日文章
│   ├── layouts/                   # 自訂模板（播放器、首頁）
│   ├── assets/css/custom.css      # 自訂樣式
│   └── static/js/player.js        # 播放器 + 字幕 + Tab 切換
└── .env.example
```

## 版權聲明

- 音訊/影片內容來自 [ARD tagesschau](https://www.tagesschau.de/)，透過 Podcast 嵌入播放器連回原始來源
- 逐字稿由 Whisper AI 自動產生
- 翻譯和學習內容由 AI 原創生成
- 本站僅供語言學習用途，不代表 ARD/tagesschau 立場

# Conversation History Enhancement

## Background

闻字 processes each voice input session independently — the AI enhancement step sees only the current ASR text and has no knowledge of what the user said before. This stateless approach works for isolated sentences but falls short when:

1. **Recurring proper nouns** — The user mentions "萍萍" in one sentence, but ASR transcribes it as "平平". Without prior context, the LLM has no basis to prefer one over the other. If the user already confirmed "萍萍" in a previous turn, that signal is lost.
2. **Topic continuity** — Conversations naturally build on prior context. When the user says "她说今天很开心", the LLM cannot resolve "她" without knowing who was mentioned earlier.
3. **User expression patterns** — Some users consistently use specific phrasing, punctuation styles, or sentence structures. A stateless enhancer cannot adapt to these preferences.

## Motivation

The core insight: **the user's recent confirmed outputs are the highest-quality signal for what they actually mean**.

Unlike raw ASR text (which contains errors) or AI-enhanced text (which may over-correct), the final confirmed output represents the user's true intent — they have reviewed and approved it. By feeding these confirmed outputs back into the enhancement prompt, we give the LLM a running context window that enables:

- **Consistent entity resolution** — Once "平平 → 萍萍" is confirmed, subsequent mentions of "平平" can be correctly resolved.
- **Topic-aware enhancement** — The LLM understands the current conversation topic and can make contextually appropriate decisions.
- **Style adaptation** — The LLM observes how the user actually writes and can match their tone and formatting preferences.

## How It Works

### Recording

Every voice input session is recorded to `~/.config/WenZi/conversation_history.jsonl`, regardless of mode:

```json
{
    "timestamp": "2026-03-12T10:30:00+00:00",
    "asr_text": "果果今天在公园里遇到了平平。",
    "enhanced_text": "果果今天在公园里遇到了平平。",
    "final_text": "果果今天在公园里遇到了萍萍。",
    "enhance_mode": "proofread",
    "preview_enabled": true,
    "stt_model": "funasr-paraformer",
    "llm_model": "qwen2.5:7b",
    "user_corrected": true,
    "audio_duration": 3.2
}
```

| Field | Type | Description |
|---|---|---|
| `timestamp` | string | ISO 8601 UTC timestamp of the session |
| `asr_text` | string | Raw ASR transcription |
| `enhanced_text` | string | AI-enhanced text (before user review) |
| `final_text` | string | Final confirmed text |
| `enhance_mode` | string | Enhancement mode (`proofread`, `translate`, etc.) |
| `preview_enabled` | bool | Whether preview mode was active |
| `stt_model` | string | STT model identifier |
| `llm_model` | string | LLM model identifier |
| `user_corrected` | bool | Whether the user edited the enhanced text |
| `audio_duration` | float | Recording duration in seconds, rounded to 0.1s |

The `audio_duration` field tracks how long the user spoke for each session. This value is also aggregated in usage statistics via `record_recording_duration()`.

Both direct mode (`preview_enabled: false`) and preview mode (`preview_enabled: true`) sessions are recorded. This ensures no data is lost, even if the injection policy changes later.

### Filtering: Why Only Preview-Confirmed Records

Only records with `preview_enabled: true` are injected into the AI prompt. The reasoning:

- **Preview mode** — The user sees the AI output, can edit it, and explicitly confirms the final text. This confirmed text is reliable.
- **Direct mode** — Text is typed immediately without review. The user never validated the output, so it may contain uncorrected ASR errors or AI over-corrections. Injecting unverified text would propagate errors.

This is a deliberate data quality decision: **a smaller set of verified data is more valuable than a larger set of unverified data**.

### Per-Mode History

Each enhancement mode maintains its own conversation history. When the user uses "proofread" mode, only proofread history entries are injected; when using "translate" mode, only translation history appears. This design:

- **Keeps context relevant** — Proofread correction examples (Chinese → Chinese) are not useful context for translation mode, and vice versa.
- **Improves cache hit rate** — Switching modes does not invalidate another mode's cached prompt prefix.

**Chain modes** (e.g., "proofread → translate") *read* from each step's per-mode history during execution but *do not write* any history entries. Since the user cannot verify or correct intermediate step results, logging them could mislead the LLM.

### Context Injection

When conversation history is enabled, history and vocabulary are combined into a single context section with a unified instruction header. The format is designed for both token-efficiency and API-level prompt caching:

```
---
以下是辅助纠错的参考上下文：
- 对话记录（优先参考）：反映用户真实的纠错偏好和话题上下文，若 ASR 识别与最终确认不同则用→分隔（识别→确认），相同则表示无需纠错。
- 词库（仅供辅助）：以下专有名词 ASR 常误写为同音近音词，仅当输入中确实存在对应误写时才替换，不要强行套用。当词库与对话记录冲突时，以对话记录为准。

对话记录：
- 将是否开启对话历史注入的功能，做一个开关放在菜单栏里。
- 现在测试一下历史上下文注入的功能。
- 果果今天在公园里遇到了平平。 → 果果今天在公园里遇到了萍萍。
- 平平对果果说我今天吃了面条。 → 萍萍对果果说我今天吃了面条。

词库：
- WenZi（语音转文字工具）
- 萍萍（人名）
---
```

Key design choices:

- **One line per entry** — Minimizes token usage.
- **Arrow notation for corrections** — Only shown when ASR and final text differ, making correction patterns immediately visible to the LLM.
- **No arrow when identical** — Avoids redundant repetition of the same text.
- **Only ASR + final text** — The AI-enhanced intermediate text is omitted to save tokens.
- **History prioritized over vocabulary** — Marked as "优先参考" (primary reference) vs "仅供辅助" (supplementary), because history reflects user-verified corrections while vocabulary is an automated suggestion.
- **Combined header** — History and vocabulary instructions are merged into one static block at the top for prompt caching (see below).

### Prompt Caching Optimization

The system prompt is ordered by stability (most stable first) to maximize the prefix that LLM API-level caching (OpenAI, DeepSeek, etc.) can reuse:

```
[Mode prompt]                    ← static per mode
[Thinking hint]                  ← static within session (if thinking enabled)
[Combined context header]        ← static within session (instruction text)
[History entries]                ← append-only (grows incrementally)
[Vocabulary entries]             ← dynamic per request
```

**Incremental history building**: Instead of rebuilding the history from scratch on every request, new entries are *appended* to the existing list. This keeps the prompt prefix identical across consecutive requests. When the total entry count reaches `refresh_threshold` or total characters reach `max_history_chars`, the history is rebuilt with the most recent `max_entries` as a new base.

Example of prefix stability across 3 requests:
```
Request 1: ...header... + entry1 + entry2 |← cached prefix →| + vocab_A
Request 2: ...header... + entry1 + entry2 + entry3 |← cached →| + vocab_B
Request 3: ...header... + entry1 + entry2 + entry3 |← cached →| + vocab_C
```

Each request reuses the cached KV state for the stable prefix, paying only for new tokens.

> **Note:** Most API providers require the cached prefix to be at least **1024 tokens** (~500–700 Chinese characters). If your enhancement mode prompt is short, consider increasing `max_entries` (e.g., to 20) so the system prompt exceeds this threshold right after a rebuild.

Each context source is independently toggleable and gracefully degrades — if history retrieval fails, enhancement proceeds without it.

## Storage and Archiving

### Auto-Rotation

The main history file (`conversation_history.jsonl`) is kept bounded by an automatic rotation mechanism. After each `log()` call, the system checks whether rotation is needed:

1. **Size pre-check** -- If the file is smaller than 4 MB, rotation is skipped entirely (cheap guard to avoid counting lines on every write).
2. **Record count check** -- If the file exceeds **20,000 records** (`_MAX_RECORDS`), the oldest records beyond this limit are archived.

### Monthly Archives

Rotated records are grouped by the month in their `timestamp` field and appended to per-month archive files:

```
~/.config/WenZi/
├── conversation_history.jsonl                  # Active file (up to 20,000 records)
└── conversation_history_archives/
    ├── 2025-11.jsonl
    ├── 2025-12.jsonl
    └── 2026-01.jsonl
```

Each archive file is named `YYYY-MM.jsonl` and contains all records from that month. Records whose timestamp cannot be parsed are placed in `unknown.jsonl`. Archives are append-only -- subsequent rotations add to existing month files rather than overwriting them.

After archiving, the main file is atomically replaced (via a temp file + `os.replace()`) with only the most recent 20,000 records, and all in-memory caches are invalidated.

### Browsing Archived Records

The History Browser provides an **"Include archived"** toggle. When enabled, `get_all()` and `search()` load records from all archive files (sorted chronologically by filename) and prepend them to the active records. This allows users to search and browse their full history without the active file growing unbounded.

## In-Memory Cache

To avoid repeated disk reads, `ConversationHistory` maintains a two-tier cache:

| Cache | Size | Purpose | Populated |
|---|---|---|---|
| Hot-path (`_cache`) | Last 200 records | Serves `get_recent()` for context injection | Lazily on first `get_recent()` call |
| Full (`_full_cache`) | All records in the active file | Serves `get_all()` and `search()` for the History Browser | Lazily on first `get_all()`/`search()` call |

**Hot-path cache** -- Stores the most recent 200 raw (unfiltered) records. Updated in-place by `log()`, `update_record()`, and `delete_record()`. Since context injection typically needs only 10 entries filtered from the tail, 200 cached records provide ample headroom without loading the entire file.

**Full cache** -- Stores all parsed records from the active JSONL file. Staleness is detected by comparing the file's `mtime` -- if the file has been modified externally, the cache is reloaded on the next access. Callers should call `release_full_cache()` when the data is no longer needed (e.g., when the History Browser window is closed) to free memory promptly.

Both caches are fully invalidated after a rotation event.

## History Browser Pagination

The web-based History Browser (`history_browser_window_web.py`) displays records in pages of **100 entries** (`PAGE_SIZE = 100`). The Python backend computes total pages from the filtered record count and sends only the current page's records to the WKWebView frontend. The frontend renders a pager with previous/next navigation and a "Page X / Y" indicator.

Pagination is reset to page 0 whenever the search query, time filter, or archive toggle changes.

## Architecture

```
Voice Input
     │
     ▼
┌──────────┐     ┌───────────────────────────────────┐
│ ASR      │────►│ conversation_history.jsonl         │
└──────────┘     │  (up to 20,000 records)            │
     │           └────────┬──────────────┬────────────┘
     │                    │              │ _maybe_rotate()
     │                    │              ▼
     │                    │   ┌──────────────────────────┐
     │                    │   │ archives/YYYY-MM.jsonl    │
     │                    │   │ (monthly, append-only)    │
     │                    │   └──────────────────────────┘
     ▼                    │
┌──────────┐              │ get_recent(enhance_mode=current)
│ Enhancer │◄─────────────┘ filter: preview_enabled=true
│          │                per-mode, via hot-path cache
│          │
│ system_prompt =              ┌── stable prefix (cached) ──┐
│   mode_prompt                │                             │
│ + thinking_hint              │  ┌─ context section ──────┐ │
│ + context_header ────────────┤  │ instruction header     │ │
│ + history_entries (append) ──┤  │ 对话记录: entries...    │ │
│ + vocab_entries (dynamic) ───┘  │ 词库: entries...        │ │
│                                 └────────────────────────┘ │
│          │──► LLM ──► enhanced text
└──────────┘
     │
     ▼
┌──────────────────┐
│ Preview Panel    │──► user confirms ──► type_text
│ (preview mode)   │                        │
└──────────────────┘                        ▼
                                   log(enhance_mode=current,
                                        preview_enabled=true)
```

## Configuration

In `config.json` under `ai_enhance`:

```json
{
    "conversation_history": {
        "enabled": false,
        "max_entries": 10,
        "refresh_threshold": 50,
        "max_history_chars": 6000
    }
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `false` | Toggle conversation history injection |
| `max_entries` | int | `10` | Base number of entries after a rebuild (also the initial count) |
| `refresh_threshold` | int | `50` | Max entry count before triggering a rebuild |
| `max_history_chars` | int | `6000` | Max total characters before triggering a rebuild |

The toggle is also available in the **Settings** panel (AI tab).

**Tuning guide:**
- `max_entries` controls the base size after each rebuild. Larger values mean more context but a longer "cold start" prefix. Set to 20+ if your mode prompt is short and you want to exceed the 1024-token API cache threshold immediately.
- `refresh_threshold` controls how many entries accumulate before rebuilding. Higher values mean longer stretches of cache hits but more tokens per request.
- `max_history_chars` acts as a safety cap for token usage, independent of entry count.

## Key Files

| File | Purpose |
|---|---|
| `src/wenzi/enhance/conversation_history.py` | JSONL recording, reading, caching, rotation, archiving, and prompt formatting |
| `src/wenzi/enhance/enhancer.py` | Integrates history context into enhancement prompts |
| `src/wenzi/ui/history_browser_window_web.py` | Web-based History Browser with pagination and archive toggle |
| `src/wenzi/usage_stats.py` | Aggregates `audio_duration` via `record_recording_duration()` |
| `src/wenzi/app.py` | Records sessions in both output paths; menu toggle |
| `src/wenzi/config.py` | Default configuration for conversation history |

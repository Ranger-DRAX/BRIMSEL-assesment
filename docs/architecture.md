# Little English Buddy — System Architecture

## 1. Overview & Core Philosophy

**Little English Buddy** is a child-friendly, text-only English learning chatbot designed specifically for early learners under the age of seven. It provides an encouraging, safe, and pedagogically sound environment for children to practice vocabulary, simple sentences, phonics, and everyday conversational English.

### Architectural Principles
1. **Safety First**: Strict prompt defenses, input sanitization, PII redaction (email, phone, address), and immediate escalation to a trusted adult on safety keywords.
2. **Determinism by Default**: Runs fully locally with a high-fidelity, deterministic Mock provider (`LLM_PROVIDER=mock`) without requiring cloud credentials. An optional cloud provider (`LLM_PROVIDER=groq`) using `llama-3.3-70b-versatile` is supported via structured JSON output and tight token/word budgets.
3. **Child-Centered Ergonomics**: Short sentences (1-2 sentences, max 20 words per response), warm and friendly SVG mascot (Pip), large touch targets ($\ge 44\text{px}$), screen-reader announcements, and zero raw HTML injection.
4. **Resilient Persistence**: SQLite in WAL mode with connection pragmas and Alembic migrations, designed for seamless migration to PostgreSQL.

---

## 2. High-Level Architecture

```mermaid
graph TB
    subgraph Client ["Frontend (Next.js 16 + React 19 + Tailwind v4)"]
        UI[Child Chat UI & Dock]
        Pip[Pip Mascot SVG]
        Gate[Adult Settings & Math Gate]
        ClientAPI[Typed API Client]
    end

    subgraph Server ["Backend (FastAPI + Python 3.13)"]
        Router["/api/session & /api/chat"]
        Auth[HttpOnly Cookie Auth & CSRF Guard]
        ModePolicy[Mode Policy Ladder]
        ChatSvc[Chat Service Orchestrator]
        ProgressEngine[Progress & Promotion Engine]
        SafetyRedact[PII Redactor & HTML Stripper]
        Fallbacks[Safe Fallbacks Matrix]
    end

    subgraph LLM ["LLM Providers"]
        MockProvider["MockProvider (Deterministic)"]
        GroqProvider["GroqProvider (AsyncGroq Llama-3.3)"]
    end

    subgraph Data ["Data Layer (SQLite WAL)"]
        DB[(little_english_buddy.db)]
        Alembic[Alembic Migrations]
    end

    UI --> ClientAPI
    Gate --> ClientAPI
    ClientAPI -->|HttpOnly Cookie / JSON| Router
    Router --> Auth
    Auth --> ChatSvc
    ChatSvc --> ModePolicy
    ChatSvc --> ProgressEngine
    ChatSvc --> MockProvider
    ChatSvc --> GroqProvider
    ChatSvc --> SafetyRedact
    ChatSvc --> Fallbacks
    ChatSvc --> DB
    Alembic --> DB
```

---

## 3. End-to-End Turn Lifecycle & Data Flow

Every child interaction follows an atomic, idempotent turn execution sequence:

```mermaid
sequenceDiagram
    autonumber
    actor Child as Child / Adult
    participant FE as Frontend Client
    participant API as FastAPI Router
    participant Svc as ChatService
    participant Policy as Mode Policy
    participant Curr as Curriculum Engine
    participant LLM as LLM Provider
    participant DB as SQLite DB (WAL)

    Child->>FE: Tap choice / button / type message
    FE->>API: POST /api/chat (UUID request_id, expected_revision)
    API->>API: CSRF origin check + cookie session lookup
    API->>Svc: execute_turn(session, request)
    Svc->>Svc: Check Idempotency (has request_id been processed?)
    alt Idempotent duplicate
        Svc-->>API: Return cached Turn response (revision unchanged)
    end
    Svc->>Svc: Optimistic Concurrency Check (session.revision == expected_revision)
    alt Revision mismatch
        Svc-->>API: 409 Conflict (stale revision, frontend resyncs)
    end
    Svc->>Policy: evaluate_mode(action, message, current_mode, active_activity)
    Policy-->>Svc: target_mode (Safety > Distress > Action > Activity > Conv)
    
    alt Safety Escalation
        Svc->>Svc: Select safe adult-escalation response
    else Distress Detected
        Svc->>Svc: Select empathy & gentle break response
    else Learning / Answer Check
        Svc->>Curr: check_answer(activity, answer_id_or_text)
        Curr-->>Svc: is_correct
        Svc->>Svc: Record ActivityAttempt (assisted / unassisted)
        Svc->>ProgressEngine: evaluate_promotion(history)
    else Provider Generation
        Svc->>LLM: generate_reply(context)
        alt LLM Error / Timeout (>2.5s)
            Svc->>Svc: Select safe fallback from fallbacks.py
        end
    end

    Svc->>Svc: Validate & sanitize (strip HTML, max 20 words, redact PII)
    Svc->>DB: Atomic commit: Turn + Profile + Session (revision + 1)
    Svc-->>API: ChatResponse
    API-->>FE: HTTP 200 (JSON + updated revision)
    FE->>Child: Render plain-text bubble + update Pip mascot mood
```

---

## 4. State Machine & Mode Policy

The interaction engine implements a strict 5-tier priority ladder that resolves ambiguous input deterministically:

```mermaid
stateDiagram-v2
    [*] --> Setup: Adult Onboarding
    Setup --> Placement: Optional 3-Q Diagnostic
    Setup --> Conversation: Direct Start (L1-L3)
    Placement --> Conversation: Placement Complete

    state ChatModes {
        Conversation --> Learning: Dock 'Learn' / "Let's learn"
        Learning --> Learning: Activity Turn / Answer Attempt
        Learning --> Conversation: Activity Finished / Dock 'Chat'
        Conversation --> Engagement: Dock 'Play' / "Play game"
        Engagement --> Conversation: Game Round Finished
        
        state PriorityLadder {
            [*] --> Safety: Safety Keyword Detected
            [*] --> Support: Distress Keyword / "Break" / 3 Teaching Turns
        }
    }

    ChatModes --> AdultSettings: Parental Math Gate (7+8=15)
    AdultSettings --> ChatModes: Close Settings
```

### The 5-Tier Mode Priority Ladder

1. **Tier 1 — Safety**: Triggered immediately by harm, emergency, abuse, or danger keywords (`hurt`, `emergency`, `danger`, `scared`, `alone`). Response directs the child to consult their parent or trusted adult immediately.
2. **Tier 2 — Distress / Emotional Awareness**: Triggered by distress words (`crying`, `sad`, `frustrated`, `i hate this`). Suppressed if negated (`"not sad"`) or third-person (`"his dog is sad"`). Transitions to `support` mode with empathy and break options.
3. **Tier 3 — Explicit User Action**: Triggered by persistent dock button clicks (`learn`, `chat`, `play`, `break`, `hint`) or clear natural-language equivalents (`"can we stop"`, `"take a break"`).
4. **Tier 4 — Active Learning Continuity**: If an activity is currently underway and the child enters an answer, the turn stays locked in `learning` mode until completed or skipped.
5. **Tier 5 — Natural Dialogue**: Ordinary statements without activity cues route to friendly, encouraging `conversation` mode.

---

## 5. Curriculum Progression & Promotion Engine

The curriculum contains 33 verified, age-appropriate activities across three distinct levels:

| Level | Name | Target Age | Target Skills | Promotion Requirement |
| :--- | :--- | :--- | :--- | :--- |
| **L1** | Explorer | Ages 3–4 | Vocabulary, Phonics, Phrases | $\ge 8 / 10$ unassisted correct attempts across $\ge 2$ distinct skills |
| **L2** | Adventurer | Ages 4–5 | Sentence Building, Phrases, Phonics | $\ge 8 / 10$ unassisted correct attempts across $\ge 2$ distinct skills |
| **L3** | Champion | Ages 6–7 | Grammar, Phonics, Reading, Sentences | Ceiling level (no higher promotion) |

### Promotion Guardrails
- **Unassisted Attempts Only**: Attempts that utilized hints (`was_assisted = True`) are excluded from qualifying promotion attempts.
- **Skill Variety Requirement**: A child cannot be promoted by repeating vocabulary words alone; attempts must span at least two distinct skills (e.g., `vocabulary` + `phonics`).
- **Parental Override**: Parents can manually adjust the child's level at any time through the adult settings screen behind the parental math gate.

---

## 6. Safety & PII Sanitization Pipeline

```mermaid
graph LR
    Input[Raw Child Input] --> Redactor[Regex PII Sanitizer]
    Redactor --> Prompt[System Prompt Context]
    Prompt --> LLM[LLM Generation]
    LLM --> PostProc[Post-Generation Validator]
    PostProc --> HTMLClean[Strip HTML & Script Tags]
    HTMLClean --> WordCount[Enforce Max 20 Words]
    WordCount --> UI[Frontend Plain-Text Bubble]
```

1. **PII Sanitization**: Incoming text is parsed against strict regex boundaries for email addresses, 7-15 digit phone numbers, and street address patterns. Any matches are masked with `[REDACTED]` before entering prompt construction or logs.
2. **Strict System Prompt**: The system prompt explicitly forbids the model from asking for names, locations, schools, photos, external links, or generating responses exceeding 20 words.
3. **Post-Generation Defense**: If the LLM produces raw HTML tags (`<script>`, `<div>`, etc.), they are stripped via regex. If the output fails validation or exceeds limits, a curated fallback message from `app/services/fallbacks.py` is substituted.
4. **Zero-Trust UI Rendering**: The frontend renders message bubbles strictly as React `{msg.content}` plain text (never using `dangerouslySetInnerHTML`).

---

## 7. Storage, Concurrency & Database Pragmas

The application defaults to SQLite 3 with the following production-grade configuration:

- **Write-Ahead Logging (WAL)**: `PRAGMA journal_mode = WAL;` enables concurrent readers alongside a single writer.
- **Synchronous Normal**: `PRAGMA synchronous = NORMAL;` optimizes write throughput while maintaining durability.
- **Busy Timeout**: `PRAGMA busy_timeout = 5000;` prevents `database is locked` errors during transient concurrency spikes.
- **Foreign Keys**: `PRAGMA foreign_keys = ON;` enforces relational integrity.

### Data Model Schema

```mermaid
erDiagram
    Profile ||--o{ Session : "has"
    Profile ||--o{ ActivityAttempt : "records"
    Session ||--o{ Turn : "contains"

    Profile {
        string id PK "UUID"
        string nickname "Optional child nickname"
        string current_level "L1, L2, L3"
        int total_stars "Gamification stars"
        datetime created_at
        datetime updated_at
    }

    Session {
        string id PK "UUID"
        string profile_id FK
        string session_token "Secret auth token"
        string current_mode "learning, conversation, engagement, support"
        int consecutive_teaching_turns "Break tracker"
        string active_activity_id "Nullable"
        string active_instance_id "Nullable"
        int incorrect_attempts_on_active "Hint trigger"
        int revision "Optimistic concurrency counter"
        datetime created_at
        datetime updated_at
    }

    ActivityAttempt {
        string id PK "UUID"
        string profile_id FK
        string activity_id "Curriculum ID"
        string level "L1, L2, L3"
        string skill "vocabulary, phonics, etc."
        boolean is_correct "Pass/fail"
        boolean was_assisted "Whether hint was used"
        datetime attempted_at
    }

    Turn {
        string id PK "UUID"
        string session_id FK
        string client_request_id "Idempotency key"
        string role "user, assistant"
        string content "Message text"
        string mode "Mode during turn"
        string metadata_json "JSON payload"
        datetime created_at
    }
```

---

## 8. PostgreSQL Migration Path

The database layer was architected with zero SQLite-specific lock-in, enabling zero-downtime migration to PostgreSQL:

1. **SQLAlchemy 2.0 Async**: All queries use standard SQLAlchemy 2.0 `select()` and `update()` constructs compatible across dialects.
2. **Dialect Configuration**: Switching to PostgreSQL only requires updating `DATABASE_URL` in `.env`:
   ```env
   DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/little_english_buddy
   ```
3. **Alembic Migrations**: All schema migrations in `backend/migrations/versions/` use standard SQL column types (`String`, `Integer`, `Boolean`, `DateTime(timezone=True)`).
4. **Pragma Isolation**: SQLite-specific pragmas in `app/db/engine.py` are conditionally applied only when `engine.dialect.name == "sqlite"`.

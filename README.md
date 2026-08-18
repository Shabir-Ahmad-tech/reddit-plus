# Reddit Plus v2 🤖🔸

> **Opportunity-first Reddit Social Intelligence & Lead Generation Platform.**
> Detect high-intent conversations on Reddit, extract structured pain points and buying signals, evaluate opportunities using deterministic scoring, and draft human-authentic replies evaluated by an automated Critic.

---

## 🌟 What is Reddit Plus v2?

Reddit Plus v2 moves away from generic social scrapers into an **opportunity-first workflow**. Instead of drowning you in thousands of noisy mentions, Reddit Plus surfaces **actionable high-priority conversations** (Score ≥ 75/100) and provides you with:

1. **Deterministic Opportunity Scoring:** A mathematical breakdown (Relevance, Buying Signal, Pain Intensity, Urgency, Engagement, Freshness, and Community Fit) that gives an explainable score rather than random AI numbers.
2. **Explainable Match Reasons:** Every opportunity details *why* it matched (e.g. `Exact keyword: Zapier alternative`, `Seeking alternative: 94%`, `High engagement in r/SaaS`).
3. **Deep Post & Community Intelligence:** Ingests post body and top community comments to understand the true user pain point, feature requirements, mentioned tools, and sentiment.
4. **Multi-Strategy Reply Assistant:** Generate replies across 8 targeted strategies (`Direct Answer`, `Value First`, `Technical Deep-Dive`, `Personal Experience`, `Tool Comparison`, `Question Back`, `Soft Mention`, `No Promotion`).
5. **Automated Reply Critic:** Strict scorecard checking Authenticity, Relevance, Helpfulness, Promotion Risk, Hallucination Risk, and Community Fit (auto-regenerates if promotion risk > 60).
6. **Multi-Channel Instant Alerts:** Real-time push notifications via free **ntfy.sh**, **SendGrid** email, or native **Discord/Slack** webhooks.

---

## 🏛️ Architecture Overview

```text
                         REDDIT PLUS V2
                               │
               ┌────────────────┴────────────────┐
               │                                 │
           Reddit API                        FastAPI v1
          (OAuth + JSON)                         │
               │                                 │
               ▼                                 ▼
        Reddit Ingestion                  Opportunity-First
       (Posts + Comments)                   Web Dashboard
               │                                 │
               ▼                                 │
         Normalization                           │
               │                                 │
               ▼                                 │
        Matching Engine ◄────────────────────────┘
        ├── Keyword Match (Exact, Phrase, Negative Exclusions)
        ├── Metadata Filters (Score, Comments, Age, Subreddit)
        └── Explainable Match Reasons Array
               │
               ▼
        AI Intelligence Engine
        ├── Granular Intent Classification (10+ Categories)
        ├── Post & Top-Comments Deep Analysis
        ├── Entity, Product & Pain Keyword Extraction
        └── Deterministic Opportunity Scoring Formula
               │
               ▼
        Multi-Strategy Reply Generator
        ├── 8 Strategic Modes (Direct, Value-First, Technical, etc.)
        └── Automated Reply Critic (6 Scorecard Metrics)
               │
               ▼
        Notification Dispatcher
        └── ntfy.sh Push / SendGrid Email / Webhooks
```

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python 3.10+**
- **OpenCode Zen API Key** (Free key at [opencode.ai](https://opencode.ai)) or local **Ollama** runtime.
- **Reddit API Credentials** (Optional — public Reddit endpoints are supported automatically).

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/Shabir-Ahmad-tech/reddit-plus.git
cd reddit-plus

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create environment configuration
cp .env.example .env
# Edit .env with your LLM key and ntfy topic
```

### 3. Initialize & Launch Dashboard
```bash
# Initialize database schema
python -m src.main init

# Launch Web Dashboard & Monitoring
python -m src.main ui --host 127.0.0.1 --port 8000
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.

---

## 🛠️ Key Dashboard Features

- **🎯 Opportunity Inbox:** Filter by score, buying intent, or subreddit. Expand cards to view signal meters, community comments, and draft replies.
- **📋 Reddit Explorer:** Search live Reddit on-the-fly and browse stored discussions.
- **⚙️ Monitoring Rules:** Build monitoring rules with threshold filters and **AI Keyword Expansion** ("n8n automation" ➔ 10 suggested variations).
- **🔸 Subreddit Profiles:** Community sensitivity ratings, promotion tolerance scores, and cultural tips.
- **⚔️ Competitor Tracker:** Add competitors to automatically monitor migration queries and complaints.
- **🤖 AI & Critic Lab:** Test intent classification and run the automated Critic on custom reply drafts.
- **🔔 Alerts & Settings:** Configure ntfy.sh push notifications, email alerts, and swap AI backends.

---

## 🧪 Testing

Run the full unit and integration test suite:
```bash
python tests/run_tests.py
```

---

## 📄 License
MIT License. Free for personal and commercial usage.

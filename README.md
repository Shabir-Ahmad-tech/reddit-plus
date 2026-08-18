# RedditPulse (reddit-plus) 🤖🔸

An advanced, self-hosted, **Reddit-native Social Intelligence & Lead Generation Dashboard**. Monitor subreddits in real-time, extract deep engagement and buying signals, classify user intent using AI, and draft authentic replies automatically. 

All powered by a local LLM (Ollama) or free cloud APIs (OpenCode Zen), stored in SQLite, and alerts sent instantly via ntfy.sh or email.

---

## ✨ Features

- **Modern Tailwind CSS Dashboard:** Dark sidebar navigation, animated opportunity/buy signal meters, skeleton loading states, toast notifications, and interactive AI playgrounds.
- **Rich Reddit-Native Metadata:**
  - Real-time upvote score (not hardcoded to 1).
  - Exact comment count tracking.
  - Upvote ratio percentage (e.g., 94% upvoted).
  - Subreddit link flairs and awards count.
  - Automated post type detection (Text, Link, Image, Video, Gallery).
- **Reddit-Specific AI Prompts:** Calibrated for Reddit slang, abbreviations (OP, TIL, AITA, ELI5), and community context to generate replies that read like a human practitioner, not a robotic sales assistant.
- **Granular Intent Classification:**
  - `buy-intent` (actively looking for product/service)
  - `pain-point` (frustrated by a bug, tool limitation, or problem)
  - `competitor-complaint` (complaining about or leaving a competitor)
  - `seeking-alternatives` (explicitly asking to migrate or switch tools)
  - `venting` (emotional frustration without a clear solution target)
  - `question`, `praise`, `success-story`, `tool-review`, `hiring`, and `other`.
- **Deep Signal Analysis:** Calculates `opportunity_score` (0-100), `buy_signal_strength` (0-100), and `engagement_potential` (0-100). Extracts mentioned products and pain keywords.
- **Multi-Channel Alert Dispatch:**
  - **ntfy.sh:** Free, unlimited push notifications directly to your phone.
  - **SendGrid:** Scheduled email digest or immediate email alerts.
  - **Webhooks:** Native integration for Discord/Slack webhooks.

---

## 🚀 Quick Start

### 1. Prerequisites

- **Python 3.10+**
- **Ollama** (optional, for local AI) or **OpenCode Zen API Key** (free cloud key from [opencode.ai](https://opencode.ai)).
- **Reddit API Credentials** (optional, fallback to public JSON endpoints is supported out-of-the-box).
  - Create a "script" app at [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) to get a `client_id` and `client_secret`.
- **ntfy App** (optional, download on iOS/Android for instant push notifications).

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

# Create and populate environment variables
cp .env.example .env
# Edit .env with your credentials
```

### 3. Initialize & Run

```bash
# Setup the database and run initial migrations
python scripts/init_db.py

# Run the FastAPI Web Dashboard
python -m src.main ui --host 127.0.0.1 --port 8000
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.

---

## 🛠️ Usage Guide

### Dashboards & Views
- **Overview:** Live monitoring stats, active keyword counts, intent category distribution, and a quick-view feed of recent posts.
- **Posts Feed:** Full searchable list of Reddit posts. Filter by Subreddit, Intent Tag, Post Age, or search text. Expand any card to see AI Deep Analysis and draft replies.
- **Keywords:** Add monitored phrases with custom minimum scores and target subreddits.
- **Subreddits:** View and configure your watched subreddits. Includes a **Live Search Test** to query Reddit on-the-fly.
- **AI Playground:** Test classification, reply generation, or deep analysis on arbitrary texts manually.
- **Activity Log:** Real-time log file stream of system events and background poller logs.
- **Settings:** Configure ntfy.sh push notification topics, alert triggers, and swap between Ollama (local) and OpenCode Zen (cloud) LLM backends.

---

## 💡 How it Works (Under the Hood)

### The Reddit JSON Poller
RedditPulse uses Reddit's public JSON API (`/r/{subreddit}/search.json` and `/r/{subreddit}/new.json`) to bypass RSS latency and extract real metadata (scores, flairs, counts) in 15-minute polling windows. If API credentials are in `.env`, it automatically upgrades to standard OAuth (PRAW) for higher rate limits.

### Intent & Reply Pipeline
1. **Fetch:** Poller retrieves submissions matching active keywords.
2. **Classify:** AI evaluates intent and calculates confidence (combating rate-limits by rotating through fallback models like DeepSeek & Nemotron).
3. **Analyze:** AI performs a secondary deep analysis evaluating the post's market signals.
4. **Draft:** For actionable intents (`buy-intent`, `pain-point`, etc.), the AI generates a context-aware 2-4 sentence reply.
5. **Alert:** High-confidence leads trigger immediate push alerts via ntfy.sh or SendGrid.

---

## ⚙️ Customization

- **Alert Configuration:** Managed via **Settings** tab in the UI or directly in `config.yaml`.
- **Adding Custom Subreddits:** Navigate to **Subreddits** tab in the UI, type your target sub, and press **Add**.
- **LLM Settings:** Edit your `config.yaml` to specify different Ollama model endpoints or temperature defaults.

---

## 📄 License

MIT License. Free for personal and commercial usage.

---

*Made with ❤️ for indie hackers, founders, and community managers.*

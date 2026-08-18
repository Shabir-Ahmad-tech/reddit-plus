# ParseStream Free 🆓

A **completely free, self-hosted** alternative to [parsestream.com](https://parsestream.com) for monitoring Reddit and Hacker News with AI-powered intent classification and reply generation.

## ✨ Features

| Feature | ParseStream | ParseStream Free |
|---------|-------------|------------------|
| Web UI / Dashboard | ✅ | ✅ (Modern Tailwind SPA) |
| Reddit Monitoring | ✅ | ✅ (PRAW + Public Fallback) |
| Hacker News Monitoring | ✅ | ✅ (Algolia Real-time API) |
| X/Twitter Monitoring | ✅ | ❌ (paid API) |
| LinkedIn Monitoring | ✅ | ❌ (restricted API) |
| Quora Monitoring | ✅ | ❌ (no API) |
| AI Intent Classification | ✅ | ✅ (local LLM + Fallback) |
| AI Reply Generation | ✅ | ✅ (local LLM + Tone Selector) |
| Email Alerts | ✅ | ✅ (SendGrid free tier) |
| Push Notifications | ❌ | ✅ (ntfy.sh free) |
| Discord / Slack Webhooks | ❌ | ✅ (Native Webhooks) |
| Semantic Search | ✅ | ✅ (local embeddings) |
| **Monthly Cost** | **$29–$199** | **$0** |

## 🚀 Quick Start

### Prerequisites

1. **Python 3.11+**
2. **Ollama** - Local LLM runtime
   ```bash
   # Install Ollama
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Start Ollama server
   ollama serve
   
   # Pull a model (choose one):
   ollama pull llama3.1:8b      # Best quality (4.7GB)
   ollama pull phi3:mini         # Fast, small (2.3GB)
   ollama pull qwen2.5:7b        # Good balance (4.4GB)
   ```

3. **Reddit API Credentials** (free)
   - Go to https://www.reddit.com/prefs/apps
   - Create a "script" type app
   - Note the `client_id` (under app name) and `client_secret`

4. **Optional: Alert Services**
   - **SendGrid** (100 emails/day free): https://app.sendgrid.com/settings/api_keys
   - **ntfy.sh** (free unlimited push): Create a topic at https://ntfy.sh

### Installation

```bash
# Clone and enter directory
cd parsestream-free

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy config and fill in your values
cp .env.example .env
# Edit .env with your Reddit credentials and optional alert keys

# Initialize database
python scripts/init_db.py

# Test Ollama connection
python scripts/test_ollama.py
```

### Configuration

Edit `config.yaml` to customize:
- Polling intervals
- Keywords and subreddits
- LLM prompts for classification/replies
- Alert thresholds and frequency

### Running

```bash
# Launch the Web Dashboard (Recommended)
python -m src.main ui

# Or start continuous monitoring with Web UI
python -m src.main start --ui

# CLI Keyword management
python -m src.main add-keyword "saas pricing" --sources reddit,hackernews --subreddits startups,saas

# Configure alerts (optional)
python -m src.main config-alerts --email you@example.com --ntfy-topic your-topic

# Run once to test
python -m src.main run-once
```

## 🐳 Docker Deployment (Recommended)

```bash
# Copy env file
cp .env.example .env
# Edit .env with your credentials

# Start (pulls model automatically on first run)
docker-compose up -d

# View logs
docker-compose logs -f app
```

### Deploy to Railway/Render/Fly.io (Free Tier)

1. Push to GitHub
2. Connect repository to Railway/Render/Fly.io
3. Add environment variables from `.env`
4. Deploy - they'll detect the Dockerfile automatically

**Railway**: 500 hours/month free, 512MB RAM  
**Render**: Free tier with 512MB RAM  
**Fly.io**: Free tier with 256MB RAM  

## 📖 Commands Reference

```bash
# Keyword management
parsestream add-keyword "keyword" --sources reddit,hackernews --subreddits python,ml
parsestream list-keywords
parsestream remove-keyword "keyword"

# Alert configuration
parsestream config-alerts --email you@example.com --ntfy-topic my-topic --frequency hourly

# Operations
parsestream run-once              # Poll → Process → Alert once
parsestream start                 # Start continuous scheduler

# Data exploration
parsestream list-mentions --limit 20 --hours 24
parsestream show-mention 123
parsestream search "pricing" --limit 10
parsestream search "pricing" --semantic  # Requires embeddings

# Testing
parsestream init                  # Test all connections
parsestream test-ollama           # Test LLM
parsestream test-alert            # Send test notification
```

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Scheduler  │────▶│  API Pollers │────▶│  SQLite +   │
│ (APScheduler)│     │ Reddit + HN  │     │  pgvector   │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                 │
                                        ┌────────▼────────┐
                                        │  Ollama (Local) │
                                        │  - Classify     │
                                        │  - Generate     │
                                        └────────┬────────┘
                                                 │
                                        ┌────────▼────────┐
                                        │  Alert Sender   │
                                        │  - SendGrid     │
                                        │  - ntfy.sh      │
                                        └─────────────────┘
```

## 🔧 Customization

### Modify Intent Categories
Edit `src/llm/prompts.py` to change classification categories.

### Custom Reply Style
Edit the `reply_prompt` in `config.yaml` to change reply tone/guidelines.

### Add New Data Sources
1. Create new poller in `src/pollers/`
2. Register in `src/scheduler.py`
3. Add config section in `config.yaml`

## 📊 Free Tier Limits

| Service | Limit | Workaround |
|---------|-------|------------|
| Reddit API | 60 req/min | Respects rate limits automatically |
| HN API | Unlimited | Polite 15-min polling |
| Ollama | Unlimited | Local inference |
| SendGrid | 100 emails/day | Use ntfy.sh for real-time |
| ntfy.sh | Unlimited | Self-host if needed |
| Railway/Render | 512MB RAM | SQLite + small models fit easily |

## 🤝 Contributing

PRs welcome! Areas for improvement:
- More data sources (RSS, YouTube comments, etc.)
- Better semantic search with sqlite-vec
- Web dashboard
- Multi-user support
- Export/backup features

## 📄 License

MIT License - Free for personal and commercial use.

## ⚠️ Disclaimer

This is a **free clone** for educational/self-hosted use. Not affiliated with parsestream.com. Respect platform ToS and API rate limits. Use responsibly.

---

**Made with ❤️ for the open-source community**
# reddit-plus

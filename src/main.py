import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from sqlalchemy import select
from src.config import settings
from src.database import init_db, get_session, add_keyword, get_active_keywords, delete_keyword, upsert_alert_config
from src.database.models import Mention, IntentTag, Reply
from src.scheduler import (
    setup_scheduler,
    run_manual_poll,
    run_manual_process,
    run_manual_alert,
)
from src.llm import get_ollama_client
from src.pollers.reddit import RedditPoller
from src.pollers.hackernews import HackerNewsPoller

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Ensure data directory exists
Path(settings.app.database_path).parent.mkdir(parents=True, exist_ok=True)

app = typer.Typer(name="parsestream", help="ParseStream Free - Self-hosted social monitoring")
console = Console()


@app.command()
def init():
    """Initialize database and test connections."""
    console.print(Panel.fit("🚀 Initializing ParseStream Free", style="bold blue"))

    # Init database
    console.print("Creating database tables...")
    init_db()
    console.print("✅ Database initialized")

    # Test Ollama
    console.print("Testing Ollama connection...")
    client = get_ollama_client()
    if asyncio.run(client.health_check()):
        console.print("✅ Ollama connected")
    else:
        console.print("⚠️  Ollama not available - start with: ollama serve")

    # Test Reddit
    console.print("Testing Reddit connection...")
    reddit = RedditPoller()
    if reddit.test_connection():
        console.print("✅ Reddit connected")
    else:
        console.print("⚠️  Reddit not configured - set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET")

    # Test HN
    console.print("Testing Hacker News connection...")
    hn = HackerNewsPoller()
    if asyncio.run(hn.test_connection()):
        console.print("✅ Hacker News connected")
    else:
        console.print("⚠️  Hacker News connection failed")

    console.print("\n[green]Initialization complete![/green]")
    console.print("Next steps:")
    console.print("  1. Add keywords: parsestream add-keyword 'saas pricing'")
    console.print("  2. Configure alerts: parsestream config-alerts --email you@example.com")
    console.print("  3. Run once: parsestream run-once")
    console.print("  4. Start scheduler: parsestream start")


@app.command()
def add_keyword(
    keyword: str,
    sources: str = typer.Option("reddit,hackernews", "--sources", "-s", help="Comma-separated sources"),
    subreddits: Optional[str] = typer.Option(None, "--subreddits", "-r", help="Comma-separated subreddits (Reddit only)"),
    min_score: int = typer.Option(1, "--min-score", help="Minimum score for mentions"),
):
    """Add a keyword to monitor."""
    source_list = [s.strip() for s in sources.split(",")]
    subreddit_list = [s.strip() for s in subreddits.split(",")] if subreddits else None

    with get_session() as session:
        kw = add_keyword(session, keyword, source_list, subreddit_list, min_score)
        console.print(f"✅ Added keyword: [bold]{kw.keyword}[/bold]")
        console.print(f"   Sources: {kw.sources}")
        if kw.subreddits:
            console.print(f"   Subreddits: {kw.subreddits}")
        console.print(f"   Min score: {kw.min_score}")


@app.command()
def list_keywords():
    """List all active keywords."""
    with get_session() as session:
        keywords = get_active_keywords(session)

    if not keywords:
        console.print("[yellow]No keywords configured[/yellow]")
        return

    table = Table(title="Active Keywords")
    table.add_column("Keyword", style="cyan")
    table.add_column("Sources", style="green")
    table.add_column("Subreddits", style="yellow")
    table.add_column("Min Score", justify="right")

    for kw in keywords:
        table.add_row(
            kw.keyword,
            ", ".join(kw.sources),
            ", ".join(kw.subreddits) if kw.subreddits else "all",
            str(kw.min_score),
        )

    console.print(table)


@app.command()
def remove_keyword(keyword: str):
    """Remove a keyword."""
    with get_session() as session:
        if delete_keyword(session, keyword):
            console.print(f"✅ Removed keyword: [bold]{keyword}[/bold]")
        else:
            console.print(f"[red]Keyword not found: {keyword}[/red]")


@app.command()
def config_alerts(
    email: Optional[str] = typer.Option(None, "--email", "-e", help="Email for SendGrid alerts"),
    ntfy_topic: Optional[str] = typer.Option(None, "--ntfy-topic", "-n", help="ntfy.sh topic for push alerts"),
    min_confidence: float = typer.Option(0.7, "--min-confidence", help="Minimum confidence (0-1)"),
    tags: str = typer.Option("buy-intent,pain-point,competitor-complaint", "--tags", help="Comma-separated tags to alert on"),
    frequency: str = typer.Option("hourly", "--frequency", "-f", help="Alert frequency: immediate, hourly, daily"),
):
    """Configure alert settings."""
    tag_list = [t.strip() for t in tags.split(",")]

    with get_session() as session:
        upsert_alert_config(
            session,
            email=email,
            ntfy_topic=ntfy_topic,
            min_intent_confidence=min_confidence,
            tags_to_alert=tag_list,
            frequency=frequency,
        )

    console.print("✅ Alert configuration updated")
    console.print(f"   Email: {email or 'not set'}")
    console.print(f"   ntfy topic: {ntfy_topic or 'not set'}")
    console.print(f"   Min confidence: {min_confidence}")
    console.print(f"   Tags: {', '.join(tag_list)}")
    console.print(f"   Frequency: {frequency}")


@app.command()
def run_once(
    poll: bool = typer.Option(True, "--poll/--no-poll", help="Poll for new mentions"),
    process: bool = typer.Option(True, "--process/--no-process", help="Process unprocessed mentions"),
    alert: bool = typer.Option(True, "--alert/--no-alert", help="Send alerts"),
):
    """Run one complete cycle: poll -> process -> alert."""
    async def _run():
        if poll:
            console.print("[bold]Polling sources...[/bold]")
            await run_manual_poll()
            console.print("✅ Polling complete")

        if process:
            console.print("[bold]Processing mentions...[/bold]")
            await run_manual_process()
            console.print("✅ Processing complete")

        if alert:
            console.print("[bold]Sending alerts...[/bold]")
            await run_manual_alert()
            console.print("✅ Alerts sent")

    asyncio.run(_run())


@app.command()
def ui(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host address to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port number to bind to"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open browser on start"),
    reload: bool = typer.Option(False, "--reload", help="Enable uvicorn reload"),
):
    """Launch ParseStream Free Web UI Dashboard."""
    import webbrowser
    import threading
    import time
    import uvicorn

    url = f"http://{host}:{port}"
    console.print(Panel.fit(f"🚀 Starting ParseStream Free Web Dashboard\n\n🌐 Open in browser: [bold underline cyan]{url}[/bold underline cyan]\n\nPress Ctrl+C to exit", style="bold green"))

    if open_browser:
        def _open():
            time.sleep(1.2)
            try:
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run("src.api.app:app", host=host, port=port, reload=reload)


@app.command()
def start(
    with_ui: bool = typer.Option(True, "--ui/--no-ui", help="Also serve the Web UI alongside scheduler"),
    port: int = typer.Option(8000, "--port", "-p", help="Web UI port (if --ui enabled)"),
):
    """Start continuous monitoring scheduler (optionally hosting Web UI)."""
    if with_ui:
        import uvicorn
        console.print(Panel.fit(f"🔄 Starting ParseStream Monitoring & Web UI\n\n🌐 Dashboard: [bold underline cyan]http://127.0.0.1:{port}[/bold underline cyan]\n\nPress Ctrl+C to stop", style="bold green"))
        uvicorn.run("src.api.app:app", host="127.0.0.1", port=port, reload=False)
    else:
        console.print(Panel.fit("🔄 Starting ParseStream Scheduler", style="bold green"))
        console.print(f"Poll interval: {settings.app.poll_interval_minutes} min")
        console.print(f"Process interval: {settings.app.process_interval_minutes} min")
        console.print(f"Alert frequency: {settings.alerts.digest_frequency}")
        console.print("\nPress Ctrl+C to stop\n")

        scheduler = setup_scheduler()
        scheduler.start()

        try:
            asyncio.get_event_loop().run_forever()
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/yellow]")
            scheduler.shutdown()


@app.command()
def list_mentions(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of mentions to show"),
    source: Optional[str] = typer.Option(None, "--source", help="Filter by source (reddit/hackernews)"),
    hours: int = typer.Option(24, "--hours", help="Show mentions from last N hours"),
):
    """List recent mentions."""
    with get_session() as session:
        from src.database import get_recent_mentions
        mentions = get_recent_mentions(session, hours=hours, limit=limit)

        if source:
            mentions = [m for m in mentions if m.source == source]

    if not mentions:
        console.print("[yellow]No mentions found[/yellow]")
        return

    table = Table(title=f"Recent Mentions (last {hours}h)")
    table.add_column("ID", justify="right", style="dim")
    table.add_column("Source", style="cyan")
    table.add_column("Title", style="white", max_width=50)
    table.add_column("Subreddit", style="green")
    table.add_column("Score", justify="right")
    table.add_column("Posted", style="dim")

    for m in mentions:
        table.add_row(
            str(m.id),
            m.source,
            (m.title or "")[:50],
            m.subreddit or "N/A",
            str(m.score),
            m.posted_at.strftime("%m/%d %H:%M"),
        )

    console.print(table)


@app.command()
def show_mention(mention_id: int):
    """Show full mention details with intent tags and replies."""
    with get_session() as session:
        mention = session.get(Mention, mention_id)
        if not mention:
            console.print(f"[red]Mention {mention_id} not found[/red]")
            return

        intent_tags = session.execute(
            select(IntentTag).where(IntentTag.mention_id == mention_id)
        ).scalars().all()

        replies = session.execute(
            select(Reply).where(Reply.mention_id == mention_id)
        ).scalars().all()

    console.print(Panel.fit(f"[bold]Mention #{mention.id}[/bold] - {mention.source}", style="blue"))
    console.print(f"URL: {mention.url}")
    console.print(f"Author: {mention.author}")
    console.print(f"Subreddit: {mention.subreddit or 'N/A'}")
    console.print(f"Score: {mention.score}")
    console.print(f"Posted: {mention.posted_at}")
    console.print(f"\n[bold]Title:[/bold] {mention.title}")
    console.print(f"\n[bold]Content:[/bold]\n{mention.content}")

    if intent_tags:
        console.print("\n[bold]Intent Tags:[/bold]")
        for t in intent_tags:
            console.print(f"  • {t.tag} ({t.confidence}%)")

    if replies:
        console.print("\n[bold]Replies:[/bold]")
        for r in replies:
            status = "✅ Sent" if r.sent else "⏳ Pending"
            console.print(f"  [{status}] {r.content[:100]}...")


@app.command()
def search(
    query: str,
    limit: int = typer.Option(10, "--limit", "-l"),
    source: Optional[str] = typer.Option(None, "--source"),
    semantic: bool = typer.Option(False, "--semantic", help="Use semantic search (requires embeddings)"),
):
    """Search mentions by keyword."""
    with get_session() as session:
        if semantic:
            from src.database import semantic_search, embed_text
            from src.config import settings
            query_emb = embed_text(query, settings.ollama.model)
            if query_emb:
                results = semantic_search(session, query_emb, limit=limit)
                mentions = [m for m, _ in results]
            else:
                console.print("[red]Semantic search not available (no embeddings)[/red]")
                return
        else:
            from src.database import keyword_search
            mentions = keyword_search(session, query, source, limit)

    if not mentions:
        console.print("[yellow]No results found[/yellow]")
        return

    table = Table(title=f"Search Results for '{query}'")
    table.add_column("ID", justify="right", style="dim")
    table.add_column("Source", style="cyan")
    table.add_column("Title", style="white", max_width=60)
    table.add_column("Score", justify="right")

    for m in mentions:
        table.add_row(str(m.id), m.source, (m.title or "")[:60], str(m.score))

    console.print(table)


@app.command()
def test_ollama(
    prompt: str = typer.Option("Say hello in one sentence", "--prompt", "-p"),
):
    """Test Ollama connection with a simple prompt."""
    async def _test():
        client = get_ollama_client()
        if await client.health_check():
            response = await client.generate(prompt)
            console.print(f"[green]Response:[/green] {response}")
        else:
            console.print("[red]Ollama not available[/red]")

    asyncio.run(_test())


@app.command()
def test_alert(
    email: bool = typer.Option(True, "--email/--no-email"),
    push: bool = typer.Option(True, "--push/--no-push"),
):
    """Send a test alert."""
    from src.alerts import get_email_sender, get_push_sender
    from src.database.models import Mention, IntentTag, Reply
    from datetime import datetime, timezone

    # Create mock mention
    mention = Mention(
        id=0,
        source="reddit",
        source_id="test123",
        url="https://reddit.com/r/test",
        title="Test mention for ParseStream",
        content="This is a test mention to verify alerts are working correctly.",
        author="testuser",
        subreddit="test",
        score=42,
        posted_at=datetime.now(timezone.utc),
    )
    intent_tags = [IntentTag(id=0, mention_id=0, tag="buy-intent", confidence=90)]
    reply = Reply(id=0, mention_id=0, content="This is a test reply generated by the system.", model="test")

    async def _test():
        if email:
            sender = get_email_sender()
            if sender.is_configured():
                sender.send_immediate_alert(mention, intent_tags, reply)
                console.print("✅ Test email sent")
            else:
                console.print("⚠️  Email not configured")

        if push:
            sender = get_push_sender()
            if sender.is_configured():
                await sender.send_immediate_alert(mention, intent_tags, reply)
                console.print("✅ Test push sent")
            else:
                console.print("⚠️  Push not configured")

    asyncio.run(_test())


if __name__ == "__main__":
    app()
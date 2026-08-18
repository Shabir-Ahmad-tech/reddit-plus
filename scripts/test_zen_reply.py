import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import asyncio
from src.llm import generate_reply, classify_intent

async def main():
    text = "We are searching for an open-source tool to monitor social media discussions without breaking the bank."
    print("Testing Intent Classification...")
    intent = await classify_intent(text)
    print(f"  -> Tag: {intent.tag} ({intent.confidence:.2f}) | Fallback: {intent.is_fallback}")

    print("\nTesting Reply Generation...")
    reply = await generate_reply("reddit", "Social monitoring alternatives?", text, intent.tag, tone="casual")
    print(f"  -> Model: {reply.model}")
    print(f"  -> Reply:\n{reply.content}")

if __name__ == "__main__":
    asyncio.run(main())

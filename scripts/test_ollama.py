#!/usr/bin/env python3
"""Test Ollama connection and model."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.llm import get_ollama_client
from src.config import settings

async def main():
    print(f"Testing Ollama at: {settings.ollama.host}")
    print(f"Model: {settings.ollama.model}")

    client = get_ollama_client()

    # Health check
    if await client.health_check():
        print("✅ Ollama is running and model is available")

        # Test generation
        print("\nTesting generation...")
        response = await client.generate("Say 'Hello from ParseStream!' in a friendly way.")
        print(f"Response: {response}")

        # Test intent classification
        print("\nTesting intent classification...")
        from src.llm import classify_intent
        result = await classify_intent("I'm looking for a good project management tool for my team")
        print(f"Tag: {result.tag}, Confidence: {result.confidence:.2f}")

        # Test reply generation
        print("\nTesting reply generation...")
        from src.llm import generate_reply
        reply = await generate_reply(
            source="reddit",
            title="Best project management tools?",
            content="Looking for recommendations for a small team",
            intent_tag="question",
        )
        print(f"Reply: {reply.content}")

    else:
        print("❌ Ollama not available")
        print("Start Ollama with: ollama serve")
        print(f"Pull model with: ollama pull {settings.ollama.model}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
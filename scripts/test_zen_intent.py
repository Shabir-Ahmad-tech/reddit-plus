import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from src.llm import get_llm_client, build_intent_prompt, parse_intent_response

async def main():
    client = get_llm_client()
    text = "I am so frustrated with our current CRM, it is constantly crashing and buggy. Looking for alternatives!"
    p = build_intent_prompt(text)
    print("PROMPT:\n", p)
    res = await client.generate(p, format_json=True)
    print("\nRAW LLM RESPONSE:\n", res)
    tag, conf = parse_intent_response(res)
    print(f"\nPARSED: tag={tag}, conf={conf}")

if __name__ == "__main__":
    asyncio.run(main())

import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import httpx
import json
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENCODE_ZEN_API_KEY") or os.getenv("LLM_API_KEY", "")
BASE_URL = os.getenv("OPENCODE_ZEN_BASE_URL", "https://opencode.ai/zen/v1")

if not API_KEY:
    print("Warning: OPENCODE_ZEN_API_KEY or LLM_API_KEY environment variable not set.")
    sys.exit(0)

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

payload = {
    "model": os.getenv("LLM_MODEL", "deepseek-v4-flash-free"),
    "messages": [
        {"role": "system", "content": "You are an AI assistant. Return JSON."},
        {"role": "user", "content": "Classify this mention into intent tags: 'Looking for a tool to replace HubSpot CRM'. Respond JSON only: {\"tag\": \"buy-intent\", \"confidence\": 0.95}"}
    ],
    "temperature": 0.2,
}

try:
    r = httpx.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=30)
    print("Status:", r.status_code)
    print("Response:", r.text)
except Exception as e:
    print("Error:", e)

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import httpx
import json

API_KEY = "sk-j96hBGcr8kZU2iwLohSWnMaCuIAmWpDp8IZN59wnp6RFnyFMEomHIpVDgTWia57y"
BASE_URL = "https://opencode.ai/zen/v1"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

payload = {
    "model": "mimo-v2.5-free",
    "messages": [
        {"role": "system", "content": "You are an AI assistant. Return JSON."},
        {"role": "user", "content": "Classify this mention into intent tags: 'Looking for a tool to replace HubSpot CRM'. Respond JSON only: {\"tag\": \"buy-intent\", \"confidence\": 0.95}"}
    ],
    "temperature": 0.2,
}

r = httpx.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=30)
print("Status:", r.status_code)
print("Response:", r.text)

"""Why is the judge failing? Calls Gemini once and lists Groq models.  Usage: python -m scripts.check_judge"""
import httpx

from app.config import settings

r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{settings.judge_model}:generateContent",
               params={"key": settings.gemini_api_key},
               json={"contents": [{"parts": [{"text": "Reply with the word ok"}]}]}, timeout=60)
print(f"Gemini {settings.judge_model}: HTTP {r.status_code}")
if r.status_code != 200:
    err = r.json().get("error", {})
    print("  message:", err.get("message", r.text)[:400])
    for d in err.get("details", []):
        for v in d.get("violations", []):
            print("  quota:", v.get("quotaId"), v.get("quotaValue", ""))
        if "retryDelay" in d:
            print("  retry after:", d["retryDelay"])

g = httpx.get("https://api.groq.com/openai/v1/models",
              headers={"Authorization": f"Bearer {settings.groq_api_key}"}, timeout=30)
print(f"\nGroq models (HTTP {g.status_code}):")
for m in sorted(x["id"] for x in g.json().get("data", [])):
    print(" ", m)

from app.agent.providers.gemini_provider import GeminiProvider

p = GeminiProvider()
print(p.complete(system="Reply only with JSON.", user='Return {"ok": true}'))
from dotenv import load_dotenv
load_dotenv()
import time
from app.agent.providers.gemini_provider import GeminiProvider

p = GeminiProvider()
t = time.time()
r = p.client.models.generate_content(
    model=p.model,
    contents='Reply with a JSON object where key ok is true',
)
print('sec', round(time.time() - t, 1))
print(r.usage_metadata)

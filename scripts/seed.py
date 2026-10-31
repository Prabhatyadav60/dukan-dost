import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))
from app.seed import seed  # noqa: E402
asyncio.run(seed())
print("seeded")

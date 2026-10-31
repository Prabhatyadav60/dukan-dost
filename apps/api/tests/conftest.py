import os

os.environ.update({"MONGO_URI": "memory", "MONGO_DB": "dukan_dost_test", "AI_PROVIDER": "fake",
                   "SARVAM_API_KEY": "", "DEMO_TODAY": "2026-10-31", "UPLOAD_DIR": "/tmp/dukan-test-uploads"})

import httpx  # noqa: E402
import pytest  # noqa: E402

from app import db as dbmod  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402


@pytest.fixture
async def client():
    dbmod.reset_client()
    await seed(dbmod.get_db())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/v1/auth/session", json={"phone": "+919999900001", "otp": "123456"})
        c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        yield c


@pytest.fixture
def key():
    import uuid
    return lambda: {"Idempotency-Key": str(uuid.uuid4())}

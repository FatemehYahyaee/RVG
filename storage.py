"""Small persistence adapter for RVG.

If UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN are configured,
state is stored in Upstash Redis through its REST API.  If they are not
configured (or temporarily unavailable), callers can continue using the
existing local-file persistence in main.py.
"""

import json
import os
from urllib.parse import quote

import httpx


UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "").rstrip("/")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
STATE_KEY = os.environ.get("RVG_STATE_KEY", "rvg:state")
TIMEOUT = float(os.environ.get("UPSTASH_TIMEOUT", "10"))


def enabled() -> bool:
    return bool(UPSTASH_URL and UPSTASH_TOKEN)


async def load_state():
    """Return the persisted state dict, None when no remote state exists.

    A remote error is deliberately converted to None so RVG can fall back to
    its existing local file persistence rather than becoming unavailable.
    """
    if not enabled():
        return None

    url = f"{UPSTASH_URL}/get/{quote(STATE_KEY, safe='')}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            )
            response.raise_for_status()
            result = response.json().get("result")
            if not result:
                return None
            if isinstance(result, str):
                return json.loads(result)
            return result
    except Exception as exc:
        print(f"[STORAGE] Upstash load failed: {exc}")
        return None


async def save_state(data: dict) -> bool:
    """Persist state in Upstash. Return True on success."""
    if not enabled():
        return False

    url = f"{UPSTASH_URL}/set/{quote(STATE_KEY, safe='')}"
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                url,
                content=payload.encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {UPSTASH_TOKEN}",
                    "Content-Type": "text/plain; charset=utf-8",
                },
            )
            response.raise_for_status()
            return response.json().get("result") == "OK"
    except Exception as exc:
        print(f"[STORAGE] Upstash save failed: {exc}")
        return False

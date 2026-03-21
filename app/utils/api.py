"""
SignalMesh API client utility.

Phase 1: Returns None (triggers mock data in handlers)
Phase 2: Calls live SignalMesh API with your key

Set SIGNALMESH_API_KEY env var when the API is live.
Set SIGNALMESH_API_URL to override the base URL.
"""

import os
import logging
import aiohttp

logger = logging.getLogger(__name__)

API_KEY = os.getenv("SIGNALMESH_API_KEY", "")
API_URL = os.getenv("SIGNALMESH_API_URL", "https://api.signalmesh.dev")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "User-Agent": "SignalMeshBot/1.0",
}


async def call_signalmesh_api(path: str) -> dict | None:
    """
    Make an authenticated call to the SignalMesh API.
    Returns None if API key not set or request fails — handlers fall back to mock data.
    """
    if not API_KEY:
        # No API key yet — silently use mock data
        return None

    url = f"{API_URL}{path}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.warning(f"API returned {resp.status} for {path}")
                    return None
    except Exception as e:
        logger.warning(f"API call failed for {path}: {e}")
        return None

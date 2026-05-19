"""
Sync local Aula tokens to Railway (or any remote backend).

Usage:
    python scripts/sync_tokens.py

This reads tokens from the local data/tokens.json and pushes them
to the configured remote backend URL.

Environment variables (or set in .env):
    AULA_SYNC_TARGET_URL  - Railway backend URL (e.g., https://aula-jkf-production.up.railway.app)
    AULA_ADMIN_SECRET     - Shared secret for the upload endpoint
"""

import json
import os
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("httpx not installed. Run: pip install httpx")
    sys.exit(1)


def main():
    # Load settings from env or .env file
    backend_dir = Path(__file__).parent.parent
    env_file = backend_dir / ".env"
    
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

    target_url = os.environ.get("AULA_SYNC_TARGET_URL", "")
    admin_secret = os.environ.get("AULA_ADMIN_SECRET", "")
    token_path = backend_dir / os.environ.get("AULA_TOKEN_STORE_PATH", "data/tokens.json")

    if not target_url:
        print("Error: AULA_SYNC_TARGET_URL not set")
        print("Set it in .env or as an environment variable")
        sys.exit(1)

    if not admin_secret:
        print("Error: AULA_ADMIN_SECRET not set")
        print("Set it in .env or as an environment variable")
        sys.exit(1)

    if not token_path.exists():
        print(f"Error: No tokens found at {token_path}")
        print("Log in locally first (run the backend and visit http://localhost:3000/login)")
        sys.exit(1)

    tokens = json.loads(token_path.read_text())
    print(f"Loaded tokens from {token_path}")
    print(f"  Access token: {tokens['access_token'][:20]}...")
    print(f"  Syncing to: {target_url}")

    url = f"{target_url.rstrip('/')}/auth/upload-tokens"
    response = httpx.post(
        url,
        json=tokens,
        headers={"X-Admin-Secret": admin_secret},
        timeout=15.0,
    )

    if response.status_code == 200:
        print(f"\n✓ Tokens synced successfully!")
        print(f"  The PWA should now work from anywhere.")
    else:
        print(f"\n✗ Sync failed: {response.status_code}")
        print(f"  Response: {response.text}")
        sys.exit(1)


if __name__ == "__main__":
    main()

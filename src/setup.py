"""Interactive first-run setup for the Hostile Object Estimation System.

Walks the user through Telegram onboarding on a new machine:
  1. Prompt for the bot token and validate it against Telegram (getMe).
  2. Auto-detect the user's numeric Telegram ID by having them message the
     bot, read back via getUpdates (with a manual-entry fallback).
  3. Persist TELEGRAM_BOT_TOKEN and AUTHORIZED_USER_ID to .env.

Stdlib only (urllib/json/getpass) so it runs on a fresh clone before any
`pip install`, and works the same on Linux and Windows. Invoke from the repo
root as:  python3 src/setup.py
"""
from __future__ import annotations

import getpass
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Add the repo root to sys.path so `from src.env_utils import ...` resolves
# when this file is run directly as `python3 src/setup.py`.
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.env_utils import set_env_var  # noqa: E402

ENV_FILE = REPO_ROOT / ".env"
EXAMPLE_FILE = REPO_ROOT / ".env.example"
API_BASE = "https://api.telegram.org/bot{token}/{method}"
HTTP_TIMEOUT = 15  # seconds per Telegram API call


def _call_api(token: str, method: str, params: dict | None = None) -> dict:
    """Call a Telegram Bot API method. Returns the parsed JSON dict.

    Raises urllib.error.HTTPError for non-2xx responses (e.g. 401 for a bad
    token) and urllib.error.URLError for network problems.
    """
    url = API_BASE.format(token=token, method=method)
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ensure_env_file() -> None:
    """Create .env from .env.example if it does not already exist."""
    if ENV_FILE.exists():
        return
    if not EXAMPLE_FILE.exists():
        # No template to copy; set_env_var will create the file on first write.
        print("Note: .env.example not found; a fresh .env will be created.")
        return
    ENV_FILE.write_bytes(EXAMPLE_FILE.read_bytes())
    print(f"Created .env from .env.example")


def prompt_token() -> str | None:
    """Prompt for the bot token and validate it via getMe.

    Returns the validated token, or None if the user chose to skip.
    """
    print()
    print("Step 1/2 - Telegram bot token")
    print("  Open Telegram, talk to @BotFather, send /newbot (or /token for an")
    print("  existing bot), and copy the token it gives you.")
    print("  Leave this blank to skip Telegram setup (detection still runs; the")
    print("  bot just stays disabled).")
    print()

    while True:
        token = getpass.getpass("  Bot token (hidden): ").strip()
        if not token:
            print("  Skipping Telegram setup.")
            return None
        try:
            data = _call_api(token, "getMe")
        except urllib.error.HTTPError as e:
            if e.code == 401:
                print("  X Telegram rejected that token (401 Unauthorized). Try again.")
            else:
                print(f"  X Telegram returned HTTP {e.code}. Try again.")
            continue
        except urllib.error.URLError as e:
            print(f"  X Could not reach Telegram ({e.reason}). Check your internet and retry.")
            continue
        except Exception as e:  # noqa: BLE001 - never crash setup on parse issues
            print(f"  X Unexpected error validating token: {e}. Try again.")
            continue

        if not data.get("ok"):
            print("  X Telegram rejected that token. Try again.")
            continue

        bot = data.get("result", {})
        username = bot.get("username", "?")
        print(f"  OK - token valid. Bot is @{username}.")
        return token


def _collect_sender_ids(token: str) -> list[tuple[int, str]]:
    """Return distinct (user_id, display_name) senders from recent updates."""
    data = _call_api(token, "getUpdates", {"timeout": 0})
    senders: dict[int, str] = {}
    for update in data.get("result", []):
        msg = update.get("message") or update.get("edited_message") or {}
        frm = msg.get("from")
        if not frm or not frm.get("id"):
            continue
        uid = frm["id"]
        name = frm.get("username") or frm.get("first_name") or "unknown"
        senders[uid] = name
    return list(senders.items())


def detect_user_id(token: str, bot_username: str = "your bot") -> str | None:
    """Auto-detect the user's numeric Telegram ID via getUpdates.

    Falls back to manual entry if no message is seen. Returns the chosen ID as
    a string, or None if the user skipped.
    """
    print()
    print("Step 2/2 - Your Telegram user ID")
    print(f"  Open Telegram and send any message (e.g. /start) to @{bot_username}.")

    for attempt in range(5):
        input("  Once you've sent it, press Enter to detect your ID... ")
        try:
            senders = _collect_sender_ids(token)
        except urllib.error.URLError as e:
            print(f"  X Could not reach Telegram ({e.reason}). Retrying may help.")
            senders = []
        except Exception as e:  # noqa: BLE001
            print(f"  X Error reading updates: {e}")
            senders = []

        if len(senders) == 1:
            uid, name = senders[0]
            ans = input(f"  Detected {name} (ID {uid}). Use it? [Y/n]: ").strip().lower()
            if ans in ("", "y", "yes"):
                return str(uid)
        elif len(senders) > 1:
            print("  Multiple senders found:")
            for i, (uid, name) in enumerate(senders, 1):
                print(f"    {i}) {name} (ID {uid})")
            choice = input(f"  Pick 1-{len(senders)} (or Enter to retry): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(senders):
                return str(senders[int(choice) - 1][0])
        else:
            remaining = 4 - attempt
            if remaining > 0:
                print(f"  No message detected yet. Make sure you messaged @{bot_username}. "
                      f"({remaining} more tr{'y' if remaining == 1 else 'ies'})")

    # Fallback: manual entry.
    print()
    print("  Couldn't auto-detect. You can enter your numeric ID manually")
    print("  (get it from @userinfobot), or leave blank to configure later.")
    while True:
        manual = input("  Your Telegram user ID: ").strip()
        if not manual:
            return None
        if manual.isdigit():
            return manual
        print("  X That doesn't look like a numeric ID. Try again.")


def main() -> int:
    print("=" * 50)
    print("  Hostile Object Estimation - Telegram setup")
    print("=" * 50)

    ensure_env_file()

    token = prompt_token()
    if token is None:
        print()
        print("Telegram setup skipped. Edit .env or run this again "
              "(./deploy.sh --setup) any time.")
        return 0

    # Re-fetch the username for nicer prompts (already validated above).
    bot_username = "your bot"
    try:
        me = _call_api(token, "getMe")
        bot_username = me.get("result", {}).get("username", bot_username)
    except Exception:  # noqa: BLE001 - cosmetic only
        pass

    user_id = detect_user_id(token, bot_username)

    set_env_var(ENV_FILE, "TELEGRAM_BOT_TOKEN", token)
    if user_id:
        set_env_var(ENV_FILE, "AUTHORIZED_USER_ID", user_id)

    print()
    print("-" * 50)
    if user_id:
        print(f"Done. Saved bot token and user ID ({user_id}) to .env.")
    else:
        print("Saved bot token to .env. Set AUTHORIZED_USER_ID later to enable the bot.")
    print("Next: the launcher will start the system, or run: python3 src/main.py")
    print("-" * 50)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nSetup cancelled.")
        sys.exit(1)

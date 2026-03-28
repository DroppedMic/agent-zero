#!/usr/bin/env python3
"""Content calendar scheduler with file-locking and efficient I/O."""

import argparse
import json
import sys
import time
import fcntl
from pathlib import Path
from datetime import datetime, timedelta
import uuid

SKILL_DIR = Path(__file__).parent.parent
CONFIG_DIR = SKILL_DIR / "config"
SCHEDULE_FILE = CONFIG_DIR / "schedule.json"


def _load() -> list:
    if not SCHEDULE_FILE.exists():
        return []
    with open(SCHEDULE_FILE) as f:
        return json.load(f)


def _save(schedule: list):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SCHEDULE_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        json.dump(schedule, f, indent=2)
    tmp.rename(SCHEDULE_FILE)


def _update_entry(post_id: str, updates: dict) -> bool:
    """Atomic update: load, modify, save in one pass."""
    schedule = _load()
    for entry in schedule:
        if entry["id"] == post_id:
            entry.update(updates)
            _save(schedule)
            return True
    return False


def add(platform: str, content: str, scheduled_at: str,
        tone: str = "", campaign: str = "") -> dict:
    schedule = _load()
    entry = {
        "id": uuid.uuid4().hex[:8],
        "platform": platform,
        "content": content,
        "scheduled_at": scheduled_at,
        "status": "scheduled",
        "created_at": datetime.now().isoformat(),
        "tone": tone,
        "campaign": campaign,
    }
    schedule.append(entry)
    _save(schedule)
    return entry


def upcoming(days: int = 7) -> list:
    now = datetime.now()
    cutoff = now + timedelta(days=days)
    out = []
    for e in _load():
        if e["status"] != "scheduled":
            continue
        try:
            t = datetime.fromisoformat(e["scheduled_at"])
            if now <= t <= cutoff:
                out.append(e)
        except (ValueError, KeyError):
            continue
    return sorted(out, key=lambda x: x["scheduled_at"])


def due() -> list:
    now = datetime.now()
    out = []
    for e in _load():
        if e["status"] != "scheduled":
            continue
        try:
            if datetime.fromisoformat(e["scheduled_at"]) <= now:
                out.append(e)
        except (ValueError, KeyError):
            continue
    return out


def cancel(post_id: str) -> bool:
    return _update_entry(post_id, {"status": "cancelled"})


def run_daemon(interval: int = 60):
    # Fix import path for sibling module
    sys.path.insert(0, str(Path(__file__).parent))
    from platform_poster import post as do_post, load_config

    print(f"Scheduler running (every {interval}s). Ctrl+C to stop.")
    while True:
        for p in due():
            print(f"  [{datetime.now().strftime('%H:%M')}] -> {p['platform']}: {p['content'][:50]}...")
            try:
                config = load_config()
                results = do_post(p["content"], [p["platform"]], config)
                r = results[0] if results else {"status": "error"}
                if r.get("status") == "success":
                    _update_entry(p["id"], {"status": "posted", "posted_at": datetime.now().isoformat(), "result": r})
                    print(f"    OK")
                else:
                    _update_entry(p["id"], {"status": "failed", "error": r.get("message", "?"), "failed_at": datetime.now().isoformat()})
                    print(f"    FAIL: {r.get('message', '?')}")
            except Exception as e:
                _update_entry(p["id"], {"status": "failed", "error": str(e), "failed_at": datetime.now().isoformat()})
                print(f"    ERROR: {e}")
        time.sleep(interval)


def display(posts: list):
    if not posts:
        print("No upcoming posts.")
        return
    print(f"\n{'ID':<10} {'Platform':<12} {'Scheduled':<18} {'Content'}")
    print("-" * 75)
    for p in posts:
        preview = p["content"][:40] + ("..." if len(p["content"]) > 40 else "")
        t = p["scheduled_at"][:16].replace("T", " ")
        print(f"{p['id']:<10} {p['platform']:<12} {t:<18} {preview}")


def main():
    ap = argparse.ArgumentParser(description="Social media scheduler")
    sub = ap.add_subparsers(dest="cmd")

    a = sub.add_parser("add")
    a.add_argument("--platform", "-p", required=True)
    a.add_argument("--content", "-c", required=True)
    a.add_argument("--date", "-d", required=True, help="YYYY-MM-DD HH:MM or ISO")
    a.add_argument("--campaign", default="")
    a.add_argument("--tone", default="")

    l = sub.add_parser("list")
    l.add_argument("--days", type=int, default=7)
    l.add_argument("--all", action="store_true")

    c = sub.add_parser("cancel")
    c.add_argument("post_id")

    r = sub.add_parser("run")
    r.add_argument("--interval", type=int, default=60)

    args = ap.parse_args()

    if args.cmd == "add":
        d = args.date
        if len(d) == 16:
            d = d.replace(" ", "T") + ":00"
        e = add(args.platform, args.content, d, args.tone, args.campaign)
        print(f"Scheduled: [{e['id']}] {args.platform} at {d}")
    elif args.cmd == "list":
        display(_load() if args.all else upcoming(args.days))
    elif args.cmd == "cancel":
        print(f"{'Cancelled' if cancel(args.post_id) else 'Not found'}: {args.post_id}")
    elif args.cmd == "run":
        run_daemon(args.interval)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()

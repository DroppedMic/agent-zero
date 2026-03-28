#!/usr/bin/env python3
"""Post performance analytics from JSONL logs."""

import argparse
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

SKILL_DIR = Path(__file__).parent.parent
LOG_DIR = SKILL_DIR / "logs"
ANALYTICS_DIR = SKILL_DIR / "analytics"


def summary(days: int = 30) -> dict:
    cutoff = datetime.now() - timedelta(days=days)
    by_platform = defaultdict(lambda: {"total": 0, "success": 0, "failed": 0})
    by_day = defaultdict(int)
    total = 0

    if LOG_DIR.exists():
        for lf in sorted(LOG_DIR.glob("posts_*.jsonl")):
            with open(lf) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    e = json.loads(line)
                    try:
                        ts = datetime.fromisoformat(e["timestamp"])
                    except (ValueError, KeyError):
                        continue
                    if ts < cutoff:
                        continue
                    total += 1
                    p = e.get("platform", "?")
                    s = e.get("result", {}).get("status", "?")
                    by_platform[p]["total"] += 1
                    if s == "success":
                        by_platform[p]["success"] += 1
                    elif s in ("error", "failed"):
                        by_platform[p]["failed"] += 1
                    by_day[ts.strftime("%Y-%m-%d")] += 1

    return {
        "period_days": days, "total_posts": total,
        "by_platform": dict(by_platform),
        "by_day": dict(sorted(by_day.items())),
        "generated_at": datetime.now().isoformat(),
    }


def display(s: dict):
    print(f"\n{'='*50}")
    print(f"  Analytics - Last {s['period_days']} days | {s['total_posts']} posts")
    print(f"{'='*50}")
    if s["by_platform"]:
        print(f"\n  {'Platform':<14} {'Total':<7} {'OK':<7} {'Fail':<7} {'Rate'}")
        print(f"  {'-'*42}")
        for p, st in s["by_platform"].items():
            rate = f"{st['success']/st['total']*100:.0f}%" if st["total"] else "-"
            print(f"  {p:<14} {st['total']:<7} {st['success']:<7} {st['failed']:<7} {rate}")
    if s["by_day"]:
        print(f"\n  Recent:")
        for day, n in list(s["by_day"].items())[-7:]:
            print(f"    {day}: {'#'*n} ({n})")
    print()


def export(s: dict, path: str = None) -> str:
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    path = path or str(ANALYTICS_DIR / f"report_{datetime.now().strftime('%Y%m%d')}.json")
    with open(path, "w") as f:
        json.dump(s, f, indent=2)
    print(f"Saved: {path}")
    return path


def main():
    ap = argparse.ArgumentParser(description="Social media analytics")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--output", "-o")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    s = summary(args.days)
    if args.json:
        print(json.dumps(s, indent=2))
    else:
        display(s)
    if args.export or args.output:
        export(s, args.output)


if __name__ == "__main__":
    main()

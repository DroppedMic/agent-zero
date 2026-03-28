#!/usr/bin/env python3
"""Multi-platform social media poster with concurrent posting."""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime

SKILL_DIR = Path(__file__).parent.parent
CONFIG_DIR = SKILL_DIR / "config"
LOG_DIR = SKILL_DIR / "logs"

PLATFORM_LIMITS = {
    "twitter": 280, "linkedin": 3000, "instagram": 2200,
    "facebook": 5000, "threads": 500,
}


def load_config() -> dict:
    path = CONFIG_DIR / "platforms.json"
    if not path.exists():
        print(f"[ERROR] No config at {path}. Run: python {__file__} --setup")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def _log(platform: str, content: str, result: dict):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"posts_{datetime.now().strftime('%Y-%m')}.jsonl"
    entry = json.dumps({
        "timestamp": datetime.now().isoformat(),
        "platform": platform,
        "content": content[:100] + ("..." if len(content) > 100 else ""),
        "result": result,
    })
    with open(log_file, "a") as f:
        f.write(entry + "\n")


def _post_twitter(content: str, config: dict) -> dict:
    try:
        import tweepy
    except ImportError:
        return {"status": "error", "message": "pip install tweepy"}
    c = config.get("twitter", {})
    if not c.get("api_key"):
        return {"status": "error", "message": "Twitter credentials not configured"}
    try:
        client = tweepy.Client(
            consumer_key=c["api_key"], consumer_secret=c["api_secret"],
            access_token=c["access_token"], access_token_secret=c["access_token_secret"],
        )
        r = client.create_tweet(text=content[:280])
        tid = r.data["id"]
        return {"status": "success", "post_id": tid, "url": f"https://x.com/i/status/{tid}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _post_linkedin(content: str, config: dict) -> dict:
    try:
        import requests
    except ImportError:
        return {"status": "error", "message": "pip install requests"}
    c = config.get("linkedin", {})
    if not c.get("access_token"):
        return {"status": "error", "message": "LinkedIn credentials not configured"}
    try:
        r = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers={
                "Authorization": f"Bearer {c['access_token']}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            json={
                "author": f"urn:li:person:{c['person_id']}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {"com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": content[:3000]},
                    "shareMediaCategory": "NONE",
                }},
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
            },
        )
        r.raise_for_status()
        return {"status": "success", "post_id": r.json().get("id", "?")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _post_instagram(content: str, config: dict, image_url: str = None) -> dict:
    if not image_url:
        return {"status": "error", "message": "Instagram requires --image-url"}
    try:
        import requests
    except ImportError:
        return {"status": "error", "message": "pip install requests"}
    c = config.get("instagram", {})
    if not c.get("access_token"):
        return {"status": "error", "message": "Instagram credentials not configured"}
    try:
        aid, tok = c["business_account_id"], c["access_token"]
        cr = requests.post(
            f"https://graph.facebook.com/v19.0/{aid}/media",
            params={"image_url": image_url, "caption": content[:2200], "access_token": tok},
        )
        cr.raise_for_status()
        pr = requests.post(
            f"https://graph.facebook.com/v19.0/{aid}/media_publish",
            params={"creation_id": cr.json()["id"], "access_token": tok},
        )
        pr.raise_for_status()
        return {"status": "success", "post_id": pr.json().get("id", "?")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _post_facebook(content: str, config: dict) -> dict:
    try:
        import requests
    except ImportError:
        return {"status": "error", "message": "pip install requests"}
    c = config.get("facebook", {})
    if not c.get("page_access_token"):
        return {"status": "error", "message": "Facebook credentials not configured"}
    try:
        r = requests.post(
            f"https://graph.facebook.com/v19.0/{c['page_id']}/feed",
            params={"message": content[:5000], "access_token": c["page_access_token"]},
        )
        r.raise_for_status()
        return {"status": "success", "post_id": r.json().get("id", "?")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


_POSTERS = {
    "twitter": _post_twitter,
    "linkedin": _post_linkedin,
    "instagram": _post_instagram,
    "facebook": _post_facebook,
}


def post(content: str, platforms: list, config: dict,
         dry_run: bool = False, image_url: str = None) -> list:
    """Post to platforms concurrently."""

    def _do_post(platform):
        limit = PLATFORM_LIMITS.get(platform, 5000)
        truncated = content[:limit]

        if dry_run:
            return {"status": "dry_run", "platform": platform, "content": truncated,
                    "char_count": len(truncated)}

        if not config.get(platform, {}).get("enabled", False):
            return {"status": "skipped", "platform": platform, "message": "disabled"}

        poster = _POSTERS.get(platform)
        if not poster:
            return {"status": "error", "platform": platform, "message": "unsupported"}

        # Instagram needs image_url kwarg
        if platform == "instagram":
            result = poster(truncated, config, image_url=image_url)
        else:
            result = poster(truncated, config)
        result["platform"] = platform
        _log(platform, truncated, result)
        return result

    # Post concurrently (I/O bound — threads are fine)
    with ThreadPoolExecutor(max_workers=len(platforms)) as pool:
        futures = {pool.submit(_do_post, p): p for p in platforms}
        results = []
        for f in as_completed(futures):
            results.append(f.result())
    return sorted(results, key=lambda r: platforms.index(r.get("platform", "")))


def setup():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    template = {
        "twitter":   {"enabled": False, "api_key": "", "api_secret": "", "access_token": "", "access_token_secret": "", "bearer_token": ""},
        "linkedin":  {"enabled": False, "access_token": "", "person_id": ""},
        "instagram": {"enabled": False, "access_token": "", "business_account_id": ""},
        "facebook":  {"enabled": False, "page_id": "", "page_access_token": ""},
        "approval":  {"required": True, "notify_via": "terminal", "auto_approve_drafts": False},
    }
    path = CONFIG_DIR / "platforms.json"
    with open(path, "w") as f:
        json.dump(template, f, indent=2)
    print(f"Config template: {path}")
    print("  Twitter/X: https://developer.x.com/en/portal/dashboard")
    print("  LinkedIn:  https://developer.linkedin.com/")
    print("  Instagram: https://developers.facebook.com/")


def main():
    ap = argparse.ArgumentParser(description="Post to social media platforms")
    ap.add_argument("--content", "-c")
    ap.add_argument("--platform", "-p")
    ap.add_argument("--platforms")
    ap.add_argument("--all", "-a", action="store_true")
    ap.add_argument("--dry-run", "-d", action="store_true")
    ap.add_argument("--image-url")
    ap.add_argument("--from-file")
    ap.add_argument("--setup", action="store_true")
    args = ap.parse_args()

    if args.setup:
        setup()
        return

    config = load_config()

    if args.all:
        targets = [p for p, c in config.items() if isinstance(c, dict) and c.get("enabled")]
    elif args.platforms:
        targets = [p.strip().lower() for p in args.platforms.split(",")]
    elif args.platform:
        targets = [args.platform.lower()]
    else:
        print("[ERROR] Specify --platform, --platforms, or --all")
        sys.exit(1)

    # Handle --from-file: post each platform's content to its own platform
    if args.from_file:
        with open(args.from_file) as f:
            data = json.load(f)
        if isinstance(data, list):
            for item in data:
                p, c = item.get("platform"), item.get("content")
                if p and c:
                    for r in post(c, [p], config, args.dry_run, args.image_url):
                        print(f"  [{r['status'].upper()}] {r['platform']}: {r.get('url', r.get('message', 'done'))}")
            return
        args.content = data.get("content", "")

    if not args.content:
        print("[ERROR] No content. Use --content or --from-file")
        sys.exit(1)

    results = post(args.content, targets, config, args.dry_run, args.image_url)
    for r in results:
        print(f"  [{r['status'].upper()}] {r['platform']}: {r.get('url', r.get('message', 'done'))}")


if __name__ == "__main__":
    main()

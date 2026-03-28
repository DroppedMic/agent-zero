#!/usr/bin/env python3
"""Claude-powered multi-platform social media content generator."""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime

try:
    from litellm import completion
    _BACKEND = "litellm"
except ImportError:
    try:
        import anthropic
        _BACKEND = "anthropic"
    except ImportError:
        _BACKEND = None

SKILL_DIR = Path(__file__).parent.parent
CONFIG_DIR = SKILL_DIR / "config"

PLATFORMS = {
    "twitter":   {"max": 280,  "name": "Twitter/X",  "style": "Concise, hook-first. 2-4 hashtags. Thread if >280."},
    "linkedin":  {"max": 3000, "name": "LinkedIn",    "style": "Professional storytelling. Hook line, line breaks, 3-5 hashtags at end."},
    "instagram": {"max": 2200, "name": "Instagram",   "style": "Visual-first caption, emoji-ok. Hashtags (up to 30) in separate block."},
    "facebook":  {"max": 5000, "name": "Facebook",    "style": "Conversational, ask questions. Minimal hashtags."},
    "threads":   {"max": 500,  "name": "Threads",     "style": "Casual hot-take energy. No hashtags."},
}

DEFAULT_MODEL = "claude-sonnet-4-20250514"


def _call_claude(prompt: str, model: str = DEFAULT_MODEL, max_tokens: int = 1500) -> str:
    if _BACKEND == "litellm":
        r = completion(
            model=f"anthropic/{model}",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens, temperature=0.8,
        )
        return r.choices[0].message.content.strip()
    if _BACKEND == "anthropic":
        r = anthropic.Anthropic().messages.create(
            model=model, max_tokens=max_tokens, temperature=0.8,
            messages=[{"role": "user", "content": prompt}],
        )
        return r.content[0].text.strip()
    print("[ERROR] No AI SDK. Install: pip install anthropic", file=sys.stderr)
    sys.exit(1)


def _build_batch_prompt(topic: str, platforms: list, tone: str = "professional",
                        context: str = "") -> str:
    """Single prompt that generates content for ALL platforms at once."""
    specs = "\n".join(
        f"- **{PLATFORMS[p]['name']}** (max {PLATFORMS[p]['max']} chars): {PLATFORMS[p]['style']}"
        for p in platforms
    )
    prompt = f"""Generate social media posts for ALL platforms below from this single topic.

TOPIC: {topic}
TONE: {tone}
{"CONTEXT: " + context if context else ""}

PLATFORMS:
{specs}

RULES:
1. Respect each platform's character limit strictly
2. Tailor voice/format per platform — don't just shorten the same text
3. Output ONLY valid JSON: a list of objects with "platform" and "content" keys
4. No markdown fences, no explanations — pure JSON array

Output:"""
    return prompt


def generate_batch(topic: str, platforms: list, tone: str = "professional",
                   context: str = "", model: str = DEFAULT_MODEL) -> list:
    """Generate posts for multiple platforms in a single API call."""
    prompt = _build_batch_prompt(topic, platforms, tone, context)

    # Scale max_tokens to number of platforms
    max_tokens = min(300 * len(platforms) + 200, 4000)
    raw = _call_claude(prompt, model, max_tokens)

    # Parse JSON from response (handle markdown fences if model wraps it)
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        items = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: try to extract JSON array
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            items = json.loads(text[start:end])
        else:
            print(f"[WARN] Could not parse batch response, falling back to single-platform mode", file=sys.stderr)
            return _generate_sequential(topic, platforms, tone, context, model)

    now = datetime.now().isoformat()
    results = []
    for item in items:
        p = item.get("platform", "").lower()
        content = item.get("content", "")
        spec = PLATFORMS.get(p)
        if not spec:
            continue
        results.append({
            "platform": p,
            "platform_name": spec["name"],
            "content": content,
            "char_count": len(content),
            "max_length": spec["max"],
            "within_limit": len(content) <= spec["max"],
            "generated_at": now,
            "topic": topic,
            "tone": tone,
        })
    return results


def generate_single(topic: str, platform: str, tone: str = "professional",
                    context: str = "", model: str = DEFAULT_MODEL) -> dict:
    """Generate a post for one platform."""
    spec = PLATFORMS[platform]
    prompt = f"""Generate a {spec['name']} post.

TOPIC: {topic}
TONE: {tone}
MAX: {spec['max']} chars
STYLE: {spec['style']}
{"CONTEXT: " + context if context else ""}

Output ONLY the post text, nothing else:"""

    # Tight token budget for short-form platforms
    max_tokens = max(150, spec["max"] // 2)
    content = _call_claude(prompt, model, max_tokens)

    return {
        "platform": platform,
        "platform_name": spec["name"],
        "content": content,
        "char_count": len(content),
        "max_length": spec["max"],
        "within_limit": len(content) <= spec["max"],
        "generated_at": datetime.now().isoformat(),
        "topic": topic,
        "tone": tone,
    }


def _generate_sequential(topic, platforms, tone, context, model):
    """Fallback: generate one platform at a time."""
    results = []
    for p in platforms:
        if p not in PLATFORMS:
            continue
        print(f"  Generating {PLATFORMS[p]['name']}...", file=sys.stderr)
        results.append(generate_single(topic, p, tone, context, model))
    return results


def display(results: list, fmt: str = "text"):
    if fmt == "json":
        print(json.dumps(results, indent=2))
        return
    for r in results:
        ok = "OK" if r["within_limit"] else "OVER"
        print(f"\n{'='*55}")
        print(f"  {r['platform_name']} ({r['char_count']}/{r['max_length']}) [{ok}]")
        print(f"{'='*55}")
        print(r["content"])


def save(results: list, path: str = None) -> str:
    if not path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = str(SKILL_DIR / f"output/generated_{ts}.json")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved: {path}")
    return path


def main():
    ap = argparse.ArgumentParser(description="Generate social media content with Claude")
    ap.add_argument("--topic", "-t", required=True)
    ap.add_argument("--platform", "-p", help="Single platform")
    ap.add_argument("--platforms", help="Comma-separated platforms")
    ap.add_argument("--all-platforms", "-a", action="store_true")
    ap.add_argument("--tone", default="professional")
    ap.add_argument("--context", "-c", default="")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--output", "-o", help="Save JSON to path")
    ap.add_argument("--format", "-f", choices=["text", "json"], default="text")
    ap.add_argument("--save", "-s", action="store_true")
    ap.add_argument("--sequential", action="store_true", help="One API call per platform (slower)")
    args = ap.parse_args()

    if args.all_platforms:
        targets = list(PLATFORMS.keys())
    elif args.platforms:
        targets = [p.strip().lower() for p in args.platforms.split(",")]
    elif args.platform:
        targets = [args.platform.lower()]
    else:
        targets = ["twitter", "linkedin"]

    invalid = [p for p in targets if p not in PLATFORMS]
    if invalid:
        print(f"[ERROR] Unknown platforms: {', '.join(invalid)}", file=sys.stderr)
        print(f"  Valid: {', '.join(PLATFORMS.keys())}", file=sys.stderr)
        sys.exit(1)

    print(f"Generating for: {', '.join(targets)} | tone: {args.tone}", file=sys.stderr)

    if len(targets) == 1 or args.sequential:
        results = _generate_sequential(args.topic, targets, args.tone, args.context, args.model)
    else:
        results = generate_batch(args.topic, targets, args.tone, args.context, args.model)

    display(results, args.format)
    if args.save or args.output:
        save(results, args.output)


if __name__ == "__main__":
    main()

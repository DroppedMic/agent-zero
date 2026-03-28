---
name: "social-media-manager"
description: "Generate, schedule, and post social media content across Twitter/X, LinkedIn, Instagram, Facebook, Threads using Claude. Supports multi-agent campaigns via ClawTeam."
version: "1.1.0"
author: "Manny"
tags: ["social-media", "content", "marketing", "automation"]
trigger_patterns:
  - "social media"
  - "post to twitter"
  - "post to linkedin"
  - "post to instagram"
  - "create post"
  - "schedule post"
  - "social campaign"
  - "content calendar"
  - "tweet"
  - "linkedin post"
allowed_tools:
  - "code_execution"
  - "web_search"
---

# Social Media Manager

## Scripts

All scripts are in this skill's `scripts/` directory. Use `code_execution_tool` with `runtime: terminal`.

### Generate Content
```bash
# Single platform
python scripts/content_generator.py -t "TOPIC" -p twitter --tone casual

# All platforms (single API call, returns JSON)
python scripts/content_generator.py -t "TOPIC" -a --save

# Multiple specific platforms
python scripts/content_generator.py -t "TOPIC" --platforms twitter,linkedin --tone excited
```
Tones: professional, casual, excited, educational, humorous

### Post
```bash
# Dry run first
python scripts/platform_poster.py -d -c "Post text" --platforms twitter,linkedin

# Post for real
python scripts/platform_poster.py -c "Post text" -p twitter

# Post from generated file
python scripts/platform_poster.py --from-file output/generated_TIMESTAMP.json -d
```
Credentials: `config/platforms.json` (run `--setup` to create template)

### Schedule
```bash
python scripts/scheduler.py add -p twitter -c "Post text" -d "2026-03-30 09:00"
python scripts/scheduler.py list --days 7
python scripts/scheduler.py cancel POST_ID
python scripts/scheduler.py run  # daemon, checks every 60s
```

### Analytics
```bash
python scripts/analytics.py --days 30
python scripts/analytics.py --export  # saves JSON report
```

### Campaign (ClawTeam swarm)
```bash
bash scripts/campaign_launcher.sh "Campaign Name" "Brief description"
# Spawns: content-strategist, copywriter, visual-designer, scheduler-agent, analytics-tracker
```

## Platform Limits
twitter: 280 | linkedin: 3000 | instagram: 2200 | facebook: 5000 | threads: 500

## Workflow
1. Generate content (`content_generator.py`)
2. Review output (always preview first)
3. Post or schedule (`platform_poster.py` / `scheduler.py`)
4. Track results (`analytics.py`)

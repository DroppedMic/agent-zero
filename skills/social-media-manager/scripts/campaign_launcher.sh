#!/usr/bin/env bash
# Launch a ClawTeam social media campaign swarm
# Usage: campaign_launcher.sh "Campaign Name" "Brief description"
set -euo pipefail

NAME="${1:?Usage: campaign_launcher.sh 'Name' 'Brief'}"
BRIEF="${2:?Provide campaign brief as second arg}"
SLUG=$(echo "$NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')
DIR="$(cd "$(dirname "$0")/.." && pwd)"

_id() { python3 -c "import sys,json;print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "fallback"; }

echo "=== Social Media Campaign: $SLUG ==="
echo "Brief: $BRIEF"
echo ""

# Create team
clawteam team spawn-team "$SLUG" -d "Campaign: $BRIEF" -n content-strategist

# Task pipeline with dependencies
SID=$(clawteam --json task create "$SLUG" "Plan 7-day content calendar for: $BRIEF" -o content-strategist | _id)
CID=$(clawteam --json task create "$SLUG" "Write platform-optimized copy for all calendar slots" -o copywriter --blocked-by "$SID" | _id)
VID=$(clawteam --json task create "$SLUG" "Create JSON image prompts for each post" -o visual-designer --blocked-by "$SID" | _id)
clawteam --json task create "$SLUG" "Schedule all posts at optimal times" -o scheduler-agent --blocked-by "$CID" >/dev/null
clawteam --json task create "$SLUG" "Define KPIs and tracking framework" -o analytics-tracker >/dev/null

# Spawn agents
clawteam spawn -t "$SLUG" -n content-strategist \
  --task "Plan 7-day content calendar for: $BRIEF. Platforms: Twitter/X, LinkedIn, Instagram. Write to content-calendar.md."

clawteam spawn -t "$SLUG" -n copywriter \
  --task "Write posts for every calendar slot. Use $DIR/scripts/content_generator.py or write directly. Save to posts/{day}/{platform}.md"

clawteam spawn -t "$SLUG" -n visual-designer \
  --task "Create compact JSON image prompts per post. Save to visual-prompts/{day}/{platform}.json"

clawteam spawn -t "$SLUG" -n scheduler-agent \
  --task "Schedule posts: python3 $DIR/scripts/scheduler.py add -p PLATFORM -c 'CONTENT' -d 'YYYY-MM-DD HH:MM'"

clawteam spawn -t "$SLUG" -n analytics-tracker \
  --task "Define campaign KPIs. Create tracking template. Save to analytics/"

echo ""
echo "=== Launched: $SLUG ==="
echo "  clawteam board show $SLUG"
echo "  clawteam board attach $SLUG"

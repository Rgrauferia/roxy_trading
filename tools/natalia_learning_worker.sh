#!/usr/bin/env zsh
set -u

PROJECT_DIR="/Users/robertograu/roxy_trading"
SOURCE_DIR="/Volumes/RoxyData/natalia_trading_copy_20260614_175259"
PYTHON="$PROJECT_DIR/.venv/bin/python"
LOCK_DIR="$PROJECT_DIR/run/natalia_learning.lock"
LOG_FILE="$PROJECT_DIR/logs/natalia_learning_worker.log"
STATUS_FILE="$PROJECT_DIR/logs/natalia_learning_worker_status.json"
PID_FILE="$PROJECT_DIR/run/natalia_learning_worker.pid"

mkdir -p "$PROJECT_DIR/run" "$PROJECT_DIR/logs"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "$(date -u +%FT%TZ) worker already running" >> "$LOG_FILE"
  exit 0
fi
trap 'rm -f "$PID_FILE"; rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

cd "$PROJECT_DIR" || exit 1

echo "$$" > "$PID_FILE"
echo "$(date -u +%FT%TZ) starting Natalia learning worker" >> "$LOG_FILE"
printf '{"status":"starting","pid":%s,"source":"%s","started_at":"%s"}\n' "$$" "$SOURCE_DIR" "$(date -u +%FT%TZ)" > "$STATUS_FILE"

while true; do
  if [ ! -d "$SOURCE_DIR" ]; then
    echo "$(date -u +%FT%TZ) source missing: $SOURCE_DIR" >> "$LOG_FILE"
    exit 1
  fi

  output="$("$PYTHON" tools/video_learning_ingest.py \
    --source "$SOURCE_DIR" \
    --limit 1 \
    --max-depth 12 \
    --every-seconds 900 \
    --idle-review 2>&1)"
  rc=$?
  printf '%s\n' "$output" >> "$LOG_FILE"
  printf '%s\n' "$output" > "$STATUS_FILE"

  if [ "$rc" -ne 0 ]; then
    echo "$(date -u +%FT%TZ) ingest failed rc=$rc" >> "$LOG_FILE"
    exit "$rc"
  fi

  processed="$(printf '%s\n' "$output" | "$PYTHON" -c 'import json,sys; data=json.load(sys.stdin); print(int(data.get("processed",0))+int(data.get("materials_processed",0))+int(data.get("manifest_reconciled",0)))' 2>/dev/null || echo 0)"
  found="$(printf '%s\n' "$output" | "$PYTHON" -c 'import json,sys; data=json.load(sys.stdin); print(int(data.get("found",0))+int(data.get("materials_found",0)))' 2>/dev/null || echo 0)"

  echo "$(date -u +%FT%TZ) batch complete processed=$processed found=$found" >> "$LOG_FILE"

  if [ "$processed" -le 0 ]; then
    "$PYTHON" tools/generate_learning_summary.py \
      --source-filter "natalia_trading_copy_20260614_175259" \
      --output "$PROJECT_DIR/training_videos/NATALIA_LEARNING_SUMMARY.md" >> "$LOG_FILE" 2>&1 || true
    echo "$(date -u +%FT%TZ) no new sources left; worker complete" >> "$LOG_FILE"
    exit 0
  fi

  sleep 30
done

#!/usr/bin/env bash
set -e

cd "$HOME/roxy_trading"
mkdir -p logs alerts
source .venv/bin/activate

# Log general (siempre)
echo "----- RUN $(date '+%Y-%m-%d %H:%M:%S') -----" >> logs/roxy_run.log
python app.py >> logs/roxy_run.log 2>&1
echo "" >> logs/roxy_run.log

ALERT_FILE="alerts/latest_alert.txt"
HASH_FILE="alerts/last_hash.txt"
ALERT_LOG="logs/roxy_alerts.log"

# Asegura que el log de alertas exista (aunque no haya alerta)
touch "$ALERT_LOG"

# Notificar SOLO si hay alerta y cambió
if [ -s "$ALERT_FILE" ]; then
  NEW_HASH="$(shasum -a 256 "$ALERT_FILE" | awk '{print $1}')"
  OLD_HASH=""
  [ -f "$HASH_FILE" ] && OLD_HASH="$(cat "$HASH_FILE")"

  if [ "$NEW_HASH" != "$OLD_HASH" ]; then
    echo "$NEW_HASH" > "$HASH_FILE"

    TITLE="🚨 Roxy Trading Alert"
    MSG="$(head -n 1 "$ALERT_FILE")"

    /usr/bin/osascript -e "display notification \"${MSG//\"/\\\"}\" with title \"${TITLE//\"/\\\"}\""

    echo "$(date '+%Y-%m-%d %H:%M:%S') | $MSG" >> "$ALERT_LOG"
  fi
fi

#!/bin/bash
# Factory Watchdog -- Layer 1: Pure bash, zero AI, zero GPU
# Triggered by cron every 10 minutes, checks factory status
# Normal -> write OK and exit
# Abnormal -> call AI engine to repair

# === CONFIGURE THESE PATHS ===
FACTORY_LOG="${AGENT_WORKSPACE:-$HOME/workspace}/logs/dispatcher.log"
STATUS_FILE="/tmp/factory-watchdog-status.txt"
ALERT_FILE="/tmp/agent-alert.md"
ENGINE="$(dirname "$0")/local-agent-engine.py"
WATCHDOG_LOG="/tmp/factory-watchdog.log"
FAIL_COUNT_FILE="/tmp/factory-watchdog-fail-count"

ts() { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(ts)] $1" >> "$WATCHDOG_LOG"; }

# === Adaptive Backoff ===
# More consecutive failures = longer wait before calling AI
# 0 -> call immediately
# 1 -> skip 1 round (wait 10 min)
# 2 -> skip 2 rounds (wait 20 min)
# 3+ -> skip 5 rounds (wait 50 min), send Telegram notification only
FAIL_COUNT=$(cat "$FAIL_COUNT_FILE" 2>/dev/null || echo 0)
FAIL_COUNT=$((FAIL_COUNT + 0))  # ensure integer

# === Check 1: Recent errors in dispatcher log ===
ERROR_PATTERN="ERROR|FAIL|syntax error|Traceback|unbound variable|command not found|Connection refused|JSONDecodeError|Permission denied|No such file|timed out"
RECENT_ERRORS=$(tail -200 "$FACTORY_LOG" 2>/dev/null | grep -c -E "$ERROR_PATTERN")

# === Check 2: Dispatcher last activity time ===
NOW_TS=$(date +%s)
LOG_TS=$(stat -c %Y "$FACTORY_LOG" 2>/dev/null || echo 0)
if [ "$LOG_TS" -gt 0 ]; then
  MINS_AGO=$(( (NOW_TS - LOG_TS) / 60 ))
else
  MINS_AGO=999
fi

# === Check 3: Gateway status (cron may lack dbus, use process check fallback) ===
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"
GW_STATUS=$(systemctl --user is-active your-gateway-service 2>/dev/null)
# Fallback: if systemctl fails in cron, check process directly
if [ -z "$GW_STATUS" ] || [ "$GW_STATUS" = "" ]; then
  if pgrep -f "your-gateway-process" > /dev/null 2>&1; then
    GW_STATUS="active"
  else
    GW_STATUS="inactive"
  fi
fi

# === Check 4: Dispatcher cron exists ===
CRON_OK=$(crontab -l 2>/dev/null | grep -c "factory-dispatcher")

# === Decision ===
PROBLEMS=""

if [ "$RECENT_ERRORS" -gt 3 ]; then
  PROBLEMS="${PROBLEMS}dispatcher log has ${RECENT_ERRORS} errors; "
fi

if [ ! -f "$FACTORY_LOG" ]; then
  PROBLEMS="${PROBLEMS}dispatcher log does not exist; "
fi

if [ "$MINS_AGO" -gt 45 ]; then
  PROBLEMS="${PROBLEMS}dispatcher log inactive for ${MINS_AGO} min; "
fi

if [ "$GW_STATUS" != "active" ]; then
  PROBLEMS="${PROBLEMS}gateway status: ${GW_STATUS}; "
fi

if [ "$CRON_OK" -eq 0 ]; then
  PROBLEMS="${PROBLEMS}dispatcher cron missing; "
fi

# === Result ===
if [ -z "$PROBLEMS" ]; then
  # Normal -> reset fail count
  echo "0" > "$FAIL_COUNT_FILE"
  echo "OK $(ts) | dispatcher ${MINS_AGO}m ago | gw=${GW_STATUS} | errors=${RECENT_ERRORS}" > "$STATUS_FILE"
  log "OK | dispatcher ${MINS_AGO}m ago | errors=${RECENT_ERRORS}"
else
  # Abnormal -> adaptive backoff
  log "ALERT(#$((FAIL_COUNT+1))): $PROBLEMS"
  echo "ERROR $(ts) | fail#$((FAIL_COUNT+1)) | $PROBLEMS" > "$STATUS_FILE"

  # Adaptive backoff: decide whether to call AI based on consecutive failures
  SKIP_THRESHOLD=0
  if [ "$FAIL_COUNT" -ge 3 ]; then
    SKIP_THRESHOLD=5  # 3+ consecutive failures: call every 5 rounds (~50 min)
  elif [ "$FAIL_COUNT" -ge 1 ]; then
    SKIP_THRESHOLD=$FAIL_COUNT  # 1-2 failures: wait corresponding rounds
  fi

  # Use fail count mod threshold to decide
  if [ "$SKIP_THRESHOLD" -gt 0 ] && [ $((FAIL_COUNT % (SKIP_THRESHOLD + 1))) -ne 0 ]; then
    log "Adaptive sleep: ${FAIL_COUNT} consecutive failures, skipping this round (call every $((SKIP_THRESHOLD+1)) rounds)"
    echo "$((FAIL_COUNT + 1))" > "$FAIL_COUNT_FILE"

    # If 3+ failures, optionally notify via Telegram
    if [ "$FAIL_COUNT" -ge 3 ] && [ -n "$BOT_TOKEN" ] && [ -n "$OPERATOR_ID" ]; then
      curl -s "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d "{\"chat_id\":\"${OPERATOR_ID}\",\"text\":\"ALERT: Factory issue persists (attempt ${FAIL_COUNT})\\n${PROBLEMS}\\nAI could not fix. Waiting for next round or manual intervention.\"}" \
        -H "Content-Type: application/json" > /dev/null 2>&1
      log "Telegram notification sent"
    fi
    exit 0
  fi

  # Extract relevant log snippet for AI (don't make it read everything)
  ERROR_CONTEXT=$(tail -50 "$FACTORY_LOG" 2>/dev/null)

  # Call AI engine
  log "Calling AI engine for repair (attempt $((FAIL_COUNT+1)))..."
  RESULT=$(cd "$(dirname "$ENGINE")" && python3 "$ENGINE" "You are the factory watchdog. Sentinel detected anomaly: ${PROBLEMS}

Recent dispatcher log:
${ERROR_CONTEXT}

Attempt repair:
1. Analyze the log to find root cause
2. If syntax error in dispatcher.sh -> bash -n to find line -> fix -> verify
3. If gateway is down -> DO NOT restart, just report
4. Before modifying any file: cp <file> <file>.bak-\$(date +%s)
5. Report what was fixed

NEVER: change Python env, delete data, modify configs, restart services
If you cannot fix after 4 attempts -> report 'needs manual intervention'" 2>&1)

  # Check repair result
  if echo "$RESULT" | grep -q "needs manual intervention"; then
    echo "$((FAIL_COUNT + 1))" > "$FAIL_COUNT_FILE"
    log "AI could not fix (#$((FAIL_COUNT+1))), writing alert, backing off longer"
    cat > "$ALERT_FILE" << EOF
Time: $(ts)
Problem: $PROBLEMS
Consecutive failures: $((FAIL_COUNT + 1))
AI repair result: Needs manual intervention
Details:
$(echo "$RESULT" | tail -30)
EOF
  else
    echo "0" > "$FAIL_COUNT_FILE"
    log "AI repair completed, resetting fail count"
    echo "FIXED $(ts) | $PROBLEMS -> AI repaired" > "$STATUS_FILE"
  fi
fi

#!/usr/bin/env bash
# Safe restart of the local NiceGUI app on Windows. Prevents the "file is being used
# by another process" race: it KILLS the old app, then WAITS until that process has
# fully exited AND port 8502 is released BEFORE relaunching — so the new process
# never contends with the dying one's log/socket handles. Use this instead of an
# inline "Stop-Process; sleep 2; python ... > app.log &".
set -u
LOG="${1:-$TEMP/praxis_app.log}"
PS() { powershell.exe -NoProfile -Command "$1" 2>/dev/null | tr -d '\r'; }

# 1) signal the running app to stop
PS "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*app_nicegui.py*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }" >/dev/null

# 2) WAIT until it is actually gone (poll up to ~25s) — do NOT race its handles
for i in $(seq 1 50); do
  n=$(PS "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*app_nicegui.py*' } | Measure-Object).Count")
  [ "${n:-0}" = "0" ] && break
  sleep 0.5
done

# 3) WAIT until port 8502 has no LISTEN socket left (lingering bind = a hung restart)
for i in $(seq 1 30); do
  n=$(PS "(Get-NetTCPConnection -LocalPort 8502 -State Listen -ErrorAction SilentlyContinue | Measure-Object).Count")
  [ "${n:-0}" = "0" ] && break
  sleep 0.5
done

# 4) old process + port confirmed clear -> safe to open the log and start fresh
: > "$LOG"                       # truncate now that no one holds it
# DEV_TENANT picks the tenant a fresh session boots into (app defaults to 'usio'). This only
# affects NEW sessions: app.storage.user["active_client_id"] is set via setdefault, and an
# existing browser session's choice lives in an httpOnly cookie the app won't override — so to
# actually land on a different tenant, use a fresh/incognito session (or clear .nicegui storage).
DEV_TENANT="${DEV_TENANT:-usio}" \
DEV_AUTOLOGIN="${DEV_AUTOLOGIN:-PPADMIN@praxispoint.com}" \
  nohup python app_nicegui.py > "$LOG" 2>&1 &
until grep -q "NiceGUI ready" "$LOG" 2>/dev/null; do sleep 1; done
echo "app restarted cleanly -> $LOG"

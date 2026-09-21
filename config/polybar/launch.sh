#!/usr/bin/env bash
set -euo pipefail

DIR="${XDG_CONFIG_HOME:-$HOME/.config}/polybar"
STATE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/polybar"
mkdir -p "$STATE_DIR"
exec 9> "$STATE_DIR/launch.lock"
flock 9

# Reload the existing bar without racing a second launch or waiting on zombies.
if pgrep -u "$UID" -x polybar >/dev/null; then
    pkill -USR1 -u "$UID" -x polybar 2>/dev/null || true
    exit 0
fi

# Do not let the long-running bar retain our launch lock.
polybar -q main -c "$DIR/config.ini" 9>&- </dev/null > "$STATE_DIR/polybar.log" 2>&1 &
bar_pid=$!
# Keep concurrent launchers behind the lock until the child has exec'd Polybar.
for attempt in {1..20}; do
    pgrep -u "$UID" -x polybar >/dev/null && exit 0
    kill -0 "$bar_pid" 2>/dev/null || { wait "$bar_pid"; exit 1; }
    sleep 0.05
done

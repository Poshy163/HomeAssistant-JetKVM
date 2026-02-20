#!/bin/sh
# =====================================================================
# JetKVM Home Assistant API Setup
# =====================================================================
# Installs a lightweight nc-based HTTP server on the JetKVM device
# that exposes system data (temperature, uptime, etc.) as JSON
# endpoints for the Home Assistant JetKVM integration.
#
# The server is supervised by a watchdog that auto-restarts on crash
# and uses setsid to survive SSH session disconnects.
#
# An auto-updater checks GitHub every 5 minutes and silently re-installs
# if a newer version of this script is available.
#
# Usage:
#   1. SSH into your JetKVM:  ssh root@<jetkvm-ip>
#   2. Run:
#      wget --no-check-certificate -O /tmp/api-setup.sh \
#        https://raw.githubusercontent.com/Poshy163/HomeAssistant-JetKVM/main/api-setup.sh \
#        && sh /tmp/api-setup.sh
#
# Endpoints (after install):
#   http://<jetkvm-ip>:8800/health
#   http://<jetkvm-ip>:8800/temperature
#   http://<jetkvm-ip>:8800/device_info
#
# To uninstall:
#   sh /tmp/api-setup.sh --uninstall
#   (or: sh /opt/ha-api/uninstall.sh)
# =====================================================================

API_VERSION="1.1.0"
API_PORT=8800
BASE_DIR="/opt/ha-api"
VERSION_FILE="${BASE_DIR}/version"
HANDLER_SCRIPT="${BASE_DIR}/handler.sh"
WATCHDOG_SCRIPT="${BASE_DIR}/watchdog.sh"
UPDATER_SCRIPT="${BASE_DIR}/updater.sh"
PID_FILE="${BASE_DIR}/watchdog.pid"
UPDATER_PID_FILE="${BASE_DIR}/updater.pid"
LOG_FILE="${BASE_DIR}/server.log"
UNINSTALL_SCRIPT="${BASE_DIR}/uninstall.sh"
SETUP_URL="https://raw.githubusercontent.com/Poshy163/HomeAssistant-JetKVM/main/api-setup.sh"
UPDATE_INTERVAL=300

# =====================================================================
# Uninstall
# =====================================================================
if [ "$1" = "--uninstall" ]; then
    echo "=== Uninstalling JetKVM HA API ==="

    # Stop updater
    if [ -f "$UPDATER_PID_FILE" ]; then
        UPID=$(cat "$UPDATER_PID_FILE")
        kill "$UPID" 2>/dev/null
        sleep 1
        kill -9 "$UPID" 2>/dev/null
        rm -f "$UPDATER_PID_FILE"
    fi

    # Stop watchdog (kills nc children too)
    if [ -f "$PID_FILE" ]; then
        WPID=$(cat "$PID_FILE")
        kill "$WPID" 2>/dev/null
        sleep 1
        kill -9 "$WPID" 2>/dev/null
        rm -f "$PID_FILE"
    fi

    # Kill anything still on our port
    for p in $(netstat -tlnp 2>/dev/null | grep ":${API_PORT} " | awk '{print $NF}' | cut -d/ -f1); do
        kill "$p" 2>/dev/null
    done

    # Remove files
    rm -rf "$BASE_DIR"

    # Remove from rc.local (current and legacy entries)
    if [ -f /etc/rc.local ]; then
        sed -i "\|${WATCHDOG_SCRIPT}|d" /etc/rc.local
        sed -i "\|${UPDATER_SCRIPT}|d" /etc/rc.local
        sed -i "\|/opt/ha-api/server.sh|d" /etc/rc.local
        sed -i "\|/opt/ha-api/start.sh|d" /etc/rc.local
    fi

    echo "Done. API server removed."
    exit 0
fi

echo "=== JetKVM Home Assistant API Setup ==="
echo ""

# =====================================================================
# Stop any existing instance
# =====================================================================
echo "Stopping any existing instance..."
if [ -f "$UPDATER_PID_FILE" ]; then
    UPID=$(cat "$UPDATER_PID_FILE")
    kill "$UPID" 2>/dev/null
    sleep 1
    kill -9 "$UPID" 2>/dev/null
fi
if [ -f "$PID_FILE" ]; then
    WPID=$(cat "$PID_FILE")
    kill "$WPID" 2>/dev/null
    sleep 1
    kill -9 "$WPID" 2>/dev/null
fi
# Also stop old server.pid if present
if [ -f "${BASE_DIR}/server.pid" ]; then
    kill "$(cat "${BASE_DIR}/server.pid")" 2>/dev/null
fi
# Kill anything on our port
for p in $(netstat -tlnp 2>/dev/null | grep ":${API_PORT} " | awk '{print $NF}' | cut -d/ -f1); do
    kill "$p" 2>/dev/null
done
# Clean up old files from previous versions
rm -f "${BASE_DIR}/server.sh" "${BASE_DIR}/fifo" "${BASE_DIR}/server.pid"
rm -rf "${BASE_DIR}/www" "${BASE_DIR}/config.sh"
sleep 1

# =====================================================================
# Check that nc is available
# =====================================================================
echo "Checking for nc (netcat)..."
NC_CMD=""
if command -v nc >/dev/null 2>&1; then
    NC_CMD="nc"
elif busybox nc --help >/dev/null 2>&1; then
    NC_CMD="busybox nc"
fi

if [ -z "$NC_CMD" ]; then
    echo "ERROR: Cannot find nc (netcat) on this device."
    echo "  which nc: $(which nc 2>&1)"
    echo "  busybox --list | grep nc:"
    busybox --list 2>&1 | grep "^nc$" || echo "    (none)"
    exit 1
fi
echo "  Found: $NC_CMD"

# Check if nc supports -e (execute) flag
echo '#!/bin/sh' > /tmp/_nc_test_handler.sh
echo 'echo test' >> /tmp/_nc_test_handler.sh
chmod +x /tmp/_nc_test_handler.sh

# Test nc -e support by trying to listen briefly
NC_HAS_E=0
$NC_CMD -l -p 18899 -e /tmp/_nc_test_handler.sh &
NC_TEST_PID=$!
sleep 1
if kill -0 "$NC_TEST_PID" 2>/dev/null; then
    NC_HAS_E=1
    kill "$NC_TEST_PID" 2>/dev/null
fi
rm -f /tmp/_nc_test_handler.sh
echo "  nc -e support: $([ "$NC_HAS_E" = "1" ] && echo "yes" || echo "no (will use pipe mode)")"

# =====================================================================
# Create directory
# =====================================================================
mkdir -p "$BASE_DIR"
echo "$API_VERSION" > "$VERSION_FILE"

# =====================================================================
# Request handler script
# =====================================================================
cat << 'HANDLER' > "$HANDLER_SCRIPT"
#!/bin/sh

# Escape a string for safe embedding inside a JSON string value.
# Handles backslash, double-quote, and control characters.
json_escape() {
    printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/	/\\t/g' | tr -d '\n\r'
}

# Read the HTTP request line (with a timeout via TMOUT or read -t)
# BusyBox ash supports read -t
read -t 5 -r REQUEST_LINE 2>/dev/null || REQUEST_LINE=""

if [ -z "$REQUEST_LINE" ]; then
    printf "HTTP/1.0 408 Timeout\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
    exit 0
fi

# Extract path
REQUEST_PATH=$(echo "$REQUEST_LINE" | awk '{print $2}')

# Consume remaining headers (read until blank line, with timeout)
while read -t 2 -r header 2>/dev/null; do
    header=$(echo "$header" | tr -d '\r')
    [ -z "$header" ] && break
done

# --- Route ---
case "$REQUEST_PATH" in
    /health)
        BODY='{"status":"ok"}'
        ;;
    /temperature)
        TEMP_RAW=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null)
        if [ -z "$TEMP_RAW" ]; then
            BODY='{"error":"cannot read temperature"}'
        else
            TEMP_INT=$((TEMP_RAW / 1000))
            TEMP_FRAC=$(( (TEMP_RAW % 1000) / 100 ))
            BODY="{\"temperature\":${TEMP_INT}.${TEMP_FRAC}}"
        fi
        ;;
    /device_info)
        # API version
        API_VER=$(cat /opt/ha-api/version 2>/dev/null)
        [ -z "$API_VER" ] && API_VER="unknown"

        # Temperature
        TEMP_RAW=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null)
        TEMP_INT=$((TEMP_RAW / 1000))
        TEMP_FRAC=$(( (TEMP_RAW % 1000) / 100 ))

        # Identity
        DEV_HOSTNAME=$(hostname 2>/dev/null || echo "jetkvm")
        SERIAL=$(cat /sys/firmware/devicetree/base/serial-number 2>/dev/null | tr -d '\0')
        MODEL=$(cat /sys/firmware/devicetree/base/model 2>/dev/null | tr -d '\0')
        [ -z "$MODEL" ] && MODEL="JetKVM"

        # Firmware / kernel
        KERNEL_VERSION=$(uname -r 2>/dev/null)
        KERNEL_BUILD=$(uname -v 2>/dev/null)

        # Network
        IP=$(ip -4 addr show eth0 2>/dev/null | awk '/inet / {split($2,a,"/"); print a[1]; exit}')
        [ -z "$IP" ] && IP=$(ifconfig eth0 2>/dev/null | awk '/inet addr/{split($2,a,":"); print a[2]; exit}')
        [ -z "$IP" ] && IP="unknown"
        MAC=$(cat /sys/class/net/eth0/address 2>/dev/null)
        LINK_STATE=$(cat /sys/class/net/eth0/operstate 2>/dev/null)

        # Uptime
        UPTIME=$(awk '{print $1}' /proc/uptime 2>/dev/null)
        [ -z "$UPTIME" ] && UPTIME=0

        # Memory (kB)
        MEM_TOTAL=$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null)
        MEM_AVAIL=$(awk '/MemAvailable/ {print $2}' /proc/meminfo 2>/dev/null)
        case "$MEM_TOTAL" in ''|*[!0-9]*) MEM_TOTAL=0 ;; esac
        case "$MEM_AVAIL" in ''|*[!0-9]*) MEM_AVAIL=0 ;; esac
        if [ "$MEM_TOTAL" -gt 0 ] 2>/dev/null; then
            MEM_USED=$((MEM_TOTAL - MEM_AVAIL))
            # percentage * 10 for one decimal place using integer math
            MEM_PCT_X10=$(( MEM_USED * 1000 / MEM_TOTAL ))
            MEM_PCT_INT=$((MEM_PCT_X10 / 10))
            MEM_PCT_FRAC=$((MEM_PCT_X10 % 10))
        else
            MEM_PCT_INT=0
            MEM_PCT_FRAC=0
        fi

        # Storage — root filesystem
        # Use awk to skip the header (NR>1) and grab the first data line.
        # BusyBox df may output differently, so try multiple approaches.
        DISK_TOTAL_KB=$(df / 2>/dev/null | awk 'NR==2 {print $2}')
        DISK_USED_KB=$(df / 2>/dev/null | awk 'NR==2 {print $3}')
        DISK_AVAIL_KB=$(df / 2>/dev/null | awk 'NR==2 {print $4}')

        # Validate values are numeric — fallback to 0 if not
        case "$DISK_TOTAL_KB" in ''|*[!0-9]*) DISK_TOTAL_KB=0 ;; esac
        case "$DISK_USED_KB" in ''|*[!0-9]*) DISK_USED_KB=0 ;; esac
        case "$DISK_AVAIL_KB" in ''|*[!0-9]*) DISK_AVAIL_KB=0 ;; esac

        if [ "$DISK_TOTAL_KB" -gt 0 ] 2>/dev/null; then
            DISK_PCT_X10=$(( DISK_USED_KB * 1000 / DISK_TOTAL_KB ))
            DISK_PCT_INT=$((DISK_PCT_X10 / 10))
            DISK_PCT_FRAC=$((DISK_PCT_X10 % 10))
        else
            DISK_PCT_INT=0
            DISK_PCT_FRAC=0
        fi

        # CPU load (1 min avg)
        LOAD_AVG=$(awk '{print $1}' /proc/loadavg 2>/dev/null)
        [ -z "$LOAD_AVG" ] && LOAD_AVG=0

        # Build JSON with properly escaped strings
        J_MODEL=$(json_escape "$MODEL")
        J_SERIAL=$(json_escape "$SERIAL")
        J_HOSTNAME=$(json_escape "$DEV_HOSTNAME")
        J_IP=$(json_escape "$IP")
        J_MAC=$(json_escape "$MAC")
        J_LINK=$(json_escape "$LINK_STATE")
        J_KVER=$(json_escape "$KERNEL_VERSION")
        J_KBUILD=$(json_escape "$KERNEL_BUILD")
        J_APIVER=$(json_escape "$API_VER")

        BODY="{\"api_version\":\"${J_APIVER}\",\"deviceModel\":\"${J_MODEL}\",\"serial_number\":\"${J_SERIAL}\",\"hostname\":\"${J_HOSTNAME}\",\"ip_address\":\"${J_IP}\",\"mac_address\":\"${J_MAC}\",\"network_state\":\"${J_LINK}\",\"kernel_version\":\"${J_KVER}\",\"kernel_build\":\"${J_KBUILD}\",\"temperature\":${TEMP_INT}.${TEMP_FRAC},\"uptime_seconds\":${UPTIME:-0},\"load_average\":${LOAD_AVG:-0},\"mem_total_kb\":${MEM_TOTAL:-0},\"mem_available_kb\":${MEM_AVAIL:-0},\"mem_used_pct\":${MEM_PCT_INT}.${MEM_PCT_FRAC},\"disk_total_kb\":${DISK_TOTAL_KB:-0},\"disk_used_kb\":${DISK_USED_KB:-0},\"disk_available_kb\":${DISK_AVAIL_KB:-0},\"disk_used_pct\":${DISK_PCT_INT}.${DISK_PCT_FRAC}}"
        ;;
    *)
        BODY='{"error":"not found"}'
        ;;
esac

CONTENT_LENGTH=$(echo -n "$BODY" | wc -c)

printf "HTTP/1.0 200 OK\r\n"
printf "Content-Type: application/json\r\n"
printf "Content-Length: %d\r\n" "$CONTENT_LENGTH"
printf "Access-Control-Allow-Origin: *\r\n"
printf "Connection: close\r\n"
printf "\r\n"
printf "%s" "$BODY"
HANDLER
chmod +x "$HANDLER_SCRIPT"

# =====================================================================
# Write config file (values expanded at install time)
# =====================================================================
cat > "${BASE_DIR}/config.sh" << CONF
NC_CMD="${NC_CMD}"
NC_HAS_E=${NC_HAS_E}
API_PORT=${API_PORT}
BASE_DIR="${BASE_DIR}"
HANDLER_SCRIPT="${HANDLER_SCRIPT}"
PID_FILE="${PID_FILE}"
LOG_FILE="${LOG_FILE}"
SETUP_URL="${SETUP_URL}"
VERSION_FILE="${VERSION_FILE}"
UPDATER_PID_FILE="${UPDATER_PID_FILE}"
UPDATE_INTERVAL=${UPDATE_INTERVAL}
CONF

# =====================================================================
# Watchdog script — runs nc in a loop, restarts on exit.
# Fully detached from terminal via setsid.
# =====================================================================
cat << 'WATCHDOG' > "$WATCHDOG_SCRIPT"
#!/bin/sh
# Watchdog for nc-based HTTP server

# Load config
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "${SCRIPT_DIR}/config.sh"

log() {
    # Keep log file under 50KB
    if [ -f "$LOG_FILE" ]; then
        LOG_SIZE=$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)
        if [ "$LOG_SIZE" -gt 50000 ]; then
            tail -c 25000 "$LOG_FILE" > "${LOG_FILE}.tmp"
            mv "${LOG_FILE}.tmp" "$LOG_FILE"
        fi
    fi
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"
}

# Write our PID
echo $$ > "$PID_FILE"

# Clean up on signal
cleanup() {
    log "Watchdog stopping (signal received)"
    # Kill all children in our process group
    kill 0 2>/dev/null
    rm -f "$PID_FILE"
    exit 0
}
trap cleanup INT TERM HUP

log "Watchdog starting (PID $$) — nc=$NC_CMD nc_e=$NC_HAS_E"

RESTART_COUNT=0
MAX_FAST_RESTARTS=50
FAST_RESTART_WINDOW=10
LAST_RESTART_TIME=0

while true; do
    if [ "$NC_HAS_E" = "1" ]; then
        # nc -e mode: nc hands off each connection to the handler script
        $NC_CMD -l -p "$API_PORT" -e "$HANDLER_SCRIPT" 2>/dev/null
    else
        # Pipe mode: use a named pipe (FIFO) for bidirectional I/O
        FIFO="${BASE_DIR}/fifo"
        [ ! -p "$FIFO" ] && { rm -f "$FIFO"; mkfifo "$FIFO"; }
        cat "$FIFO" | $NC_CMD -l -p "$API_PORT" | "$HANDLER_SCRIPT" > "$FIFO" 2>/dev/null
    fi

    # nc exits after each connection — this is normal.
    # Track rapid restarts only to detect real problems.
    NOW=$(date +%s 2>/dev/null || awk '{printf "%d", $1}' /proc/uptime)
    ELAPSED=$((NOW - LAST_RESTART_TIME))
    if [ "$ELAPSED" -lt "$FAST_RESTART_WINDOW" ]; then
        RESTART_COUNT=$((RESTART_COUNT + 1))
    else
        RESTART_COUNT=0
    fi
    LAST_RESTART_TIME=$NOW

    if [ "$RESTART_COUNT" -ge "$MAX_FAST_RESTARTS" ]; then
        log "ERROR: nc restarted $RESTART_COUNT times in <${FAST_RESTART_WINDOW}s — backing off 30s"
        sleep 30
        RESTART_COUNT=0
    fi
done
WATCHDOG
chmod +x "$WATCHDOG_SCRIPT"

# =====================================================================
# Uninstall helper
# =====================================================================
cat << 'UNINST' > "$UNINSTALL_SCRIPT"
#!/bin/sh
API_PORT=8800
BASE_DIR="/opt/ha-api"
PID_FILE="${BASE_DIR}/watchdog.pid"
UPDATER_PID_FILE="${BASE_DIR}/updater.pid"
WATCHDOG_SCRIPT="${BASE_DIR}/watchdog.sh"
UPDATER_SCRIPT="${BASE_DIR}/updater.sh"

if [ -f "$UPDATER_PID_FILE" ]; then
    kill $(cat "$UPDATER_PID_FILE") 2>/dev/null
    sleep 1
    kill -9 $(cat "$UPDATER_PID_FILE") 2>/dev/null
fi
if [ -f "$PID_FILE" ]; then
    kill $(cat "$PID_FILE") 2>/dev/null
    sleep 1
    kill -9 $(cat "$PID_FILE") 2>/dev/null
fi
for p in $(netstat -tlnp 2>/dev/null | grep ":${API_PORT} " | awk '{print $NF}' | cut -d/ -f1); do
    kill "$p" 2>/dev/null
done
rm -rf "$BASE_DIR"
if [ -f /etc/rc.local ]; then
    sed -i "\|${WATCHDOG_SCRIPT}|d" /etc/rc.local
    sed -i "\|${UPDATER_SCRIPT}|d" /etc/rc.local
    sed -i "\|/opt/ha-api/server.sh|d" /etc/rc.local
    sed -i "\|/opt/ha-api/start.sh|d" /etc/rc.local
fi
echo "Uninstalled."
UNINST
chmod +x "$UNINSTALL_SCRIPT"

# =====================================================================
# Auto-updater script — checks GitHub every 5 minutes, re-runs if newer
# =====================================================================
cat << 'UPDATER' > "$UPDATER_SCRIPT"
#!/bin/sh
# Auto-updater for JetKVM HA API
# Checks the remote api-setup.sh for a higher version every UPDATE_INTERVAL
# seconds. If the remote API_VERSION is greater than the local version,
# downloads and re-runs the script automatically.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "${SCRIPT_DIR}/config.sh"

log() {
    # Reuse the server log file, keep it trimmed
    if [ -f "$LOG_FILE" ]; then
        LOG_SIZE=$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)
        if [ "$LOG_SIZE" -gt 50000 ]; then
            tail -c 25000 "$LOG_FILE" > "${LOG_FILE}.tmp"
            mv "${LOG_FILE}.tmp" "$LOG_FILE"
        fi
    fi
    echo "$(date '+%Y-%m-%d %H:%M:%S') [updater] $1" >> "$LOG_FILE"
}

# Compare two semver strings: returns 0 if $1 < $2, 1 if $1 >= $2
version_lt() {
    _a="$1"; _b="$2"
    # Split on '.' and compare each numeric component
    _a1=$(echo "$_a" | cut -d. -f1); _a2=$(echo "$_a" | cut -d. -f2); _a3=$(echo "$_a" | cut -d. -f3)
    _b1=$(echo "$_b" | cut -d. -f1); _b2=$(echo "$_b" | cut -d. -f2); _b3=$(echo "$_b" | cut -d. -f3)
    # Default empty components to 0
    _a1=${_a1:-0}; _a2=${_a2:-0}; _a3=${_a3:-0}
    _b1=${_b1:-0}; _b2=${_b2:-0}; _b3=${_b3:-0}
    if [ "$_a1" -lt "$_b1" ] 2>/dev/null; then return 0; fi
    if [ "$_a1" -gt "$_b1" ] 2>/dev/null; then return 1; fi
    if [ "$_a2" -lt "$_b2" ] 2>/dev/null; then return 0; fi
    if [ "$_a2" -gt "$_b2" ] 2>/dev/null; then return 1; fi
    if [ "$_a3" -lt "$_b3" ] 2>/dev/null; then return 0; fi
    return 1
}

# Write our PID
echo $$ > "$UPDATER_PID_FILE"

cleanup() {
    log "Updater stopping (signal received)"
    rm -f "$UPDATER_PID_FILE"
    exit 0
}
trap cleanup INT TERM HUP

log "Updater starting (PID $$) — checking every ${UPDATE_INTERVAL}s"

while true; do
    sleep "$UPDATE_INTERVAL"

    log "Checking for updates..."

    # Download latest script to a temp file
    TMP_SCRIPT="/tmp/api-setup-update.sh"
    rm -f "$TMP_SCRIPT"

    wget --no-check-certificate -qO "$TMP_SCRIPT" "$SETUP_URL" 2>/dev/null
    if [ $? -ne 0 ] || [ ! -s "$TMP_SCRIPT" ]; then
        log "Update check failed: could not download $SETUP_URL"
        rm -f "$TMP_SCRIPT"
        continue
    fi

    # Extract API_VERSION from the downloaded script
    REMOTE_VER=$(grep '^API_VERSION=' "$TMP_SCRIPT" | head -1 | sed 's/API_VERSION="\(.*\)"/\1/')
    LOCAL_VER=$(cat "$VERSION_FILE" 2>/dev/null)

    if [ -z "$REMOTE_VER" ]; then
        log "Update check failed: could not extract API_VERSION from remote script"
        rm -f "$TMP_SCRIPT"
        continue
    fi

    if [ -z "$LOCAL_VER" ]; then
        LOCAL_VER="0.0.0"
    fi

    if ! version_lt "$LOCAL_VER" "$REMOTE_VER"; then
        log "No update available (local=$LOCAL_VER remote=$REMOTE_VER)"
        rm -f "$TMP_SCRIPT"
        continue
    fi

    log "Update found! local=$LOCAL_VER remote=$REMOTE_VER — applying..."

    # Run the new setup script (it will stop existing watchdog/updater, reinstall, and restart everything)
    sh "$TMP_SCRIPT" 2>&1 | while IFS= read -r line; do log "  $line"; done
    rm -f "$TMP_SCRIPT"

    log "Update applied — exiting old updater (new one should be running)"
    rm -f "$UPDATER_PID_FILE"
    exit 0
done
UPDATER
chmod +x "$UPDATER_SCRIPT"

# =====================================================================
# Persist across reboots via /etc/rc.local
# =====================================================================
if [ ! -f /etc/rc.local ]; then
    printf '#!/bin/sh\nexit 0\n' > /etc/rc.local
    chmod +x /etc/rc.local
fi

# Remove old entries
sed -i "\|/opt/ha-api/server.sh|d" /etc/rc.local
sed -i "\|/opt/ha-api/start.sh|d" /etc/rc.local
sed -i "\|${WATCHDOG_SCRIPT}|d" /etc/rc.local
sed -i "\|${UPDATER_SCRIPT}|d" /etc/rc.local

# Add watchdog with setsid (fully detached from terminal)
sed -i "/^exit 0/i (sleep 3 && setsid ${WATCHDOG_SCRIPT} </dev/null >/dev/null 2>&1 &)" /etc/rc.local

# Add auto-updater with setsid (fully detached from terminal)
sed -i "/^exit 0/i (sleep 10 && setsid ${UPDATER_SCRIPT} </dev/null >/dev/null 2>&1 &)" /etc/rc.local

# =====================================================================
# Start the server now
# =====================================================================
echo ""
echo "Starting API server on port ${API_PORT}..."

setsid "$WATCHDOG_SCRIPT" </dev/null >/dev/null 2>&1 &
setsid "$UPDATER_SCRIPT" </dev/null >/dev/null 2>&1 &
sleep 2

# =====================================================================
# Verify
# =====================================================================
RUNNING=0
if netstat -tlnp 2>/dev/null | grep -q ":${API_PORT} "; then
    RUNNING=1
fi
# Also check if watchdog PID is alive
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    RUNNING=1
fi

if [ "$RUNNING" = "1" ]; then
    IP=$(ip -4 addr show eth0 2>/dev/null | awk '/inet / {split($2,a,"/"); print a[1]; exit}')
    [ -z "$IP" ] && IP=$(ifconfig eth0 2>/dev/null | awk '/inet addr/{split($2,a,":"); print a[2]; exit}')
    [ -z "$IP" ] && IP="<jetkvm-ip>"

    echo ""
    echo "=== Setup Complete ==="
    echo ""
    echo "API server is running on port ${API_PORT}"
    if [ -f "$PID_FILE" ]; then
        echo "Watchdog PID: $(cat "$PID_FILE")"
    fi
    echo ""
    echo "Endpoints:"
    echo "  http://${IP}:${API_PORT}/health"
    echo "  http://${IP}:${API_PORT}/temperature"
    echo "  http://${IP}:${API_PORT}/device_info"
    echo ""
    echo "The server will:"
    echo "  - Automatically restart after each request (nc is single-shot)"
    echo "  - Survive SSH session disconnect"
    echo "  - Start automatically on boot"
    echo "  - Timeout idle connections after 5 seconds"
    echo "  - Auto-update from GitHub every 5 minutes"
    echo ""
    echo "To uninstall:  sh ${UNINSTALL_SCRIPT}"
    echo "To view logs:  cat ${LOG_FILE}"
    echo ""
    echo "In Home Assistant, add the JetKVM integration with host: ${IP}"
    echo ""
else
    echo ""
    echo "WARNING: Server may not have started correctly."
    echo ""
    echo "Debug info:"
    echo "  nc command:    $NC_CMD"
    echo "  nc -e support: $([ "$NC_HAS_E" = "1" ] && echo "yes" || echo "no")"
    echo "  Log file:      cat ${LOG_FILE}"
    echo "  Config file:   cat ${BASE_DIR}/config.sh"
    echo "  Check port:    netstat -tlnp | grep ${API_PORT}"
    echo ""
    if [ -f "$LOG_FILE" ]; then
        echo "Recent log:"
        tail -5 "$LOG_FILE"
    fi
fi


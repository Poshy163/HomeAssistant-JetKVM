#!/bin/sh
# =====================================================================
# JetKVM Home Assistant API Setup
# =====================================================================
# Installs a lightweight BusyBox httpd server on the JetKVM device
# that exposes system data (temperature, uptime, etc.) as JSON
# endpoints for the Home Assistant JetKVM integration.
#
# Usage:
#   1. SSH into your JetKVM:  ssh root@<jetkvm-ip>
#   2. Run:
#      wget --no-check-certificate -O /tmp/api-setup.sh \
#        https://raw.githubusercontent.com/Poshy163/HomeAssistant-JetKVM/main/api-setup.sh \
#        && sh /tmp/api-setup.sh
#
# Endpoints (after install):
#   http://<jetkvm-ip>:8800/cgi-bin/health
#   http://<jetkvm-ip>:8800/cgi-bin/temperature
#   http://<jetkvm-ip>:8800/cgi-bin/device_info
#
# To uninstall:
#   sh /tmp/api-setup.sh --uninstall
#   (or: sh /opt/ha-api/uninstall.sh)
# =====================================================================

API_PORT=8800
BASE_DIR="/opt/ha-api"
WWW_DIR="${BASE_DIR}/www"
CGI_DIR="${WWW_DIR}/cgi-bin"
WATCHDOG_SCRIPT="${BASE_DIR}/watchdog.sh"
PID_FILE="${BASE_DIR}/watchdog.pid"
LOG_FILE="${BASE_DIR}/server.log"
UNINSTALL_SCRIPT="${BASE_DIR}/uninstall.sh"

# =====================================================================
# Uninstall
# =====================================================================
if [ "$1" = "--uninstall" ]; then
    echo "=== Uninstalling JetKVM HA API ==="

    # Stop watchdog (which will also stop httpd)
    if [ -f "$PID_FILE" ]; then
        WPID=$(cat "$PID_FILE")
        kill "$WPID" 2>/dev/null
        sleep 1
        kill -9 "$WPID" 2>/dev/null
        rm -f "$PID_FILE"
    fi

    # Kill any httpd still listening on our port
    for p in $(netstat -tlnp 2>/dev/null | grep ":${API_PORT} " | awk '{print $NF}' | cut -d/ -f1); do
        kill "$p" 2>/dev/null
    done

    # Remove files
    rm -rf "$BASE_DIR"

    # Remove from rc.local (current and legacy entries)
    if [ -f /etc/rc.local ]; then
        sed -i "\|${WATCHDOG_SCRIPT}|d" /etc/rc.local
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
if [ -f "$PID_FILE" ]; then
    WPID=$(cat "$PID_FILE")
    kill "$WPID" 2>/dev/null
    sleep 1
    kill -9 "$WPID" 2>/dev/null
fi
# Also stop old nc-based server if present
if [ -f "${BASE_DIR}/server.pid" ]; then
    kill "$(cat "${BASE_DIR}/server.pid")" 2>/dev/null
fi
# Kill anything on our port
for p in $(netstat -tlnp 2>/dev/null | grep ":${API_PORT} " | awk '{print $NF}' | cut -d/ -f1); do
    kill "$p" 2>/dev/null
done
# Clean up old nc-based files
rm -f "${BASE_DIR}/server.sh" "${BASE_DIR}/handler.sh" "${BASE_DIR}/fifo" "${BASE_DIR}/server.pid"
sleep 1

# =====================================================================
# Detect httpd binary
# =====================================================================
HTTPD_CMD=""
if command -v httpd >/dev/null 2>&1; then
    HTTPD_CMD="httpd"
elif busybox --list 2>/dev/null | grep -qx "httpd"; then
    HTTPD_CMD="busybox httpd"
elif [ -x /usr/sbin/httpd ]; then
    HTTPD_CMD="/usr/sbin/httpd"
elif [ -x /usr/bin/httpd ]; then
    HTTPD_CMD="/usr/bin/httpd"
fi

if [ -z "$HTTPD_CMD" ]; then
    echo ""
    echo "ERROR: Cannot find httpd (BusyBox httpd) on this device."
    echo ""
    echo "Debug info:"
    echo "  busybox --list 2>&1 | grep httpd:"
    busybox --list 2>&1 | grep httpd
    echo "  which httpd: $(which httpd 2>&1)"
    echo "  busybox httpd --help:"
    busybox httpd --help 2>&1 | head -3
    echo ""
    echo "If BusyBox httpd is available as an applet, try:"
    echo "  ln -s /bin/busybox /usr/sbin/httpd"
    echo "  sh /tmp/api-setup.sh"
    exit 1
fi

echo "Found httpd: $HTTPD_CMD"

# =====================================================================
# Create directory structure
# =====================================================================
mkdir -p "$CGI_DIR"

# =====================================================================
# CGI: /cgi-bin/health
# =====================================================================
cat << 'EOF' > "$CGI_DIR/health"
#!/bin/sh
echo "Content-Type: application/json"
echo "Access-Control-Allow-Origin: *"
echo ""
echo '{"status":"ok"}'
EOF
chmod +x "$CGI_DIR/health"

# =====================================================================
# CGI: /cgi-bin/temperature
# =====================================================================
cat << 'EOF' > "$CGI_DIR/temperature"
#!/bin/sh
echo "Content-Type: application/json"
echo "Access-Control-Allow-Origin: *"
echo ""

TEMP_RAW=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null)
if [ -z "$TEMP_RAW" ]; then
    echo '{"error":"cannot read temperature"}'
    exit 0
fi

# millidegrees -> degrees with one decimal
TEMP_INT=$((TEMP_RAW / 1000))
TEMP_FRAC=$(( (TEMP_RAW % 1000) / 100 ))

echo "{\"temperature\":${TEMP_INT}.${TEMP_FRAC}}"
EOF
chmod +x "$CGI_DIR/temperature"

# =====================================================================
# CGI: /cgi-bin/device_info
# =====================================================================
cat << 'DEVINFO' > "$CGI_DIR/device_info"
#!/bin/sh
echo "Content-Type: application/json"
echo "Access-Control-Allow-Origin: *"
echo ""

# Temperature
TEMP_RAW=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null)
TEMP_INT=$((TEMP_RAW / 1000))
TEMP_FRAC=$(( (TEMP_RAW % 1000) / 100 ))

# Hostname
DEV_HOSTNAME=$(hostname 2>/dev/null || echo "jetkvm")

# IP address (BusyBox-compatible)
IP=$(ip -4 addr show eth0 2>/dev/null | awk '/inet / {split($2,a,"/"); print a[1]; exit}')
if [ -z "$IP" ]; then
    IP=$(ifconfig eth0 2>/dev/null | awk '/inet addr/{split($2,a,":"); print a[2]; exit}')
fi
if [ -z "$IP" ]; then
    IP="unknown"
fi

# Uptime
UPTIME=$(awk '{print $1}' /proc/uptime 2>/dev/null)

# Memory (in kB)
MEM_TOTAL=$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null)
MEM_AVAIL=$(awk '/MemAvailable/ {print $2}' /proc/meminfo 2>/dev/null)

cat << ENDJSON
{
    "deviceModel": "JetKVM",
    "hostname": "${DEV_HOSTNAME}",
    "ip_address": "${IP}",
    "temperature": ${TEMP_INT}.${TEMP_FRAC},
    "uptime_seconds": ${UPTIME:-0},
    "mem_total_kb": ${MEM_TOTAL:-0},
    "mem_available_kb": ${MEM_AVAIL:-0}
}
ENDJSON
DEVINFO
chmod +x "$CGI_DIR/device_info"

# =====================================================================
# Watchdog script — starts httpd and restarts it if it ever dies.
# Fully detached from the terminal so it survives SSH disconnect.
# =====================================================================

# Write a config file with detected values (expanded at install time)
cat > "${BASE_DIR}/config.sh" << CONF
HTTPD_CMD="${HTTPD_CMD}"
API_PORT=${API_PORT}
BASE_DIR="${BASE_DIR}"
WWW_DIR="${WWW_DIR}"
PID_FILE="${PID_FILE}"
LOG_FILE="${LOG_FILE}"
CONF

# Write watchdog script (NO expansion — single-quoted heredoc)
cat << 'WATCHDOG' > "$WATCHDOG_SCRIPT"
#!/bin/sh
# Watchdog for BusyBox httpd — restarts automatically if it exits.

# Load config written at install time
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

# Write our PID so the uninstaller can stop us
echo $$ > "$PID_FILE"

# Trap signals so we can clean up
cleanup() {
    log "Watchdog stopping (signal received)"
    if [ -n "$HTTPD_PID" ] && kill -0 "$HTTPD_PID" 2>/dev/null; then
        kill "$HTTPD_PID" 2>/dev/null
    fi
    rm -f "$PID_FILE"
    exit 0
}
trap cleanup INT TERM HUP

log "Watchdog starting (PID $$) — using: $HTTPD_CMD"

RESTART_COUNT=0
MAX_FAST_RESTARTS=10
FAST_RESTART_WINDOW=60
LAST_RESTART_TIME=0

while true; do
    # Start httpd in foreground mode (-f) so we can monitor its PID
    $HTTPD_CMD -f -p "$API_PORT" -h "$WWW_DIR" &
    HTTPD_PID=$!

    # Track timing for rapid-restart detection
    NOW=$(date +%s 2>/dev/null || awk '{printf "%d", $1}' /proc/uptime)
    log "httpd started (PID $HTTPD_PID)"

    ELAPSED=$((NOW - LAST_RESTART_TIME))
    if [ "$ELAPSED" -lt "$FAST_RESTART_WINDOW" ]; then
        RESTART_COUNT=$((RESTART_COUNT + 1))
    else
        RESTART_COUNT=0
    fi
    LAST_RESTART_TIME=$NOW

    # Back off if httpd keeps crashing
    if [ "$RESTART_COUNT" -ge "$MAX_FAST_RESTARTS" ]; then
        log "ERROR: httpd restarted $RESTART_COUNT times in <${FAST_RESTART_WINDOW}s — backing off 60s"
        sleep 60
        RESTART_COUNT=0
    fi

    # Wait for httpd to exit
    wait $HTTPD_PID
    EXIT_CODE=$?
    log "httpd exited (code $EXIT_CODE) — restarting in 2s..."
    sleep 2
done
WATCHDOG
chmod +x "$WATCHDOG_SCRIPT"

# =====================================================================
# Uninstall helper (convenience script on the device)
# =====================================================================
cat << 'UNINST' > "$UNINSTALL_SCRIPT"
#!/bin/sh
API_PORT=8800
BASE_DIR="/opt/ha-api"
PID_FILE="${BASE_DIR}/watchdog.pid"
WATCHDOG_SCRIPT="${BASE_DIR}/watchdog.sh"

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
    sed -i "\|/opt/ha-api/server.sh|d" /etc/rc.local
    sed -i "\|/opt/ha-api/start.sh|d" /etc/rc.local
fi
echo "Uninstalled."
UNINST
chmod +x "$UNINSTALL_SCRIPT"

# =====================================================================
# Persist across reboots via /etc/rc.local
# =====================================================================
if [ ! -f /etc/rc.local ]; then
    printf '#!/bin/sh\nexit 0\n' > /etc/rc.local
    chmod +x /etc/rc.local
fi

# Remove any old entries (nc-based server.sh, old start.sh, etc.)
sed -i "\|/opt/ha-api/server.sh|d" /etc/rc.local
sed -i "\|/opt/ha-api/start.sh|d" /etc/rc.local
sed -i "\|${WATCHDOG_SCRIPT}|d" /etc/rc.local

# Add the watchdog with setsid so it's fully detached
# Sleep 3s at boot to let networking come up first
sed -i "/^exit 0/i (sleep 3 && setsid ${WATCHDOG_SCRIPT} </dev/null >/dev/null 2>&1 &)" /etc/rc.local

# =====================================================================
# Start the server now
# =====================================================================
echo "Starting API server on port ${API_PORT}..."

# Use setsid to fully detach from this terminal session
# This ensures the server survives SSH disconnect
setsid "$WATCHDOG_SCRIPT" </dev/null >/dev/null 2>&1 &

# Give httpd a moment to start inside the watchdog
sleep 2

# =====================================================================
# Verify it's running
# =====================================================================
RUNNING=0
if netstat -tlnp 2>/dev/null | grep -q ":${API_PORT} "; then
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
    echo "  http://${IP}:${API_PORT}/cgi-bin/health"
    echo "  http://${IP}:${API_PORT}/cgi-bin/temperature"
    echo "  http://${IP}:${API_PORT}/cgi-bin/device_info"
    echo ""
    echo "The server will:"
    echo "  - Automatically restart if it crashes"
    echo "  - Survive SSH session disconnect"
    echo "  - Start automatically on boot"
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
    echo "  httpd command: $HTTPD_CMD"
    echo "  Log file:      cat ${LOG_FILE}"
    echo "  Config file:   cat ${BASE_DIR}/config.sh"
    echo "  Check port:    netstat -tlnp | grep ${API_PORT}"
    echo "  Manual start:  $HTTPD_CMD -f -p ${API_PORT} -h ${WWW_DIR}"
    echo ""
    if [ -f "$LOG_FILE" ]; then
        echo "Recent log:"
        tail -5 "$LOG_FILE"
    fi
fi


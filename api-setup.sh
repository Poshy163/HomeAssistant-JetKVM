#!/bin/sh
# =====================================================================
# JetKVM Home Assistant API Setup
# =====================================================================
# Installs a lightweight HTTP API server on the JetKVM device using
# netcat (nc).  Exposes temperature and device info as JSON endpoints
# for the Home Assistant JetKVM integration.
#
# Usage:
#   ssh root@<jetkvm-ip>
#   sh api-setup.sh
#
# Endpoints (after install):
#   http://<jetkvm-ip>:8800/health
#   http://<jetkvm-ip>:8800/temperature
#   http://<jetkvm-ip>:8800/device_info
#
# To uninstall:
#   sh api-setup.sh --uninstall
# =====================================================================

API_PORT=8800
BASE_DIR="/opt/ha-api"
SERVER_SCRIPT="${BASE_DIR}/server.sh"
HANDLER_SCRIPT="${BASE_DIR}/handler.sh"
PID_FILE="${BASE_DIR}/server.pid"

# --- Uninstall ---
if [ "$1" = "--uninstall" ]; then
    echo "=== Uninstalling JetKVM HA API ==="
    if [ -f "$PID_FILE" ]; then
        kill "$(cat "$PID_FILE")" 2>/dev/null
        rm -f "$PID_FILE"
    fi
    # kill any remaining listeners on the port
    for p in $(netstat -tlnp 2>/dev/null | grep ":${API_PORT} " | awk '{print $NF}' | cut -d/ -f1); do
        kill "$p" 2>/dev/null
    done
    rm -rf "$BASE_DIR"
    [ -f /etc/rc.local ] && sed -i "\|${SERVER_SCRIPT}|d" /etc/rc.local
    echo "Done. API server removed."
    exit 0
fi

echo "=== JetKVM Home Assistant API Setup ==="
echo ""

# Kill any existing instance
if [ -f "$PID_FILE" ]; then
    kill "$(cat "$PID_FILE")" 2>/dev/null
fi
for p in $(netstat -tlnp 2>/dev/null | grep ":${API_PORT} " | awk '{print $NF}' | cut -d/ -f1); do
    kill "$p" 2>/dev/null
done
sleep 1

mkdir -p "$BASE_DIR"

# ------------------------------------------------------------------
# handler.sh — called for each HTTP request, reads stdin, writes
#              HTTP response to stdout
# ------------------------------------------------------------------
cat << 'HANDLER' > "$HANDLER_SCRIPT"
#!/bin/sh

# Read the HTTP request line
read -r REQUEST_LINE

# Extract method and path
REQUEST_PATH=$(echo "$REQUEST_LINE" | awk '{print $2}')

# Consume remaining headers (read until empty line)
while read -r header; do
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
        TEMP_RAW=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null)
        TEMP_INT=$((TEMP_RAW / 1000))
        TEMP_FRAC=$(( (TEMP_RAW % 1000) / 100 ))
        DEV_HOSTNAME=$(hostname 2>/dev/null || echo "jetkvm")
        IP=$(ip -4 addr show eth0 2>/dev/null | awk '/inet / {split($2,a,"/"); print a[1]; exit}')
        [ -z "$IP" ] && IP=$(ifconfig eth0 2>/dev/null | awk '/inet addr/{split($2,a,":"); print a[2]; exit}')
        [ -z "$IP" ] && IP="unknown"
        UPTIME=$(awk '{print $1}' /proc/uptime 2>/dev/null)
        MEM_TOTAL=$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null)
        MEM_AVAIL=$(awk '/MemAvailable/ {print $2}' /proc/meminfo 2>/dev/null)
        BODY="{\"deviceModel\":\"JetKVM\",\"hostname\":\"${DEV_HOSTNAME}\",\"ip_address\":\"${IP}\",\"temperature\":${TEMP_INT}.${TEMP_FRAC},\"uptime_seconds\":${UPTIME:-0},\"mem_total_kb\":${MEM_TOTAL:-0},\"mem_available_kb\":${MEM_AVAIL:-0}}"
        ;;
    *)
        BODY='{"error":"not found"}'
        ;;
esac

# Calculate content length
CONTENT_LENGTH=$(echo -n "$BODY" | wc -c)

# Send HTTP response
printf "HTTP/1.1 200 OK\r\n"
printf "Content-Type: application/json\r\n"
printf "Content-Length: %d\r\n" "$CONTENT_LENGTH"
printf "Access-Control-Allow-Origin: *\r\n"
printf "Connection: close\r\n"
printf "\r\n"
printf "%s" "$BODY"
HANDLER
chmod +x "$HANDLER_SCRIPT"

# ------------------------------------------------------------------
# server.sh — main loop: listen with nc, dispatch to handler
# ------------------------------------------------------------------
cat << SERVEREOF > "$SERVER_SCRIPT"
#!/bin/sh
while true; do
    nc -l -p ${API_PORT} -e ${HANDLER_SCRIPT} 2>/dev/null
    # If nc doesn't support -e, try the pipe approach
    if [ \$? -ne 0 ] 2>/dev/null; then
        break
    fi
done
SERVEREOF
chmod +x "$SERVER_SCRIPT"

# ------------------------------------------------------------------
# Persist across reboots
# ------------------------------------------------------------------
if [ ! -f /etc/rc.local ]; then
    printf '#!/bin/sh\nexit 0\n' > /etc/rc.local
    chmod +x /etc/rc.local
fi
grep -q "$SERVER_SCRIPT" /etc/rc.local || \
    sed -i "/^exit 0/i ${SERVER_SCRIPT} &" /etc/rc.local

# ------------------------------------------------------------------
# Start now
# ------------------------------------------------------------------
echo "Starting API server on port ${API_PORT}..."
"$SERVER_SCRIPT" &
SERVER_PID=$!
echo "$SERVER_PID" > "$PID_FILE"
sleep 1

# Verify — try to connect
if kill -0 "$SERVER_PID" 2>/dev/null; then
    IP=$(ip -4 addr show eth0 2>/dev/null | awk '/inet / {split($2,a,"/"); print a[1]; exit}')
    [ -z "$IP" ] && IP="<jetkvm-ip>"
    echo ""
    echo "=== Setup Complete ==="
    echo ""
    echo "API server is running (PID $SERVER_PID)"
    echo ""
    echo "Endpoints:"
    echo "  http://${IP}:${API_PORT}/health"
    echo "  http://${IP}:${API_PORT}/temperature"
    echo "  http://${IP}:${API_PORT}/device_info"
    echo ""
    echo "In Home Assistant, add the JetKVM integration with host: ${IP}"
    echo ""
else
    echo ""
    echo "WARNING: Server may not have started."
    echo "Trying alternative nc mode..."
    echo ""

    # Alternative: use a fifo-based approach if nc -e is not supported
    FIFO="${BASE_DIR}/fifo"
    rm -f "$FIFO"
    mkfifo "$FIFO"

    cat << ALTEOF > "$SERVER_SCRIPT"
#!/bin/sh
FIFO="${BASE_DIR}/fifo"
while true; do
    cat "\$FIFO" | nc -l -p ${API_PORT} | ${HANDLER_SCRIPT} > "\$FIFO" 2>/dev/null
done
ALTEOF
    chmod +x "$SERVER_SCRIPT"

    "$SERVER_SCRIPT" &
    SERVER_PID=$!
    echo "$SERVER_PID" > "$PID_FILE"
    sleep 1

    if kill -0 "$SERVER_PID" 2>/dev/null; then
        IP=$(ip -4 addr show eth0 2>/dev/null | awk '/inet / {split($2,a,"/"); print a[1]; exit}')
        [ -z "$IP" ] && IP="<jetkvm-ip>"
        echo "=== Setup Complete (fifo mode) ==="
        echo ""
        echo "Endpoints:"
        echo "  http://${IP}:${API_PORT}/health"
        echo "  http://${IP}:${API_PORT}/temperature"
        echo "  http://${IP}:${API_PORT}/device_info"
        echo ""
    else
        echo "ERROR: Could not start server. Please report this issue."
        echo "Debug info:"
        which nc 2>&1
        nc --help 2>&1
        busybox --list 2>&1 | grep -i "nc\|http"
    fi
fi


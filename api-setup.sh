#!/bin/sh
# =====================================================================
# JetKVM Home Assistant API Setup
# =====================================================================
# Installs a lightweight BusyBox httpd server on the JetKVM device
# that exposes system data (temperature, etc.) as JSON endpoints
# for the Home Assistant JetKVM integration.
#
# Usage:
#   1. SSH into your JetKVM:  ssh root@<jetkvm-ip>
#   2. Copy this script to the device or paste it
#   3. Run:  sh api-setup.sh
#
# Endpoints (after install):
#   http://<jetkvm-ip>:8800/cgi-bin/health
#   http://<jetkvm-ip>:8800/cgi-bin/temperature
#   http://<jetkvm-ip>:8800/cgi-bin/device_info
#
# To uninstall:
#   sh api-setup.sh --uninstall
# =====================================================================

API_PORT=8800
BASE_DIR="/opt/ha-api"
CGI_DIR="${BASE_DIR}/cgi-bin"
INIT_SCRIPT="${BASE_DIR}/start.sh"
PID_FILE="${BASE_DIR}/httpd.pid"

# --- Uninstall ---
if [ "$1" = "--uninstall" ]; then
    echo "=== Uninstalling JetKVM HA API ==="
    # Stop the server
    if [ -f "$PID_FILE" ]; then
        kill "$(cat "$PID_FILE")" 2>/dev/null
        rm -f "$PID_FILE"
    fi
    # Also kill by port just in case
    kill "$(netstat -tlnp 2>/dev/null | grep ":${API_PORT} " | awk '{print $NF}' | cut -d/ -f1)" 2>/dev/null
    # Remove files
    rm -rf "$BASE_DIR"
    # Remove from rc.local
    [ -f /etc/rc.local ] && sed -i "\|${INIT_SCRIPT}|d" /etc/rc.local
    echo "Done. API server removed."
    exit 0
fi

echo "=== JetKVM Home Assistant API Setup ==="
echo ""

# Kill any existing instance
if [ -f "$PID_FILE" ]; then
    kill "$(cat "$PID_FILE")" 2>/dev/null
fi
kill "$(netstat -tlnp 2>/dev/null | grep ":${API_PORT} " | awk '{print $NF}' | cut -d/ -f1)" 2>/dev/null

# Create directories
mkdir -p "$CGI_DIR"

# ------------------------------------------------------------------
# CGI: /cgi-bin/health
# ------------------------------------------------------------------
cat << 'EOF' > "$CGI_DIR/health"
#!/bin/sh
echo "Content-Type: application/json"
echo "Access-Control-Allow-Origin: *"
echo ""
echo '{"status":"ok"}'
EOF
chmod +x "$CGI_DIR/health"

# ------------------------------------------------------------------
# CGI: /cgi-bin/temperature
# ------------------------------------------------------------------
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

# millidegrees -> degrees with one decimal (pure sh math)
TEMP_INT=$((TEMP_RAW / 1000))
TEMP_FRAC=$(( (TEMP_RAW % 1000) / 100 ))

echo "{\"temperature\":${TEMP_INT}.${TEMP_FRAC}}"
EOF
chmod +x "$CGI_DIR/temperature"

# ------------------------------------------------------------------
# CGI: /cgi-bin/device_info
# ------------------------------------------------------------------
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

# IP address (BusyBox-compatible: no grep -P)
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

# ------------------------------------------------------------------
# Startup script
# ------------------------------------------------------------------
cat << STARTUP > "$INIT_SCRIPT"
#!/bin/sh
cd ${BASE_DIR}
httpd -p ${API_PORT} -h ${BASE_DIR} &
echo \$! > ${PID_FILE}
STARTUP
chmod +x "$INIT_SCRIPT"

# ------------------------------------------------------------------
# Persist across reboots via /etc/rc.local
# ------------------------------------------------------------------
if [ ! -f /etc/rc.local ]; then
    printf '#!/bin/sh\nexit 0\n' > /etc/rc.local
    chmod +x /etc/rc.local
fi

grep -q "$INIT_SCRIPT" /etc/rc.local || \
    sed -i "/^exit 0/i ${INIT_SCRIPT}" /etc/rc.local

# ------------------------------------------------------------------
# Start now
# ------------------------------------------------------------------
echo "Starting API server on port ${API_PORT}..."
sh "$INIT_SCRIPT"
sleep 1

# Verify
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo ""
    echo "=== Setup Complete ==="
    echo ""
    echo "API server is running (PID $(cat "$PID_FILE"))"
    echo ""
    echo "Endpoints:"
    echo "  http://${IP}:${API_PORT}/cgi-bin/health"
    echo "  http://${IP}:${API_PORT}/cgi-bin/temperature"
    echo "  http://${IP}:${API_PORT}/cgi-bin/device_info"
    echo ""
    echo "In Home Assistant, add the JetKVM integration with host: ${IP}"
    echo ""
else
    echo ""
    echo "WARNING: Server may not have started. Check manually:"
    echo "  netstat -tlnp | grep ${API_PORT}"
    echo ""
fi


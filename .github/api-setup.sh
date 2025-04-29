#!/bin/sh

mkdir -p /opt
cat << 'EOL' > /opt/home-assistant-API.sh
#!/bin/sh
while true; do
    # Get the temperature (in millidegrees Celsius, so divide by 1000)
    temp=$(cat /sys/class/thermal/thermal_zone0/temp)
    temp_celsius=$((temp / 1000))

    # Output "PING" and temperature to a log file
    echo "PING - Temp: ${temp_celsius}°C" >> /var/log/home-assistant-API.log

    # Sleep for 5 seconds
    sleep 5
done
EOL

chmod +x /opt/home-assistant-API.sh

if [ ! -f /etc/rc.local ]; then
  echo '#!/bin/sh' > /etc/rc.local
  echo 'exit 0' >> /etc/rc.local
  chmod +x /etc/rc.local
fi

grep -q "/opt/home-assistant-API.sh &" /etc/rc.local || \
  sed -i '/^exit 0/i /opt/home-assistant-API.sh &' /etc/rc.local

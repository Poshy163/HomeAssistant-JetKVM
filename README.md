# Home Assistant JetKVM Integration

![Project Stage](https://img.shields.io/badge/project%20stage-experimental-orange.svg?style=for-the-badge)
![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)

A custom [Home Assistant](https://www.home-assistant.io/) integration for [JetKVM](https://jetkvm.com/) KVM-over-IP devices.

## Features

- **SoC Temperature Sensor** — Monitors the JetKVM device's SoC temperature in °C (polled every 60 seconds)

## Setup

### Step 1 — Install the API server on your JetKVM (one-time)

SSH into the JetKVM and run **one command**:

```sh
ssh root@<your-jetkvm-ip>
wget --no-check-certificate -qO- https://raw.githubusercontent.com/Poshy163/HomeAssistant-JetKVM/main/api-setup.sh | sh
```

That's it. You should see output like:

```
=== JetKVM Home Assistant API Setup ===
Starting API server on port 8800...
=== Setup Complete ===
API server is running (PID 1234)
```

> The script installs a tiny BusyBox `httpd` on port 8800 that reads the SoC temperature from the Linux thermal zone. It survives reboots automatically. To uninstall later: `wget --no-check-certificate -qO- https://raw.githubusercontent.com/Poshy163/HomeAssistant-JetKVM/main/api-setup.sh | sh -s -- --uninstall`

**Verify it works** — from your PC browser, open:

```
http://<your-jetkvm-ip>:8800/cgi-bin/temperature
```

You should see:

```json
{"temperature":47.2}
```

### Step 2 — Install the Home Assistant integration

#### HACS (Recommended)

1. Open HACS → **Integrations** → **⋮** → **Custom repositories**
2. Add `https://github.com/Poshy163/HomeAssistant-JetKVM` as **Integration**
3. Install and restart Home Assistant

#### Manual

Copy `custom_components/jetkvm` into your HA `config/custom_components/` directory, then restart.

### Step 3 — Add the device

1. **Settings** → **Devices & Services** → **Add Integration**
2. Search **JetKVM**
3. Enter the IP address of your JetKVM (e.g. `192.168.1.178`)

Done — a **SoC Temperature** sensor will appear under the new JetKVM device.

## How It Works

```
┌──────────────────┐         ┌──────────────────────────┐
│  Home Assistant   │  HTTP   │       JetKVM device      │
│                   │ ──────► │  BusyBox httpd :8800     │
│  polls every 60s  │ ◄────── │  /cgi-bin/temperature    │
│                   │  JSON   │  reads thermal_zone0     │
└──────────────────┘         └──────────────────────────┘
```

`api-setup.sh` installs a BusyBox `httpd` server on port **8800** with CGI scripts that read `/sys/class/thermal/thermal_zone0/temp`. The HA integration polls these endpoints every 60 seconds.

## API Endpoints (port 8800 on the JetKVM)

| Endpoint | Response |
|---|---|
| `/cgi-bin/health` | `{"status":"ok"}` |
| `/cgi-bin/temperature` | `{"temperature":47.2}` |
| `/cgi-bin/device_info` | `{"deviceModel":"JetKVM","hostname":"...","temperature":47.2,...}` |

## Requirements

- Home Assistant 2024.1+
- JetKVM on your local network
- One-time SSH access to run the setup script


# Home Assistant JetKVM Integration

![Project Stage](https://img.shields.io/badge/project%20stage-experimental-orange.svg?style=for-the-badge)
![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)

A custom [Home Assistant](https://www.home-assistant.io/) integration for [JetKVM](https://jetkvm.com/) KVM-over-IP devices.

## Features

- **SoC Temperature Sensor** — Monitors the JetKVM device's SoC temperature in °C (polled every 60 seconds)
- **Live Video Camera** — Native WebRTC stream from JetKVM (requires JetKVM password)

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
http://<your-jetkvm-ip>:8800/temperature
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
3. Enter the JetKVM IP address or hostname (for example `192.168.1.178`)
4. (Optional) Enter your JetKVM web UI password to enable the camera stream

Done — the JetKVM device and sensors will appear in Home Assistant. If a password is provided and valid, the camera entity is created as well.

### Step 4 — Manage password later (Options Flow)

You can update the JetKVM password at any time without removing the integration:

1. Go to **Settings** → **Devices & Services**
2. Open **JetKVM**
3. Click **Configure**
4. Set password to enable/fix camera, or leave blank to disable camera access

When options are saved, the integration reloads automatically.

## Camera / WebRTC Notes

- The camera uses JetKVM native WebRTC signaling over port **80**.
- No RTSP/HLS endpoint is required or used.
- If password is empty or invalid, the integration still works for sensors but the camera is unavailable.
- Newer JetKVM firmware uses WebSocket signaling (`/webrtc/signaling/client`), and this integration supports that flow.

## How It Works

```
┌──────────────────┐         ┌──────────────────────────┐
│  Home Assistant   │  HTTP   │       JetKVM device      │
│                   │ ──────► │  nc-based server :8800   │
│  polls every 60s  │ ◄────── │  /temperature            │
│                   │  JSON   │  reads thermal_zone0     │
└──────────────────┘         └──────────────────────────┘
```

`api-setup.sh` installs a netcat-based HTTP server on port **8800** with a handler script that reads `/sys/class/thermal/thermal_zone0/temp`. The HA integration polls these endpoints every 60 seconds.

## API Endpoints (port 8800 on the JetKVM)

| Endpoint | Response |
|---|---|
| `/health` | `{"status":"ok"}` |
| `/temperature` | `{"temperature":47.2}` |
| `/device_info` | `{"deviceModel":"JetKVM","hostname":"...","temperature":47.2,...}` |

## Troubleshooting

### Sensors work, but camera is stuck on loading

1. Confirm you entered the JetKVM password in **JetKVM → Configure**.
2. Check Home Assistant debug logs for `custom_components.jetkvm`.
3. Look for these expected lines when opening the camera:

```text
JetKVM WebRTC signaling: connecting to ws://<ip>/webrtc/signaling/client
JetKVM WebRTC signaling: got SDP answer via WS (... bytes)
JetKVM camera: WebRTC OK (session ..., ... bytes)
```

If you do not see these lines, verify JetKVM web UI login still works with the same password and that Home Assistant can reach JetKVM on port 80.

### I need to remove or change the camera password

- Open **JetKVM → Configure** in Home Assistant.
- Enter a new password to re-enable camera authentication.
- Leave password blank to disable camera/WebRTC while keeping sensors active.

### Integration cannot connect

- Re-run the setup script on JetKVM:

```sh
wget --no-check-certificate -qO- https://raw.githubusercontent.com/Poshy163/HomeAssistant-JetKVM/main/api-setup.sh | sh
```

- Verify endpoint from another machine:

```text
http://<your-jetkvm-ip>:8800/health
```

Expected response: `{"status":"ok"}`

## Requirements

- Home Assistant 2024.1+
- JetKVM on your local network
- One-time SSH access to run the setup script


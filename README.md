# OpenVPN Telegram Bot

A Telegram bot for managing OpenVPN server, monitoring traffic, and managing certificates.

## Features

- Control OpenVPN service (start, stop, restart, status)
- View connected clients and disconnect them
- Monitor traffic usage with statistics from SQLite3 database
- Manage certificates (generate, revoke, renew, list)
- Receive notifications when traffic crosses configured thresholds (500GB, 700GB, 900GB)
- Authorization by Telegram user ID

## Deploy on Linux Server

### Prerequisites

- Ubuntu/Debian server with root access
- OpenVPN installed and running
- Python 3.9+

### Step 1: Prepare the Server

```bash
# Update and install dependencies
sudo apt update
sudo apt install -y python3 python3-venv python3-pip

# Verify OpenVPN is running
systemctl status openvpn
```

### Step 2: Upload the Project

Clone the repo to the server:

```bash
git clone https://github.com/baffoRti/OpenVPN_Telegram_Bot
```

### Step 3: Set Up Python Environment

```bash
cd /OpenVPN_Telegram_Bot/openvpn-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 4: Configure OpenVPN

#### 4a. Management Interface

openvpn-install.sh does **not** enable the management interface by default. Add it to allow the bot to disconnect clients:

```bash
sudo nano /etc/openvpn/server.conf
```

Add this line at the end:

```
management localhost 7505
```

Restart OpenVPN:

```bash
sudo systemctl restart openvpn-server@server
# or on Debian/Ubuntu:
# sudo systemctl restart openvpn@server
```

#### 4b. Status File

openvpn-install.sh already configures the status file at `/var/log/openvpn/status.log` (line in server.conf). Verify:

```bash
grep '^status' /etc/openvpn/server.conf
```

Expected output: `status /var/log/openvpn/status.log 30`

#### 4c. Certificate Script (manage_certs.sh)

Make the certificate management script executable:

```bash
sudo chmod +x /OpenVPN_Telegram_Bot/manage_certs.sh
```

Test it:

```bash
sudo /OpenVPN_Telegram_Bot/manage_certs.sh list
```

The script wraps easy-rsa at `/etc/openvpn/easy-rsa/` (installed by openvpn-install.sh) and supports 4 operations:

| Command | Description |
|---|---|
| `manage_certs.sh list` | Lists valid client certificates from `pki/index.txt` |
| `manage_certs.sh generate <name>` | Creates cert + private key + `.ovpn` config |
| `manage_certs.sh revoke <name>` | Revokes cert, updates CRL, deletes `.ovpn` |
| `manage_certs.sh renew <name>` | Revoke + generate (re-issues the certificate) |

Generated `.ovpn` files are saved to the path configured in `OPENVPN_CERT_DIR` (default: `/etc/openvpn/easy-rsa/pki`). The bot can send these files to users via the "Download Config" button.

### Step 5: Configure the Bot

```bash
cp .env.example .env
nano .env
```

Fill in:

```env
TELEGRAM_TOKEN=your_bot_token_from_botfather
ADMIN_IDS=your_telegram_id,another_admin_id
OPENVPN_DB_PATH=/OpenVPN_Telegram_Bot/openvpn_stats.db
CERT_SCRIPT_PATH=/OpenVPN_Telegram_Bot/manage_certs.sh
OPENVPN_CERT_DIR=/etc/openvpn/easy-rsa/pki
OPENVPN_STATUS_FILE=/var/log/openvpn/status.log
OPENVPN_MANAGEMENT_HOST=localhost
OPENVPN_MANAGEMENT_PORT=7505
TRAFFIC_THRESHOLDS=500,700,900
```

### Step 6: Configure Sudoers (No-Password Commands)

The bot needs to run systemctl and manage_certs.sh without a password prompt:

```bash
sudo visudo -f /etc/sudoers.d/openvpn-bot
```

Add this line (replace `your_user` with the actual user running the bot, adjust service name if needed):

```
your_user ALL=(ALL) NOPASSWD: /usr/bin/systemctl start openvpn-server@server, /usr/bin/systemctl stop openvpn-server@server, /usr/bin/systemctl restart openvpn-server@server, /usr/bin/systemctl is-active openvpn-server@server, /OpenVPN_Telegram_Bot/manage_certs.sh
```

> **Note:** openvpn-install.sh may use `openvpn@server` instead of `openvpn-server@server` depending on the OS. Check with `systemctl list-units | grep openvpn`.

Verify:

```bash
sudo -l
```

Then update the `run_command` calls in the code to use `sudo systemctl` instead of just `systemctl`. The simplest approach — modify `openvpn_service.py` to prepend `sudo`:

```python
success, output = run_command(f"sudo systemctl {action} {service_name}")
```

### Step 7: Create systemd Service

Create a service file so the bot starts automatically:

```bash
sudo nano /etc/systemd/system/openvpn-bot.service
```

```ini
[Unit]
Description=OpenVPN Telegram Bot
After=network.target openvpn-server@server.service

[Service]
Type=simple
User=your_user # Specify your user
Group=your_user # Specify your user
WorkingDirectory=/OpenVPN_Telegram_Bot # Specify your directory
ExecStart=/OpenVPN_Telegram_Bot/venv/bin/python -m openvpn_bot.bot # Specify your path
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable openvpn-bot
sudo systemctl start openvpn-bot
```

### Step 8: Verify

```bash
# Check bot status
sudo systemctl status openvpn-bot

# View logs
sudo journalctl -u openvpn-bot -f
```

Send `/start` to your bot in Telegram.

## Configuration Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_TOKEN` | Yes | — | Bot token from @BotFather |
| `ADMIN_IDS` | Yes | — | Comma-separated Telegram user IDs |
| `OPENVPN_DB_PATH` | No | `openvpn_stats.db` | Path to SQLite traffic database |
| `CERT_SCRIPT_PATH` | No | `./manage_certs.sh` | Path to certificate management script |
| `OPENVPN_CERT_DIR` | No | `/etc/openvpn/easy-rsa/pki` | Directory for certificates and `.ovpn` config files |
| `OPENVPN_STATUS_FILE` | No | `/var/log/openvpn/status.log` | OpenVPN status file path |
| `OPENVPN_MANAGEMENT_HOST` | No | `localhost` | Management interface host |
| `OPENVPN_MANAGEMENT_PORT` | No | `7505` | Management interface port |
| `TRAFFIC_THRESHOLDS` | No | `500,700,900` | Traffic alert thresholds in GB |

## Database Schema

The bot expects an SQLite3 database with the following tables (You can find out more [here](https://github.com/baffoRti/OpenVPN_Traffic_Monitor "OpenVPN Traffic Monitor")):

### user_traffic_monthly
- `common_name` (TEXT, PRIMARY KEY)
- `year_month` (TEXT, PRIMARY KEY) — format YYYY-MM
- `bytes_received` (INTEGER)
- `bytes_sent` (INTEGER)

### current_client_state
- `common_name` (TEXT, PRIMARY KEY)
- `connected_since` (TEXT)
- `bytes_received` (INTEGER)
- `bytes_sent` (INTEGER)

### log_metadata
- `id` (INTEGER, PRIMARY KEY)
- `last_updated_time` (TEXT)

## Management Commands

```bash
# Start/stop/restart
sudo systemctl start openvpn-bot
sudo systemctl stop openvpn-bot
sudo systemctl restart openvpn-bot

# View logs
sudo journalctl -u openvpn-bot -f

# Update the bot
cd /OpenVPN_Telegram_Bot
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart openvpn-bot
```

## Security

- Only users listed in `ADMIN_IDS` can interact with the bot
- Sudoers is restricted to specific systemctl commands only
- Ensure the certificate management script is owned by root and not world-writable

#!/bin/bash
#
# install.sh - Automated installation script for OpenVPN Telegram Bot
#
# Usage: sudo bash install.sh
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[+]${NC} $1"
}

print_error() {
    echo -e "${RED}[!]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[~]${NC} $1"
}

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$(dirname "$SCRIPT_DIR")"

echo "================================================"
echo "   OpenVPN Telegram Bot - Installation Script"
echo "================================================"
echo ""
echo "Installation directory: $INSTALL_DIR"
echo ""

# --------------------------------------------------
# Step 1: Check root privileges
# --------------------------------------------------
print_status "Checking root privileges..."

if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root (use sudo)"
    echo "Usage: sudo bash install.sh"
    exit 1
fi

# Get the actual user (when running with sudo)
if [[ -n "${SUDO_USER:-}" ]]; then
    ACTUAL_USER="$SUDO_USER"
else
    ACTUAL_USER="$(whoami)"
fi

print_status "Running as root, actual user: $ACTUAL_USER"

# --------------------------------------------------
# Step 2: Check for OpenVPN
# --------------------------------------------------
print_status "Checking OpenVPN installation..."

if ! command -v openvpn &> /dev/null; then
    print_error "OpenVPN is not installed!"
    echo ""
    echo "Please install OpenVPN first:"
    echo "  sudo apt update && sudo apt install openvpn"
    echo ""
    echo "Or use the openvpn-install script:"
    echo "  wget https://git.io/vpn -O openvpn-install.sh"
    echo "  sudo bash openvpn-install.sh"
    exit 1
fi

print_status "OpenVPN is installed"

# Detect OpenVPN config directory
if [[ -f "/etc/openvpn/server/server.conf" ]]; then
    OPENVPN_DIR="/etc/openvpn/server"
elif [[ -f "/etc/openvpn/server.conf" ]]; then
    OPENVPN_DIR="/etc/openvpn"
else
    print_warning "Could not detect OpenVPN configuration directory"
    OPENVPN_DIR="/etc/openvpn"
fi

print_status "OpenVPN directory: $OPENVPN_DIR"

# --------------------------------------------------
# Step 3: Check Python version
# --------------------------------------------------
print_status "Checking Python version..."

if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed!"
    echo ""
    echo "Installing Python 3..."
    apt update && apt install -y python3 python3-pip python3-venv
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [[ "$PYTHON_MAJOR" -lt 3 ]] || [[ "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 9 ]]; then
    print_error "Python 3.9+ is required. Current version: $PYTHON_VERSION"
    exit 1
fi

print_status "Python version: $PYTHON_VERSION"

# --------------------------------------------------
# Step 4: Install system dependencies
# --------------------------------------------------
print_status "Installing system dependencies..."

apt update -qq
apt install -y -qq python3-venv python3-pip curl

print_status "System dependencies installed"

# --------------------------------------------------
# Step 5: Make manage_certs.sh executable
# --------------------------------------------------
print_status "Setting up certificate management script..."

chmod +x "$INSTALL_DIR/manage_certs.sh"

print_status "manage_certs.sh is now executable"

# --------------------------------------------------
# Step 6: Create virtual environment
# --------------------------------------------------
print_status "Creating Python virtual environment..."

cd "$INSTALL_DIR"

if [[ -d "venv" ]]; then
    print_warning "Virtual environment already exists, skipping creation"
else
    python3 -m venv venv
fi

print_status "Virtual environment created"

# --------------------------------------------------
# Step 7: Install pip dependencies
# --------------------------------------------------
print_status "Installing Python dependencies..."

source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

print_status "Python dependencies installed"

# --------------------------------------------------
# Step 8: Configure .env file
# --------------------------------------------------
print_status "Configuring environment file..."

if [[ -f ".env" ]]; then
    print_warning ".env file already exists, skipping"
else
    cp .env.example .env
    print_warning "Created .env file - YOU MUST EDIT IT BEFORE RUNNING THE BOT!"
    echo ""
    echo "Edit the configuration file:"
    echo "  nano $INSTALL_DIR/.env"
    echo ""
    echo "Required settings:"
    echo "  TELEGRAM_TOKEN - Get from @BotFather in Telegram"
    echo "  ADMIN_IDS - Your Telegram user ID (can get from @userinfobot)"
    echo ""
fi

# --------------------------------------------------
# Step 9: Setup sudoers
# --------------------------------------------------
print_status "Configuring sudoers for user $ACTUAL_USER..."

SUDOERS_FILE="/etc/sudoers.d/openvpn-bot"

# Build the sudoers entry based on detected service name
if systemctl list-units --type=service | grep -q "openvpn-server@"; then
    OPENVPN_SERVICE="openvpn-server@server"
elif systemctl list-units --type=service | grep -q "openvpn@"; then
    OPENVPN_SERVICE="openvpn@server"
else
    OPENVPN_SERVICE="openvpn-server@server"
    print_warning "Could not detect OpenVPN service name, using default: $OPENVPN_SERVICE"
fi

cat > "$SUDOERS_FILE" << EOF
# OpenVPN Bot - Allow managing OpenVPN service without password
$ACTUAL_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl start $OPENVPN_SERVICE, /usr/bin/systemctl stop $OPENVPN_SERVICE, /usr/bin/systemctl restart $OPENVPN_SERVICE, /usr/bin/systemctl is-active $OPENVPN_SERVICE, $INSTALL_DIR/manage_certs.sh
EOF

chmod 440 "$SUDOERS_FILE"

print_status "Sudoers configured for $ACTUAL_USER"
print_status "OpenVPN service: $OPENVPN_SERVICE"

# --------------------------------------------------
# Step 10: Install systemd service
# --------------------------------------------------
print_status "Installing systemd service..."

# Replace placeholder paths in service file
SERVICE_CONTENT=$(sed "s|{INSTALL_DIR}|$INSTALL_DIR|g" "$SCRIPT_DIR/openvpn-bot.service")

echo "$SERVICE_CONTENT" > /etc/systemd/system/openvpn-bot.service

systemctl daemon-reload
systemctl enable openvpn-bot

print_status "Systemd service installed and enabled"

# --------------------------------------------------
# Step 11: Summary
# --------------------------------------------------
echo ""
echo "================================================"
echo "   Installation Complete!"
echo "================================================"
echo ""
echo "IMPORTANT: Before starting the bot, configure the .env file:"
echo ""
echo "  nano $INSTALL_DIR/.env"
echo ""
echo "Required settings:"
echo "  TELEGRAM_TOKEN=your_token_from_botfather"
echo "  ADMIN_IDS=your_telegram_id"
echo ""
echo "After configuration, start the bot with:"
echo ""
echo "  sudo systemctl start openvpn-bot"
echo ""
echo "Check status and logs:"
echo ""
echo "  sudo systemctl status openvpn-bot"
echo "  sudo journalctl -u openvpn-bot -f"
echo ""
echo "================================================"

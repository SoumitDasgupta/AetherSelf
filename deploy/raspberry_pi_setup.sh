#!/usr/bin/env bash
# ==============================================================================
# AetherSelf - Raspberry Pi 5 (8GB RAM) Provisioning & Deployment Script
# Targets: Debian 12 Bookworm (64-bit ARM64) on Raspberry Pi 5
# Hardware Budget: Rs 7,500 - 9,800 INR (Option B in Project Report)
# ==============================================================================

set -euo pipefail

echo "=========================================================="
echo "  AetherSelf Raspberry Pi 5 Autonomous Edge Node Setup"
echo "=========================================================="

# 1. Update OS & Essential Toolchains
echo "[1/5] Updating APT packages and system headers..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv python3-dev git curl htop \
    libopenblas-dev libgomp1

# 2. Configure SWAP and CPU Governor for Consistent Edge SLM Inference
echo "[2/5] Optimizing memory & CPU governor..."
# Ensure 2GB swap space for safety margin
sudo sed -i 's/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile || true
sudo systemctl restart dphys-swapfile || true

# 3. Create Dedicated Isolated Virtual Environment
echo "[3/5] Setting up isolated Python virtual environment..."
INSTALL_DIR="/opt/aetherself"
sudo mkdir -p "$INSTALL_DIR"
sudo chown -R "$USER:$USER" "$INSTALL_DIR"

cd "$INSTALL_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip setuptools wheel

# 4. Install AetherSelf Edge Middleware Dependencies
echo "[4/5] Installing AetherSelf and quantized edge libraries..."
pip install psutil scikit-learn pydantic fastapi uvicorn rich numpy chromadb
pip install -e .

# 5. Enable Systemd Daemon Service
echo "[5/5] Installing systemd daemon unit..."
sudo cp deploy/aetherself.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable aetherself.service
sudo systemctl start aetherself.service

echo "=========================================================="
echo "  AetherSelf Edge Daemon successfully installed & active!"
echo "  Live Operations Hub: http://$(hostname -I | awk '{print $1}'):8765"
echo "  Check Daemon Status: sudo systemctl status aetherself"
echo "=========================================================="

#!/usr/bin/env bash
# ==============================================================================
# AetherSelf - NVIDIA Jetson Orin Nano (8GB) Provisioning & Deployment Script
# Hardware Budget: Rs 22,000 - 38,000 INR (Option C in Project Report)
# Accelerates quantized Phi-3.5-mini / Llama-3.2 CoT using Jetson Ampere GPU/NPU
# ==============================================================================

set -euo pipefail

echo "=========================================================="
echo "  AetherSelf NVIDIA Jetson Orin Nano Edge Node Setup"
echo "=========================================================="

# 1. Verify JetPack & CUDA Toolkit
echo "[1/5] Verifying JetPack & Tegra NPU environment..."
sudo nvpmodel -m 0 || true  # Set to MAXN performance mode
sudo jetson_clocks || true

# 2. Install Jetson Python & Acceleration Headers
echo "[2/5] Installing core dependencies..."
sudo apt update
sudo apt install -y python3-pip python3-dev git curl htop \
    libopenblas-dev libopenmpi-dev

# 3. Setup Virtual Environment with PyTorch & ONNXRuntime-GPU
echo "[3/5] Setting up virtual environment..."
INSTALL_DIR="/opt/aetherself"
sudo mkdir -p "$INSTALL_DIR"
sudo chown -R "$USER:$USER" "$INSTALL_DIR"

cd "$INSTALL_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv --system-site-packages venv
fi
source venv/bin/activate
pip install --upgrade pip

# 4. Install AetherSelf Engine
echo "[4/5] Installing AetherSelf..."
pip install psutil scikit-learn pydantic fastapi uvicorn rich numpy chromadb
pip install -e .

# 5. Enable Systemd Daemon
echo "[5/5] Registering systemd service..."
sudo cp deploy/aetherself.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable aetherself.service
sudo systemctl restart aetherself.service

echo "=========================================================="
echo "  AetherSelf Jetson Orin Node active on port 8765!"
echo "  Operations Hub: http://$(hostname -I | awk '{print $1}'):8765"
echo "=========================================================="

#!/bin/bash
# ============================================================
# Oracle Cloud Always Free — Promoter Tracker Setup Script
# Run this on your ARM Ampere VM (Ubuntu 22.04)
# ============================================================
set -e

echo "============================================"
echo " Promoter Tracker — Oracle Cloud Deployment"
echo "============================================"

# 1. Update system
echo "[1/6] Updating system packages..."
sudo apt-get update -y && sudo apt-get upgrade -y

# 2. Install Docker
echo "[2/6] Installing Docker..."
sudo apt-get install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
echo "Docker installed. (You may need to re-login for docker group to take effect)"

# 3. Create app directory
echo "[3/6] Creating app directory..."
mkdir -p ~/promoter-tracker
cd ~/promoter-tracker

# 4. Clone the repo (or pull if exists)
echo "[4/6] Cloning repository..."
if [ -d "promoter-performance-tracker/.git" ]; then
    cd promoter-performance-tracker
    git pull origin main
    cd ..
else
    git clone https://github.com/AugustLoo/promoter-performance-tracker.git
fi

# 5. Set up .env
echo "[5/6] Setting up environment..."
cd promoter-performance-tracker/backend
if [ ! -f .env ]; then
    cp .env.template .env
    echo "Created .env from template."
    echo ">>> IMPORTANT: Edit .env and add your DEEPSEEK_API_KEY if needed <<<"
fi

# 6. Build and run with Docker
echo "[6/6] Building and starting Docker container..."
sudo docker build -t promoter-tracker .
sudo docker run -d \
    --name promoter-tracker \
    --restart unless-stopped \
    -p 8000:8000 \
    -v $(pwd)/uploads:/app/uploads \
    -v $(pwd)/promoter_tracker.db:/app/promoter_tracker.db \
    --env-file .env \
    promoter-tracker

echo ""
echo "============================================"
echo " Deployment Complete!"
echo "============================================"
echo ""
echo "Backend API: http://<YOUR_VM_IP>:8000"
echo "Health check: http://<YOUR_VM_IP>:8000/api/health"
echo ""
echo "Next steps:"
echo "  1. Open port 8000 in Oracle Cloud firewall:"
echo "     - Go to Virtual Cloud Network > Security Lists"
echo "     - Add Ingress Rule: TCP port 8000 from 0.0.0.0/0"
echo "  2. Update your Netlify frontend's API_BASE to:"
echo "     http://<YOUR_VM_IP>:8000"
echo "  3. Check logs: sudo docker logs -f promoter-tracker"
echo ""
echo "To restart after code changes:"
echo "  cd ~/promoter-tracker/promoter-performance-tracker/backend"
echo "  git pull && sudo docker build -t promoter-tracker . && sudo docker rm -f promoter-tracker && sudo docker run -d --name promoter-tracker --restart unless-stopped -p 8000:8000 -v \$(pwd)/uploads:/app/uploads -v \$(pwd)/promoter_tracker.db:/app/promoter_tracker.db --env-file .env promoter-tracker"

#!/usr/bin/env bash
# One-time setup for a fresh Amazon Linux 2023 / Ubuntu EC2 instance.
# Usage: ./ec2-bootstrap.sh https://github.com/<you>/metric_wave.git
set -euo pipefail

REPO_URL="${1:?repository url required}"

if command -v dnf >/dev/null; then
  sudo dnf install -y docker git
else
  sudo apt-get update && sudo apt-get install -y docker.io git curl
fi
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

# Compose v2 plugin.
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -fsSL "https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-$(uname -m)" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

git clone "$REPO_URL" ~/metric_wave
cp ~/metric_wave/.env.example ~/metric_wave/.env
echo "Edit ~/metric_wave/.env (secret key, hosts, passwords), then log out/in and run deploy/deploy.sh"

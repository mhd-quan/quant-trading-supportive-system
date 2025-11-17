# Deployment Guide

Comprehensive guide for deploying the Crypto Research Platform in development and production environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development](#local-development)
3. [Docker Deployment](#docker-deployment)
4. [Production Server](#production-server)
5. [Cloud Deployment](#cloud-deployment)
6. [Monitoring](#monitoring)
7. [Backup & Recovery](#backup--recovery)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### Hardware Requirements

**Minimum (Development):**
- 8GB RAM
- 4 CPU cores
- 20GB SSD storage
- 10 Mbps internet

**Recommended (Production):**
- 16GB RAM
- 8 CPU cores
- 500GB SSD storage
- 100 Mbps internet with low latency to exchanges

### Software Requirements

- Operating System: Ubuntu 22.04+ / macOS 13+ / Windows 11 with WSL2
- Python 3.11 or higher
- Docker & Docker Compose (optional, for containerized deployment)
- Git

## Local Development

### 1. Clone Repository

```bash
git clone https://github.com/mhd-quan/quant-trading-supportive-system.git
cd quant-trading-supportive-system
```

### 2. Install Dependencies

Using uv (recommended):
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```

Using pip:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Configure Environment

```bash
cp .env.example .env
nano .env  # Edit with your API credentials
```

Required variables:
```bash
# Exchange API Keys
BINANCE_API_KEY=your_binance_key
BINANCE_SECRET=your_binance_secret
COINBASE_API_KEY=your_coinbase_key
COINBASE_SECRET=your_coinbase_secret

# Data paths
DATA_PATH=./data
LOG_LEVEL=INFO
```

### 4. Initialize Database

```bash
make init-db
```

### 5. Run Services

Start Streamlit UI:
```bash
make ui
# Access at http://localhost:8501
```

Start live data streaming:
```bash
make stream
```

Start Prefect server:
```bash
make scheduler
# Access at http://localhost:4200
```

## Docker Deployment

### Development Profile

```bash
# Start all services with hot-reload
docker-compose --profile development up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

Services started:
- Prefect server (port 4200)
- Streamlit UI (port 8501)
- Development container with mounted source

### Production Profile

```bash
# Build images
docker-compose build

# Start production services
docker-compose --profile production up -d

# View status
docker-compose ps
```

Services started:
- Prefect server
- Streamlit UI
- Data collectors (Binance, Coinbase)
- Data validator

### Monitoring Profile

```bash
# Start with monitoring stack
docker-compose --profile production --profile monitoring up -d
```

Additional services:
- Prometheus (port 9090)
- Grafana (port 3000, admin/admin)

## Production Server

### 1. System Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3.11 python3.11-venv build-essential \
    libssl-dev libffi-dev redis-server nginx

# Install Docker (optional)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

### 2. Application Installation

```bash
# Run installation script
sudo bash deploy/install.sh
```

This script will:
- Create `crypto-research` user and group
- Set up directories in `/opt/crypto-research`
- Install Python dependencies
- Configure systemd services
- Set up log rotation

### 3. Configuration

```bash
# Edit production configuration
sudo nano /etc/crypto-research/env

# Edit production settings
sudo nano /opt/crypto-research/configs/production.yaml
```

### 4. Start Services

```bash
# Start Prefect server
sudo systemctl start prefect

# Start data collector
sudo systemctl start crypto-research-collector

# Start data validator
sudo systemctl start crypto-research-validator

# Start Streamlit UI
sudo systemctl start crypto-research

# Enable auto-start on boot
sudo systemctl enable prefect crypto-research-collector \
    crypto-research-validator crypto-research
```

### 5. Verify Deployment

```bash
# Check service status
sudo systemctl status crypto-research

# View logs
sudo journalctl -u crypto-research -f

# Test UI
curl http://localhost:8501
```

### 6. Configure Nginx (Optional)

```bash
# Create nginx config
sudo nano /etc/nginx/sites-available/crypto-research
```

```nginx
server {
    listen 80;
    server_name crypto.yourdomain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/crypto-research /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Cloud Deployment

### AWS EC2

1. **Launch Instance:**
   - AMI: Ubuntu 22.04 LTS
   - Instance type: t3.xlarge (4 vCPU, 16 GB RAM)
   - Storage: 500 GB gp3 SSD
   - Security group: Allow ports 22, 80, 443, 8501

2. **Connect and Install:**
```bash
ssh -i your-key.pem ubuntu@your-ec2-ip
git clone https://github.com/mhd-quan/quant-trading-supportive-system.git
cd quant-trading-supportive-system
sudo bash deploy/install.sh
```

3. **Configure Auto-scaling (Optional):**
   - Create AMI from configured instance
   - Set up Auto Scaling group
   - Configure CloudWatch alarms

### Digital Ocean Droplet

```bash
# Create droplet via CLI
doctl compute droplet create crypto-research \
    --image ubuntu-22-04-x64 \
    --size s-4vcpu-8gb \
    --region nyc1 \
    --ssh-keys your-ssh-key-id

# SSH and install
ssh root@droplet-ip
# Follow production server steps
```

### Kubernetes (Advanced)

```bash
# Apply manifests
kubectl apply -f deploy/k8s/

# Check status
kubectl get pods -n crypto-research
```

## Monitoring

### Prometheus Metrics

Metrics exposed at `http://localhost:9090/metrics`:
- `data_points_collected_total`
- `websocket_reconnections_total`
- `backtest_duration_seconds`
- `query_latency_seconds`

### Grafana Dashboards

Access Grafana at `http://localhost:3000` (admin/admin)

Pre-configured dashboards:
1. System Overview
2. Exchange Data Collection
3. Strategy Performance
4. Database Performance

### Health Checks

```bash
# Application health
curl http://localhost:8080/health

# Prefect health
curl http://localhost:4200/health
```

### Alerts

Configure alerts in `configs/production.yaml`:

```yaml
monitoring:
  alerts:
    enabled: true
    channels:
      - type: email
        recipients: ["alerts@example.com"]
      - type: slack
        webhook_url: "https://hooks.slack.com/..."
```

## Backup & Recovery

### Automated Backups

Backups run daily at 2 AM (configured in `configs/production.yaml`):

```bash
# Manual backup
make backup

# Backups stored in /var/backups/crypto-research/
```

### Restore from Backup

```bash
# Stop services
sudo systemctl stop crypto-research crypto-research-collector

# Restore database
cp /var/backups/crypto-research/backup-20240101/crypto.duckdb \
   /var/lib/crypto-research/data/

# Restore configs
cp -r /var/backups/crypto-research/backup-20240101/configs/* \
   /etc/crypto-research/

# Start services
sudo systemctl start crypto-research crypto-research-collector
```

### Cloud Backups

#### AWS S3

```bash
# Install AWS CLI
sudo apt install awscli

# Configure credentials
aws configure

# Sync to S3
aws s3 sync /var/lib/crypto-research/data/ \
    s3://your-bucket/crypto-research/data/ \
    --exclude "*.log"
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
sudo journalctl -u crypto-research -n 100

# Check permissions
ls -la /var/lib/crypto-research
sudo chown -R crypto-research:crypto-research /var/lib/crypto-research

# Verify configuration
sudo -u crypto-research /opt/crypto-research/.venv/bin/python -c \
    "from src.config import load_config; print(load_config())"
```

### High Memory Usage

```bash
# Check memory
free -h

# Restart services
sudo systemctl restart crypto-research

# Adjust memory limits in systemd
sudo nano /etc/systemd/system/crypto-research.service
# Change: MemoryLimit=8G
sudo systemctl daemon-reload
sudo systemctl restart crypto-research
```

### Database Issues

```bash
# Check database size
du -h /var/lib/crypto-research/data/crypto.duckdb

# Compact database
sudo -u crypto-research /opt/crypto-research/.venv/bin/python \
    scripts/compact_database.py

# Rebuild indexes
sudo -u crypto-research /opt/crypto-research/.venv/bin/python \
    scripts/rebuild_indexes.py
```

### Exchange Connection Errors

```bash
# Test connectivity
curl https://api.binance.com/api/v3/ping

# Check API credentials
grep BINANCE_API_KEY /etc/crypto-research/env

# View exchange logs
sudo journalctl -u crypto-research-collector -f | grep -i error
```

### Data Gaps

```bash
# Run validation
make validate-data

# Backfill missing data
python scripts/backfill.py --exchange binance \
    --symbol BTC/USDT --timeframe 1m \
    --start 2024-01-01 --end 2024-01-02
```

## Performance Tuning

### Database Optimization

```sql
-- In DuckDB
PRAGMA threads=8;
PRAGMA memory_limit='8GB';
ANALYZE;
```

### System Limits

```bash
# Increase file descriptors
sudo nano /etc/security/limits.conf
```

Add:
```
crypto-research soft nofile 65536
crypto-research hard nofile 65536
```

### Network Optimization

```bash
# For high-frequency data collection
sudo sysctl -w net.ipv4.tcp_tw_reuse=1
sudo sysctl -w net.core.somaxconn=1024
```

## Security Hardening

See [SECURITY.md](SECURITY.md) for comprehensive security guidelines.

Quick checklist:
- [ ] Firewall configured (UFW/iptables)
- [ ] SSH key-only authentication
- [ ] API keys in secure storage
- [ ] Regular security updates
- [ ] Log monitoring enabled
- [ ] Fail2ban configured

## Updates & Maintenance

### Update Application

```bash
# Pull latest code
cd /opt/crypto-research
sudo -u crypto-research git pull origin main

# Install new dependencies
sudo -u crypto-research .venv/bin/pip install -e ".[dev]"

# Restart services
sudo systemctl restart crypto-research crypto-research-collector
```

### Database Migrations

```bash
# Run migrations
sudo -u crypto-research /opt/crypto-research/.venv/bin/python \
    scripts/migrate_database.py
```

## Support

- Documentation: [docs/](docs/)
- Issues: GitHub Issues
- Logs: `/var/log/crypto-research/`
- Status: `sudo systemctl status crypto-research`

---

**Note:** This is a private research platform. Ensure all security measures are properly configured before exposing to the internet.

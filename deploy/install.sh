#!/bin/bash
# Installation script for Crypto Research Platform

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Crypto Research Platform Installation ===${NC}\n"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root${NC}"
   exit 1
fi

# Variables
APP_USER="crypto-research"
APP_GROUP="crypto-research"
INSTALL_DIR="/opt/crypto-research"
DATA_DIR="/var/lib/crypto-research"
LOG_DIR="/var/log/crypto-research"
CONFIG_DIR="/etc/crypto-research"
BACKUP_DIR="/var/backups/crypto-research"

# Create user and group
echo -e "${YELLOW}Creating application user and group...${NC}"
if ! id -u $APP_USER > /dev/null 2>&1; then
    groupadd --system $APP_GROUP
    useradd --system --gid $APP_GROUP --home-dir $INSTALL_DIR --shell /bin/bash $APP_USER
    echo -e "${GREEN}✓ User created${NC}"
else
    echo -e "${GREEN}✓ User already exists${NC}"
fi

# Create directories
echo -e "\n${YELLOW}Creating directories...${NC}"
mkdir -p $INSTALL_DIR
mkdir -p $DATA_DIR/lake
mkdir -p $LOG_DIR
mkdir -p $CONFIG_DIR
mkdir -p $BACKUP_DIR

# Set ownership
chown -R $APP_USER:$APP_GROUP $INSTALL_DIR
chown -R $APP_USER:$APP_GROUP $DATA_DIR
chown -R $APP_USER:$APP_GROUP $LOG_DIR
chown -R $APP_USER:$APP_GROUP $BACKUP_DIR
chown -R root:$APP_GROUP $CONFIG_DIR

# Set permissions
chmod 750 $INSTALL_DIR
chmod 750 $DATA_DIR
chmod 750 $LOG_DIR
chmod 750 $CONFIG_DIR
chmod 750 $BACKUP_DIR

echo -e "${GREEN}✓ Directories created${NC}"

# Install system dependencies
echo -e "\n${YELLOW}Installing system dependencies...${NC}"
apt-get update
apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    git \
    build-essential \
    libssl-dev \
    libffi-dev \
    redis-server

echo -e "${GREEN}✓ System dependencies installed${NC}"

# Copy application files
echo -e "\n${YELLOW}Copying application files...${NC}"
if [ -d "$(dirname $0)/.." ]; then
    cp -r "$(dirname $0)/.." $INSTALL_DIR/
    chown -R $APP_USER:$APP_GROUP $INSTALL_DIR
    echo -e "${GREEN}✓ Files copied${NC}"
else
    echo -e "${RED}Error: Source directory not found${NC}"
    exit 1
fi

# Create virtual environment and install dependencies
echo -e "\n${YELLOW}Setting up Python environment...${NC}"
su - $APP_USER -c "cd $INSTALL_DIR && python3.11 -m venv .venv"
su - $APP_USER -c "cd $INSTALL_DIR && .venv/bin/pip install --upgrade pip setuptools wheel"
su - $APP_USER -c "cd $INSTALL_DIR && .venv/bin/pip install -e '.[dev]'"
echo -e "${GREEN}✓ Python environment ready${NC}"

# Copy configuration files
echo -e "\n${YELLOW}Setting up configuration...${NC}"
if [ -f "$INSTALL_DIR/configs/production.yaml" ]; then
    cp $INSTALL_DIR/configs/*.yaml $CONFIG_DIR/
    chown root:$APP_GROUP $CONFIG_DIR/*.yaml
    chmod 640 $CONFIG_DIR/*.yaml
    echo -e "${GREEN}✓ Configuration files copied${NC}"
fi

# Copy environment file template
if [ -f "$INSTALL_DIR/.env.example" ]; then
    cp $INSTALL_DIR/.env.example $CONFIG_DIR/env
    chown root:$APP_GROUP $CONFIG_DIR/env
    chmod 640 $CONFIG_DIR/env
    echo -e "${YELLOW}⚠ Please edit $CONFIG_DIR/env with your API credentials${NC}"
fi

# Install systemd services
echo -e "\n${YELLOW}Installing systemd services...${NC}"
cp $INSTALL_DIR/deploy/*.service /etc/systemd/system/
systemctl daemon-reload
echo -e "${GREEN}✓ Services installed${NC}"

# Initialize database
echo -e "\n${YELLOW}Initializing database...${NC}"
su - $APP_USER -c "cd $INSTALL_DIR && .venv/bin/python scripts/init_database.py"
echo -e "${GREEN}✓ Database initialized${NC}"

# Enable services
echo -e "\n${YELLOW}Enabling services...${NC}"
systemctl enable prefect.service
systemctl enable crypto-research.service
systemctl enable crypto-research-collector.service
systemctl enable crypto-research-validator.service
echo -e "${GREEN}✓ Services enabled${NC}"

# Setup log rotation
echo -e "\n${YELLOW}Setting up log rotation...${NC}"
cat > /etc/logrotate.d/crypto-research << EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 $APP_USER $APP_GROUP
    sharedscripts
    postrotate
        systemctl reload crypto-research crypto-research-collector crypto-research-validator
    endscript
}
EOF
echo -e "${GREEN}✓ Log rotation configured${NC}"

# Setup backup cron job
echo -e "\n${YELLOW}Setting up backup cron job...${NC}"
(crontab -u $APP_USER -l 2>/dev/null; echo "0 2 * * * cd $INSTALL_DIR && .venv/bin/python -c 'from scripts.backup import run_backup; run_backup()'") | crontab -u $APP_USER -
echo -e "${GREEN}✓ Backup job scheduled${NC}"

# Print summary
echo -e "\n${GREEN}=== Installation Complete ===${NC}\n"
echo -e "Next steps:"
echo -e "1. Edit configuration: ${YELLOW}sudo nano $CONFIG_DIR/env${NC}"
echo -e "2. Start Prefect: ${YELLOW}sudo systemctl start prefect${NC}"
echo -e "3. Start collector: ${YELLOW}sudo systemctl start crypto-research-collector${NC}"
echo -e "4. Start validator: ${YELLOW}sudo systemctl start crypto-research-validator${NC}"
echo -e "5. Start UI: ${YELLOW}sudo systemctl start crypto-research${NC}"
echo -e "\nMonitor logs: ${YELLOW}sudo journalctl -u crypto-research -f${NC}"
echo -e "Check status: ${YELLOW}sudo systemctl status crypto-research${NC}\n"

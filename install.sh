#!/bin/bash

# ADI Onboarding Checklist Installation Script

set -e

echo "==================================================="
echo "ADI Onboarding Checklist - Installation Script"
echo "==================================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

# Variables
INSTALL_DIR="/usr/local/bin/onboarding_checklist"
SERVICE_FILE="onboarding_checklist.service"
SYSTEMD_DIR="/etc/systemd/system"

# Check Python3
echo "Checking Python3 installation..."
if ! command -v python3 &> /dev/null; then
    echo "Python3 is not installed. Please install Python3 first."
    exit 1
fi
echo "✓ Python3 found: $(python3 --version)"

# Check pip3
echo "Checking pip3 installation..."
if ! command -v pip3 &> /dev/null; then
    echo "pip3 is not installed. Installing..."
    yum install -y python3-pip || apt-get install -y python3-pip
fi
echo "✓ pip3 found"

# Check MongoDB
echo "Checking MongoDB service..."
if ! systemctl is-active --quiet mongod; then
    echo "⚠ MongoDB is not running. Please start MongoDB:"
    echo "  systemctl start mongod"
    echo "  systemctl enable mongod"
else
    echo "✓ MongoDB is running"
fi

# Create installation directory
echo "Creating installation directory..."
mkdir -p "$INSTALL_DIR"
echo "✓ Created $INSTALL_DIR"

# Copy files
echo "Copying application files..."
cp -r ./* "$INSTALL_DIR/"
echo "✓ Files copied"

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r "$INSTALL_DIR/requirements.txt"
echo "✓ Dependencies installed"

# Create onboarding documents directory
echo "Creating onboarding documents directory..."
mkdir -p /opt/onboardingdoc/
chmod 755 /opt/onboardingdoc/
echo "✓ Created /opt/onboardingdoc/"

# Install systemd service
echo "Installing systemd service..."
cp "$INSTALL_DIR/$SERVICE_FILE" "$SYSTEMD_DIR/"
systemctl daemon-reload
echo "✓ Systemd service installed"

# Set permissions
echo "Setting permissions..."
chmod +x "$INSTALL_DIR/app.py"
echo "✓ Permissions set"

echo ""
echo "==================================================="
echo "Installation Complete!"
echo "==================================================="
echo ""
echo "Next steps:"
echo "1. Place onboarding documents in /opt/onboardingdoc/"
echo "2. Start the service:"
echo "   systemctl start onboarding_checklist"
echo "3. Enable auto-start on boot:"
echo "   systemctl enable onboarding_checklist"
echo "4. Check service status:"
echo "   systemctl status onboarding_checklist"
echo "5. View logs:"
echo "   journalctl -u onboarding_checklist -f"
echo ""
echo "The application will be available at:"
echo "http://$(hostname):5000"
echo ""
echo "==================================================="

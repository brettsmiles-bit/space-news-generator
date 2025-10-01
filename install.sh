#!/bin/bash
set -e

echo "================================"
echo "Space News Pipeline - Setup"
echo "================================"
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  This script needs sudo access to install system packages"
    echo "   Run: sudo bash install.sh"
    echo
    echo "   Or manually run:"
    echo "   1. sudo apt-get install -y python3-venv python3-pip ffmpeg"
    echo "   2. python3 -m venv venv"
    echo "   3. source venv/bin/activate"
    echo "   4. pip install -r requirements.txt"
    exit 1
fi

echo "📦 Installing system packages..."
apt-get update -qq
apt-get install -y python3-venv python3-pip ffmpeg

echo
echo "✅ System packages installed!"
echo
echo "🐍 Now run these commands as your regular user:"
echo
echo "   cd /tmp/cc-agent/57819754/project"
echo "   python3 -m venv venv"
echo "   source venv/bin/activate"
echo "   pip install -r requirements.txt"
echo
echo "Then configure your API keys in pipeline_config.json"
echo "and run: python space_news_pipeline_optimized.py"

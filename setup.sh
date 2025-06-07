#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse command line arguments
DEV_MODE=false
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --dev) DEV_MODE=true ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

if [ "$DEV_MODE" = true ]; then
    echo -e "${BLUE}Starting KingShotBot setup in DEVELOPMENT MODE...${NC}"
    export DISCORD_ENABLED=0
else
    echo -e "${GREEN}Starting KingShotBot setup in PRODUCTION MODE...${NC}"
    export DISCORD_ENABLED=1
fi

set -e  # optional: exit on first error

echo "🔧 Starting setup..."

# Activate virtual env or create it
if [ ! -d ".venv" ]; then
    echo "🧪 Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check if .env file exists, if not create a template
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env template file...${NC}"
    echo "# Bot Configuration" > .env
    if [ "$DEV_MODE" = true ]; then
        echo "# Development mode is enabled - Discord connection is disabled" >> .env
        echo "DISCORD_ENABLED=0" >> .env
    else
        echo "DISCORD_ENABLED=1" >> .env
    fi
    echo "KINGSHOT_DEV_TOKEN=your_discord_token_here" >> .env
    echo "BOT_PREFIX=!" >> .env
    if [ "$DEV_MODE" = false ]; then
        echo -e "${YELLOW}Please edit the .env file and add your Discord bot token.${NC}"
    fi
fi

echo -e "${GREEN}Setup completed successfully!${NC}"
echo -e "${YELLOW}Next steps:${NC}"
if [ "$DEV_MODE" = true ]; then
    echo "1. Development mode is enabled - Discord connection is disabled"
    echo "2. Run the bot using: python bot.py"
    echo "   The bot will start in development mode without connecting to Discord"
else
    echo "1. Edit the .env file and add your Discord bot token"
    echo "2. Run the bot using: python bot.py"
    echo "   Or on Windows: start bot.bat"
fi

#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting KingShotBot setup...${NC}"

# Install requirements
echo -e "${GREEN}Installing Python dependencies...${NC}"
pip install -r requirements.txt

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}Python 3 is not installed. Please install Python 3.8 or higher.${NC}"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo -e "${GREEN}Creating virtual environment...${NC}"
    python3 -m venv .venv
fi

# Activate virtual environment
echo -e "${GREEN}Activating virtual environment...${NC}"
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi

# Upgrade pip
echo -e "${GREEN}Upgrading pip...${NC}"
python -m pip install --upgrade pip



# Check if .env file exists, if not create a template
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env template file...${NC}"
    echo "# Bot Configuration" > .env
    echo "DISCORD_TOKEN=your_discord_token_here" >> .env
    echo "BOT_PREFIX=!" >> .env
    echo -e "${YELLOW}Please edit the .env file and add your Discord bot token.${NC}"
fi

echo -e "${GREEN}Setup completed successfully!${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Edit the .env file and add your Discord bot token"
echo "2. Run the bot using: python bot.py"
echo "   Or on Windows: start bot.bat" 
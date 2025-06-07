#!/bin/bash

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting KingShotBot setup...${NC}"

# Check if Python 3 is installed
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
source .venv/bin/activate

# Upgrade pip
echo -e "${GREEN}Upgrading pip...${NC}"
python -m pip install --upgrade pip

# Install dependencies
echo -e "${GREEN}Installing Python dependencies...${NC}"
pip install -r requirements.txt

# Create .env template if missing
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env template file...${NC}"
    cat <<EOT > .env
# Discord Bot Token
KINGSHOT_DEV_TOKEN=your_discord_token_here
EOT
    echo -e "${YELLOW}Please edit the .env file and add your Discord bot token.${NC}"
fi

echo -e "${GREEN}Setup completed successfully!${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Edit the .env file and add your Discord bot token"
echo "2. Run the bot using: python bot.py"

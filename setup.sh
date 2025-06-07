#!/bin/bash

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

echo "✅ Setup complete. Launching bot..."
python bot.py

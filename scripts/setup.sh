#!/bin/bash
echo "🚀 Setting up NoorLink Automation..."
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "⚠️ Update .env with your credentials!"
fi
echo "✅ Setup complete!"

#!/bin/bash
# Botni ishga tushirish scripti

cd "$(dirname "$0")"

# Eski bot jarayonlarini to'xtatish
echo "Eski bot jarayonlarini to'xtatish..."
pkill -f "python3 bot.py" 2>/dev/null
sleep 2

# Botni ishga tushirish
echo "Bot ishga tushmoqda..."
python3 bot.py


#!/bin/bash
# Botni backgroundda ishga tushirish scripti

cd "$(dirname "$0")"

# Eski bot jarayonlarini to'xtatish
echo "Eski bot jarayonlarini to'xtatish..."
pkill -f "python3 bot.py" 2>/dev/null
sleep 2

# Botni backgroundda ishga tushirish
echo "Bot backgroundda ishga tushmoqda..."
nohup python3 bot.py > bot.log 2>&1 &

# Jarayon ID ni ko'rsatish
sleep 1
BOT_PID=$(pgrep -f "python3 bot.py")
if [ -n "$BOT_PID" ]; then
    echo "✅ Bot muvaffaqiyatli ishga tushdi! (PID: $BOT_PID)"
    echo "Log fayl: $(pwd)/bot.log"
    echo "Botni to'xtatish uchun: ./stop_bot.sh"
else
    echo "❌ Bot ishga tushmadi. Log faylni tekshiring: bot.log"
fi


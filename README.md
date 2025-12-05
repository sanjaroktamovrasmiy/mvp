# Telegram Test Bot

Telegram bot test tizimi - boss, admin va oddiy foydalanuvchilar uchun.

## Loyiha strukturi

```
mvp/
├── bot.py                    # Asosiy bot fayli
├── config.py                 # Konfiguratsiya (token, boss_id)
├── database.py               # Ma'lumotlar bazasi funksiyalari
├── handlers.py               # Barcha handler funksiyalari
├── utils.py                  # Yordamchi funksiyalar (pdf)
├── requirements.txt          # Python paketlari
├── start_bot.sh              # Botni ishga tushirish (foreground)
├── start_bot_background.sh   # Botni backgroundda ishga tushirish
├── stop_bot.sh               # Botni to'xtatish
├── bot.log                   # Bot log fayli
└── README.md                 # Qo'llanma
```

## Xususiyatlar

- ✅ Majburiy kanal obunasi tekshiruvi
- ✅ Boss boshqaruvi (adminlar va kanallar)
- ✅ Adminlar test yaratishi
- ✅ Foydalanuvchilar test ishlashi
- ✅ PDF formatida batafsil natijalar
- ✅ 0-1 Matrix Excel formatda eksport
- ✅ Modullashtirilgan kod struktura
- ✅ Xatoliklarni qayta ishlash (error handling)

## O'rnatish

1. Python 3.8+ o'rnatilgan bo'lishi kerak

2. Python paketlarini o'rnating:
```bash
pip install -r requirements.txt
```

3. wkhtmltopdf o'rnating (PDF yaratish uchun):
```bash
# Ubuntu/Debian uchun:
sudo apt-get install wkhtmltopdf

# Yoki manuel o'rnatish:
# https://wkhtmltopdf.org/downloads.html
```

**Muhim:** Agar wkhtmltopdf o'rnatilmagan bo'lsa, PDF reportlab orqali yaratiladi (oddiyroq format).

## Ishga tushirish

### Oddiy ishga tushirish (foreground)
```bash
python3 bot.py
```

### Backgroundda ishga tushirish (tavsiya etiladi)
```bash
./start_bot_background.sh
```

Bu script:
- Eski bot jarayonlarini avtomatik to'xtatadi
- Botni backgroundda ishga tushadi
- Log faylga yozadi (`bot.log`)

### Botni to'xtatish
```bash
./stop_bot.sh
```

### Qayta ishga tushirish
```bash
./start_bot.sh
```

**Eslatma:** Agar bot ishga tushmasa, ehtimol allaqachon ishlamoqda. Avval `./stop_bot.sh` ni ishga tushiring.

## Foydalanish

### Boss (ID: 7537966029)
- `/admin` - Adminlar boshqaruvi
- `/channels` - Majburiy kanallar boshqaruvi
- `/createtest` - Test yaratish

### Adminlar
- `/createtest` - Test yaratish
- `/tests` - Testlar ro'yxati

### Oddiy foydalanuvchilar
- `/tests` - Mavjud testlar
- `/myresults` - Mening natijalarim

## Test yaratish formati

```
Test nomi
1. Savol?
a) Variant 1
b) Variant 2
c) Variant 3
d) Variant 4
Javob: a

2. Savol?
a) Variant 1
b) Variant 2
c) Variant 3
d) Variant 4
Javob: b
```

## Ma'lumotlar saqlash

Barcha ma'lumotlar `data.json` faylida saqlanadi.

## Texnologiyalar

- **Python 3.8+**
- **python-telegram-bot** - Telegram bot API
- **openpyxl** - Excel fayl o'qish/yozish
- **pdfkit** - PDF generatsiya (HTML → PDF)
- **reportlab** - PDF generatsiya (fallback)
- **pytz** - Vaqt zonalari (O'zbekiston vaqti)


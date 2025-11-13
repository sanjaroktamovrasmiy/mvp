# Telegram Test Bot

Telegram bot test tizimi - boss, admin va oddiy foydalanuvchilar uchun.

## Loyiha strukturi

```
mvp/
├── bot.py                    # Asosiy bot fayli
├── config.py                 # Konfiguratsiya (token, boss_id)
├── database.py               # Ma'lumotlar bazasi funksiyalari
├── handlers.py               # Barcha handler funksiyalari
├── utils.py                  # Yordamchi funksiyalar (rasch, pdf)
├── rasch_pkg.py              # Rasch Model IRT implementatsiyasi
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
- ✅ **Rasch Model IRT** orqali ilmiy baholash tizimi
- ✅ **T-score** (standart ball) formulasi: **T = 50 + 10Z**
- ✅ PDF formatida batafsil natijalar
- ✅ 0-1 Matrix Excel formatda eksport
- ✅ Modullashtirilgan kod struktura
- ✅ Xatoliklarni qayta ishlash (error handling)

## O'rnatish

1. Python 3.8+ o'rnatilgan bo'lishi kerak

2. R va eRm kutubxonasini o'rnating (Rasch Model uchun):
```bash
# Ubuntu/Debian uchun:
sudo apt-get update
sudo apt-get install r-base r-base-dev

# R konsolida eRm kutubxonasini o'rnatish:
R
> install.packages("eRm")
> quit()
```

**Muhim:** eRm - Extended Rasch Modeling - eng ishonchli Rasch model implementatsiyasi. Agar eRm o'rnatilmagan bo'lsa, fallback JMLE algoritmi ishlatiladi (kam aniq).

3. Python paketlarini o'rnating:
```bash
pip install -r requirements.txt
```

**Eslatma:** `rpy2` paketi R bilan Python orasidagi ko'prik. R va eRm o'rnatilmagan bo'lsa, `rpy2` xato beradi, lekin bot fallback algoritm bilan ishlaydi.

4. wkhtmltopdf o'rnating (PDF yaratish uchun):
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
- `/rasch` - **Rasch Model** orqali talabalarni baholash

### Adminlar
- `/createtest` - Test yaratish
- `/tests` - Testlar ro'yxati
- `/rasch` - **Rasch Model** orqali talabalarni baholash

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

## Rasch Model Baholash

### `/rasch` commandasi qanday ishlaydi?

1. Boss yoki Admin `/rasch` commandasini yuboradi
2. Bot Excel fayl (.xlsx) yuborishni so'raydi
3. Excel fayl formatini to'g'ri tayyorlang:

**Excel fayl formati:**
```
user_id  | Q1 | Q2 | Q3 | Q4 | Q5 | ...
---------|----|----|----|----|----|----- 
12345    | 1  | 0  | 1  | 1  | 0  | ...
67890    | 0  | 1  | 1  | 0  | 1  | ...
54321    | 1  | 1  | 0  | 1  | 1  | ...
```

- **Birinchi qator**: `user_id`, `Q1`, `Q2`, `Q3`, ... (header)
- **Keyingi qatorlar**: har bir talaba uchun `user_id` va javoblar
- **Javoblar**: `1` = to'g'ri, `0` = noto'g'ri

4. Bot Rasch modelini ishga tushiradi va natijalarni PDF formatda qaytaradi

### Rasch Model formulalari

**Z-score:**
```
Z = (θ - μ) / σ
```
Bu yerda:
- **θ (theta)** - talabaning qobiliyati (ability)
- **μ (mu)** - o'rtacha qiymat
- **σ (sigma)** - standart tafovut

**T-score (Standart ball):**
```
T = 50 + 10Z
```

**Baholash mezonlari:**
- 🟢 **A (A'lo)**: T ≥ 70
- 🟡 **B (Yaxshi)**: 60 ≤ T < 70
- 🟠 **C (Qoniqarli)**: 50 ≤ T < 60
- 🔴 **D (Qoniqarsiz)**: 40 ≤ T < 50
- ⚫ **E (Juda past)**: T < 40

### PDF natijalar

PDF faylida quyidagi ma'lumotlar bo'ladi:
- Umumiy statistika (o'rtacha, standart tafovut)
- Baholash formulalari va mezonlari
- Har bir talaba uchun:
  - θ (theta) - qobiliyat
  - Z-score
  - T-score (standart ball)
  - Baho (A, B, C, D, E)
- Barcha talabalar T-score bo'yicha tartiblangan jadvalda

## Ma'lumotlar saqlash

Barcha ma'lumotlar `data.json` faylida saqlanadi.

## Texnologiyalar

- **Python 3.8+**
- **R** - Statistik hisoblash tili
- **eRm** - Extended Rasch Modeling (R kutubxonasi)
- **rpy2** - Python va R orasidagi ko'prik
- **python-telegram-bot** - Telegram bot API
- **numpy** - Matematik hisob-kitoblar
- **scipy** - Statistik hisob-kitoblar va optimizatsiya
- **openpyxl** - Excel fayl o'qish/yozish
- **pdfkit** - PDF generatsiya (HTML → PDF)
- **reportlab** - PDF generatsiya (fallback)
- **pytz** - Vaqt zonalari (O'zbekiston vaqti)

### Rasch Model implementatsiyasi

Bot 3 xil usulda ishlashi mumkin (prioritet tartibida):

1. **eRm (R kutubxonasi)** - ✅ Eng ishonchli va aniq
   - Professional ilmiy standart
   - Person va item parametrlarini to'g'ri hisoblaydi
   - Standart xatolarni beradi
   
2. **JMLE (Python fallback)** - ⚠️ O'rtacha aniqlik
   - eRm mavjud bo'lmasa ishlatiladi
   - Joint Maximum Likelihood Estimation
   
3. **Oddiy logit** - ⚠️ Kam aniq
   - JMLE ham ishlamasa ishlatiladi
   - Faqat asosiy ballni hisoblaydi


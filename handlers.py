
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot handler funksiyalari
"""

import logging
import re
import os
from datetime import datetime, timedelta
import pytz
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
import pdfkit

from config import BOSS_ID
from database import load_data, save_data
from utils import check_subscription, calculate_rasch_score, generate_pdf, evaluate_students_from_matrix

# O'zbekiston vaqti (UTC+5)
UZBEKISTAN_TZ = pytz.timezone('Asia/Tashkent')

logger = logging.getLogger(__name__)


def generate_test_post(test_data, test_id, bot_username=None):
    """
    Test haqida ko'rkam va tushunarli post yaratish
    
    Args:
        test_data: Test ma'lumotlari
        test_id: Test ID
        bot_username: Bot username (ixtiyoriy)
    
    Returns:
        tuple: (post_text, inline_keyboard) - HTML formatidagi post matni va inline keyboard
    """
    test_name = test_data.get('name', 'Test')
    total_questions = len(test_data.get('questions', []))
    
    # Test boshlanish vaqti
    start_time_text = ""
    if 'start_time' in test_data:
        try:
            start_time = datetime.fromisoformat(test_data['start_time'])
            if start_time.tzinfo is None:
                start_time = UZBEKISTAN_TZ.localize(start_time)
            start_time_text = f"\n⏰ <b>Test boshlanish vaqti:</b> {start_time.strftime('%d.%m.%Y %H:%M')}\n"
        except:
            pass
    
    # Bot username (agar berilmagan bo'lsa, default)
    if not bot_username:
        bot_username = "Test Bot"
    
    post = f"""
📝 <b>{test_name}</b>

📊 <b>Ma'lumotlar:</b>
• Savollar soni: {total_questions} ta
• Format: Ko'p tanlovli (a, b, c, d){start_time_text}
⚠️ <b>Shartlar:</b>
• Har bir testni faqat <b>1 marta</b> ishlash mumkin
• Javoblarni <b>1a2b3c4d...</b> formatida yuboring
• Javoblar soni savollar soniga mos kelishi kerak

✅ Test yakunlangach, natijalar o'qituvchi tomonidan e'lon qilinadi.

🎓 Muvaffaqiyatlar!
"""
    
    # Inline keyboard yaratish - testni boshlash uchun
    keyboard = [
        [InlineKeyboardButton("🚀 Testni boshlash", callback_data=f"start_test_{test_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    return post, reply_markup


async def check_user_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Foydalanuvchining ism va familyasini tekshirish"""
    user_id = update.effective_user.id
    data = load_data()
    
    # Foydalanuvchi ma'lumotlarini tekshirish
    user_info = data.get('users', {}).get(str(user_id), {})
    first_name = user_info.get('first_name', '').strip()
    last_name = user_info.get('last_name', '').strip()
    
    # Ism va familya to'liq bo'lishi kerak
    if not first_name or not last_name:
        return False
    
    # Ism va familya kamida 2 ta harfdan iborat bo'lishi kerak
    if len(first_name) < 2 or len(last_name) < 2:
        return False
    
    return True


async def process_user_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ism va familya kiritish jarayonini qayta ishlash"""
    if not update.message or not update.message.text:
        return
    
    text = update.message.text.strip()
    user_id = update.effective_user.id
    step = context.user_data.get('name_step', 'first_name')
    
    # Ism kiritish
    if step == 'first_name':
        # Ism validatsiyasi
        if len(text) < 2:
            await update.message.reply_text(
                "❌ Ism kamida 2 ta harfdan iborat bo'lishi kerak.\n\n"
                "📝 Ismingizni qayta kiriting:"
            )
            return
        
        # Raqamlar yoki maxsus belgilar tekshiruvi (faqat harflar va probellar)
        if not all(c.isalpha() or c.isspace() for c in text):
            await update.message.reply_text(
                "❌ Ism faqat harflardan iborat bo'lishi kerak.\n\n"
                "📝 Ismingizni qayta kiriting:"
            )
            return
        
        # Ismni saqlash
        context.user_data['first_name'] = text.strip()
        context.user_data['name_step'] = 'last_name'
        
        await update.message.reply_text(
            "✅ Ism qabul qilindi!\n\n"
            "📝 Familyangizni kiriting:"
        )
        return
    
    # Familya kiritish
    elif step == 'last_name':
        # Familya validatsiyasi
        if len(text) < 2:
            await update.message.reply_text(
                "❌ Familya kamida 2 ta harfdan iborat bo'lishi kerak.\n\n"
                "📝 Familyangizni qayta kiriting:"
            )
            return
        
        # Raqamlar yoki maxsus belgilar tekshiruvi (faqat harflar va probellar)
        if not all(c.isalpha() or c.isspace() for c in text):
            await update.message.reply_text(
                "❌ Familya faqat harflardan iborat bo'lishi kerak.\n\n"
                "📝 Familyangizni qayta kiriting:"
            )
            return
        
        # Familyani saqlash
        first_name = context.user_data.get('first_name', '').strip()
        last_name = text.strip()
        
        # Ma'lumotlar bazasiga saqlash
        data = load_data()
        if 'users' not in data:
            data['users'] = {}
        
        data['users'][str(user_id)] = {
            'first_name': first_name,
            'last_name': last_name,
            'registered_at': datetime.now().isoformat()
        }
        save_data(data)
        
        # User data ni tozalash
        context.user_data.pop('waiting_for_name', None)
        context.user_data.pop('name_step', None)
        context.user_data.pop('first_name', None)
        
        # Xush kelibsiz xabari
        full_name = f"{first_name} {last_name}"
        keyboard = [
            [KeyboardButton("📝 Test ishlash"), KeyboardButton("📊 Test natijalarim")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            f"✅ {full_name}, ma'lumotlaringiz qabul qilindi!\n\n"
            f"Endi botdan foydalanishingiz mumkin.",
            reply_markup=reply_markup
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komandasi"""
    user_id = update.effective_user.id
    
    # Majburiy obuna tekshiruvi
    if not await check_subscription(update, context):
        data = load_data()
        
        # Inline keyboard yaratish kanallar uchun
        keyboard = []
        for ch in data["mandatory_channels"]:
            # Kanal username yoki ID ni tayyorlash
            if ch.startswith('@'):
                channel_username = ch.replace('@', '')
                button_text = ch
                # Inline button yaratish (kanalga havola)
                keyboard.append([InlineKeyboardButton(
                    text=f"📢 {button_text}",
                    url=f"https://t.me/{channel_username}"
                )])
            elif ch.startswith('-'):
                # Kanal ID bo'lsa, button yaratib bo'lmaydi (URL kerak emas)
                # Faqat matn sifatida ko'rsatamiz
                pass
            else:
                # Username @ belgisiz bo'lsa
                channel_username = ch
                button_text = f"@{ch}"
                # Inline button yaratish (kanalga havola)
                keyboard.append([InlineKeyboardButton(
                    text=f"📢 {button_text}",
                    url=f"https://t.me/{channel_username}"
                )])
        
        # Inline keyboard markup yaratish
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        
        # Kanal ro'yxatini matn sifatida ham ko'rsatish
        channels_text = "\n".join([
            f"• {ch if ch.startswith('@') else f'@{ch}' if not ch.startswith('-') else f'Kanal ID: {ch}'}"
            for ch in data["mandatory_channels"]
        ])
        
        text = f"❌ Botdan foydalanish uchun quyidagi kanallarga obuna bo'lishingiz kerak:\n\n{channels_text}\n\n"
        text += "Quyidagi tugmalar orqali kanallarga o'ting va obuna bo'ling.\n"
        text += "Obuna bo'lgach, /start ni qayta bosing."
        
        await update.message.reply_text(text, reply_markup=reply_markup)
        return
    
    # Ism va familya tekshiruvi
    if not await check_user_name(update, context):
        # Ism va familya kiritish rejimini boshlash
        context.user_data['waiting_for_name'] = True
        context.user_data['name_step'] = 'first_name'
        
        await update.message.reply_text(
            "👤 Botdan foydalanish uchun ism va familyangizni kiriting.\n\n"
            "Iltimos, to'g'ri ism va familyangizni kiriting:\n\n"
            "📝 Ismingizni kiriting:"
        )
        return
    
    # Foydalanuvchi turini aniqlash
    data = load_data()
    is_boss = user_id == BOSS_ID
    is_admin = user_id in data["admins"]
    
    # Reply keyboard markup yaratish (barcha foydalanuvchilar uchun)
    keyboard = [
        [KeyboardButton("📝 Test ishlash"), KeyboardButton("📊 Test natijalarim")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    # Foydalanuvchi ismi va familyasini olish
    user_info = data.get('users', {}).get(str(user_id), {})
    first_name = user_info.get('first_name', '')
    last_name = user_info.get('last_name', '')
    full_name = f"{first_name} {last_name}".strip()
    
    if is_boss:
        text = f"👑 {full_name}, Boss paneliga xush kelibsiz!\n\n"
        text += "/admin - Adminlar boshqaruvi\n"
        text += "/channels - Kanal boshqaruvi\n"
        text += "/createtest - Test yaratish\n\n"
        text += "Yoki quyidagi tugmalardan foydalaning:"
    elif is_admin:
        text = f"👨‍💼 {full_name}, Admin paneliga xush kelibsiz!\n\n"
        text += "/createtest - Test yaratish\n\n"
        text += "Yoki quyidagi tugmalardan foydalaning:"
    else:
        text = f"👋 {full_name}, Test botiga xush kelibsiz!\n\n"
        text += "Quyidagi tugmalardan foydalaning:"
    
    await update.message.reply_text(text, reply_markup=reply_markup)


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel (faqat boss uchun)"""
    if update.effective_user.id != BOSS_ID:
        await update.message.reply_text("❌ Bu funksiya faqat boss uchun!")
        return
    
    data = load_data()
    keyboard = [
        [InlineKeyboardButton("➕ Admin qo'shish", callback_data="add_admin")],
        [InlineKeyboardButton("➖ Admin olib tashlash", callback_data="remove_admin")],
        [InlineKeyboardButton("📋 Adminlar ro'yxati", callback_data="list_admins")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👑 Admin boshqaruvi:", reply_markup=reply_markup)


async def channels_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kanal boshqaruvi (faqat boss uchun)"""
    if update.effective_user.id != BOSS_ID:
        await update.message.reply_text("❌ Bu funksiya faqat boss uchun!")
        return
    
    data = load_data()
    keyboard = [
        [InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel")],
        [InlineKeyboardButton("➖ Kanal olib tashlash", callback_data="remove_channel")],
        [InlineKeyboardButton("📋 Kanallar ro'yxati", callback_data="list_channels")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📢 Kanal boshqaruvi:", reply_markup=reply_markup)


async def create_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test yaratish"""
    user_id = update.effective_user.id
    data = load_data()
    
    if user_id != BOSS_ID and user_id not in data["admins"]:
        await update.message.reply_text("❌ Bu funksiya faqat adminlar uchun!")
        return
    
    # Test yaratish rejimini boshlash
    context.user_data['creating_test'] = True
    context.user_data['test_creation_step'] = 'name'
    
    await update.message.reply_text(
        "📝 Test yaratish:\n\n"
        "Test nomini kiriting:\n\n"
        "Yoki /cancel ni bosing bekor qilish uchun."
    )


async def process_test_editing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test tahrirlash jarayonini qayta ishlash"""
    if not context.user_data.get('editing_test'):
        return
    
    if not update.message or not update.message.text:
        return
    
    user_id = update.effective_user.id
    test_id = context.user_data.get('editing_test_id')
    step = context.user_data.get('test_editing_step', 'name')
    
    data = load_data()
    if test_id not in data['tests']:
        await update.message.reply_text("❌ Test topilmadi!")
        context.user_data.pop('editing_test', None)
        return
    
    test = data['tests'][test_id]
    
    if step == 'name':
        # Test nomi o'zgartirildi
        new_name = update.message.text.strip()
        if new_name == '/cancel':
            context.user_data.pop('editing_test', None)
            context.user_data.pop('editing_test_id', None)
            context.user_data.pop('test_editing_step', None)
            await update.message.reply_text("❌ Tahrirlash bekor qilindi.")
            return
        
        test['name'] = new_name
        save_data(data)
        context.user_data.pop('editing_test', None)
        context.user_data.pop('editing_test_id', None)
        context.user_data.pop('test_editing_step', None)
        await update.message.reply_text(f"✅ Test nomi o'zgartirildi: {new_name}")
        return
    
    elif step == 'answers':
        # Javoblar o'zgartirildi
        answers_text = update.message.text.strip().lower()
        if answers_text == '/cancel':
            context.user_data.pop('editing_test', None)
            context.user_data.pop('editing_test_id', None)
            context.user_data.pop('test_editing_step', None)
            await update.message.reply_text("❌ Tahrirlash bekor qilindi.")
            return
        
        try:
            questions = test['questions']
            answers = []
            
            for char in answers_text:
                if char.lower() in 'abcd':
                    answers.append(char.lower())
            
            if len(answers) != len(questions):
                await update.message.reply_text(
                    f"❌ Javoblar soni noto'g'ri!\n"
                    f"Savollar soni: {len(questions)}\n"
                    f"Javoblar soni: {len(answers)}\n\n"
                    f"Qayta kiriting: 1a2b3c4d... formatida"
                )
                return
            
            # Javoblarni yangilash
            for idx, answer in enumerate(answers):
                if idx < len(questions):
                    questions[idx]['correct'] = answer
            
            test['questions'] = questions
            save_data(data)
            context.user_data.pop('editing_test', None)
            context.user_data.pop('editing_test_id', None)
            context.user_data.pop('test_editing_step', None)
            await update.message.reply_text(f"✅ Javoblar yangilandi!")
            
        except Exception as e:
            logger.error(f"Javoblar yangilash xatosi: {e}")
            await update.message.reply_text(f"❌ Xatolik: {str(e)}")
    
    elif step == 'start_time':
        # Test boshlanish vaqti o'zgartirildi
        time_input = update.message.text.strip().lower()
        if time_input == '/cancel':
            context.user_data.pop('editing_test', None)
            context.user_data.pop('editing_test_id', None)
            context.user_data.pop('test_editing_step', None)
            await update.message.reply_text("❌ Tahrirlash bekor qilindi.")
            return
        
        try:
            # Agar 'hozir' deb yozilgan bo'lsa
            if time_input == 'hozir' or time_input == 'now':
                start_time = datetime.now(UZBEKISTAN_TZ)
            else:
                # Vaqtni parse qilish
                try:
                    start_time = datetime.strptime(time_input, '%Y-%m-%d %H:%M')
                    # O'zbekiston vaqtiga o'tkazish
                    start_time = UZBEKISTAN_TZ.localize(start_time)
                except ValueError:
                    await update.message.reply_text(
                        "❌ Noto'g'ri format!\n\n"
                        "Format: YYYY-MM-DD HH:MM\n"
                        "Masalan: 2024-12-25 14:30"
                    )
                    return
            
            # Vaqtni tekshirish (o'tmish bo'lmasligi kerak)
            now_uz = datetime.now(UZBEKISTAN_TZ)
            if start_time < now_uz:
                await update.message.reply_text(
                    "❌ Test boshlanish vaqti o'tmish bo'lishi mumkin emas!\n\n"
                    f"Hozirgi vaqt: {now_uz.strftime('%m-%d %H:%M')}\n"
                    "Qayta kiriting:"
                )
                return
            
            # Testni yangilash
            test['start_time'] = start_time.isoformat()
            save_data(data)
            context.user_data.pop('editing_test', None)
            context.user_data.pop('editing_test_id', None)
            context.user_data.pop('test_editing_step', None)
            
            start_time_str = start_time.strftime('%m-%d %H:%M')
            await update.message.reply_text(f"✅ Test boshlanish vaqti yangilandi: {start_time_str}")
            
        except Exception as e:
            logger.error(f"Vaqt yangilash xatosi: {e}")
            await update.message.reply_text(f"❌ Xatolik: {str(e)}")


async def process_time_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, start_time):
    """Vaqt tanlangandan keyin testni saqlash"""
    user_id = update.effective_user.id
    
    # Vaqtni tekshirish (o'tmish bo'lmasligi kerak)
    now_uz = datetime.now(UZBEKISTAN_TZ)
    if start_time < now_uz:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "❌ Test boshlanish vaqti o'tmish bo'lishi mumkin emas!\n\n"
                f"Hozirgi vaqt: {now_uz.strftime('%d.%m.%Y %H:%M')}\n"
                "Qayta tanlang:"
            )
        else:
            await update.message.reply_text(
                "❌ Test boshlanish vaqti o'tmish bo'lishi mumkin emas!\n\n"
                f"Hozirgi vaqt: {now_uz.strftime('%d.%m.%Y %H:%M')}"
            )
        return
    
    # Testni saqlash
    data = load_data()
    test_id = f"test_{len(data['tests']) + 1}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    test_data = {
        'name': context.user_data['test_name'],
        'questions': context.user_data['test_questions'],
        'created_by': user_id,
        'created_at': datetime.now(UZBEKISTAN_TZ).isoformat(),
        'start_time': start_time.isoformat()
    }
    # Agar fayl yuklangan bo'lsa, faylni test ID bilan qayta nomlash
    if 'test_file_path' in context.user_data:
        old_file_path = context.user_data['test_file_path']
        test_files_dir = "test_files"
        file_name = context.user_data.get('test_file_name', 'test.txt')
        # Fayl kengaytmasini saqlash
        file_ext = os.path.splitext(file_name)[1] or '.txt'
        new_file_path = os.path.join(test_files_dir, f"{test_id}{file_ext}")
        
        # Faylni qayta nomlash
        if os.path.exists(old_file_path):
            os.rename(old_file_path, new_file_path)
            test_data['file_path'] = new_file_path
        else:
            test_data['file_path'] = old_file_path
        test_data['file_name'] = file_name
    data['tests'][test_id] = test_data
    save_data(data)
    
    test_name = context.user_data.get('test_name', 'Noma\'lum')
    test_questions = context.user_data.get('test_questions', [])
    
    # Test post yaratish va yuborish
    # Bot username ni olish
    try:
        bot_info = await context.bot.get_me()
        bot_username = f"@{bot_info.username}" if bot_info.username else "Test Bot"
    except:
        bot_username = "Test Bot"
    
    post_text, reply_markup = generate_test_post(test_data, test_id, bot_username)
    
    start_time_str = start_time.strftime('%d.%m.%Y %H:%M')
    
    # Xabar yuborish
    if update.callback_query:
        await update.callback_query.edit_message_text(
            f"✅ Test muvaffaqiyatli yaratildi!\n\n"
            f"Test ID: {test_id}\n"
            f"Test nomi: {test_name}\n"
            f"Savollar soni: {len(test_questions)}\n"
            f"Boshlanish vaqti: {start_time_str}"
        )
        await update.callback_query.message.reply_text(
            post_text,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            post_text,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    # Test yaratildi xabari
    if update.callback_query:
        await update.callback_query.message.reply_text(
            f"✅ Test muvaffaqiyatli yaratildi!\n\n"
            f"Test ID: {test_id}\n"
            f"Test nomi: {test_name}\n"
            f"Savollar soni: {len(test_questions)}\n"
            f"Boshlanish vaqti: {start_time_str}"
        )
    else:
        await update.message.reply_text(
            f"✅ Test muvaffaqiyatli yaratildi!\n\n"
            f"Test ID: {test_id}\n"
            f"Test nomi: {test_name}\n"
            f"Savollar soni: {len(test_questions)}\n"
            f"Boshlanish vaqti: {start_time_str}"
        )
    
    context.user_data.clear()


async def process_test_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test yaratish jarayonini qayta ishlash"""
    if not context.user_data.get('creating_test'):
        return
    
    if not update.message or not update.message.text:
        return
    
    user_id = update.effective_user.id
    step = context.user_data.get('test_creation_step', 'name')
    
    if step == 'name':
        # Test nomi kiritildi
        test_name = update.message.text.strip()
        if test_name == '/cancel':
            context.user_data.clear()
            await update.message.reply_text("❌ Test yaratish bekor qilindi.")
            return
        
        # Test nomini saqlash va keyingi bosqichga o'tish
        context.user_data['test_name'] = test_name
        context.user_data['test_creation_step'] = 'file'
        await update.message.reply_text("📄 Test faylini yuboring:")
        return
    
    elif step == 'text_answers':
        # 36-40 savollar uchun yozma javoblar kiritildi
        text_answers_input = update.message.text.strip()
        if text_answers_input == '/cancel':
            context.user_data.clear()
            await update.message.reply_text("❌ Test yaratish bekor qilindi.")
            return
        
        try:
            # Yozma javoblarni qatorlarga ajratish va qavs ichidagi matnlarni birlashtirish
            lines = text_answers_input.split('\n')
            text_answers = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Qavs ichidagi matnni topish va olib tashlash (alohida javob deb hisoblanmasligi uchun)
                # Qavs ichidagi matn javobning bir qismi bo'lib qoladi
                # Masalan: "Javob (qavs ichidagi)" -> "Javob (qavs ichidagi)" butun javob bo'ladi
                # Lekin qavs ichidagi matn alohida qator deb hisoblanmaydi
                
                # Agar qator qavs bilan boshlansa va tugasa, uni bitta javob deb hisoblaymiz
                # Lekin qavs ichidagi matn alohida javob emas, faqat tushuntirish
                text_answers.append(line)
            
            # 36-40 savollar uchun 5 ta javob kerak
            if len(text_answers) != 5:
                await update.message.reply_text(
                    f"❌ Yozma javoblar soni noto'g'ri!\n\n"
                    f"36-40 savollar uchun 5 ta javob kerak.\n"
                    f"Hozirgi son: {len(text_answers)} ta\n\n"
                    f"Har bir savol uchun alohida qatorda javob yozing.\n"
                    f"Qavs ichida tushuntirish yozishingiz mumkin:\n"
                    f"Masalan:\n"
                    f"Javob 36-savolga (tushuntirish)\n"
                    f"Javob 37-savolga\n"
                    f"Javob 38-savolga (qavs ichidagi matn)\n"
                    f"Javob 39-savolga\n"
                    f"Javob 40-savolga"
                )
                return
            
            # Yozma javoblarni saqlash
            context.user_data['text_answers'] = text_answers
            
            # Savollarni yaratish
            questions = []
            # Avval 1-35 savollar uchun ko'p tanlov savollarini yaratish
            mc_answers = context.user_data.get('mc_answers', [])
            for idx, answer in enumerate(mc_answers):
                # 33, 34, 35-savollar uchun 6 ta variant, boshqalar uchun 4 ta
                if idx in [32, 33, 34]:  # 33, 34, 35-savollar (0-based index: 32, 33, 34)
                    options = ['a', 'b', 'c', 'd', 'e', 'f']
                    questions.append({
                        'question': f"Savol {idx + 1}",
                        'options': options,
                        'correct': answer
                    })
                else:
                    options = ['a', 'b', 'c', 'd']
                    questions.append({
                        'question': f"Savol {idx + 1}",
                        'options': options,
                        'correct': answer
                    })
            
            # 36-40 savollar uchun yozma javob savollarini yaratish
            for idx, answer in enumerate(text_answers):
                question_idx = 35 + idx  # 36, 37, 38, 39, 40-savollar (0-based: 35, 36, 37, 38, 39)
                questions.append({
                    'question': f"Savol {question_idx + 1}",
                    'type': 'text_answer',  # Yozma javob turi
                    'options': [],  # Variantlar yo'q
                    'correct': answer  # To'g'ri javob (qo'lda tekshirish uchun)
                })
            
            # Javoblarni saqlash va vaqt belgilash bosqichiga o'tish
            context.user_data['test_questions'] = questions
            context.user_data['test_creation_step'] = 'start_time'
            
            # Hozirgi vaqtni ko'rsatish (O'zbekiston vaqti)
            now_uz = datetime.now(UZBEKISTAN_TZ)
            current_time = now_uz.strftime('%d.%m.%Y %H:%M')
            
            # Inline keyboard yaratish - tez variantlar
            keyboard = [
                [InlineKeyboardButton("⚡ Hozir", callback_data="time_now")],
                [
                    InlineKeyboardButton("15 min", callback_data="time_15m"),
                    InlineKeyboardButton("30 min", callback_data="time_30m"),
                    InlineKeyboardButton("1 soat", callback_data="time_1h")
                ],
                [InlineKeyboardButton("📝 Boshqa vaqt kiritish", callback_data="time_custom")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ Barcha javoblar saqlandi!\n\n"
                f"📅 Test boshlanish vaqtini belgilang:\n\n"
                f"🕐 Hozirgi vaqt: {current_time}\n\n"
                f"Quyidagi variantlardan birini tanlang:",
                reply_markup=reply_markup
            )
            return
        
        except Exception as e:
            logger.error(f"Yozma javoblar qayta ishlash xatosi: {e}")
            await update.message.reply_text(f"❌ Xatolik: {str(e)}")
    
    elif step == 'answers':
        # Javoblar kiritildi (1a2b3c4d... yoki 1a2b3b4b5b6a...36(36savoluchun yozmajavob)(37savoluchunyozma javob)...)
        answers_text = update.message.text.strip()
        if answers_text.lower() == '/cancel':
            context.user_data.clear()
            await update.message.reply_text("❌ Test yaratish bekor qilindi.")
            return
        
        try:
            # Parser: barcha javoblarni bir qatorda qabul qilish
            mc_answers = {}  # {question_num: answer}
            text_answers = {}  # {question_num: answer}
            
            # 1. Raqam + harf kombinatsiyalarini topish (1a, 2b, 10c, ...)
            pattern = r'(\d+)([a-fA-F])'
            matches = re.findall(pattern, answers_text)
            for num_str, letter in matches:
                q_num = int(num_str)
                if q_num <= 35:
                    mc_answers[q_num] = letter.lower()
                elif q_num > 40:
                    # 41+ savollar uchun ham variant javoblar bo'lishi mumkin
                    mc_answers[q_num] = letter.lower()
            
            # 2. Qavs ichidagi matnlarni topish - ketma-ketlikda
            # Format: raqam(qavs ichidagi matn) yoki (qavs ichidagi matn)
            paren_positions = []
            for match in re.finditer(r'(\d+)?\(([^)]+)\)', answers_text):
                num_str = match.group(1)
                content = match.group(2)
                paren_positions.append((match.start(), num_str, content))
            
            # Qavslarni ketma-ketlikda qayta ishlash
            next_text_q = 36  # Keyingi yozma javob savol raqami
            for pos, num_str, content in paren_positions:
                # Faqat raqamlar bo'lgan qavslarni e'tiborsiz qoldirish
                if content.strip().isdigit():
                    continue
                
                # Agar qavs oldida raqam bo'lsa, o'sha raqam savol raqami
                if num_str:
                    q_num = int(num_str)
                    if 36 <= q_num <= 40:
                        text_answers[q_num] = content.strip()
                        if q_num >= next_text_q:
                            next_text_q = q_num + 1
                else:
                    # Agar qavs oldida raqam bo'lmasa, qavs ichidagi matnda savol raqamini qidirish
                    # Masalan: "36savoluchun yozmajavob" -> 36
                    content_num_match = re.search(r'^(\d+)', content.strip())
                    if content_num_match:
                        q_num = int(content_num_match.group(1))
                        if 36 <= q_num <= 40:
                            text_answers[q_num] = content.strip()
                            if q_num >= next_text_q:
                                next_text_q = q_num + 1
                    else:
                        # Agar qavs ichida ham raqam bo'lmasa, ketma-ketlikda 36, 37, 38, 39, 40 deb hisoblaymiz
                        if next_text_q <= 40:
                            text_answers[next_text_q] = content.strip()
                            next_text_q += 1
            
            # 1-35 savollar uchun javoblarni tekshirish
            REQUIRED_MC_ANSWERS = 35
            if len(mc_answers) < REQUIRED_MC_ANSWERS:
                # Eski formatni qo'llab-quvvatlash: faqat harflar (abc...)
                # Agar raqam+harf formatida yetarli javob bo'lmasa, eski formatni sinab ko'ramiz
                if len(mc_answers) == 0:
                    # Eski format: faqat harflar
                    answers_text_lower = answers_text.lower()
                    answers = []
                    for char in answers_text_lower:
                        char_lower = char.lower()
                        question_idx = len(answers)
                        if question_idx >= 35:
                            break
                        if question_idx in [32, 33, 34]:  # 33, 34, 35-savollar
                            if char_lower in 'abcdef':
                                answers.append(char_lower)
                        else:
                            if char_lower in 'abcd':
                                answers.append(char_lower)
                    
                    if len(answers) == REQUIRED_MC_ANSWERS:
                        # Eski format ishladi
                        mc_answers = {i+1: answers[i] for i in range(len(answers))}
                    else:
                        await update.message.reply_text(
                            f"❌ Javoblar soni noto'g'ri!\n\n"
                            f"⚠️ 1-35 savollar uchun {REQUIRED_MC_ANSWERS} ta javob kerak.\n"
                            f"🔢 Hozirgi son: {len(answers)} ta\n\n"
                            f"Format: 1a2b3c4d... yoki abc... (35 ta javob)\n"
                            f"⚠️ 33, 34, 35-savollar uchun e va f javoblar ham mumkin!"
                        )
                        return
                else:
                    await update.message.reply_text(
                        f"❌ Javoblar soni noto'g'ri!\n\n"
                        f"⚠️ 1-35 savollar uchun {REQUIRED_MC_ANSWERS} ta javob kerak.\n"
                        f"🔢 Hozirgi son: {len(mc_answers)} ta\n\n"
                        f"Format: 1a2b3c4d... yoki abc... (35 ta javob)\n"
                        f"⚠️ 33, 34, 35-savollar uchun e va f javoblar ham mumkin!"
                    )
                    return
            
            # 1-35 savollar uchun javoblarni listga o'tkazish (tartibda)
            mc_answers_list = []
            for q_num in range(1, 36):
                if q_num in mc_answers:
                    mc_answers_list.append(mc_answers[q_num])
                else:
                    await update.message.reply_text(
                        f"❌ {q_num}-savol uchun javob topilmadi!\n\n"
                        f"Barcha 1-35 savollar uchun javoblar kerak.\n"
                        f"Format: 1a2b3c4d... yoki abc... (35 ta javob)"
                    )
                    return
            
            # 36-40 savollar uchun yozma javoblarni tekshirish (IXTIYORIY)
            # Agar kiritilgan bo'lsa, faqat kiritilganlarni saqlash
            # Agar kiritilmagan bo'lsa (0 ta), avtomatik ravishda vaqt belgilashga o'tish
            
            if len(text_answers) == 0:
                # Hech qanday yozma javob kiritilmagan - bu normal, davom etamiz
                # 36-40 savollar yo'q deb hisoblaymiz
                context.user_data['mc_answers'] = mc_answers_list
                context.user_data['test_creation_step'] = 'start_time'
                
                # Hozirgi vaqtni ko'rsatish
                now_uz = datetime.now(UZBEKISTAN_TZ)
                current_time = now_uz.strftime('%d.%m.%Y %H:%M')
                
                keyboard = [
                    [InlineKeyboardButton("⚡ Hozir", callback_data="time_now")],
                    [
                        InlineKeyboardButton("15 min", callback_data="time_15m"),
                        InlineKeyboardButton("30 min", callback_data="time_30m"),
                        InlineKeyboardButton("1 soat", callback_data="time_1h")
                    ],
                    [InlineKeyboardButton("📝 Boshqa vaqt kiritish", callback_data="time_custom")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"✅ 1-35 savollar uchun javoblar qabul qilindi!\n\n"
                    f"ℹ️ 36-40 savollar uchun yozma javoblar kiritilmadi (bu normal).\n\n"
                    f"📅 Test boshlanish vaqtini belgilang:\n\n"
                    f"🕐 Hozirgi vaqt: {current_time}\n\n"
                    f"Quyidagi variantlardan birini tanlang:",
                    reply_markup=reply_markup
                )
                return
            elif len(text_answers) < 5:
                # Ba'zi yozma javoblar kiritilgan, lekin barcha emas
                # Qolgan javoblarni so'rash (lekin MAJBURIY emas)
                context.user_data['test_creation_step'] = 'text_answers'
                context.user_data['mc_answers'] = mc_answers_list
                
                missing = [q for q in range(36, 41) if q not in text_answers]
                if missing:
                    keyboard = [
                        [InlineKeyboardButton("⏭️ Qolgan javoblarni o'tkazib yuborish", callback_data="skip_text_answers")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        f"✅ 1-35 savollar uchun javoblar qabul qilindi!\n\n"
                        f"📝 36-40 savollar uchun yozma javoblarni kiriting:\n\n"
                        f"⚠️ Quyidagi savollar uchun javoblar kerak: {', '.join(map(str, missing))}\n\n"
                        f"Har bir savol uchun alohida qatorda javob yozing yoki qavs ichida kiriting:\n"
                        f"Masalan:\n"
                        f"38savol javobi\n"
                        f"39savol javobi\n\n"
                        f"📌 Yoki qolgan javoblarni o'tkazib yuborishingiz mumkin:",
                        reply_markup=reply_markup
                    )
                    return
            else:
                # Barcha 5 ta yozma javob kiritilgan
                text_answers_list = []
                for q_num in range(36, 41):
                    if q_num in text_answers:
                        text_answers_list.append(text_answers[q_num])
                
                # Barcha javoblar mavjud, keyingi bosqichga o'tish
                context.user_data['mc_answers'] = mc_answers_list
                context.user_data['text_answers'] = text_answers_list
                context.user_data['test_creation_step'] = 'start_time'
                
                # Hozirgi vaqtni ko'rsatish (O'zbekiston vaqti)
                now_uz = datetime.now(UZBEKISTAN_TZ)
                current_time = now_uz.strftime('%d.%m.%Y %H:%M')
                
                # Inline keyboard yaratish - tez variantlar
                keyboard = [
                    [InlineKeyboardButton("⚡ Hozir", callback_data="time_now")],
                    [
                        InlineKeyboardButton("15 min", callback_data="time_15m"),
                        InlineKeyboardButton("30 min", callback_data="time_30m"),
                        InlineKeyboardButton("1 soat", callback_data="time_1h")
                    ],
                    [InlineKeyboardButton("📝 Boshqa vaqt kiritish", callback_data="time_custom")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"✅ Barcha javoblar saqlandi!\n\n"
                    f"📅 Test boshlanish vaqtini belgilang:\n\n"
                    f"🕐 Hozirgi vaqt: {current_time}\n\n"
                    f"Quyidagi variantlardan birini tanlang:",
                    reply_markup=reply_markup
                )
                return
        
        except Exception as e:
            logger.error(f"Javoblar qayta ishlash xatosi: {e}")
            await update.message.reply_text(f"❌ Xatolik: {str(e)}")
    elif step == 'start_time':
        # Test boshlanish vaqti kiritildi (faqat custom vaqt kiritganda)
        time_input = update.message.text.strip().lower()
        if time_input == '/cancel':
            context.user_data.clear()
            await update.message.reply_text("❌ Test yaratish bekor qilindi.")
            return
        
        try:
            now_uz = datetime.now(UZBEKISTAN_TZ)
            start_time = None
            
            # Sodda formatlar
            if time_input == 'hozir' or time_input == 'now':
                start_time = now_uz
            elif time_input.endswith('m') or time_input.endswith('min'):
                # Daqiqalar: "15m", "30min" kabi
                try:
                    minutes = int(time_input.rstrip('min').rstrip('m').strip())
                    start_time = now_uz + timedelta(minutes=minutes)
                except ValueError:
                    pass
            elif time_input.endswith('h') or time_input.endswith('soat'):
                # Soatlar: "1h", "2soat" kabi
                try:
                    hours = int(time_input.rstrip('soat').rstrip('h').strip())
                    start_time = now_uz + timedelta(hours=hours)
                except ValueError:
                    pass
            elif ':' in time_input:
                # Faqat vaqt formatida (HH:MM) - bugungi kunda
                try:
                    hour, minute = map(int, time_input.split(':'))
                    today = now_uz.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    # Agar bu vaqt o'tmish bo'lsa, ertaga qo'yamiz
                    if today <= now_uz:
                        today = today + timedelta(days=1)
                    start_time = today
                except ValueError:
                    pass
            elif ' ' in time_input:
                # Eski format (MM-DD HH:MM)
                try:
                    time_parts = time_input.split()
                    if len(time_parts) == 2:
                        date_part = time_parts[0]  # MM-DD
                        time_part = time_parts[1]  # HH:MM
                        
                        month, day = map(int, date_part.split('-'))
                        hour, minute = map(int, time_part.split(':'))
                        
                        year = now_uz.year
                        start_time = datetime(year, month, day, hour, minute)
                        start_time = UZBEKISTAN_TZ.localize(start_time)
                        
                        # Agar o'tmish bo'lsa, keyingi yilga o'tkazish
                        if start_time < now_uz:
                            start_time = datetime(year + 1, month, day, hour, minute)
                            start_time = UZBEKISTAN_TZ.localize(start_time)
                except (ValueError, IndexError):
                    pass
            
            if start_time is None:
                await update.message.reply_text(
                    "❌ Noto'g'ri format!\n\n"
                    "✅ Qulay variantlar:\n"
                    "• \"hozir\" - darhol\n"
                    "• \"15m\" yoki \"15 min\" - 15 daqiqadan keyin\n"
                    "• \"1h\" yoki \"1 soat\" - 1 soatdan keyin\n"
                    "• \"14:30\" - bugungi kunda 14:30 da\n"
                    "• \"12-25 14:30\" - eski format (oy-kun soat:daqiqa)\n\n"
                    "Yoki /cancel ni bosing."
                )
                return
            
            # Vaqtni tekshirish (o'tmish bo'lmasligi kerak)
            now_uz = datetime.now(UZBEKISTAN_TZ)
            if start_time < now_uz:
                await update.message.reply_text(
                    "❌ Test boshlanish vaqti o'tmish bo'lishi mumkin emas!\n\n"
                    f"Hozirgi vaqt: {now_uz.strftime('%d.%m.%Y %H:%M')}\n"
                    "Qayta kiriting:"
                )
                return
            
            # Testni saqlash
            await process_time_selection(update, context, start_time)
            
        except Exception as e:
            logger.error(f"Javoblar qayta ishlash xatosi: {e}")
            await update.message.reply_text(f"❌ Xatolik: {str(e)}")


async def process_test_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test faylini qayta ishlash"""
    # Test yaratish yoki tahrirlash rejimida bo'lishi kerak
    is_creating = context.user_data.get('creating_test')
    is_editing = context.user_data.get('editing_test')
    
    if not is_creating and not is_editing:
        return
    
    step = context.user_data.get('test_creation_step') or context.user_data.get('test_editing_step')
    if step != 'file':
        return
    
    try:
        user_id = update.effective_user.id
        
        # Faylni yuklash
        document = update.message.document
        if not document:
            await update.message.reply_text("❌ Fayl topilmadi. Qayta yuboring.")
            return
        
        file = await context.bot.get_file(document.file_id)
        
        # Fayl mazmunini o'qish
        file_content = await file.download_as_bytearray()
        text_content = file_content.decode('utf-8', errors='ignore')
        
        # Test faylini saqlash (savollarni avtomatik ajratmaslik)
        # Foydalanuvchi o'zi test faylini yuboradi, savollar sonini avtomatik aniqlashga harakat qilmaymiz
        # Faylni saqlash
        test_files_dir = "test_files"
        os.makedirs(test_files_dir, exist_ok=True)
        
        # Vaqtinchalik fayl nomi
        temp_file_name = f"temp_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        file_ext = os.path.splitext(document.file_name or 'test.txt')[1] or '.txt'
        temp_file_path = os.path.join(test_files_dir, f"{temp_file_name}{file_ext}")
        
        # Faylni diskga saqlash
        with open(temp_file_path, 'wb') as f:
            f.write(file_content)
        
        # Fayl ma'lumotlarini saqlash
        context.user_data['test_file_path'] = temp_file_path
        context.user_data['test_file_name'] = document.file_name or 'test.txt'
        
        # Savollarni avtomatik ajratmaslik - foydalanuvchi javoblarni kiritadi
        # Savollar sonini avtomatik aniqlashga harakat qilmaymiz
        
        # Agar tahrirlash rejimida bo'lsa
        if is_editing:
            test_id = context.user_data.get('editing_test_id')
            data = load_data()
            if test_id and test_id in data['tests']:
                # Eski faylni o'chirish (agar mavjud bo'lsa)
                old_file_path = data['tests'][test_id].get('file_path')
                if old_file_path and os.path.exists(old_file_path):
                    try:
                        os.remove(old_file_path)
                    except:
                        pass
                
                # Yangi faylni saqlash
                test_files_dir = "test_files"
                os.makedirs(test_files_dir, exist_ok=True)
                file_name = document.file_name or "test.txt"
                file_ext = os.path.splitext(file_name)[1] or '.txt'
                new_file_path = os.path.join(test_files_dir, f"{test_id}{file_ext}")
                
                # Faylni diskga saqlash
                with open(new_file_path, 'wb') as f:
                    f.write(file_content)
                
                # Testni yangilash (savollarni o'zgartirmaslik, faqat faylni yangilash)
                data['tests'][test_id]['file_path'] = new_file_path
                data['tests'][test_id]['file_name'] = file_name
                save_data(data)
                
                context.user_data.pop('editing_test', None)
                context.user_data.pop('editing_test_id', None)
                context.user_data.pop('test_editing_step', None)
                await update.message.reply_text("✅ Test fayli yangilandi!\n\nJavoblarni yangilash uchun testni qayta tahrirlang.")
                return
        
        # Test yaratish rejimi
        # Faylni doimiy saqlash
        test_files_dir = "test_files"
        os.makedirs(test_files_dir, exist_ok=True)
        
        file_name = document.file_name or "test.txt"
        # Fayl nomini test ID bilan biriktirish uchun vaqtinchalik saqlash
        temp_file_path = os.path.join(test_files_dir, f"temp_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file_name}")
        
        # Faylni diskka yuklash
        await file.download_to_drive(temp_file_path)
        
        # Fayl yo'lini saqlash
        context.user_data['test_file_path'] = temp_file_path
        context.user_data['test_file_name'] = file_name
        context.user_data['test_creation_step'] = 'answers'
        
        # Javoblar kiritishni so'rash (1-35 savollar uchun ko'p tanlov, 36-40 uchun yozma javob)
        await update.message.reply_text(
            "✅ Fayl yuklandi!\n\n"
            "📝 Avval 1-35 savollar uchun javoblarni kiriting:\n\n"
            "Format: 1a2b3c4d... yoki abc... (35 ta javob)\n\n"
            "⚠️ Javoblar soni aniq 35 ta bo'lishi kerak!\n"
            "ℹ️ 33, 34, 35-savollar uchun e va f javoblar ham mumkin!\n\n"
            "📝 Keyin 36-40 savollar uchun yozma javoblar so'raladi."
        )
        
    except Exception as e:
        logger.error(f"Fayl qayta ishlash xatosi: {e}")
        await update.message.reply_text(f"❌ Xatolik: {str(e)}")


async def list_tests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Testlar ro'yxati"""
    if not await check_subscription(update, context):
        return
    
    # Ism va familya tekshiruvi
    if not await check_user_name(update, context):
        await update.message.reply_text(
            "❌ Botdan foydalanish uchun ism va familyangizni kiriting.\n\n"
            "Iltimos, /start ni bosing va ism va familyangizni kiriting."
        )
        return
    
    data = load_data()
    if not data['tests']:
        await update.message.reply_text("❌ Hozircha testlar mavjud emas.")
        return
    
    user_id = update.effective_user.id
    is_boss = user_id == BOSS_ID
    is_admin = user_id in data["admins"]
    
    keyboard = []
    for test_id, test_data in data['tests'].items():
        # Test yaratgan foydalanuvchi yoki admin/boss bo'lsa, tahrirlash tugmasi qo'shish
        can_edit = (is_boss or is_admin) and test_data.get('created_by') == user_id
        
        if can_edit:
            # Test nomi va tahrirlash tugmasi
            keyboard.append([
                InlineKeyboardButton(
                    test_data['name'],
                    callback_data=f"start_test_{test_id}"
                ),
                InlineKeyboardButton(
                    "✏️ Tahrirlash",
                    callback_data=f"edit_test_{test_id}"
                )
            ])
        else:
            # Oddiy foydalanuvchilar uchun faqat test nomi
            keyboard.append([InlineKeyboardButton(
                test_data['name'],
                callback_data=f"start_test_{test_id}"
            )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📋 Mavjud testlar:", reply_markup=reply_markup)


async def edit_test(update: Update, context: ContextTypes.DEFAULT_TYPE, test_id: str):
    """Testni tahrirlash"""
    user_id = update.effective_user.id
    data = load_data()
    
    if test_id not in data['tests']:
        if update.callback_query:
            await update.callback_query.answer("❌ Test topilmadi!")
        return
    
    test = data['tests'][test_id]
    
    # Faqat test yaratgan foydalanuvchi yoki boss tahrirlashi mumkin
    if user_id != BOSS_ID and test.get('created_by') != user_id:
        if update.callback_query:
            await update.callback_query.answer("❌ Bu testni tahrirlash huquqingiz yo'q!")
        return
    
    # Test tahrirlash rejimini boshlash
    context.user_data['editing_test'] = True
    context.user_data['editing_test_id'] = test_id
    context.user_data['test_editing_step'] = 'name'
    
    keyboard = [
        [InlineKeyboardButton("📝 Test nomini o'zgartirish", callback_data=f"edit_name_{test_id}")],
        [InlineKeyboardButton("📄 Test faylini qayta yuklash", callback_data=f"edit_file_{test_id}")],
        [InlineKeyboardButton("✅ Javoblarni o'zgartirish", callback_data=f"edit_answers_{test_id}")],
        [InlineKeyboardButton("📅 Boshlanish vaqtini o'zgartirish", callback_data=f"edit_start_time_{test_id}")],
        [InlineKeyboardButton("📊 Testni natijalash", callback_data=f"finalize_test_{test_id}")],
        [InlineKeyboardButton("📋 0-1 Matrix yuklab olish", callback_data=f"download_matrix_{test_id}")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_edit")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"✏️ Test tahrirlash: {test['name']}\n\n"
    text += f"Savollar soni: {len(test['questions'])}\n\n"
    text += "Nimani tahrirlamoqchisiz?"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)


async def start_test(update: Update, context: ContextTypes.DEFAULT_TYPE, test_id: str):
    """Testni boshlash"""
    if not await check_subscription(update, context):
        return
    
    data = load_data()
    if test_id not in data['tests']:
        if update.callback_query:
            await update.callback_query.answer("❌ Test topilmadi!")
        else:
            await update.message.reply_text("❌ Test topilmadi!")
        return
    
    test = data['tests'][test_id]
    user_id = update.effective_user.id
    
    # Foydalanuvchi bu testni allaqachon ishlaganligini tekshirish
    user_results = data.get('user_results', {})
    for r_id, result in user_results.items():
        if result.get('user_id') == user_id and result.get('test_id') == test_id:
            # Foydalanuvchi bu testni allaqachon ishlagan
            error_text = "❌ Siz bu testni allaqachon ishlagansiz!\n\nHar bir testni faqat bir marta ishlash mumkin."
            if update.callback_query:
                await update.callback_query.answer(error_text, show_alert=True)
            else:
                await update.message.reply_text(error_text)
            return
    
    # Test boshlanish vaqtini tekshirish
    if 'start_time' in test:
        try:
            start_time = datetime.fromisoformat(test['start_time'])
            if start_time.tzinfo is None:
                start_time = UZBEKISTAN_TZ.localize(start_time)
            
            now_uz = datetime.now(UZBEKISTAN_TZ)
            if start_time > now_uz:
                # Test hali boshlanmagan
                start_time_str = start_time.strftime('%m-%d %H:%M')
                now_str = now_uz.strftime('%m-%d %H:%M')
                error_text = (
                    f"⏰ Test hali boshlanmagan!\n\n"
                    f"Test boshlanish vaqti: {start_time_str}\n"
                    f"Hozirgi vaqt: {now_str}\n\n"
                    f"Iltimos, test boshlanish vaqtini kuting."
                )
                if update.callback_query:
                    await update.callback_query.answer(error_text, show_alert=True)
                else:
                    await update.message.reply_text(error_text)
                return
        except Exception as e:
            logger.error(f"Vaqt tekshirish xatosi: {e}")
            # Vaqt tekshirishda xatolik bo'lsa, testni ishlatishga ruxsat beramiz
    
    # Testni boshlash
    context.user_data[f'test_{test_id}'] = {
        'test_id': test_id,
        'answers': {},
        'started_at': datetime.now().isoformat(),
        'waiting_answers': True
    }
    
    # Agar test fayli mavjud bo'lsa, uni yuborish
    if 'file_path' in test and os.path.exists(test['file_path']):
        try:
            # Faylni yuborish
            file_name = test.get('file_name', 'test.txt')
            if update.callback_query:
                await update.callback_query.edit_message_text(f"📝 {test['name']}\n\nTest fayli yuborilmoqda...")
                with open(test['file_path'], 'rb') as f:
                    await update.callback_query.message.reply_document(
                        document=f,
                        filename=file_name
                    )
                # 36-40 savollar mavjudligini tekshirish
                has_text_questions = any(
                    q.get('type') == 'text_answer' 
                    for q in test['questions']
                )
                instruction_text = "✅ Test fayli yuborildi!\n\n"
                if has_text_questions:
                    instruction_text += "📝 1-35 savollar uchun javoblarni kiriting: 1a2b3c4d...\n"
                    instruction_text += "⚠️ 36-40 savollar uchun keyinroq yozma javoblar so'raladi."
                else:
                    instruction_text += "Javoblarni kiriting: 1a2b3c4d..."
                await update.callback_query.message.reply_text(instruction_text)
            else:
                await update.message.reply_text(f"📝 {test['name']}")
                with open(test['file_path'], 'rb') as f:
                    await update.message.reply_document(
                        document=f,
                        filename=file_name
                    )
                # 36-40 savollar mavjudligini tekshirish
                has_text_questions = any(
                    q.get('type') == 'text_answer' 
                    for q in test['questions']
                )
                instruction_text = "✅ Test fayli yuborildi!\n\n"
                if has_text_questions:
                    instruction_text += "📝 1-35 savollar uchun javoblarni kiriting: 1a2b3c4d...\n"
                    instruction_text += "⚠️ 36-40 savollar uchun keyinroq yozma javoblar so'raladi."
                else:
                    instruction_text += "Javoblarni kiriting: 1a2b3c4d..."
                await update.message.reply_text(instruction_text)
        except Exception as e:
            logger.error(f"Fayl yuborish xatosi: {e}")
            # Agar fayl yuborib bo'lmasa, oddiy matn ko'rsatish
            text = f"📝 {test['name']}\n\n"
            has_text_questions = False
            for idx, question in enumerate(test['questions'], 1):
                text += f"{idx}. {question['question']}\n"
                if question.get('type') == 'text_answer':
                    text += "   (Yozma javob)\n"
                    has_text_questions = True
                else:
                    for opt_idx, option in enumerate(question['options']):
                        letter = chr(97 + opt_idx)  # a, b, c, d
                        text += f"   {letter}) {option}\n"
                text += "\n"
            if has_text_questions:
                text += "📝 1-35 savollar uchun javoblarni kiriting: 1a2b3c4d...\n"
                text += "⚠️ 36-40 savollar uchun keyinroq yozma javoblar so'raladi."
            else:
                text += "Javoblarni kiriting: 1a2b3c4d..."
            
            if update.callback_query:
                await update.callback_query.edit_message_text(text)
            else:
                await update.message.reply_text(text)
    else:
        # Agar fayl mavjud bo'lmasa, oddiy matn ko'rsatish
        text = f"📝 {test['name']}\n\n"
        has_text_questions = False
        for idx, question in enumerate(test['questions'], 1):
            text += f"{idx}. {question['question']}\n"
            if question.get('type') == 'text_answer':
                text += "   (Yozma javob)\n"
                has_text_questions = True
            else:
                for opt_idx, option in enumerate(question['options']):
                    letter = chr(97 + opt_idx)  # a, b, c, d
                    text += f"   {letter}) {option}\n"
            text += "\n"
        
        if has_text_questions:
            text += "📝 1-35 savollar uchun javoblarni kiriting: 1a2b3c4d...\n"
            text += "⚠️ 36-40 savollar uchun keyinroq yozma javoblar so'raladi."
        else:
            text += "Javoblarni kiriting: 1a2b3c4d..."
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)


async def process_test_answers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test javoblarini qayta ishlash (1a2b3c4d... formatida va yozma javoblar)"""
    if not update.message or not update.message.text:
        return False
    
    # Qaysi test uchun javob kiritilayotganini topish
    test_data_key = None
    test_id = None
    for key in context.user_data.keys():
        if key.startswith('test_'):
            test_data = context.user_data[key]
            # Faqat dictionary bo'lsa va 'waiting_answers' mavjud bo'lsa
            if isinstance(test_data, dict) and test_data.get('waiting_answers'):
                test_data_key = key
                test_id = test_data.get('test_id')
                break
    
    if not test_data_key or not test_id:
        return False  # Test ishlash rejimida emas
    
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    data = load_data()
    if test_id not in data['tests']:
        await update.message.reply_text("❌ Test topilmadi!")
        return False
    
    test = data['tests'][test_id]
    
    # Yozma javoblar kiritilayotganini tekshirish (36-40 savollar uchun)
    waiting_text_answers = context.user_data[test_data_key].get('waiting_text_answers', False)
    
    if waiting_text_answers:
        # Yozma javoblar kiritilmoqda (36-40 savollar)
        # Javoblarni qatorlarga ajratish (har bir qator bitta savol uchun)
        # Qavs ichidagi matn alohida javob deb hisoblanmaydi
        lines = text.split('\n')
        text_answers = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Qavs ichidagi matn javobning bir qismi bo'lib qoladi, alohida javob emas
            text_answers.append(line)
        
        # 36-40 savollar uchun 5 ta javob kerak
        text_question_indices = [35, 36, 37, 38, 39]  # 0-based index
        
        if len(text_answers) != len(text_question_indices):
            await update.message.reply_text(
                f"❌ Yozma javoblar soni noto'g'ri!\n\n"
                f"36-40 savollar uchun {len(text_question_indices)} ta javob kerak.\n"
                f"Hozirgi son: {len(text_answers)} ta\n\n"
                f"Har bir savol uchun alohida qatorda javob yozing.\n"
                f"Qavs ichida tushuntirish yozishingiz mumkin:\n"
                f"Masalan:\n"
                f"Javob 36-savolga (tushuntirish)\n"
                f"Javob 37-savolga\n"
                f"Javob 38-savolga (qavs ichidagi matn)\n"
                f"Javob 39-savolga\n"
                f"Javob 40-savolga"
            )
            return True
        
        # Yozma javoblarni saqlash
        for idx, answer in enumerate(text_answers):
            question_idx = text_question_indices[idx]
            context.user_data[test_data_key]['answers'][str(question_idx)] = answer
        
        # Testni yakunlash
        context.user_data[test_data_key]['waiting_answers'] = False
        context.user_data[test_data_key]['waiting_text_answers'] = False
        await finish_test(update, context, test_id)
        return True
    
    else:
        # Ko'p tanlov javoblari kiritilmoqda (1-35 savollar)
        text_lower = text.lower()
        
        # 36-40 savollar mavjudligini tekshirish
        has_text_questions = any(
            q.get('type') == 'text_answer' 
            for q in test['questions']
        )
        
        # Javoblarni ajratish (1a2b3c4d... yoki abc...)
        # Faqat 1-35 savollar uchun (0-based: 0-34)
        answers = []
        for char in text_lower:
            char_lower = char.lower()
            # Hozirgi savol indexini aniqlash (mavjud javoblar soni)
            question_idx = len(answers)
            
            # Faqat 1-35 savollar uchun javob qabul qilamiz (0-based: 0-34)
            if question_idx >= 35:
                break
            
            # 33, 34, 35-savollar (idx 32, 33, 34) uchun e va f ham qabul qilamiz
            if question_idx in [32, 33, 34]:  # 33, 34, 35-savollar
                if char_lower in 'abcdef':
                    answers.append(char_lower)
            else:
                # Boshqa savollar uchun faqat a-d qabul qilamiz
                if char_lower in 'abcd':
                    answers.append(char_lower)
        
        # 1-35 savollar uchun 35 ta javob kerak
        required_mc_answers = 35
        if len(answers) != required_mc_answers:
            await update.message.reply_text(
                f"❌ Javoblar soni noto'g'ri!\n"
                f"1-35 savollar uchun {required_mc_answers} ta javob kerak.\n"
                f"Hozirgi son: {len(answers)} ta\n\n"
                f"Qayta kiriting: 1a2b3c4d... formatida\n"
                f"⚠️ 33, 34, 35-savollar uchun e va f javoblar ham mumkin!"
            )
            return True
        
        # Ko'p tanlov javoblarini saqlash
        for idx, answer in enumerate(answers):
            context.user_data[test_data_key]['answers'][str(idx)] = answer
        
        # Agar 36-40 savollar mavjud bo'lsa, yozma javoblarni so'rash
        if has_text_questions:
            context.user_data[test_data_key]['waiting_text_answers'] = True
            await update.message.reply_text(
                "✅ 1-35 savollar uchun javoblar qabul qilindi!\n\n"
                "📝 Endi 36-40 savollar uchun yozma javoblarni kiriting:\n\n"
                "Har bir savol uchun alohida qatorda javob yozing.\n"
                "Qavs ichida tushuntirish yozishingiz mumkin (qavs ichidagi matn alohida javob deb hisoblanmaydi).\n\n"
                "Masalan:\n"
                "Javob 36-savolga (tushuntirish)\n"
                "Javob 37-savolga\n"
                "Javob 38-savolga (qavs ichidagi matn)\n"
                "Javob 39-savolga\n"
                "Javob 40-savolga"
            )
            return True
        else:
            # 36-40 savollar yo'q bo'lsa, testni yakunlash
            context.user_data[test_data_key]['waiting_answers'] = False
            await finish_test(update, context, test_id)
            return True


async def finish_test(update: Update, context: ContextTypes.DEFAULT_TYPE, test_id: str):
    """Testni yakunlash va natijalarni hisoblash"""
    test_data_key = f'test_{test_id}'
    if test_data_key not in context.user_data:
        return
    
    data = load_data()
    test = data['tests'][test_id]
    user_answers = context.user_data[test_data_key]['answers']
    user_id = update.effective_user.id
    
    # To'g'ri javoblar soni
    correct = 0
    total = len(test['questions'])
    results = []
    
    for idx, question in enumerate(test['questions']):
        user_answer = user_answers.get(str(idx), '')
        
        # Yozma javoblar uchun avtomatik baholash qilinmaydi (qo'lda tekshirish kerak)
        if question.get('type') == 'text_answer':
            # Yozma javoblar uchun is_correct None yoki False bo'ladi (qo'lda tekshirish uchun)
            is_correct = None  # Qo'lda tekshirish kerak
            results.append({
                'question': question['question'],
                'user_answer': user_answer,
                'correct_answer': question.get('correct', ''),
                'is_correct': is_correct,
                'type': 'text_answer'  # Yozma javob ekanligini belgilash
            })
        else:
            # Ko'p tanlov javoblari uchun avtomatik tekshirish
            is_correct = user_answer == question['correct']
            if is_correct:
                correct += 1
            results.append({
                'question': question['question'],
                'user_answer': user_answer,
                'correct_answer': question['correct'],
                'is_correct': is_correct
            })
    
    # Rasch model orqali hisoblash (natijalash uchun saqlash)
    score = calculate_rasch_score(results, test['questions'])
    
    # Natijalarni saqlash (lekin hozir ko'rsatmaymiz)
    result_id = f"result_{user_id}_{test_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    if 'user_results' not in data:
        data['user_results'] = {}
    data['user_results'][result_id] = {
        'user_id': user_id,
        'test_id': test_id,
        'test_name': test['name'],
        'correct': correct,
        'total': total,
        'percentage': (correct / total * 100) if total > 0 else 0,
        'rasch_score': score,
        'results': results,
        'completed_at': datetime.now().isoformat()
    }
    save_data(data)
    
    # 0-1 Matrix yaratish va yangilash
    from utils import generate_response_matrix
    matrix_file_path, _ = generate_response_matrix(test_id, data)
    if matrix_file_path:
        # Matrix faylini test ma'lumotlariga saqlash
        if 'matrix_file' not in test:
            test['matrix_file'] = matrix_file_path
            data['tests'][test_id] = test
            save_data(data)
    
    # Faqat "javobingiz qabul qilindi" deb yuborish
    # Natijalar testni natijalash tugmasi bosilguncha ko'rsatilmaydi
    text = "✅ Javobingiz qabul qilindi!\n\nTest natijalari o'qituvchi tomonidan e'lon qilingandan keyin ko'rsatiladi."
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await update.message.reply_text(text)
    
    # User data tozalash
    del context.user_data[test_data_key]


async def finalize_test(update: Update, context: ContextTypes.DEFAULT_TYPE, test_id: str):
    """Testni natijalash - barcha natijalarni to'plash va o'qituvchiga yuborish"""
    user_id = update.effective_user.id
    data = load_data()
    
    if test_id not in data['tests']:
        if update.callback_query:
            await update.callback_query.answer("❌ Test topilmadi!")
        return
    
    test = data['tests'][test_id]
    
    # Faqat test yaratgan foydalanuvchi yoki boss natijalashi mumkin
    if user_id != BOSS_ID and test.get('created_by') != user_id:
        if update.callback_query:
            await update.callback_query.answer("❌ Bu testni natijalash huquqingiz yo'q!")
        return
    
    # Barcha foydalanuvchi natijalarini to'plash
    all_results = [
        r for r_id, r in data.get('user_results', {}).items()
        if r.get('test_id') == test_id
    ]
    
    if not all_results:
        if update.callback_query:
            await update.callback_query.answer("❌ Bu test uchun hali natijalar yo'q!")
        return
    
    # Natijalarni tayyorlash
    teacher_id = test.get('created_by')
    
    # Barcha natijalarni Rasch modelida hisoblash va tartiblash
    finalized_results = []
    for result in all_results:
        finalized_results.append({
            'user_id': result['user_id'],
            'correct': result['correct'],
            'total': result['total'],
            'percentage': result['percentage'],
            'rasch_score': result.get('rasch_score', 0.0),
            'completed_at': result['completed_at']
        })
    
    # Rasch score bo'yicha tartiblash (yuqoridan pastga)
    finalized_results.sort(key=lambda x: x.get('rasch_score', 0), reverse=True)
    
    # Umumiy statistika
    total_students = len(finalized_results)
    avg_percentage = sum(r['percentage'] for r in finalized_results) / total_students if total_students > 0 else 0
    avg_rasch = sum(r['rasch_score'] for r in finalized_results) / total_students if total_students > 0 else 0
    
    # O'qituvchiga natijalar xabari
    text = f"📊 Test natijalari: {test['name']}\n\n"
    text += f"📈 Umumiy statistika:\n"
    text += f"   Jami ishtirokchilar: {total_students}\n"
    text += f"   O'rtacha foiz: {avg_percentage:.1f}%\n"
    text += f"   O'rtacha Rasch score: {avg_rasch:.2f}\n\n"
    text += f"📋 Natijalar (Rasch score bo'yicha):\n\n"
    
    for idx, result in enumerate(finalized_results[:20], 1):  # Top 20
        text += f"{idx}. Talabgor: {result['user_id']}\n"
        text += f"   {result['correct']}/{result['total']} ({result['percentage']:.1f}%) | Rasch: {result['rasch_score']:.2f}\n\n"
    
    if total_students > 20:
        text += f"... va yana {total_students - 20} ta natija\n"
    
    # PDF yaratish (barcha natijalar uchun)
    try:
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Test Natijalari - {test['name']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                h1 {{ color: #333; }}
                .info {{ background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>Test Natijalari: {test['name']}</h1>
            <div class="info">
                <p><strong>Test ID:</strong> {test_id}</p>
                <p><strong>Jami ishtirokchilar:</strong> {total_students}</p>
                <p><strong>O'rtacha foiz:</strong> {avg_percentage:.1f}%</p>
                <p><strong>O'rtacha Rasch Score:</strong> {avg_rasch:.2f}</p>
                <p><strong>Natijalash vaqti:</strong> {datetime.now(UZBEKISTAN_TZ).strftime('%Y-%m-%d %H:%M')}</p>
            </div>
            <h2>Barcha natijalar (Rasch score bo'yicha tartiblangan):</h2>
            <table>
                <tr>
                    <th>#</th>
                    <th>Talabgor</th>
                    <th>To'g'ri javoblar</th>
                    <th>Foiz</th>
                    <th>Rasch Score</th>
                    <th>Vaqt</th>
                </tr>
        """
        
        for idx, result in enumerate(finalized_results, 1):
            completed_time = datetime.fromisoformat(result['completed_at']).strftime('%Y-%m-%d %H:%M')
            html_content += f"""
                <tr>
                    <td>{idx}</td>
                    <td>{result['user_id']}</td>
                    <td>{result['correct']}/{result['total']}</td>
                    <td>{result['percentage']:.1f}%</td>
                    <td>{result['rasch_score']:.2f}</td>
                    <td>{completed_time}</td>
                </tr>
            """
        
        html_content += """
            </table>
        </body>
        </html>
        """
        
        # Fallback matnli ro'yxat (reportlab uchun)
        fallback_lines = [
            f"Test natijalari: {test['name']}",
            f"Test ID: {test_id}",
            f"Jami ishtirokchilar: {total_students}",
            f"O'rtacha foiz: {avg_percentage:.1f}%",
            f"O'rtacha Rasch score: {avg_rasch:.2f}",
            f"Natijalash vaqti: {datetime.now(UZBEKISTAN_TZ).strftime('%Y-%m-%d %H:%M')}",
            "",
            "Ishtirokchilar (Rasch score bo'yicha):"
        ]
        for idx, result in enumerate(finalized_results, 1):
            fallback_lines.append(
                f"{idx}. Talabgor: {result['user_id']} | "
                f"{result['correct']}/{result['total']} | "
                f"{result['percentage']:.1f}% | Rasch: {result.get('rasch_score', 0):.2f} | "
                f"Vaqt: {datetime.fromisoformat(result['completed_at']).strftime('%Y-%m-%d %H:%M')}"
            )
        
        # PDF yaratish
        pdf_file = generate_pdf(
            f"final_{test_id}",
            {
                'test_name': test['name'],
                'html_content': html_content,
                'fallback_title': f"Test natijalari - {test['name']}",
                'fallback_lines': fallback_lines
            }
        )
        
        # O'qituvchiga yuborish
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        
        if pdf_file:
            if update.callback_query:
                await update.callback_query.message.reply_document(
                    document=pdf_file,
                    filename=f"test_final_results_{test_id}.pdf"
                )
            else:
                await update.message.reply_document(
                    document=pdf_file,
                    filename=f"test_final_results_{test_id}.pdf"
                )
        
        # Testni testlar ro'yxatidan olib tashlash
        del data['tests'][test_id]
        save_data(data)
        
        # Test faylini o'chirish (ixtiyoriy)
        if 'file_path' in test and os.path.exists(test['file_path']):
            try:
                os.remove(test['file_path'])
            except:
                pass
        
        success_text = f"✅ Test muvaffaqiyatli natijalandi va testlar ro'yxatidan olib tashlandi!"
        if update.callback_query:
            await update.callback_query.message.reply_text(success_text)
        else:
            await update.message.reply_text(success_text)
        
    except Exception as e:
        logger.error(f"Test natijalash xatosi: {e}")
        error_text = f"❌ Xatolik: {str(e)}"
        if update.callback_query:
            await update.callback_query.answer(error_text, show_alert=True)
        else:
            await update.message.reply_text(error_text)


async def download_matrix(update: Update, context: ContextTypes.DEFAULT_TYPE, test_id: str):
    """0-1 Matrix yuklab olish"""
    user_id = update.effective_user.id
    data = load_data()
    
    if test_id not in data['tests']:
        if update.callback_query:
            await update.callback_query.answer("❌ Test topilmadi!")
        return
    
    test = data['tests'][test_id]
    
    # Faqat test yaratgan foydalanuvchi yoki boss yuklab olishi mumkin
    if user_id != BOSS_ID and test.get('created_by') != user_id:
        if update.callback_query:
            await update.callback_query.answer("❌ Bu testni matrixini yuklab olish huquqingiz yo'q!")
        return
    
    # Matrix yaratish/yangilash
    from utils import generate_response_matrix
    matrix_file_path, matrix_text = generate_response_matrix(test_id, data)
    
    if not matrix_file_path or not matrix_text:
        if update.callback_query:
            await update.callback_query.answer("❌ Matrix yaratib bo'lmadi yoki hali natijalar yo'q!", show_alert=True)
        else:
            await update.message.reply_text("❌ Matrix yaratib bo'lmadi yoki hali natijalar yo'q!")
        return
    
    # Matrix faylini yuborish
    try:
        with open(matrix_file_path, 'rb') as f:
            if update.callback_query:
                await update.callback_query.message.reply_document(
                    document=f,
                    filename=f"matrix_{test_id}.xlsx",
                    caption=f"📋 0-1 Matrix: {test['name']}\n\n"
                            f"Format: user_id, Q1, Q2, Q3, ...\n"
                            f"0 = xato javob, 1 = to'g'ri javob"
                )
                await update.callback_query.answer("✅ Matrix yuborildi!")
            else:
                await update.message.reply_document(
                    document=f,
                    filename=f"matrix_{test_id}.xlsx",
                    caption=f"📋 0-1 Matrix: {test['name']}\n\n"
                            f"Format: user_id, Q1, Q2, Q3, ...\n"
                            f"0 = xato javob, 1 = to'g'ri javob"
                )
    except Exception as e:
        logger.error(f"Matrix yuborish xatosi: {e}")
        # Agar fayl yuborib bo'lmasa, matn sifatida yuborish
        if update.callback_query:
            await update.callback_query.message.reply_text(
                f"📋 0-1 Matrix: {test['name']}\n\n"
                f"```\n{matrix_text}\n```",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"📋 0-1 Matrix: {test['name']}\n\n"
                f"```\n{matrix_text}\n```",
                parse_mode='Markdown'
            )


async def my_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi natijalari"""
    if not await check_subscription(update, context):
        return
    
    # Ism va familya tekshiruvi
    if not await check_user_name(update, context):
        await update.message.reply_text(
            "❌ Botdan foydalanish uchun ism va familyangizni kiriting.\n\n"
            "Iltimos, /start ni bosing va ism va familyangizni kiriting."
        )
        return
    
    user_id = update.effective_user.id
    data = load_data()
    
    # Faqat natijalangan testlar natijalarini ko'rsatish
    # Test natijalangan bo'lsa, u data['tests'] dan o'chirilgan bo'ladi
    user_results = []
    for r_id, r in data.get('user_results', {}).items():
        if r['user_id'] == user_id:
            test_id = r.get('test_id')
            # Agar test hali mavjud bo'lsa (natijalanmagan), natijalarni ko'rsatmaymiz
            if test_id not in data.get('tests', {}):
                user_results.append(r)
    
    if not user_results:
        await update.message.reply_text("❌ Sizda hali test natijalari yo'q yoki testlar hali natijalanmagan.")
        return
    
    text = "📊 Mening natijalarim:\n\n"
    for result in sorted(user_results, key=lambda x: x['completed_at'], reverse=True)[:10]:
        text += f"📝 {result['test_name']}\n"
        text += f"   {result['correct']}/{result['total']} ({result['percentage']:.1f}%)\n"
        text += f"   Rasch: {result['rasch_score']:.2f}\n\n"
    
    await update.message.reply_text(text)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback query handler"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Admin boshqaruvi
    if data == "add_admin":
        await query.edit_message_text("Admin ID ni yuboring:")
        context.user_data['adding_admin'] = True
    elif data == "remove_admin":
        await query.edit_message_text("Olib tashlash kerak bo'lgan admin ID ni yuboring:")
        context.user_data['removing_admin'] = True
    elif data == "list_admins":
        data_file = load_data()
        admins = data_file['admins']
        if admins:
            text = "📋 Adminlar ro'yxati:\n\n" + "\n".join([f"• {admin_id}" for admin_id in admins])
        else:
            text = "❌ Adminlar mavjud emas."
        await query.edit_message_text(text)
    
    # Kanal boshqaruvi
    elif data == "add_channel":
        await query.edit_message_text("Kanal username yoki ID ni yuboring (masalan: @channel yoki -1001234567890):")
        context.user_data['adding_channel'] = True
    elif data == "remove_channel":
        await query.edit_message_text("Olib tashlash kerak bo'lgan kanal username yoki ID ni yuboring:")
        context.user_data['removing_channel'] = True
    elif data == "list_channels":
        data_file = load_data()
        channels = data_file['mandatory_channels']
        if channels:
            text = "📋 Majburiy kanallar:\n\n" + "\n".join([f"• {ch}" for ch in channels])
        else:
            text = "❌ Majburiy kanallar mavjud emas."
        await query.edit_message_text(text)
    
    # Test boshlash
    elif data.startswith("start_test_"):
        test_id = data.replace("start_test_", "")
        await start_test(update, context, test_id)
    
    # Postni ko'rish (ulashish)
    elif data.startswith("view_post_"):
        test_id = data.replace("view_post_", "")
        data_file = load_data()
        if test_id in data_file['tests']:
            test_data = data_file['tests'][test_id]
            try:
                bot_info = await context.bot.get_me()
                bot_username = f"@{bot_info.username}" if bot_info.username else "Test Bot"
            except:
                bot_username = "Test Bot"
            
            post_text, reply_markup = generate_test_post(test_data, test_id, bot_username)
            # Postni yangi xabar sifatida yuborish (nusxalab yuborish uchun)
            await query.answer("📢 Post yuborilmoqda...")
            await query.message.reply_text(
                post_text,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        else:
            await query.answer("❌ Test topilmadi!", show_alert=True)
    
    # Barcha testlar ro'yxati
    elif data == "list_all_tests":
        await query.answer("📋 Testlar ro'yxati yuborilmoqda...")
        # list_tests funksiyasini to'g'ridan-to'g'ri chaqirish
        # Lekin u message kerak, shuning uchun callback query message orqali yuboramiz
        data_file = load_data()
        if not data_file['tests']:
            await query.message.reply_text("❌ Hozircha testlar mavjud emas.")
            return
        
        user_id = query.from_user.id
        is_boss = user_id == BOSS_ID
        is_admin = user_id in data_file.get("admins", [])
        
        keyboard = []
        for test_id, test_data in data_file['tests'].items():
            can_edit = (is_boss or is_admin) and test_data.get('created_by') == user_id
            
            if can_edit:
                keyboard.append([
                    InlineKeyboardButton(
                        f"📝 {test_data['name']}",
                        callback_data=f"start_test_{test_id}"
                    ),
                    InlineKeyboardButton("✏️", callback_data=f"edit_test_{test_id}")
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton(
                        f"📝 {test_data['name']}",
                        callback_data=f"start_test_{test_id}"
                    )
                ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "📋 <b>Mavjud testlar:</b>\n\nTestni tanlang:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    # Test boshlanish vaqti tanlash (inline keyboard)
    elif data == "time_now":
        # Darhol boshlash
        context.user_data['test_creation_step'] = 'start_time'
        await process_time_selection(update, context, datetime.now(UZBEKISTAN_TZ))
    elif data == "time_15m":
        # 15 daqiqadan keyin
        context.user_data['test_creation_step'] = 'start_time'
        await process_time_selection(update, context, datetime.now(UZBEKISTAN_TZ) + timedelta(minutes=15))
    elif data == "time_30m":
        # 30 daqiqadan keyin
        context.user_data['test_creation_step'] = 'start_time'
        await process_time_selection(update, context, datetime.now(UZBEKISTAN_TZ) + timedelta(minutes=30))
    elif data == "time_1h":
        # 1 soatdan keyin
        context.user_data['test_creation_step'] = 'start_time'
        await process_time_selection(update, context, datetime.now(UZBEKISTAN_TZ) + timedelta(hours=1))
    elif data == "time_custom":
        # Boshqa vaqt kiritish
        context.user_data['test_creation_step'] = 'start_time'
        await query.edit_message_text(
            "📝 Boshqa vaqt kiriting:\n\n"
            "✅ Qulay formatlar:\n"
            "• \"hozir\" - darhol\n"
            "• \"15m\" yoki \"15 min\" - 15 daqiqadan keyin\n"
            "• \"1h\" yoki \"1 soat\" - 1 soatdan keyin\n"
            "• \"14:30\" - bugungi kunda 14:30 da\n"
            "• \"12-25 14:30\" - eski format (oy-kun soat:daqiqa)\n\n"
            "Yoki /cancel ni bosing."
        )
    # Skip text answers (36-40)
    elif data == "skip_text_answers":
        # 36-40 savollar uchun javoblarni o'tkazib yuborish
        mc_answers_list = context.user_data.get('mc_answers', [])
        if not mc_answers_list:
            await query.answer("❌ Xatolik: javoblar topilmadi!", show_alert=True)
            return
        
        context.user_data['test_creation_step'] = 'start_time'
        
        # Hozirgi vaqtni ko'rsatish
        now_uz = datetime.now(UZBEKISTAN_TZ)
        current_time = now_uz.strftime('%d.%m.%Y %H:%M')
        
        keyboard = [
            [InlineKeyboardButton("⚡ Hozir", callback_data="time_now")],
            [
                InlineKeyboardButton("15 min", callback_data="time_15m"),
                InlineKeyboardButton("30 min", callback_data="time_30m"),
                InlineKeyboardButton("1 soat", callback_data="time_1h")
            ],
            [InlineKeyboardButton("📝 Boshqa vaqt kiritish", callback_data="time_custom")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ 1-35 savollar uchun javoblar qabul qilindi!\n\n"
            f"ℹ️ 36-40 savollar uchun yozma javoblar o'tkazib yuborildi.\n\n"
            f"📅 Test boshlanish vaqtini belgilang:\n\n"
            f"🕐 Hozirgi vaqt: {current_time}\n\n"
            f"Quyidagi variantlardan birini tanlang:",
            reply_markup=reply_markup
        )
    
    # Test tahrirlash
    elif data.startswith("edit_test_"):
        test_id = data.replace("edit_test_", "")
        await edit_test(update, context, test_id)
    
    # Test tahrirlash bosqichlari
    elif data.startswith("edit_name_"):
        test_id = data.replace("edit_name_", "")
        context.user_data['editing_test'] = True
        context.user_data['editing_test_id'] = test_id
        context.user_data['test_editing_step'] = 'name'
        await query.edit_message_text("Yangi test nomini kiriting:")
    
    elif data.startswith("edit_file_"):
        test_id = data.replace("edit_file_", "")
        context.user_data['editing_test'] = True
        context.user_data['editing_test_id'] = test_id
        context.user_data['test_editing_step'] = 'file'
        await query.edit_message_text("Yangi test faylini yuboring:")
    
    elif data.startswith("edit_answers_"):
        test_id = data.replace("edit_answers_", "")
        data_file = load_data()
        if test_id in data_file['tests']:
            test = data_file['tests'][test_id]
            context.user_data['editing_test'] = True
            context.user_data['editing_test_id'] = test_id
            context.user_data['test_editing_step'] = 'answers'
            context.user_data['test_questions'] = test['questions']
            await query.edit_message_text(f"Javoblarni kiriting: 1a2b3c4d...\n\nSavollar soni: {len(test['questions'])}")
        else:
            await query.answer("❌ Test topilmadi!")
    
    elif data.startswith("edit_start_time_"):
        test_id = data.replace("edit_start_time_", "")
        data_file = load_data()
        if test_id in data_file['tests']:
            test = data_file['tests'][test_id]
            context.user_data['editing_test'] = True
            context.user_data['editing_test_id'] = test_id
            context.user_data['test_editing_step'] = 'start_time'
            
            # Hozirgi vaqtni ko'rsatish
            now_uz = datetime.now(UZBEKISTAN_TZ)
            current_time = now_uz.strftime('%m-%d %H:%M')
            
            # Eski vaqtni ko'rsatish (agar mavjud bo'lsa)
            old_time_text = ""
            if 'start_time' in test:
                try:
                    old_time = datetime.fromisoformat(test['start_time'])
                    if old_time.tzinfo is None:
                        old_time = UZBEKISTAN_TZ.localize(old_time)
                    old_time_text = f"\nEski vaqt: {old_time.strftime('%m-%d %H:%M')}\n"
                except:
                    pass
            
            await query.edit_message_text(
                f"📅 Test boshlanish vaqtini o'zgartirish (O'zbekiston vaqti):\n\n"
                f"Hozirgi vaqt: {current_time}{old_time_text}\n"
                f"Format: MM-DD HH:MM\n"
                f"Masalan: 12-25 14:30\n\n"
                f"Yoki 'hozir' deb yozing testni darhol boshlash uchun."
            )
        else:
            await query.answer("❌ Test topilmadi!")
    
    elif data.startswith("finalize_test_"):
        test_id = data.replace("finalize_test_", "")
        await finalize_test(update, context, test_id)
    
    elif data.startswith("download_matrix_"):
        test_id = data.replace("download_matrix_", "")
        await download_matrix(update, context, test_id)
    
    elif data == "cancel_edit":
        context.user_data.pop('editing_test', None)
        context.user_data.pop('editing_test_id', None)
        context.user_data.pop('test_editing_step', None)
        await query.edit_message_text("❌ Tahrirlash bekor qilindi.")


async def process_admin_channel_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin va kanal qo'shish/olib tashlash"""
    if update.effective_user.id != BOSS_ID:
        return
    
    # Agar hech qanday operatsiya kutilayotgan bo'lmasa, hech narsa qilmaymiz
    if not any([
        context.user_data.get('adding_admin'),
        context.user_data.get('removing_admin'),
        context.user_data.get('adding_channel'),
        context.user_data.get('removing_channel')
    ]):
        return
    
    text = update.message.text.strip()
    data = load_data()
    
    # Admin qo'shish
    if context.user_data.get('adding_admin'):
        try:
            admin_id = int(text)
            if admin_id not in data['admins']:
                data['admins'].append(admin_id)
                save_data(data)
                await update.message.reply_text(f"✅ Admin {admin_id} qo'shildi!")
            else:
                await update.message.reply_text(f"⚠️ Bu admin allaqachon mavjud.")
            context.user_data['adding_admin'] = False
        except ValueError:
            await update.message.reply_text("❌ Noto'g'ri ID format. Faqat raqam kiriting.")
    
    # Admin olib tashlash
    elif context.user_data.get('removing_admin'):
        try:
            admin_id = int(text)
            if admin_id in data['admins']:
                data['admins'].remove(admin_id)
                save_data(data)
                await update.message.reply_text(f"✅ Admin {admin_id} olib tashlandi!")
            else:
                await update.message.reply_text(f"❌ Bu admin topilmadi.")
            context.user_data['removing_admin'] = False
        except ValueError:
            await update.message.reply_text("❌ Noto'g'ri ID format. Faqat raqam kiriting.")
    
    # Kanal qo'shish
    elif context.user_data.get('adding_channel'):
        channel = text.replace('@', '').strip()
        if channel not in data['mandatory_channels']:
            data['mandatory_channels'].append(channel)
            save_data(data)
            await update.message.reply_text(f"✅ Kanal {channel} qo'shildi!")
        else:
            await update.message.reply_text(f"⚠️ Bu kanal allaqachon mavjud.")
        context.user_data['adding_channel'] = False
    
    # Kanal olib tashlash
    elif context.user_data.get('removing_channel'):
        channel = text.replace('@', '').strip()
        if channel in data['mandatory_channels']:
            data['mandatory_channels'].remove(channel)
            save_data(data)
            await update.message.reply_text(f"✅ Kanal {channel} olib tashlandi!")
        else:
            await update.message.reply_text(f"❌ Bu kanal topilmadi.")
        context.user_data['removing_channel'] = False


async def rasch_evaluation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rasch modeliga asoslanib talabalarni baholash"""
    user_id = update.effective_user.id
    data = load_data()
    
    # Faqat boss va adminlar foydalanishi mumkin
    if user_id != BOSS_ID and user_id not in data.get("admins", []):
        await update.message.reply_text("❌ Bu funksiya faqat adminlar uchun!")
        return
    
    # Excel fayl kutilayotganini belgilash
    context.user_data['waiting_for_rasch_matrix'] = True
    
    await update.message.reply_text(
        "📊 Rasch modeliga asoslanib talabalarni baholash\n\n"
        "Iltimos, .xlsx formatidagi matrix faylini yuboring.\n\n"
        "Fayl formati:\n"
        "- Birinchi qator: user_id, Q1, Q2, Q3, ...\n"
        "- Keyingi qatorlar: har bir talaba uchun user_id va javoblar (0 yoki 1)\n\n"
        "Masalan:\n"
        "user_id | Q1 | Q2 | Q3\n"
        "12345   | 1  | 0  | 1\n"
        "67890   | 0  | 1  | 1"
    )


async def process_rasch_matrix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rasch matrix faylini qayta ishlash va standart ball (T-score) bilan baholash"""
    if not context.user_data.get('waiting_for_rasch_matrix'):
        return
    
    if not update.message or not update.message.document:
        return
    
    document = update.message.document
    file_name = document.file_name or "matrix.xlsx"
    
    # Faqat .xlsx fayllarni qabul qilish
    if not file_name.lower().endswith('.xlsx'):
        await update.message.reply_text(
            "❌ Faqat .xlsx formatidagi fayllar qabul qilinadi!\n\n"
            "Iltimos, Excel faylini (.xlsx) yuboring."
        )
        return
    
    try:
        # Faylni yuklash
        file = await context.bot.get_file(document.file_id)
        
        # Vaqtinchalik fayl sifatida saqlash
        temp_dir = "temp_rasch"
        os.makedirs(temp_dir, exist_ok=True)
        temp_file_path = os.path.join(temp_dir, f"rasch_matrix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        
        await file.download_to_drive(temp_file_path)
        
        # Matrixni baholash
        await update.message.reply_text("⏳ Matrix tahlil qilinmoqda... Rasch modeli ishga tushirilmoqda...")
        
        students_results, statistics = evaluate_students_from_matrix(temp_file_path)
        
        if not students_results or not statistics:
            await update.message.reply_text(
                "❌ Matrix tahlil qilib bo'lmadi!\n\n"
                "Iltimos, fayl formati to'g'ri ekanligini tekshiring:\n"
                "- Birinchi qator: user_id, Q1, Q2, Q3, ...\n"
                "- Keyingi qatorlar: user_id va javoblar (0 yoki 1)\n\n"
                "Misol:\n"
                "user_id | Q1 | Q2 | Q3\n"
                "12345   | 1  | 0  | 1\n"
                "67890   | 0  | 1  | 1"
            )
            # Vaqtinchalik faylni o'chirish
            try:
                os.remove(temp_file_path)
            except:
                pass
            context.user_data.pop('waiting_for_rasch_matrix', None)
            return
        
        # Baholash mezonlari (rasmga asoslangan)
        def get_grade_level(t_score):
            """T-score bo'yicha baho darajasini aniqlash"""
            if t_score >= 70:
                return "A (A'lo)", "🟢"
            elif t_score >= 60:
                return "B (Yaxshi)", "🟡"
            elif t_score >= 50:
                return "C (Qoniqarli)", "🟠"
            elif t_score >= 40:
                return "D (Qoniqarsiz)", "🔴"
            else:
                return "E (Juda past)", "⚫"
        
        # Natijalarni ko'rsatish
        text = "📊 Rasch Model Baholash Natijalari\n\n"
        text += f"📐 Baholash formulasi: T = 50 + 10Z\n"
        text += f"   Z = (θ - μ) / σ\n\n"
        text += f"📈 Umumiy statistika:\n"
        text += f"   Jami talabalar: {statistics['total_students']}\n"
        text += f"   Jami savollar: {statistics['total_questions']}\n"
        text += f"   O'rtacha foiz: {statistics['avg_percentage']:.1f}%\n"
        text += f"   O'rtacha θ (theta): {statistics.get('avg_theta', 0):.2f}\n"
        text += f"   Standart tafovut (σ): {statistics.get('std_theta', 0):.2f}\n"
        text += f"   O'rtacha T-score: {statistics.get('avg_t_score', 50):.1f}\n\n"
        text += f"📊 Baholash mezonlari:\n"
        text += f"   🟢 A (A'lo): T ≥ 70\n"
        text += f"   🟡 B (Yaxshi): 60 ≤ T < 70\n"
        text += f"   🟠 C (Qoniqarli): 50 ≤ T < 60\n"
        text += f"   🔴 D (Qoniqarsiz): 40 ≤ T < 50\n"
        text += f"   ⚫ E (Juda past): T < 40\n\n"
        text += f"📋 Top 15 talaba (T-score bo'yicha):\n\n"
        
        # Top 15 talaba
        for idx, student in enumerate(students_results[:15], 1):
            t_score = student.get('t_score', 50)
            grade, emoji = get_grade_level(t_score)
            text += f"{idx}. {emoji} Talabgor: {student['user_id']}\n"
            text += f"   {student['correct']}/{student['total']} ({student['percentage']:.1f}%) | "
            text += f"θ: {student.get('theta', 0):.2f} | T: {t_score:.2f} | {grade}\n\n"
        
        if statistics['total_students'] > 15:
            text += f"... va yana {statistics['total_students'] - 15} ta talaba\n"
        
        # PDF yaratish - rasmda ko'rsatilgan formatga asoslangan
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Rasch Model - Test Natijalari</title>
            <style>
                body {{ 
                    font-family: 'Times New Roman', serif; 
                    padding: 30px; 
                    line-height: 1.6;
                }}
                h1 {{ 
                    color: #2c3e50; 
                    text-align: center;
                    border-bottom: 3px solid #3498db;
                    padding-bottom: 10px;
                }}
                .formula {{
                    background: #ecf0f1;
                    padding: 15px;
                    margin: 20px 0;
                    border-left: 4px solid #3498db;
                    font-family: 'Courier New', monospace;
                    font-size: 14px;
                }}
                .info {{ 
                    background: #e8f5e9; 
                    padding: 15px; 
                    margin: 15px 0; 
                    border-radius: 5px;
                    border-left: 4px solid #4caf50;
                }}
                .criteria {{
                    background: #fff3e0;
                    padding: 15px;
                    margin: 15px 0;
                    border-radius: 5px;
                    border-left: 4px solid #ff9800;
                }}
                table {{ 
                    width: 100%; 
                    border-collapse: collapse; 
                    margin: 20px 0;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                th, td {{ 
                    border: 1px solid #bdc3c7; 
                    padding: 10px; 
                    text-align: center;
                }}
                th {{ 
                    background-color: #3498db; 
                    color: white;
                    font-weight: bold;
                }}
                tr:nth-child(even) {{ 
                    background-color: #ecf0f1; 
                }}
                tr:hover {{
                    background-color: #d5dbdb;
                }}
                .grade-A {{ background-color: #2ecc71; color: white; font-weight: bold; }}
                .grade-B {{ background-color: #f1c40f; color: black; font-weight: bold; }}
                .grade-C {{ background-color: #e67e22; color: white; font-weight: bold; }}
                .grade-D {{ background-color: #e74c3c; color: white; font-weight: bold; }}
                .grade-E {{ background-color: #7f8c8d; color: white; font-weight: bold; }}
                .footer {{
                    margin-top: 30px;
                    padding-top: 15px;
                    border-top: 2px solid #bdc3c7;
                    text-align: center;
                    font-size: 12px;
                    color: #7f8c8d;
                }}
            </style>
        </head>
        <body>
            <h1>📊 Rasch Model - Test Natijalari</h1>
            
            <div class="formula">
                <strong>Baholash formulasi (Rasch Model):</strong><br><br>
                Z = (θ - μ) / σ<br>
                T = 50 + 10Z<br><br>
                Bu yerda:<br>
                • θ (theta) - talabaning qobiliyati<br>
                • μ (mu) - o'rtacha qiymat<br>
                • σ (sigma) - standart tafovut<br>
                • Z - Z-score (standartlashtirilgan ball)<br>
                • T - T-score (standart ball, 0-100 oralig'ida)
            </div>
            
            <div class="info">
                <h3>📈 Umumiy Statistika</h3>
                <p><strong>Jami talabalar:</strong> {statistics['total_students']}</p>
                <p><strong>Jami savollar:</strong> {statistics['total_questions']}</p>
                <p><strong>O'rtacha foiz:</strong> {statistics['avg_percentage']:.2f}%</p>
                <p><strong>O'rtacha θ (theta):</strong> {statistics.get('avg_theta', 0):.4f}</p>
                <p><strong>Standart tafovut (σ):</strong> {statistics.get('std_theta', 1):.4f}</p>
                <p><strong>O'rtacha T-score:</strong> {statistics.get('avg_t_score', 50):.2f}</p>
                <p><strong>Eng yuqori θ:</strong> {statistics.get('max_theta', 0):.4f}</p>
                <p><strong>Eng past θ:</strong> {statistics.get('min_theta', 0):.4f}</p>
                <p><strong>Tahlil vaqti:</strong> {datetime.now(UZBEKISTAN_TZ).strftime('%Y-%m-%d %H:%M')}</p>
            </div>
            
            <div class="criteria">
                <h3>📊 Baholash Mezonlari</h3>
                <table style="width: 60%; margin: 0 auto;">
                    <tr>
                        <th>Baho</th>
                        <th>T-score oralig'i</th>
                        <th>Daraja</th>
                    </tr>
                    <tr>
                        <td class="grade-A">A</td>
                        <td>T ≥ 70</td>
                        <td>A'lo</td>
                    </tr>
                    <tr>
                        <td class="grade-B">B</td>
                        <td>60 ≤ T &lt; 70</td>
                        <td>Yaxshi</td>
                    </tr>
                    <tr>
                        <td class="grade-C">C</td>
                        <td>50 ≤ T &lt; 60</td>
                        <td>Qoniqarli</td>
                    </tr>
                    <tr>
                        <td class="grade-D">D</td>
                        <td>40 ≤ T &lt; 50</td>
                        <td>Qoniqarsiz</td>
                    </tr>
                    <tr>
                        <td class="grade-E">E</td>
                        <td>T &lt; 40</td>
                        <td>Juda past</td>
                    </tr>
                </table>
            </div>
            
            <h2 style="text-align: center; margin-top: 30px;">Barcha talabalar natijalari (T-score bo'yicha tartiblangan)</h2>
            <table>
                <tr>
                    <th>#</th>
                    <th>Talabgor</th>
                    <th>To'g'ri / Jami</th>
                    <th>Foiz (%)</th>
                    <th>θ (Theta)</th>
                    <th>Z-score</th>
                    <th>T-score</th>
                    <th>Baho</th>
                </tr>
        """
        
        # Har bir talaba uchun natijalarni jadvaldga qo'shish
        for idx, student in enumerate(students_results, 1):
            t_score = student.get('t_score', 50)
            theta = student.get('theta', 0)
            
            # Z-score ni hisoblash
            avg_theta = statistics.get('avg_theta', 0)
            std_theta = statistics.get('std_theta', 1)
            z_score = (theta - avg_theta) / std_theta if std_theta != 0 else 0
            
            # Baho va rang
            if t_score >= 70:
                grade = "A"
                grade_class = "grade-A"
            elif t_score >= 60:
                grade = "B"
                grade_class = "grade-B"
            elif t_score >= 50:
                grade = "C"
                grade_class = "grade-C"
            elif t_score >= 40:
                grade = "D"
                grade_class = "grade-D"
            else:
                grade = "E"
                grade_class = "grade-E"
            
            html_content += f"""
                <tr>
                    <td>{idx}</td>
                    <td>{student['user_id']}</td>
                    <td>{student['correct']}/{student['total']}</td>
                    <td>{student['percentage']:.1f}%</td>
                    <td>{theta:.4f}</td>
                    <td>{z_score:.4f}</td>
                    <td><strong>{t_score:.2f}</strong></td>
                    <td class="{grade_class}">{grade}</td>
                </tr>
            """
        
        html_content += """
            </table>
            
            <div class="footer">
                <p><strong>Rasch Model IRT (Item Response Theory)</strong></p>
                <p>Test talabalar natijalarini ilmiy usulda baholash tizimi</p>
            </div>
        </body>
        </html>
        """
        
        # Fallback matni (reportlab uchun)
        fallback_lines = [
            "Rasch Model Baholash Natijalari",
            f"Jami talabalar: {statistics['total_students']}",
            f"Jami savollar: {statistics['total_questions']}",
            f"O'rtacha foiz: {statistics['avg_percentage']:.1f}%",
            f"O'rtacha θ (theta): {statistics.get('avg_theta', 0):.2f}",
            f"Standart tafovut (σ): {statistics.get('std_theta', 0):.2f}",
            f"O'rtacha T-score: {statistics.get('avg_t_score', 50):.1f}",
            "",
            "Baholash mezonlari:",
            "  A (A'lo)       : T ≥ 70",
            "  B (Yaxshi)     : 60 ≤ T < 70",
            "  C (Qoniqarli)  : 50 ≤ T < 60",
            "  D (Qoniqarsiz) : 40 ≤ T < 50",
            "  E (Juda past)  : T < 40",
            "",
            "Talabalar (T-score bo'yicha):"
        ]
        for idx, student in enumerate(students_results, 1):
            fallback_lines.append(
                f"{idx}. Talabgor: {student['user_id']} | "
                f"{student['correct']}/{student['total']} | "
                f"{student['percentage']:.1f}% | "
                f"θ: {student.get('theta', 0):.2f} | "
                f"T: {student.get('t_score', 0):.2f}"
            )
        
        # generate_pdf funksiyasidan foydalanish
        pdf_file = generate_pdf(
            f"rasch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            {
                'html_content': html_content,
                'fallback_title': "Rasch Model Baholash Natijalari",
                'fallback_lines': fallback_lines
            }
        )
        
        await update.message.reply_text(text)
        
        if pdf_file:
            try:
                await update.message.reply_document(
                    document=pdf_file,
                    filename=f"rasch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    caption="📊 Rasch Model Baholash Natijalari (PDF)\n\nFormula: T = 50 + 10Z, bu yerda Z = (θ - μ) / σ"
                )
            except Exception as doc_error:
                logger.error(f"PDF yuborish xatosi: {doc_error}")
                await update.message.reply_text("⚠️ PDF yuborib bo'lmadi, lekin natijalar yuborildi.")
        else:
            logger.warning("PDF yaratib bo'lmadi")
            await update.message.reply_text("⚠️ PDF yaratib bo'lmadi, lekin natijalar yuborildi.")
        
        # Vaqtinchalik faylni o'chirish
        try:
            os.remove(temp_file_path)
        except:
            pass
        
        context.user_data.pop('waiting_for_rasch_matrix', None)
        
    except Exception as e:
        logger.error(f"Rasch matrix qayta ishlash xatosi: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await update.message.reply_text(f"❌ Xatolik: {str(e)}\n\nIltimos, fayl formatini tekshiring.")
        context.user_data.pop('waiting_for_rasch_matrix', None)


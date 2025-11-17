#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Test Bot - Asosiy fayl
Boss, admin va oddiy foydalanuvchilar uchun test tizimi
"""

import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config import BOT_TOKEN
from handlers import (
    start,
    admin_panel,
    channels_panel,
    create_test,
    list_tests,
    my_results,
    callback_handler,
    process_test_file,
    process_test_creation,
    process_test_editing,
    process_test_answers,
    process_admin_channel_commands,
    process_user_name,
    check_user_name,
)

# Logging sozlash
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Botni ishga tushirish"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("channels", channels_panel))
    application.add_handler(CommandHandler("createtest", create_test))
    application.add_handler(CommandHandler("tests", list_tests))
    application.add_handler(CommandHandler("myresults", my_results))
    
    # Cancel handler - async lambda
    async def cancel_handler(update, context):
        context.user_data.clear()
        if update.message:
            await update.message.reply_text("❌ Jarayon bekor qilindi.")
    
    application.add_handler(CommandHandler("cancel", cancel_handler))
    
    # Callback handler
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Document handler (test faylini qabul qilish uchun)
    async def document_handler(update, context):
        await process_test_file(update, context)
    
    application.add_handler(MessageHandler(
        filters.Document.ALL,
        document_handler
    ))
    
    # Message handler (test yaratish, test javoblari va admin/kanal boshqaruvi uchun)
    async def message_handler(update, context):
        # Avval ism va familya kiritish jarayonini tekshirish
        if context.user_data.get('waiting_for_name'):
            await process_user_name(update, context)
            return
        
        # Ism va familya tekshiruvi (barcha funksiyalar uchun)
        if not await check_user_name(update, context):
            await update.message.reply_text(
                "❌ Botdan foydalanish uchun ism va familyangizni kiriting.\n\n"
                "Iltimos, /start ni bosing va ism va familyangizni kiriting."
            )
            return
        
        # Reply keyboard tugmalarini tekshirish
        if update.message and update.message.text:
            text = update.message.text
            if text == "📝 Test ishlash":
                await list_tests(update, context)
                return
            elif text == "📊 Test natijalarim":
                await my_results(update, context)
                return
        
        # Avval test tahrirlash jarayonini tekshirish
        if context.user_data.get('editing_test'):
            await process_test_editing(update, context)
            return
        
        # Keyin test yaratish jarayonini tekshirish
        if context.user_data.get('creating_test'):
            await process_test_creation(update, context)
            return
        
        # Keyin test javoblarini tekshirish (faqat test ishlash rejimida bo'lsa)
        test_processed = await process_test_answers(update, context)
        if test_processed:
            return  # Agar test javoblari qayta ishlandi bo'lsa, boshqa ishlarni qilmaymiz
        
        # Admin/kanal boshqaruvi
        await process_admin_channel_commands(update, context)
    
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        message_handler
    ))
    
    # Error handler qo'shish
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Xatoliklarni qayta ishlash"""
        logger.error(f"Xatolik yuz berdi: {context.error}", exc_info=context.error)
        
        if update and isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring yoki /start ni bosing."
                )
            except Exception:
                pass  # Agar xabar yuborib bo'lmasa, hech narsa qilmaymiz
    
    application.add_error_handler(error_handler)
    
    # Botni ishga tushirish
    logger.info("Bot ishga tushmoqda...")
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi.")
    except Exception as e:
        logger.error(f"Bot ishga tushishda xatolik: {e}", exc_info=True)


if __name__ == '__main__':
    main()

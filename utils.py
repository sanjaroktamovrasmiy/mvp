#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Yordamchi funksiyalar
"""

import logging
import os
import pdfkit
import numpy as np
from io import BytesIO
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from database import load_data
from rasch_pkg import RaschModel
from openpyxl import Workbook

logger = logging.getLogger(__name__)


async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Majburiy kanallarga obuna tekshiruvi"""
    data = load_data()
    if not data["mandatory_channels"]:
        return True
    
    user_id = update.effective_user.id
    for channel in data["mandatory_channels"]:
        try:
            # Kanal username yoki ID bo'lishi mumkin
            channel_id = channel if channel.startswith('@') or channel.startswith('-') else f"@{channel}"
            member = await context.bot.get_chat_member(channel_id, user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception as e:
            logger.error(f"Kanal tekshiruvi xatosi: {e} - Kanal: {channel}")
            # Agar kanal topilmasa, xavfsizlik uchun False qaytaramiz
            return False
    return True


def calculate_rasch_score(results, questions):
    """
    Haqiqiy Rasch model kutubxonasi (rasch-pkg) orqali ball hisoblash
    Rasch modeli: P(X=1|θ, β) = exp(θ - β) / (1 + exp(θ - β))
    Bu yerda θ - foydalanuvchining qobiliyati, β - savolning qiyinligi
    
    rasch-pkg kutubxonasi orqali ilmiy hisob-kitob qilinadi
    """
    try:
        correct_count = sum(1 for r in results if r['is_correct'])
        total = len(results)
        
        if total == 0:
            return 0.0
        
        # Rasch model obyektini yaratish (rasch-pkg kutubxonasi)
        rasch_model = RaschModel()
        
        # Foydalanuvchi javoblarini matritsaga aylantirish
        # 1 = to'g'ri javob, 0 = noto'g'ri javob
        responses = [1 if r['is_correct'] else 0 for r in results]
        
        # Rasch model orqali foydalanuvchi qobiliyatini hisoblash
        # rasch-pkg kutubxonasining ilmiy metodlaridan foydalanish
        try:
            # calculate_theta - foydalanuvchi qobiliyatini (theta) hisoblash
            # Theta - Rasch modelida foydalanuvchi qobiliyati o'lchovi
            # Metod: calculate_theta(correct_answers: int, total_questions: int)
            theta = rasch_model.calculate_theta(correct_count, total)
            
            # Theta ni Rasch score ga aylantirish
            rasch_score = float(theta)
            
        except Exception as method_error:
            logger.warning(f"Rasch model metodlari xatosi: {method_error}, oddiy logit transformatsiya ishlatilmoqda")
            # Agar metodlar ishlamasa, oddiy logit transformatsiya
            p = correct_count / total
            if p > 0 and p < 1:
                logit = np.log(p / (1 - p))
                rasch_score = float(logit)
            elif p == 1:
                rasch_score = 3.0
            else:
                rasch_score = -3.0
        
        # Score ni -3 dan +3 gacha shkalaga normalizatsiya qilish
        rasch_score = np.clip(rasch_score, -3.0, 3.0)
        
        return float(rasch_score)
        
    except Exception as e:
        logger.error(f"Rasch model kutubxonasi xatosi: {e}")
        # Xatolik bo'lsa, oddiy logit transformatsiya qilamiz
        try:
            correct_count = sum(1 for r in results if r['is_correct'])
            total = len(results)
            if total == 0:
                return 0.0
            
            p = correct_count / total
            if p > 0 and p < 1:
                logit = np.log(p / (1 - p))
                return float(np.clip(logit, -3.0, 3.0))
            else:
                return 3.0 if p == 1 else -3.0
        except Exception as e2:
            logger.error(f"Fallback Rasch hisoblash xatosi: {e2}")
            return 0.0


def generate_pdf(result_id, result_data):
    """PDF fayl yaratish"""
    try:
        # Agar html_content to'g'ridan-to'g'ri berilgan bo'lsa (finalize_test uchun)
        if 'html_content' in result_data:
            html_content = result_data['html_content']
        else:
            # Oddiy natija PDF (foydalanuvchi uchun)
            html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Test Natijasi</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                h1 {{ color: #333; }}
                .info {{ background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .result {{ margin: 20px 0; }}
                .question {{ margin: 15px 0; padding: 10px; background: #fff; border-left: 3px solid #007bff; }}
                .correct {{ color: green; }}
                .incorrect {{ color: red; }}
            </style>
        </head>
        <body>
            <h1>Test Natijasi</h1>
            <div class="info">
                <p><strong>Test nomi:</strong> {result_data['test_name']}</p>
                <p><strong>Sana:</strong> {result_data['completed_at']}</p>
                <p><strong>To'g'ri javoblar:</strong> {result_data['correct']}/{result_data['total']}</p>
                <p><strong>Foiz:</strong> {result_data['percentage']:.1f}%</p>
                <p><strong>Rasch Score:</strong> {result_data['rasch_score']:.2f}</p>
            </div>
            <h2>Javoblar tafsiloti:</h2>
        """
        
        for idx, res in enumerate(result_data['results'], 1):
            status = "✅ To'g'ri" if res['is_correct'] else "❌ Noto'g'ri"
            status_class = "correct" if res['is_correct'] else "incorrect"
            html_content += f"""
            <div class="question">
                <p><strong>Savol {idx}:</strong> {res['question']}</p>
                <p class="{status_class}"><strong>Javobingiz:</strong> {res['user_answer']} | <strong>To'g'ri javob:</strong> {res['correct_answer']} | {status}</p>
            </div>
            """
        
        html_content += """
        </body>
        </html>
        """
        
        # PDF yaratish
        try:
            pdf_bytes = pdfkit.from_string(html_content, False, options={
                'page-size': 'A4',
                'encoding': 'UTF-8',
                'no-outline': None,
                'enable-local-file-access': None
            })
            return BytesIO(pdf_bytes)
        except Exception as pdf_error:
            logger.error(f"PDF yaratish xatosi: {pdf_error}")
            # Agar PDF yaratib bo'lmasa, None qaytaramiz
            return None
    except Exception as e:
        logger.error(f"PDF yaratish xatosi: {e}")
        return None


def generate_response_matrix(test_id, data):
    """0-1 matrix yaratish Excel formatida (user_id, question1, question2, ...)"""
    try:
        # Test natijalarini to'plash
        test_results = [
            r for r_id, r in data.get('user_results', {}).items()
            if r.get('test_id') == test_id
        ]
        
        if not test_results:
            return None, None
        
        # Excel workbook yaratish
        wb = Workbook()
        ws = wb.active
        ws.title = "Response Matrix"
        
        # Header: user_id, Q1, Q2, Q3, ...
        total_questions = len(test_results[0]['results']) if test_results else 0
        header = ['user_id'] + [f'Q{i+1}' for i in range(total_questions)]
        ws.append(header)
        
        # Header qatorini qalinlashtirish
        from openpyxl.styles import Font
        for cell in ws[1]:
            cell.font = Font(bold=True)
        
        # Har bir foydalanuvchi uchun qator
        for result in test_results:
            user_id = result['user_id']
            row = [user_id]
            
            # Har bir savol uchun 0 yoki 1
            for res in result['results']:
                value = 1 if res['is_correct'] else 0
                row.append(value)
            
            ws.append(row)
        
        # Matn formatini ham saqlash (fallback uchun)
        matrix_lines = []
        matrix_lines.append('\t'.join(header))
        for result in test_results:
            user_id = result['user_id']
            row = [str(user_id)]
            for res in result['results']:
                value = '1' if res['is_correct'] else '0'
                row.append(value)
            matrix_lines.append('\t'.join(row))
        matrix_text = '\n'.join(matrix_lines)
        
        # Excel fayl sifatida saqlash
        matrix_dir = "matrices"
        os.makedirs(matrix_dir, exist_ok=True)
        matrix_file_path = os.path.join(matrix_dir, f"matrix_{test_id}.xlsx")
        
        wb.save(matrix_file_path)
        
        return matrix_file_path, matrix_text
        
    except Exception as e:
        logger.error(f"Matrix yaratish xatosi: {e}")
        return None, None


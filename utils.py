#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Yordamchi funksiyalar
"""

import logging
import os
import re
import shutil
import textwrap
import pdfkit
import numpy as np
from io import BytesIO
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from database import load_data
from rasch_pkg import RaschModel
from openpyxl import Workbook, load_workbook

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
    """PDF fayl yaratish (pdfkit + reportlab fallback)"""
    html_content = None
    fallback_lines = result_data.get('fallback_lines')
    fallback_title = result_data.get('fallback_title') or result_data.get('test_name') or "Natijalar hisobot"
    
    try:
        if 'html_content' in result_data:
            html_content = result_data['html_content']
        else:
            # Oddiy foydalanuvchi natijasi uchun HTML yaratamiz
            html_content = _build_default_result_html(result_data)
            if fallback_lines is None:
                fallback_lines = _build_fallback_lines_from_result(result_data)
        
        # Avval pdfkit orqali urinib ko'ramiz (wkhtmltopdf talab qiladi)
        if html_content:
            try:
                config = None
                wkhtml_path = shutil.which("wkhtmltopdf")
                if wkhtml_path:
                    config = pdfkit.configuration(wkhtmltopdf=wkhtml_path)
                pdf_bytes = pdfkit.from_string(
                    html_content,
                    False,
                    configuration=config,
                    options={
                        'page-size': 'A4',
                        'encoding': 'UTF-8',
                        'no-outline': None,
                        'enable-local-file-access': None
                    }
                )
                return BytesIO(pdf_bytes)
            except Exception as pdf_error:
                logger.error(f"PDF yaratish xatosi (pdfkit): {pdf_error}")
                # pdfkit ishlamasa, fallbackga o'tamiz
                if fallback_lines is None:
                    fallback_lines = _html_to_plain_text_lines(html_content)
        
        # Agar html_content mavjud bo'lmasa yoki pdfkit ishlamasa - fallback
        if fallback_lines is None:
            if html_content:
                fallback_lines = _html_to_plain_text_lines(html_content)
            else:
                fallback_lines = ["Hisobotni yaratib bo'lmadi."]
        
        return _generate_pdf_with_reportlab(fallback_title, fallback_lines)
    
    except Exception as e:
        logger.error(f"PDF yaratish xatosi: {e}")
        return None


def _build_default_result_html(result_data):
    """Oddiy foydalanuvchi natijasi uchun HTML yaratish"""
    try:
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Test Natijasi</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 24px; }}
                h1 {{ color: #2c3e50; }}
                .info {{ background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 6px; }}
                .question {{ margin: 15px 0; padding: 12px; background: #fff; border-left: 3px solid #007bff; border-radius: 4px; }}
                .correct {{ color: #2ecc71; }}
                .incorrect {{ color: #e74c3c; }}
            </style>
        </head>
        <body>
            <h1>Test Natijasi</h1>
            <div class="info">
                <p><strong>Test nomi:</strong> {result_data.get('test_name', "Noma'lum")}</p>
                <p><strong>Sana:</strong> {result_data.get('completed_at', '')}</p>
                <p><strong>To'g'ri javoblar:</strong> {result_data.get('correct', 0)}/{result_data.get('total', 0)}</p>
                <p><strong>Foiz:</strong> {result_data.get('percentage', 0):.1f}%</p>
                <p><strong>Rasch Score:</strong> {result_data.get('rasch_score', 0.0):.2f}</p>
            </div>
            <h2>Javoblar tafsiloti:</h2>
        """
        
        for idx, res in enumerate(result_data.get('results', []), 1):
            status = "✅ To'g'ri" if res.get('is_correct') else "❌ Noto'g'ri"
            status_class = "correct" if res.get('is_correct') else "incorrect"
            html_content += f"""
            <div class="question">
                <p><strong>Savol {idx}:</strong> {res.get('question', '')}</p>
                <p class="{status_class}"><strong>Javobingiz:</strong> {res.get('user_answer', '')} | <strong>To'g'ri javob:</strong> {res.get('correct_answer', '')} | {status}</p>
            </div>
            """
        
        html_content += """
        </body>
        </html>
        """
        return html_content
    except Exception as e:
        logger.error(f"HTML yaratish xatosi: {e}")
        return None


def _build_fallback_lines_from_result(result_data):
    """Oddiy foydalanuvchi natijasi uchun fallback matn"""
    lines = []
    try:
        test_name = result_data.get('test_name')
        if test_name:
            lines.append(f"Test nomi: {test_name}")
        completed_at = result_data.get('completed_at')
        if completed_at:
            lines.append(f"Sana: {completed_at}")
        correct = result_data.get('correct')
        total = result_data.get('total')
        if correct is not None and total is not None:
            lines.append(f"Natija: {correct}/{total} savol to'g'ri")
        percentage = result_data.get('percentage')
        if percentage is not None:
            lines.append(f"Foiz: {percentage:.1f}%")
        rasch_score = result_data.get('rasch_score')
        if rasch_score is not None:
            lines.append(f"Rasch score: {rasch_score:.2f}")
        lines.append("")
        lines.append("Javoblar tafsiloti:")
        for idx, res in enumerate(result_data.get('results', []), 1):
            status = "To'g'ri" if res.get('is_correct') else "Noto'g'ri"
            lines.append(f"Savol {idx}: {res.get('question', '')}")
            lines.append(
                f"  Javobingiz: {res.get('user_answer', '-')}, To'g'ri javob: {res.get('correct_answer', '-')}, {status}"
            )
        return lines
    except Exception as e:
        logger.error(f"Fallback matn yaratish xatosi: {e}")
        return ["Natijalar mavjud emas."]


def _html_to_plain_text_lines(html_content):
    """HTML matnini oddiy matn satrlariga aylantirish"""
    try:
        if not html_content:
            return []
        # Taglarni yangi qator bilan almashtirish
        html = re.sub(r'<\s*(br|BR)\s*/?>', '\n', html_content)
        html = re.sub(r'</\s*(p|div|tr|h[1-6]|li|ul|ol|table|thead|tbody|tfoot)>', '\n', html)
        html = re.sub(r'<\s*li\s*>', '• ', html)
        text = re.sub(r'<[^>]+>', '', html)
        lines = [line.strip() for line in text.splitlines()]
        return [line for line in lines if line]
    except Exception as e:
        logger.error(f"HTML ni oddiy matnga o'tkazish xatosi: {e}")
        return []


def _generate_pdf_with_reportlab(title, lines):
    """Reportlab orqali oddiy PDF yaratish"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm
    except Exception as import_error:
        logger.error(f"Reportlab kutubxonasini import qilib bo'lmadi: {import_error}")
        return None
    
    try:
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        x_margin = 20 * mm
        y_margin = 20 * mm
        y_position = height - y_margin
        
        # Sarlavha
        if title:
            c.setFont("Helvetica-Bold", 14)
            c.drawString(x_margin, y_position, str(title))
            y_position -= 18
        
        c.setFont("Helvetica", 11)
        line_height = 13
        
        for raw_line in lines:
            wrapped_lines = textwrap.wrap(str(raw_line), width=90) or ['']
            for line in wrapped_lines:
                if y_position < y_margin:
                    c.showPage()
                    c.setFont("Helvetica", 11)
                    y_position = height - y_margin
                c.drawString(x_margin, y_position, line)
                y_position -= line_height
        
        c.save()
        buffer.seek(0)
        return buffer
    except Exception as e:
        logger.error(f"Reportlab orqali PDF yaratish xatosi: {e}")
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


def evaluate_students_from_matrix(file_path):
    """
    Excel matrix faylidan talabalarni Rasch modeliga asoslanib baholash
    T = 50 + 10Z formulasi bilan standart ball hisoblash
    
    Args:
        file_path: Excel fayl yo'li (.xlsx)
    
    Returns:
        list: Talabalar natijalari ro'yxati
        dict: Umumiy statistika
    """
    try:
        # Excel faylni yuklash
        wb = load_workbook(file_path)
        ws = wb.active
        
        # Header qatorini o'qish
        header_row = list(ws.iter_rows(min_row=1, max_row=1, values_only=True))[0]
        if not header_row:
            return None, None
        
        # Savollar sonini aniqlash (user_id dan tashqari)
        question_columns = [col for col in header_row[1:] if col and str(col).startswith('Q')]
        total_questions = len(question_columns)
        
        if total_questions == 0:
            return None, None
        
        # Response matrix yaratish
        response_matrix = []
        user_ids = []
        
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not row or not row[0]:  # user_id bo'sh bo'lsa, o'tkazib yuborish
                continue
            
            user_id = str(row[0])
            user_ids.append(user_id)
            responses = []
            
            # Javoblarni olish (1 yoki 0)
            for col_idx in range(1, min(len(row), total_questions + 1)):
                value = row[col_idx]
                if value is None:
                    responses.append(0)
                elif isinstance(value, (int, float)):
                    responses.append(1 if value == 1 else 0)
                elif isinstance(value, str):
                    responses.append(1 if value.strip() == '1' else 0)
                else:
                    responses.append(0)
            
            # Agar javoblar soni etarli bo'lmasa, 0 bilan to'ldirish
            while len(responses) < total_questions:
                responses.append(0)
            
            response_matrix.append(responses)
        
        if not response_matrix:
            return None, None
        
        # Response matrix ni numpy array ga aylantirish
        response_matrix = np.array(response_matrix)
        
        # Rasch modelini import qilish va baholash
        from rasch_pkg import evaluate_with_rasch
        
        # Rasch model orqali to'liq baholash (fit qilish)
        students_results, statistics = evaluate_with_rasch(response_matrix, user_ids)
        
        if students_results is None or statistics is None:
            logger.error("Rasch model baholash muvaffaqiyatsiz tugadi")
            return None, None
        
        return students_results, statistics
        
    except Exception as e:
        logger.error(f"Matrix baholash xatosi: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None, None


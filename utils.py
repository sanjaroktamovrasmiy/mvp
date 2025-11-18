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
    """0-1 matrix yaratish Excel formatida - ikkita alohida fayl
    
    Ikkita alohida Excel fayl yaratadi:
    1. matrix_1-40_*.xlsx - Questions 1-40 uchun
    2. matrix_41-43_*.xlsx - Questions 41-43 uchun
    
    Returns:
        tuple: (file_path_1_40, file_path_41_43, matrix_text) yoki (None, None, None)
    """
    try:
        # Test natijalarini to'plash
        test_results = [
            r for r_id, r in data.get('user_results', {}).items()
            if r.get('test_id') == test_id
        ]
        
        if not test_results:
            return None, None, None
        
        from openpyxl.styles import Font, Alignment
        
        matrix_dir = "matrices"
        os.makedirs(matrix_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        
        # ===== 1. Questions 1-40 uchun alohida Excel fayl =====
        wb_main = Workbook()
        
        # Standart sheetni o'chirish
        if 'Sheet' in wb_main.sheetnames:
            wb_main.remove(wb_main['Sheet'])
        
        ws_main = wb_main.create_sheet("Questions 1-40")
        
        # Header: user_id, Q1, Q2, ..., Q40
        main_header = ['user_id'] + [f'Q{i+1}' for i in range(40)]
        ws_main.append(main_header)
        
        # Header qatorini qalinlashtirish
        for cell in ws_main[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')
        
        # Har bir foydalanuvchi uchun qator (1-40 savollar)
        for result in test_results:
            user_id = result['user_id']
            row = [user_id]
            
            # Birinchi 40 ta savol (0-39 indices)
            for i, res in enumerate(result['results'][:40]):
                value = 1 if res.get('is_correct') else 0
                row.append(value)
            
            ws_main.append(row)
        
        # Birinchi faylni saqlash
        file_path_1_40 = os.path.join(matrix_dir, f"matrix_1-40_{test_id}_{timestamp}.xlsx")
        wb_main.save(file_path_1_40)
        
        # ===== 2. Questions 41-43 uchun alohida Excel fayl =====
        # Har bir kichik savol uchun alohida ustun
        wb_problem = Workbook()
        
        # Standart sheetni o'chirish
        if 'Sheet' in wb_problem.sheetnames:
            wb_problem.remove(wb_problem['Sheet'])
        
        ws_problem = wb_problem.create_sheet("Questions 41-43")
        
        # Header yaratish: Talabgor, 41.1, 41.2, ..., 43.n
        problem_header = ['Talabgor']
        
        # Testdan masalaviy savollar strukturasini olish
        test = data.get('tests', {}).get(test_id)
        if test and test.get('questions'):
            problem_questions = [q for q in test['questions'][40:43] if q.get('type') == 'problem']
            
            for q_idx, question in enumerate(problem_questions, start=41):
                sub_count = question.get('sub_question_count', 0)
                if sub_count > 0:
                    # Har bir kichik savol uchun ustun
                    for sub_idx in range(1, sub_count + 1):
                        problem_header.append(f"{q_idx}.{sub_idx}")
                else:
                    # Eski format - faqat Q41, Q42, Q43
                    problem_header.append(f"Q{q_idx}")
        
        ws_problem.append(problem_header)
        
        # Header qatorini qalinlashtirish
        for cell in ws_problem[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')
        
        # Har bir foydalanuvchi uchun qator (41-43 savollar)
        for result in test_results:
            user_id = result['user_id']
            
            # Foydalanuvchi ismini olish
            user_name = data.get('users', {}).get(str(user_id), {}).get('full_name', str(user_id))
            row = [user_name]
            
            # 41-43 savollar uchun javoblar (indices 40-42)
            problem_results = result['results'][40:43] if len(result['results']) > 40 else []
            
            for q_idx, res in enumerate(problem_results, start=41):
                if res.get('type') == 'problem' and 'sub_results' in res:
                    # Yangi format - har bir kichik javob uchun alohida ustun
                    for sub in res['sub_results']:
                        value = 1 if sub.get('is_correct') else 0
                        row.append(value)
                else:
                    # Eski format - sub_results ni qayta yaratish
                    # user_answer va correct_answer ni taqqoslash
                    if test and len(test.get('questions', [])) > 40:
                        original_q_idx = 40 + (q_idx - 41)
                        question = test['questions'][original_q_idx]
                        
                        # Testdan to'g'ri javoblar ro'yxatini olish
                        correct_answers = question.get('correct', [])
                        
                        # Foydalanuvchi javoblarini olish
                        user_answer = res.get('user_answer', '')
                        user_answers_list = [a.strip() for a in user_answer.split(',')] if user_answer else []
                        
                        # Har bir javobni taqqoslash
                        for i, correct_ans in enumerate(correct_answers):
                            if i < len(user_answers_list):
                                user_ans = user_answers_list[i]
                                is_sub_correct = user_ans.lower() == correct_ans.strip().lower()
                                row.append(1 if is_sub_correct else 0)
                            else:
                                # Javob berilmagan
                                row.append(0)
                    else:
                        # Test topilmasa, faqat umumiy natijani qo'shamiz
                        value = 1 if res.get('is_correct') else 0
                        row.append(value)
            
            ws_problem.append(row)
        
        # Ikkinchi faylni saqlash
        file_path_41_43 = os.path.join(matrix_dir, f"matrix_41-43_{test_id}_{timestamp}.xlsx")
        wb_problem.save(file_path_41_43)
        
        # Matn formatini ham saqlash (1-40 savollar uchun)
        matrix_lines = []
        matrix_lines.append('\t'.join(main_header))
        for result in test_results:
            user_id = result['user_id']
            row = [str(user_id)]
            for i, res in enumerate(result['results'][:40]):
                value = '1' if res.get('is_correct') else '0'
                row.append(value)
            matrix_lines.append('\t'.join(row))
        matrix_text = '\n'.join(matrix_lines)
        
        return file_path_1_40, file_path_41_43, matrix_text
        
    except Exception as e:
        logger.error(f"Matrix yaratish xatosi: {e}")
        return None, None, None



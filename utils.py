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
    """0-1 matrix yaratish Excel formatida (user_id, question1, question2, ...)
    
    Uchta alohida sheet yaratadi:
    1. Multiple Choice (1-35 savollar) - 0/1 formatida
    2. Text Answers (36-40 savollar) - javoblar matni
    3. Problem-based (41-43 savollar) - javoblar matni
    """
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
        
        # Standart sheetni o'chirish
        if 'Sheet' in wb.sheetnames:
            wb.remove(wb['Sheet'])
        
        from openpyxl.styles import Font, Alignment
        
        # 1. Multiple Choice (1-35 savollar) uchun sheet
        ws_mc = wb.create_sheet("Multiple Choice (1-35)")
        
        # Header: user_id, Q1, Q2, ..., Q35
        mc_header = ['user_id'] + [f'Q{i+1}' for i in range(35)]
        ws_mc.append(mc_header)
        
        # Header qatorini qalinlashtirish
        for cell in ws_mc[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')
        
        # Har bir foydalanuvchi uchun qator (faqat 1-35 savollar)
        for result in test_results:
            user_id = result['user_id']
            row = [user_id]
            
            # Faqat birinchi 35 ta savol (0-34 indices)
            for i, res in enumerate(result['results'][:35]):
                if res.get('is_correct') is None:
                    value = 'N/A'
                else:
                    value = 1 if res['is_correct'] else 0
                row.append(value)
            
            ws_mc.append(row)
        
        # 2. Text Answers (36-40 savollar) uchun sheet
        ws_text = wb.create_sheet("Text Answers (36-40)")
        
        # Header: user_id, Q36, Q37, ..., Q40, Q36_correct, Q37_correct, ...
        text_header = ['user_id']
        for i in range(36, 41):
            text_header.append(f'Q{i}_javob')
        for i in range(36, 41):
            text_header.append(f'Q{i}_tugri')
        ws_text.append(text_header)
        
        # Header qatorini qalinlashtirish
        for cell in ws_text[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')
        
        # Har bir foydalanuvchi uchun qator (36-40 savollar)
        for result in test_results:
            user_id = result['user_id']
            row = [user_id]
            
            # 36-40 savollar uchun javoblar (indices 35-39)
            text_results = result['results'][35:40] if len(result['results']) > 35 else []
            
            # Foydalanuvchi javoblari
            for res in text_results:
                user_answer = res.get('user_answer', '')
                row.append(user_answer)
            
            # To'g'ri javoblar
            for res in text_results:
                correct_answer = res.get('correct_answer', '')
                row.append(correct_answer)
            
            ws_text.append(row)
        
        # 3. Problem-based (41-43 savollar) uchun sheet
        ws_problem = wb.create_sheet("Problems (41-43)")
        
        # Header: user_id, Q41, Q42, Q43, Q41_correct, Q42_correct, Q43_correct
        problem_header = ['user_id']
        for i in range(41, 44):
            problem_header.append(f'Q{i}_javob')
        for i in range(41, 44):
            problem_header.append(f'Q{i}_tugri')
        ws_problem.append(problem_header)
        
        # Header qatorini qalinlashtirish
        for cell in ws_problem[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')
        
        # Har bir foydalanuvchi uchun qator (41-43 savollar)
        for result in test_results:
            user_id = result['user_id']
            row = [user_id]
            
            # 41-43 savollar uchun javoblar (indices 40-42)
            problem_results = result['results'][40:43] if len(result['results']) > 40 else []
            
            # Foydalanuvchi javoblari
            for res in problem_results:
                user_answer = res.get('user_answer', '')
                row.append(user_answer)
            
            # To'g'ri javoblar
            for res in problem_results:
                correct_answer = res.get('correct_answer', '')
                row.append(correct_answer)
            
            ws_problem.append(row)
        
        # Matn formatini ham saqlash (faqat Multiple Choice uchun)
        matrix_lines = []
        matrix_lines.append('\t'.join(mc_header))
        for result in test_results:
            user_id = result['user_id']
            row = [str(user_id)]
            for i, res in enumerate(result['results'][:35]):
                if res.get('is_correct') is None:
                    value = 'N/A'
                else:
                    value = '1' if res['is_correct'] else '0'
                row.append(value)
            matrix_lines.append('\t'.join(row))
        matrix_text = '\n'.join(matrix_lines)
        
        # Excel fayl sifatida saqlash
        matrix_dir = "matrices"
        os.makedirs(matrix_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        matrix_file_path = os.path.join(matrix_dir, f"matrix_{test_id}_{timestamp}.xlsx")
        
        wb.save(matrix_file_path)
        
        return matrix_file_path, matrix_text
        
    except Exception as e:
        logger.error(f"Matrix yaratish xatosi: {e}")
        return None, None



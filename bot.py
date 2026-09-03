import os
import io
import json
import logging
from datetime import datetime
from flask import Flask, render_template_string, send_from_directory
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler

# ReportLab kutubxonasi (PDF jadval yaratish)
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(name)

# Environment Variable orqali olinadigan o'zgaruvchilar
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID", "-100XXXXXXXXXX")

BOM = {
    "Kalla": 1, "Oyoq": 4, "Kalla kichgina": 2, "Qol": 2, "Qol tagi": 2,
    "Sdina T": 1, "Sdina": 1, "Sdina tagi": 2, "Kashak katta": 1, "Kashak kichgina": 2,
    "20 lik truba": 2, "13 lik truba": 3, "Zontik": 2, "Zontik tagi": 2, "Ilgich": 4
}

# --- PDF GENERATOR (JADVAL SHAKLIDA) ---

def generate_pdf_report(period_title, report_data):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#0f172a'),
        alignment=1,
        spaceAfter=10
    )

    subtitle_style = ParagraphStyle(
        'SubTitleStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#64748b'),
        alignment=1,
        spaceAfter=15
    )

    elements.append(Paragraph("AROM ENTERPRISE", title_style))
    elements.append(Paragraph(f"Laser Cutting Data Center — {period_title} Hisoboti", title_style))
    elements.append(Paragraph(f"Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}", subtitle_style))
    elements.append(Spacer(1, 10))

    table_data = [
        ["№", "Detal Nomi", "BOM Norma", "Kesilgan Soni", "Tayyor Komplekt"]
    ]

    idx = 1
    total_cut = 0
    for part, norm in report_data.items():
        cut_qty = 120 * norm
        ready_sets = cut_qty // norm
        total_cut += cut_qty
        table_data.append([str(idx), part, f"{norm} ta", f"{cut_qty} dona", f"{ready_sets} ta"])
        idx += 1

    table_data.append(["", "JAMI KESILGAN DETALLAR:", "", f"{total_cut} dona", ""])

    t = Table(table_data, colWidths=[25, 175, 80, 100, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -2), colors.HexColor('#f8fafc')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e2e8f0')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))

    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- FLASK WEB SERVER ---

@app.route('/')
def index():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return render_template_string(f.read())
    except Exception as e:
        return f"Xatolik: {e}", 500

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

# --- TELEGRAM BOT LOGIKASI ---

async def send_auto_daily_report(bot):
    """Har kuni soat 20:00 da guruhga avto kunlik hisobot yuborish"""
    pdf_buffer = generate_pdf_report("Kunlik (Avto)", BOM)
    await bot.send_document(
        chat_id=GROUP_CHAT_ID,
        document=InputFile(pdf_buffer, filename=f"Kunlik_Hisobot_{datetime.now().strftime('%Y_%m_%d')}.pdf"),
        caption="📊 AROM Enterprise\nBugungi kunlik hisobot PDF formatda shakllantirildi."
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salom! ⚙️ AROM Laser Data Center Mini App'dan foydalanishingiz mumkin.")

async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = json.loads(update.effective_message.web_app_data.data)
    action = data.get("action")

    if action in ["generate_report_pdf", "report"]:
        period = data.get("period", "today")
        period_map = {
            "today": "Kunlik",
            "week": "Haftalik",
            "month": "Oylik",
            "6months": "6 Oylik",
            "year": "1 Yillik"
        }
        title = period_map.get(period, "Davriy")
        pdf_buffer = generate_pdf_report(title, BOM)
        
        await context.bot.send_document(
            chat_id=GROUP_CHAT_ID,
            document=InputFile(pdf_buffer, filename=f"{title}_Hisobot_{datetime.now().strftime('%Y_%m_%d')}.pdf"),
            caption=f"📄 AROM Laser Data Center\n{title} hisoboti guruhga yuborildi."
        )
        await update.message.reply_text(f"✅ {title} hisoboti Telegram guruhiga PDF formatda yuborildi!")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    
    # WebApp data qabul qiluvchi handler yangilandi:
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))

    # Avto-hisobot (Har kuni soat 20:00 da)
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        lambda: application.job_queue.run_once(lambda ctx: send_auto_daily_report(ctx.bot), 0),
        'cron', hour=20, minute=0
    )
    scheduler.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

if name == 'main':
    main()

from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas


def _build_overlay(page_width, page_height, lines):
    """Create a visible diagonal watermark overlay for a single page."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(page_width, page_height))

    try:
        pdf.setFillAlpha(0.14)
    except Exception:
        pass

    pdf.saveState()
    pdf.translate(page_width / 2, page_height / 2)
    pdf.rotate(35)
    pdf.setFillColor(Color(0.75, 0.1, 0.1, alpha=0.14))
    pdf.setFont("Helvetica-Bold", 24)

    y = 26
    for line in lines:
        pdf.drawCentredString(0, y, line)
        y -= 30
    pdf.restoreState()

    pdf.saveState()
    pdf.setFillColor(Color(0.2, 0.2, 0.2, alpha=0.8))
    pdf.setFont("Helvetica", 9)
    footer_y = 22
    for line in lines:
        pdf.drawString(24, footer_y, line)
        footer_y += 11
    pdf.restoreState()

    pdf.save()
    buffer.seek(0)
    return buffer


def add_watermark_to_pdf_stream(pdf_bytes, download_time, downloader_name, directory_name):
    """Return PDF bytes with a visible watermark on every page."""
    if not pdf_bytes:
        return pdf_bytes

    reader = PdfReader(BytesIO(pdf_bytes))
    writer = PdfWriter()
    timestamp = download_time.strftime("%Y-%m-%d %H:%M:%S")
    watermark_lines = [
        "PPAA RMS CONFIDENTIAL",
        f"Downloaded by: {downloader_name}",
        f"Department: {directory_name}",
        f"Downloaded at: {timestamp}",
    ]

    for page in reader.pages:
        overlay_stream = _build_overlay(
            float(page.mediabox.width),
            float(page.mediabox.height),
            watermark_lines,
        )
        overlay_page = PdfReader(overlay_stream).pages[0]
        page.merge_page(overlay_page)
        writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()

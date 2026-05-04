"""Apply a visible security watermark to RMS PDF downloads (pypdf + reportlab)."""

from __future__ import annotations

import logging
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)


def watermark_rms_pdf_download(
    pdf_bytes: bytes,
    *,
    user_display: str,
    department: str,
    report_ref: str,
    downloaded_at: str,
) -> bytes:
    """
    Overlay semi-transparent diagonal text on every page.
    Falls back to original bytes if anything fails.
    """
    if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
        return pdf_bytes

    lines = [
        "PPAA INTERNAL PORTAL",
        f"Downloaded: {downloaded_at}",
        f"User: {user_display or '—'}",
    ]
    if department:
        lines.append(f"Department: {department}")
    if report_ref:
        lines.append(f"Report ref: {report_ref}")
    lines.append("Confidential — internal use only")

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                logger.warning("Encrypted PDF; skipping watermark")
                return pdf_bytes

        writer = PdfWriter()
        for page in reader.pages:
            w = float(page.mediabox.width)
            h = float(page.mediabox.height)
            packet = BytesIO()
            c = canvas.Canvas(packet, pagesize=(w, h))
            # Primary block — larger type + higher contrast so the mark reads in viewers/print.
            c.saveState()
            c.setFillColor(Color(0.28, 0.28, 0.28, alpha=0.58))
            c.setFont("Helvetica-Bold", 11)
            c.translate(w / 2, h / 2)
            c.rotate(36)
            y = 54
            for line in lines:
                c.drawCentredString(0, y, (line or "")[:140])
                y -= 14
            c.restoreState()
            # Secondary stamp toward a corner so pages with busy centres still show a mark.
            c.saveState()
            c.setFillColor(Color(0.42, 0.42, 0.42, alpha=0.42))
            c.setFont("Helvetica-Bold", 8)
            c.translate(w * 0.86, h * 0.14)
            c.rotate(36)
            c.drawCentredString(0, 0, "PPAA — INTERNAL")
            c.restoreState()
            c.save()
            packet.seek(0)
            wmark = PdfReader(packet)
            page.merge_page(wmark.pages[0])
            writer.add_page(page)

        out = BytesIO()
        writer.write(out)
        return out.getvalue()
    except Exception:
        logger.exception("RMS PDF watermark failed; serving original file")
        return pdf_bytes

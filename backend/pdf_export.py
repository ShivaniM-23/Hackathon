"""
ShadowTrace AI — pdf_export.py
Generates a professional PDF due diligence report using ReportLab.
"""

import os
import uuid
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


RISK_COLORS = {
    "HIGH": colors.HexColor("#E24B4A"),
    "MEDIUM": colors.HexColor("#BA7517"),
    "LOW": colors.HexColor("#1D9E75"),
}

OUTPUT_DIR = "/tmp/shadowtrace_reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)


async def generate_pdf_report(report: dict) -> str:
    """
    Generates a PDF report and returns the file path.
    Falls back to plain text if ReportLab is unavailable.
    """
    if not REPORTLAB_AVAILABLE:
        logger.warning("ReportLab not available. Falling back to plain text report.")
        return await _generate_text_fallback(report)

    filename = os.path.join(OUTPUT_DIR, f"report_{uuid.uuid4().hex[:8]}.pdf")
    try:
        _build_pdf(report, filename)
        return filename
    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}")
        return await _generate_text_fallback(report)


def _build_pdf(report: dict, filename: str):
    doc = SimpleDocTemplate(
        filename, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    story = []
    risk = report.get("risk_level", "UNKNOWN")
    risk_color = RISK_COLORS.get(risk, colors.gray)

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph(
        "<font size=22><b>ShadowTrace AI</b></font><br/><font size=12 color='#888780'>Due Diligence Report</font>",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#D3D1C7")))
    story.append(Spacer(1, 0.4*cm))

    # ── Company + Score ───────────────────────────────────────────────────────
    company_name = report.get("company_name", "Unknown")
    score = report.get("trust_score", 0)

    story.append(Paragraph(f"<b>{company_name}</b>", ParagraphStyle(
        "CompanyTitle", parent=styles["Normal"], fontSize=18, spaceAfter=4,
    )))
    story.append(Paragraph(
        f"Trust Score: <b><font color='{risk_color.hexval() if hasattr(risk_color, 'hexval') else '#333'}'>{score}/100 — {risk} RISK</font></b>",
        ParagraphStyle("Score", parent=styles["Normal"], fontSize=13, spaceAfter=8),
    ))
    story.append(Paragraph(
        f"Report generated: {datetime.now().strftime('%d %B %Y, %H:%M')} IST",
        ParagraphStyle("Meta", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#888780"), spaceAfter=16),
    ))

    # ── Contradictions table ──────────────────────────────────────────────────
    story.append(Paragraph("<b>Contradiction Analysis</b>", ParagraphStyle(
        "H2", parent=styles["Normal"], fontSize=13, spaceBefore=12, spaceAfter=8,
    )))

    contradictions = report.get("contradictions", [])
    if contradictions:
        table_data = [["Claim", "Evidence", "Status", "Severity"]]
        for c in contradictions:
            status = c.get("status", "UNVERIFIED")
            status_color = "#E24B4A" if status == "MISMATCH" else "#BA7517" if status == "UNVERIFIED" else "#1D9E75"
            table_data.append([
                Paragraph(c.get("claim", ""), styles["Normal"]),
                Paragraph(c.get("evidence", ""), styles["Normal"]),
                Paragraph(f"<font color='{status_color}'><b>{status}</b></font>", styles["Normal"]),
                c.get("severity", "LOW"),
            ])

        t = Table(table_data, colWidths=[4.5*cm, 7*cm, 3*cm, 2.5*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1EFE8")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D3D1C7")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9F8F5")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No contradictions detected.", styles["Normal"]))

    # ── Red flags ─────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("<b>Red Flags</b>", ParagraphStyle(
        "H2", parent=styles["Normal"], fontSize=13, spaceBefore=8, spaceAfter=8,
    )))
    red_flags = report.get("red_flags", [])
    if red_flags:
        for flag in red_flags:
            story.append(Paragraph(
                f"• {flag}",
                ParagraphStyle("Flag", parent=styles["Normal"], fontSize=10, spaceAfter=4,
                               textColor=colors.HexColor("#A32D2D")),
            ))
    else:
        story.append(Paragraph("No major red flags identified.", styles["Normal"]))

    # ── Score breakdown ───────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("<b>Score Breakdown</b>", ParagraphStyle(
        "H2", parent=styles["Normal"], fontSize=13, spaceBefore=8, spaceAfter=8,
    )))
    breakdown = report.get("score_breakdown", {})
    if breakdown:
        bd_data = [["Factor", "Score", "Max"]]
        for factor, val in breakdown.items():
            if isinstance(val, dict):
                bd_data.append([factor.replace("_", " ").title(), str(val.get("score", 0)), str(val.get("max", 0))])
            else:
                bd_data.append([factor.replace("_", " ").title(), str(val), "—"])

        bt = Table(bd_data, colWidths=[9*cm, 3*cm, 3*cm])
        bt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1EFE8")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D3D1C7")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9F8F5")]),
        ]))
        story.append(bt)

    # ── Disclaimer ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#D3D1C7")))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "DISCLAIMER: This report is AI-generated for informational purposes only and does not constitute legal, financial, or professional advice. "
        "ShadowTrace AI makes no warranties about the accuracy or completeness of this analysis. "
        "Always verify critical information independently before making business decisions.",
        ParagraphStyle("Disclaimer", parent=styles["Normal"], fontSize=8,
                       textColor=colors.HexColor("#888780"), spaceAfter=4),
    ))

    doc.build(story)


async def _generate_text_fallback(report: dict) -> str:
    """Plain text report when ReportLab is not installed."""
    filename = os.path.join(OUTPUT_DIR, f"report_{uuid.uuid4().hex[:8]}.txt")
    with open(filename, "w") as f:
        f.write(f"SHADOWTRACE AI — DUE DILIGENCE REPORT\n{'='*60}\n\n")
        f.write(f"Company: {report.get('company_name', 'Unknown')}\n")
        f.write(f"Trust Score: {report.get('trust_score', 0)}/100 — {report.get('risk_level', 'UNKNOWN')} RISK\n\n")
        f.write("CONTRADICTIONS:\n")
        for c in report.get("contradictions", []):
            f.write(f"  [{c.get('status')}] {c.get('claim')} → {c.get('evidence')}\n")
        f.write("\nRED FLAGS:\n")
        for flag in report.get("red_flags", []):
            f.write(f"  • {flag}\n")
        f.write("\n\nDISCLAIMER: AI-generated report for informational purposes only.\n")
    return filename

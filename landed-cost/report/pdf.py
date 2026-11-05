"""A4 한 장 착지가 견적 리포트 (reportlab)."""
from __future__ import annotations

import io
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
INK = colors.HexColor("#14263b")
MUTED = colors.HexColor("#5b6b7f")
RULE = colors.HexColor("#c9cfc7")
TINT = colors.HexColor("#eef1ea")
ACCENT = colors.HexColor("#b97a10")


def _fonts():
    if "KR" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("KR", str(FONTS / "NotoSansKR-Regular-subset.ttf")))
        pdfmetrics.registerFont(TTFont("KR-Bold", str(FONTS / "NotoSansKR-Bold-subset.ttf")))


def _fmt(value, places=0):
    return f"{value:,.{places}f}"


def build_pdf(*, product: str, hs6: str, hs_name: str, quantity, input_currency: str,
              rows: list[dict], detail: dict, rates_note: str, caveats: list[str]) -> bytes:
    """rows: 국가 비교 [{name, currency, duty_rate, landed_local, landed_krw, per_unit_krw, flag}]
    detail: 1순위 국가 {name, currency, lines:[(label, amount_local, note)], landed_local, landed_krw}
    """
    _fonts()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=12 * mm,
                            title="수출 착지가 견적", author="Landed Cost Calculator")
    st = lambda size, color=INK, bold=False, lead=None: ParagraphStyle(
        "s", fontName="KR-Bold" if bold else "KR", fontSize=size, leading=lead or size * 1.45, textColor=color)
    story = [
        Paragraph("수출 착지가 견적", st(17, bold=True)),
        Paragraph(f"{date.today().isoformat()} 작성 · {rates_note}", st(8.5, MUTED)),
        Spacer(1, 5 * mm),
        Table([["제품", product], ["HS 코드", f"{hs6[:4]}.{hs6[4:]} {hs_name}"], ["수량", f"{_fmt(quantity)}개"], ["입력 통화", input_currency]],
              colWidths=[26 * mm, 120 * mm], hAlign="LEFT", style=TableStyle([
                  ("FONT", (0, 0), (-1, -1), "KR", 9), ("FONT", (0, 0), (0, -1), "KR-Bold", 9),
                  ("TEXTCOLOR", (0, 0), (0, -1), MUTED), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, -1), 2),
                  ("LINEBELOW", (0, -1), (-1, -1), 0.6, RULE)])),
        Spacer(1, 5 * mm),
        Paragraph("목적지별 착지가 비교", st(11.5, bold=True)),
        Spacer(1, 2 * mm),
    ]
    head = ["목적지", "관세율", "착지가(현지 통화)", "착지가(원)", "개당(원)"]
    body = [[r["name"] + (" *" if r.get("flag") else ""), r["duty_rate"], f"{_fmt(r['landed_local'], 2)} {r['currency']}",
             _fmt(r["landed_krw"]), _fmt(r["per_unit_krw"], 1)] for r in rows]
    t = Table([head] + body, colWidths=[52 * mm, 20 * mm, 42 * mm, 33 * mm, 31 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "KR", 8.5), ("FONT", (0, 0), (-1, 0), "KR-Bold", 8.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("LINEBELOW", (0, 1), (-1, -1), 0.4, RULE),
        ("BACKGROUND", (0, 1), (-1, 1), TINT), ("FONT", (0, 1), (-1, 1), "KR-Bold", 8.5),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story += [t, Paragraph("첫 줄이 개당 착지가가 가장 낮은 목적지입니다. * 표시는 세율·세금 정보에 확인이 필요한 목적지입니다.", st(7.5, MUTED)),
              Spacer(1, 5 * mm), Paragraph(f"계산 과정 · {detail['name']}", st(11.5, bold=True)), Spacer(1, 2 * mm)]
    lines = [[label, f"{_fmt(amount, 2)} {detail['currency']}", note] for label, amount, note in detail["lines"]]
    lines.append(["착지가", f"{_fmt(detail['landed_local'], 2)} {detail['currency']}", f"{_fmt(detail['landed_krw'])}원"])
    t2 = Table(lines, colWidths=[38 * mm, 42 * mm, 98 * mm], hAlign="LEFT")
    t2.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "KR", 8.5), ("TEXTCOLOR", (2, 0), (2, -1), MUTED), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, RULE), ("LINEABOVE", (0, -1), (-1, -1), 1, INK),
        ("FONT", (0, -1), (1, -1), "KR-Bold", 9.5), ("TEXTCOLOR", (0, -1), (1, -1), ACCENT),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    story += [t2, Spacer(1, 5 * mm), Paragraph("확인할 점", st(10, bold=True))]
    story += [Paragraph("· " + c, st(8, MUTED, lead=11.5)) for c in caveats]
    doc.build(story)
    return buf.getvalue()

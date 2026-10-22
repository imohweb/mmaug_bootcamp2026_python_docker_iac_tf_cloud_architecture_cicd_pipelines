#!/usr/bin/env python3
"""Build the participant PDF from Markdown with ReportLab (documentation only).

Run from any directory: python3 scripts/build-participant-pdf.py
Each ## heading starts one slide. Supported content: paragraphs, bullets,
fenced code, > takeaways and the {{architecture}} vector-diagram marker.
"""

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
)
from reportlab.pdfbase.pdfmetrics import stringWidth

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/participant-slides.md"
OUTPUT = ROOT / "docs/MMAUG_Python_docker_terraform_Fundamentals_Participant.pdf"
NAVY = colors.HexColor("#142D4E")
TEAL = colors.HexColor("#007F86")
INK = colors.HexColor("#28384C")
PALE = colors.HexColor("#EDF5F8")
WIDTH, HEIGHT = 960, 540

TITLE = ParagraphStyle(
    "title", fontName="Helvetica-Bold", fontSize=29, leading=34,
    textColor=NAVY, spaceAfter=20,
)
BODY = ParagraphStyle(
    "body", fontName="Helvetica", fontSize=17, leading=24,
    textColor=INK, spaceAfter=12,
)
BULLET = ParagraphStyle(
    "bullet", parent=BODY, leftIndent=15, firstLineIndent=-15, spaceAfter=9,
)
CODE = ParagraphStyle(
    "code", fontName="Courier", fontSize=12.5, leading=18,
    textColor=NAVY, backColor=PALE, borderPadding=10, spaceBefore=4, spaceAfter=14,
)
TAKEAWAY = ParagraphStyle(
    "takeaway", parent=BODY, fontName="Helvetica-Bold", fontSize=13,
    leading=19, textColor=TEAL, spaceBefore=12, spaceAfter=0,
)


class OneSlide(Flowable):
    """Reject overflow before an accidental extra page is written."""

    def __init__(self, parts: list[Flowable], title: str):
        super().__init__()
        self.parts = parts
        self.title = title
        self.layout: list[tuple[Flowable, float, float]] = []

    def wrap(self, available_width: float, available_height: float):
        self.layout = []
        total = 0
        for part in self.parts:
            before, after = part.getSpaceBefore(), part.getSpaceAfter()
            width, height = part.wrap(available_width, available_height)
            if width > available_width + 0.1:
                raise ValueError(f"Slide {self.title!r}: content is too wide.")
            total += before + height + after
            self.layout.append((part, height, before))
        if total > available_height:
            raise ValueError(
                f"Slide {self.title!r}: needs {total:.0f}pt; "
                f"only {available_height:.0f}pt available. Shorten or split it."
            )
        self.width, self.height = available_width, total
        return self.width, self.height

    def draw(self):
        y = self.height
        for part, height, before in self.layout:
            y -= before + height
            part.drawOn(self.canv, 0, y)
            y -= part.getSpaceAfter()


def architecture() -> Drawing:
    drawing = Drawing(840, 265)

    def box(x: int, y: int, width: int, label: str):
        drawing.add(Rect(x, y, width, 56, rx=8, fillColor=PALE, strokeColor=TEAL))
        lines = label.split("\n")
        for index, text in enumerate(lines):
            drawing.add(String(
                x + width / 2, y + 34 - 16 * index, text,
                fontName="Helvetica-Bold", fontSize=13,
                textAnchor="middle", fillColor=NAVY,
            ))

    def arrow(x1: int, y1: int, x2: int, y2: int):
        drawing.add(Line(x1, y1, x2, y2, strokeColor=TEAL, strokeWidth=1.5))
        if x2 > x1:
            points = [x2, y2, x2 - 7, y2 + 4, x2 - 7, y2 - 4]
        else:
            points = [x2, y2, x2 - 4, y2 + 7, x2 + 4, y2 + 7]
        drawing.add(Polygon(points, fillColor=TEAL, strokeColor=TEAL))

    box(0, 170, 190, "Customer portal\nTicket ID + access key")
    box(0, 62, 190, "Specialist console\nReview / approve")
    box(290, 116, 240, "Two App Service web apps\nReact proxy + Flask backend")
    box(290, 208, 240, "Container Registry\nImmutable image digest")
    box(640, 200, 200, "Blob: knowledge\nMarkdown sources")
    box(640, 108, 200, "Blob: tickets\nJSON + ETag updates")
    box(640, 16, 200, "Foundry + AI Search\nIndexed knowledge / agent")
    arrow(190, 198, 290, 155)
    arrow(190, 90, 290, 135)
    arrow(410, 208, 410, 172)
    arrow(530, 155, 640, 228)
    arrow(530, 144, 640, 136)
    arrow(530, 132, 640, 44)
    drawing.add(String(
        410, 80, "Existing RG-MMAUG-Bootcamp",
        fontName="Helvetica", fontSize=12, textAnchor="middle", fillColor=TEAL,
    ))
    return drawing


def slide_parts(title: str, lines: list[str]) -> list[Flowable]:
    parts: list[Flowable] = [Paragraph(escape(title), TITLE)]
    paragraph: list[str] = []
    code: list[str] | None = None

    def flush():
        if paragraph:
            parts.append(Paragraph(escape(" ".join(paragraph)), BODY))
            paragraph.clear()

    for line in lines:
        if line.startswith("```"):
            flush()
            if code is None:
                code = []
            else:
                # Preformatted does not wrap long lines. Fail instead of clipping.
                for text in code:
                    if stringWidth(text, CODE.fontName, CODE.fontSize) > 820:
                        raise ValueError(f"Slide {title!r}: split long code line: {text}")
                parts.append(Preformatted("\n".join(code), CODE))
                code = None
        elif code is not None:
            code.append(line)
        elif line == "{{architecture}}":
            flush()
            parts.append(architecture())
        elif line.startswith("- "):
            flush()
            parts.append(Paragraph("- " + escape(line[2:]), BULLET))
        elif line.startswith("> "):
            flush()
            parts.append(Paragraph(escape(line[2:]), TAKEAWAY))
        elif line.strip():
            paragraph.append(line.strip())
        else:
            flush()
    if code is not None:
        raise ValueError(f"Slide {title!r}: unclosed code fence.")
    flush()
    return parts


def page_chrome(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, HEIGHT - 43, WIDTH, 43, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(48, HEIGHT - 27, "MMAUG / 27 OCTOBER 2026 / CUSTOMER SUPPORT AGENT")
    canvas.setStrokeColor(TEAL)
    canvas.line(48, 37, WIDTH - 48, 37)
    canvas.setFillColor(INK)
    canvas.setFont("Helvetica", 10)
    canvas.drawString(48, 21, "Imoh Etuk | MMAUG | Learn. Innovate. Build.")
    canvas.drawRightString(WIDTH - 48, 21, f"{doc.page:02d}")
    canvas.restoreState()


def main() -> None:
    slides: list[tuple[str, list[str]]] = []
    for line in SOURCE.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            slides.append((line[3:], []))
        elif slides:
            slides[-1][1].append(line)
        elif line.strip() and not line.startswith("# "):
            raise ValueError("Content before the first slide heading.")
    if not slides:
        raise ValueError("No slide headings found.")
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=(WIDTH, HEIGHT),
        leftMargin=48, rightMargin=48, topMargin=65, bottomMargin=53,
        title="MMAUG Bootcamp 2026 | Customer Support Agent | 27 October",
        author="Imoh Etuk | MMAUG",
        subject="React, Flask, Blob Storage, App Service, Terraform and CI/CD",
    )
    story: list[Flowable] = []
    for index, (title, lines) in enumerate(slides):
        if index:
            story.append(PageBreak())
        story.append(OneSlide(slide_parts(title, lines), title))
    document.build(story, onFirstPage=page_chrome, onLaterPages=page_chrome)
    if document.page != len(slides):
        raise ValueError(f"Expected {len(slides)} pages, got {document.page}.")
    OUTPUT.write_bytes(buffer.getvalue())
    print(f"Built {OUTPUT.relative_to(ROOT)} ({len(slides)} slides).")


if __name__ == "__main__":
    main()

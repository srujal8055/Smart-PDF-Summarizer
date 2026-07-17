import io
import re

from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_pdf_report(filename: str, summary_type: str, summary_content: str) -> io.BytesIO:
    """
    Generates a beautifully styled PDF report of the summary using ReportLab.
    
    Args:
        filename: Source PDF document name.
        summary_type: The format of summary (e.g. Executive Summary).
        summary_content: The markdown summary text.
        
    Returns:
        BytesIO stream of the PDF file.
    """
    buffer = io.BytesIO()
    
    # Page setup
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    story = []
    
    # Custom styles
    title_style = ParagraphStyle(
        name='DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=colors.HexColor('#1E3A8A'),  # Deep Blue
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        name='DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=12,
        leading=14,
        textColor=colors.HexColor('#4B5563'),  # Gray
        spaceAfter=15
    )
    
    meta_style = ParagraphStyle(
        name='MetaText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=12,
        textColor=colors.HexColor('#374151'),
        spaceAfter=4
    )
    
    heading2_style = ParagraphStyle(
        name='SummaryHeading2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#2563EB'),  # Royal Blue
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        name='SummaryBody',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor('#1F2937'),
        spaceAfter=8
    )
    
    bullet_style = ParagraphStyle(
        name='SummaryBullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#1F2937'),
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    )

    # 1. Title Block
    story.append(Paragraph("Multi-Format PDF Summarization Studio", title_style))
    story.append(Paragraph(f"Generated Analysis Report: {summary_type}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E5E7EB'), spaceBefore=0, spaceAfter=15))
    
    # 2. Metadata Section
    story.append(Paragraph(f"<b>Source Document:</b> {filename}", meta_style))
    story.append(Paragraph(f"<b>Report Format:</b> {summary_type}", meta_style))
    story.append(Paragraph(f"<b>Generation Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", meta_style))
    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#D1D5DB'), spaceBefore=0, spaceAfter=15))
    
    # 3. Parse Markdown Content and Append to Story
    # We implement a simple Markdown to PDF styling translator
    lines = summary_content.split('\n')
    in_list = False
    
    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            story.append(Spacer(1, 4))
            continue
            
        # Parse headings (e.g. ## Title)
        if stripped_line.startswith('#'):
            # Count the header level
            level = len(stripped_line) - len(stripped_line.lstrip('#'))
            header_text = stripped_line.lstrip('#').strip()
            
            # Highlight with dynamic styling
            h_style = ParagraphStyle(
                name=f'Heading{level}_{datetime.now().microsecond}',
                parent=heading2_style,
                fontSize=max(11, 16 - level),
                leading=max(14, 20 - level),
                spaceBefore=10,
                spaceAfter=5
            )
            story.append(Paragraph(header_text, h_style))
            
        # Parse list items (e.g. * Item, - Item, - [ ] Item)
        elif stripped_line.startswith(('* ', '- ', '- [ ] ', '- [x] ')):
            bullet_text = stripped_line
            # Strip standard checkmarks or list markdown symbols
            if stripped_line.startswith('* '):
                bullet_text = stripped_line[2:]
            elif stripped_line.startswith('- '):
                # Check for checklist item
                if stripped_line.startswith('- [ ] '):
                    bullet_text = f"[ ] {stripped_line[6:]}"
                elif stripped_line.startswith('- [x] '):
                    bullet_text = f"[x] {stripped_line[6:]}"
                else:
                    bullet_text = stripped_line[2:]
            
            # Format text formatting inside bullets (bold/italic)
            bullet_text = format_markdown_inline(bullet_text)
            story.append(Paragraph(f"&bull; {bullet_text}", bullet_style))
            
        else:
            # Paragraph text
            p_text = format_markdown_inline(stripped_line)
            story.append(Paragraph(p_text, body_style))
            
    # Build Document
    doc.build(story)
    buffer.seek(0)
    return buffer

def format_markdown_inline(text: str) -> str:
    """Helper to convert basic markdown inline tokens (**bold**, *italic*) to HTML tags."""
    # Convert bold (**text** or __text__)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
    # Convert italic (*text* or _text_)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    text = re.sub(r'_(.*?)_', r'<i>\1</i>', text)
    # Escape ampersand
    text = text.replace("&", "&amp;")
    # Fix nested ampersands inside HTML entities
    text = text.replace("&amp;bull;", "&bull;")
    text = text.replace("&amp;lt;", "&lt;")
    text = text.replace("&amp;gt;", "&gt;")
    return text

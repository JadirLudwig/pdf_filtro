import fitz # PyMuPDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from io import BytesIO
import re

def parse_page_ranges(range_str):
    pages = set()
    if not range_str.strip():
        return pages
    for part in range_str.replace(" ", "").split(","):
        if "-" in part:
            try:
                start, end = part.split("-")
                pages.update(range(int(start), int(end) + 1))
            except: pass
        elif part.isdigit():
            pages.add(int(part))
    return pages

def get_font_stats(pdf_stream, ignore_pages_str=""):
    """
    Analisa o PDF e retorna um dicionário de tamanhos de fonte encontrados
    e um exemplo de texto para cada.
    """
    doc = fitz.open(stream=pdf_stream, filetype="pdf")
    pages_to_ignore = parse_page_ranges(ignore_pages_str)
    stats = {}
    
    for page_idx, page in enumerate(doc):
        if (page_idx + 1) in pages_to_ignore:
            continue
            
        blocks = page.get_text("dict", flags=11).get("blocks", [])
        for b in blocks:
            for l in b.get("lines", []):
                for s in l.get("spans", []):
                    size = round(s["size"], 1)
                    text = s["text"].strip()
                    if text:
                        if size not in stats:
                            stats[size] = {"count": 0, "sample": text[:100]}
                        stats[size]["count"] += len(text)
    doc.close()
    return stats

def clean_text(text, abbreviations, is_title, inject_title_pauses, inject_normal_pauses):
    # Regex substitutions for abbreviations
    for item in abbreviations:
        origem = item.get('origem', '')
        destino = item.get('destino', '')
        if origem and destino:
            # We can use direct replace or word boundary regex depending on precision needed.
            # Using simple text.replace for exact matches
            text = text.replace(origem, destino)
    
    if is_title and inject_title_pauses:
        # Títulos normalmente não tem ponto no final
        text = text.strip()
        if text and text[-1] not in ['.', ';', '!', '?', ':']:
            text += " . " # Adiciona pausas sutis reconhecíveis pelo TTS (depende da engine, mas ". " geralmente serve)
    
    if not is_title and inject_normal_pauses:
        # Trocar ; por ponto ou adicionar quebra invisivel para forçar pausa maior no TTS
        text = text.replace("; ", ".\n\n").replace(". ", ".\n\n")
        
    return text

def process_pdf(pdf_stream, top_margin_perc, bottom_margin_perc, abbreviations, inject_title_pauses, inject_normal_pauses, ignore_pages_str="", force_pages_str="", output_format="pdf", allowed_font_sizes=None):
    """
    Realiza o parse do PDF injetado via streamlit.
    Detecta fontes, limpa o texto baseando se a linha é título/capítulo
    e recria o documento via ReportLab.
    """
    doc = fitz.open(stream=pdf_stream, filetype="pdf")
    
    pages_to_ignore = parse_page_ranges(ignore_pages_str)
    pages_to_force = parse_page_ranges(force_pages_str)
    
    # 1. Determinar o tamanho de fonte mais comum (para definir o threshold do corpo do texto)
    font_sizes = []
    for page in doc:
        blocks = page.get_text("dict", flags=11).get("blocks", [])
        for b in blocks:
            for l in b.get("lines", []):
                for s in l.get("spans", []):
                    font_sizes.append(s["size"])
                    
    median_size = sorted(font_sizes)[len(font_sizes)//2] if font_sizes else 11.0
    title_threshold = median_size + 1.5 # fontes 1.5 pontos maiores que o corpo normal
    
    # 2. Extrair texto, analisando blocos que não toquem as margens ignoradas
    extracted_elements = [] # Lista de tuplas (texto, is_title)
    
    for page_idx, page in enumerate(doc):
        current_page_num = page_idx + 1
        
        if current_page_num in pages_to_ignore:
            continue 
            
        bypass_margins = current_page_num in pages_to_force 
        
        page_height = page.rect.height
        clip_top = page_height * (top_margin_perc / 100.0)
        clip_bottom = page_height * (1.0 - (bottom_margin_perc / 100.0))
        
        blocks = page.get_text("dict", flags=11).get("blocks", [])
        for b in blocks:
            y0, y1 = b["bbox"][1], b["bbox"][3]
            
            if not bypass_margins:
                if y1 < clip_top or y0 > clip_bottom:
                    continue 
            
            for l in b.get("lines", []):
                line_text = ""
                line_is_title = False
                
                for s in l.get("spans", []):
                    txt = s["text"]
                    sz = round(s["size"], 1)
                    
                    # Filtro 1: Se o usuário restringiu tamanhos de fonte
                    if allowed_font_sizes is not None and sz not in allowed_font_sizes:
                        continue

                    # Filtro 2: Remoção automática de sobrescritos numéricos
                    # (Se o tamanho for menor que o corpo e for apenas número)
                    if sz < (median_size - 1.0) and txt.strip().isdigit():
                        continue
                    
                    if sz >= title_threshold:
                        line_is_title = True
                        
                    line_text += txt
                
                if line_text.strip():
                    extracted_elements.append((line_text.strip(), line_is_title))
                    
    doc.close()

    # 3. Gerar PDF limpo usando ReportLab ou TXT puro
    out_io = BytesIO()
    
    if output_format.lower() == "pdf":
        doc_out = SimpleDocTemplate(out_io, pagesize=A4,
                                    rightMargin=2*cm, leftMargin=2*cm,
                                    topMargin=2*cm, bottomMargin=2*cm)
        
        styles = getSampleStyleSheet()
        style_normal = styles["Normal"]
        style_normal.fontSize = 12
        style_normal.leading = 18 
        style_normal.alignment = 4 
        
        style_title = styles["Heading2"]
        
        story = []
        current_paragraph = []
        
        def flush_paragraph():
            if current_paragraph:
                text = " ".join(current_paragraph)
                cleaned = clean_text(text, abbreviations, False, inject_title_pauses, inject_normal_pauses)
                cleaned = cleaned.replace('<', '&lt;').replace('>', '&gt;')
                if cleaned:
                    for chunk in cleaned.split('\n\n'):
                        if chunk.strip():
                            story.append(Paragraph(chunk, style_normal))
                current_paragraph.clear()
                
        for text, is_title in extracted_elements:
            if is_title:
                flush_paragraph() 
                cleaned = clean_text(text, abbreviations, True, inject_title_pauses, inject_normal_pauses)
                cleaned = cleaned.replace('<', '&lt;').replace('>', '&gt;')
                story.append(Spacer(1, 18))
                story.append(Paragraph(cleaned, style_title))
                story.append(Spacer(1, 12))
            else:
                current_paragraph.append(text)
                if text.endswith('.') or text.endswith(';') or text.endswith('?') or text.endswith('!'):
                     flush_paragraph()
        
        flush_paragraph()
        doc_out.build(story)
        
    else:
        # Formato TXT
        lines = []
        current_paragraph = []
        
        def flush_paragraph_txt():
            if current_paragraph:
                text = " ".join(current_paragraph)
                cleaned = clean_text(text, abbreviations, False, inject_title_pauses, inject_normal_pauses)
                if cleaned:
                    lines.append(cleaned)
                current_paragraph.clear()

        for text, is_title in extracted_elements:
            if is_title:
                flush_paragraph_txt()
                cleaned = clean_text(text, abbreviations, True, inject_title_pauses, inject_normal_pauses)
                lines.append("\n" + cleaned + "\n")
            else:
                current_paragraph.append(text)
                if text.endswith('.') or text.endswith(';') or text.endswith('?') or text.endswith('!'):
                     flush_paragraph_txt()
                     
        flush_paragraph_txt()
        final_text = "\n".join(lines)
        out_io.write(final_text.encode('utf-8'))
    
    out_io.seek(0)
    return out_io

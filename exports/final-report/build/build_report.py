"""Build MealMatch-Final-Report.docx from MealMatch-Final-Report.md and count words.

Word count follows the brief: chapter titles, figure/table/listing captions and the
reference list are excluded. Placeholders and code listings are also left out; table
text is counted separately and included in the totals, to stay on the safe side.
Run with a Python that has python-docx:  python build_report.py
The contents page is a real table-of-contents field. Its page numbers come from
`python build_report.py --pages pages.json` (heading text -> page, measured on a PDF of the
previous build); in Word or WPS, "Update Table" refreshes them for that program's layout.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "MealMatch-Final-Report.md"
TARGET = ROOT / "MealMatch-Final-Report.docx"
CREST = Path(__file__).resolve().parent / "uol-crest.png"
LIMITS = {1: 1000, 2: 2500, 3: 2000, 4: 2500, 5: 2500, 6: 1000}
TOTAL_LIMIT = 10500
BODY_FONT, CODE_FONT = "Times New Roman", "Menlo"
DEEP = RGBColor(0x0C, 0x3A, 0x35)
WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’.\-/%×·]*")
INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)")


def words(text: str) -> int:
    text = re.sub(r"`[^`]*`", " x ", text)
    return len(WORD.findall(re.sub(r"[*_>#|]", " ", text)))


# ---------------------------------------------------------------- parsing

def parse(markdown: str):
    front, body = {}, markdown
    if markdown.startswith("---"):
        _, header, body = markdown.split("---", 2)
        for line in header.strip().splitlines():
            key, value = line.split(":", 1)
            front[key.strip()] = value.strip().strip('"')
    blocks, lines, i = [], body.strip("\n").splitlines(), 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("```"):
            code = []
            i += 1
            while not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            blocks.append(("code", "\n".join(code)))
            i += 1
            continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            blocks.append((f"h{level}", line[level:].strip()))
        elif line.startswith("[[PLACEHOLDER:"):
            blocks.append(("placeholder", line.strip()[len("[[PLACEHOLDER:"):-2].strip()))
        elif line.startswith("[[FIGURE-SLOT:"):
            blocks.append(("slot", line.strip()[len("[[FIGURE-SLOT:"):-2].strip()))
        elif line.startswith("!["):
            match = re.match(r"!\[(.*)\]\((.*)\)", line.strip())
            blocks.append(("figure", (match.group(1), match.group(2))))
        elif re.match(r"^(Table|Listing) [A-Z]?\d+:", line):
            blocks.append(("caption", line.strip()))
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [cell.strip() for cell in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                    rows.append(cells)
                i += 1
            blocks.append(("table", rows))
            continue
        elif line.startswith("> "):
            blocks.append(("quote", line[2:].strip()))
        elif re.match(r"^- ", line):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(lines[i][2:].strip())
                i += 1
            blocks.append(("bullets", items))
            continue
        elif re.match(r"^\d+\. ", line):
            items = []
            while i < len(lines) and re.match(r"^\d+\. ", lines[i]):
                items.append(re.sub(r"^\d+\. ", "", lines[i]).strip())
                i += 1
            blocks.append(("numbers", items))
            continue
        else:
            text = [line.strip()]
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#|- |\d+\. |\||!\[|\[\[|```|> |Table [A-Z]?\d+:|Listing \d+:)", lines[i]):
                text.append(lines[i].strip())
                i += 1
            blocks.append(("para", " ".join(text)))
            continue
        i += 1
    return front, blocks


def count(blocks):
    counts, chapter, in_refs = {}, 0, False
    for kind, value in blocks:
        if kind == "h1":
            match = re.match(r"Chapter (\d)", value)
            chapter = int(match.group(1)) if match else 0
            in_refs = not match
            continue
        if in_refs or not chapter:
            continue
        prose, table = counts.setdefault(chapter, [0, 0])
        if kind in ("para", "quote"):
            counts[chapter][0] += words(value)
        elif kind in ("bullets", "numbers"):
            counts[chapter][0] += sum(words(item) for item in value)
        elif kind == "table":
            counts[chapter][1] += sum(words(cell) for row in value for cell in row)
    return counts


# ---------------------------------------------------------------- docx helpers

def shade(paragraph, colour: str):
    properties = paragraph._p.get_or_add_pPr()
    fill = OxmlElement("w:shd")
    fill.set(qn("w:val"), "clear")
    fill.set(qn("w:color"), "auto")
    fill.set(qn("w:fill"), colour)
    properties.append(fill)


def cell_shade(cell, colour: str):
    properties = cell._tc.get_or_add_tcPr()
    fill = OxmlElement("w:shd")
    fill.set(qn("w:val"), "clear")
    fill.set(qn("w:color"), "auto")
    fill.set(qn("w:fill"), colour)
    properties.append(fill)


def add_runs(paragraph, text: str, size: float | None = None, italic: bool = False):
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**"):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        elif part.startswith("`"):
            run = paragraph.add_run(part[1:-1])
            run.font.name = CODE_FONT
            run.font.size = Pt((size or 12) - 1.5)
            continue
        elif part.startswith("*"):
            run = paragraph.add_run(part[1:-1])
            run.italic = True
        else:
            run = paragraph.add_run(part)
        if size:
            run.font.size = Pt(size)
        if italic:
            run.italic = True


def add_field(paragraph, instruction: str, shown: str = "1", size: float | None = None):
    """A complex field in Word's own layout: begin, code, separate, result and end, one run each."""
    def run_with(element):
        run = paragraph.add_run()
        if size:
            run.font.size = Pt(size)
        run._r.append(element)
        return run

    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    begin.set(qn("w:dirty"), "true")
    code = OxmlElement("w:instrText")
    code.set(qn("xml:space"), "preserve")
    code.text = f" {instruction} "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    result = OxmlElement("w:t")
    result.text = shown
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for element in (begin, code, separate, result, end):
        run_with(element)


def caption(document, text: str):
    paragraph = document.add_paragraph(style="Caption")
    match = re.match(r"^((?:Figure|Table|Listing) [A-Z]?\d+:)(.*)$", text)
    if match:
        label = paragraph.add_run(match.group(1))
        label.bold = True
        add_runs(paragraph, match.group(2))
    else:
        add_runs(paragraph, text)
    return paragraph


def xml_run(text: str | None = None, element=None):
    run = OxmlElement("w:r")
    if text is not None:
        piece = OxmlElement("w:t")
        piece.set(qn("xml:space"), "preserve")
        piece.text = text
        run.append(piece)
    if element is not None:
        run.append(element)
    return run


def field_char(kind: str):
    char = OxmlElement("w:fldChar")
    char.set(qn("w:fldCharType"), kind)
    return char


def instruction(text: str):
    code = OxmlElement("w:instrText")
    code.set(qn("xml:space"), "preserve")
    code.text = f" {text} "
    return code


def bookmark(paragraph, name: str, number: int):
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(number))
    start.set(qn("w:name"), name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), str(number))
    properties = paragraph._p.pPr
    if properties is not None:
        properties.addnext(start)
    else:
        paragraph._p.insert(0, start)
    paragraph._p.append(end)


def contents(document, entries, pages: dict[str, int], width: float):
    """A table-of-contents field laid out as Word writes one: each entry links to its heading's
    bookmark and ends in a PAGEREF field, so Word or WPS can refresh the numbers in place."""
    for index, (level, text, mark) in enumerate(entries):
        paragraph = document.add_paragraph(style=f"toc {level}")
        paragraph.paragraph_format.tab_stops.add_tab_stop(Cm(width), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        if index == 0:
            for element in (field_char("begin"), instruction('TOC \\o "1-2" \\h \\z \\u'), field_char("separate")):
                paragraph._p.append(xml_run(element=element))
        link = OxmlElement("w:hyperlink")
        link.set(qn("w:anchor"), mark)
        link.set(qn("w:history"), "1")
        link.append(xml_run(text))
        link.append(xml_run(element=OxmlElement("w:tab")))
        for element in (field_char("begin"), instruction(f"PAGEREF {mark} \\h"), field_char("separate")):
            link.append(xml_run(element=element))
        link.append(xml_run(str(pages.get(text, ""))))
        link.append(xml_run(element=field_char("end")))
        paragraph._p.append(link)
    closing = document.add_paragraph()
    closing._p.append(xml_run(element=field_char("end")))


def placeholder(document, text: str, centre: bool = False):
    paragraph = document.add_paragraph()
    if centre:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    shade(paragraph, "FFF2B3")
    run = paragraph.add_run("PLACEHOLDER: ")
    run.bold = True
    run.font.color.rgb = RGBColor(0x8A, 0x4B, 0x12)
    add_runs(paragraph, text, size=11)
    return paragraph


def keep_table_together(table):
    """Keep a table on one page: rows never split, and every row stays with the next.
    The header row also repeats, in case a table is ever longer than a page."""
    rows = table.rows
    for index, row in enumerate(rows):
        properties = row._tr.get_or_add_trPr()
        properties.append(OxmlElement("w:cantSplit"))
        if index == 0:
            properties.append(OxmlElement("w:tblHeader"))
        if index < len(rows) - 1:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.keep_with_next = True


def cover_line(document, text: str, size: float, bold: bool = False, before: float = 0, colour=None):
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(before)
    paragraph.paragraph_format.space_after = Pt(4)
    run = paragraph.add_run(text)
    run.font.size = Pt(size)
    run.bold = bold
    if colour:
        run.font.color.rgb = colour
    return paragraph


def detail_line(document, label: str, value: str, empty_note: str):
    """One "Label: value" line of the cover, laid out as in the CM3070 template."""
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.left_indent = Cm(1.5)
    paragraph.paragraph_format.space_after = Pt(3)
    paragraph.paragraph_format.tab_stops.add_tab_stop(Cm(6.5))
    run = paragraph.add_run(f"{label}\t: ")
    run.font.size = Pt(13)
    if value:
        run = paragraph.add_run(value)
        run.font.size = Pt(13)
    else:
        shade(paragraph, "FFF2B3")
        run = paragraph.add_run(f"PLACEHOLDER: {empty_note}")
        run.font.size = Pt(11)
        run.bold = True
        run.font.color.rgb = RGBColor(0x8A, 0x4B, 0x12)


def build(pages: dict[str, int]):
    front, blocks = parse(SOURCE.read_text())
    entries = [(1 if kind == "h1" else 2, value, f"_Toc{100001 + index}")
               for index, (kind, value) in enumerate(item for item in blocks if item[0] in ("h1", "h2"))]
    counts = count(blocks)
    document = Document()
    # The blank template carries its own author, description and 2013 dates; use the report's.
    properties = document.core_properties
    properties.title = front.get("title", "")
    properties.author = properties.last_modified_by = front.get("student", "")
    properties.comments = properties.keywords = properties.subject = properties.category = ""
    properties.created = properties.modified = datetime.now()
    section = document.sections[0]
    section.page_height, section.page_width = Cm(29.7), Cm(21.0)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, side, Cm(2.5))

    styles = document.styles
    normal = styles["Normal"]
    normal.font.name = BODY_FONT
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing = 1.15
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.widow_control = True
    for name, size, before in (("Heading 1", 20, 0), ("Heading 2", 14, 12), ("Heading 3", 12.5, 10)):
        style = styles[name]
        style.font.name = BODY_FONT
        style.element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = DEEP
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.keep_with_next = True
    cap = styles["Caption"]
    cap.font.name = BODY_FONT
    cap.font.size = Pt(10.5)
    cap.font.italic = True
    cap.font.bold = False
    cap.font.color.rgb = RGBColor(0x26, 0x33, 0x2F)
    cap.paragraph_format.space_after = Pt(10)
    names = [style.name for style in styles]
    for level, indent in ((1, 0), (2, 0.6)):
        # Word lays out contents entries with its built-in "toc 1" and "toc 2" styles.
        toc = styles[f"toc {level}"] if f"toc {level}" in names else styles.add_style(f"toc {level}", WD_STYLE_TYPE.PARAGRAPH)
        toc.base_style = normal
        toc.font.size = Pt(12 if level == 1 else 11)
        toc.font.bold = level == 1
        toc.paragraph_format.left_indent = Cm(indent)
        toc.paragraph_format.space_before = Pt(6 if level == 1 else 0)
        toc.paragraph_format.space_after = Pt(1)

    # Footer "Page X of Y", as in the CM3070 template
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run("Page ").font.size = Pt(10)
    add_field(footer, "PAGE", size=10)
    footer.add_run(" of ").font.size = Pt(10)
    add_field(footer, "NUMPAGES", size=10)

    # Cover page, following the first page of the CM3070 report template
    cover_line(document, "INTERNATIONAL PROGRAMMES", 18, bold=True, before=6)
    cover_line(document, "BSc Computer Science and Related Subjects", 20, bold=True, before=10)
    crest = document.add_paragraph()
    crest.alignment = WD_ALIGN_PARAGRAPH.CENTER
    crest.paragraph_format.space_before = Pt(14)
    crest.add_run().add_picture(str(CREST), height=Cm(6.2))
    cover_line(document, "CM3070 PROJECT", 18, bold=True, before=14)
    cover_line(document, "FINAL PROJECT REPORT", 18, bold=True)
    cover_line(document, front.get("title", ""), 17, bold=True, before=16, colour=DEEP)
    spacer = document.add_paragraph()
    spacer.paragraph_format.space_after = Pt(12)
    detail_line(document, "Author", front.get("student", ""), "author")
    detail_line(document, "Student Number", front.get("uol_id", ""), "student number")
    detail_line(document, "Date of Submission", front.get("submitted", ""), "date of submission")
    detail_line(document, "Supervisor", front.get("supervisor", ""), "supervisor's name")
    detail_line(document, "Project template", front.get("template", ""), "project template")
    detail_line(document, "Code repository", front.get("repository", ""), "repository link")
    detail_line(document, "Demonstration video", front.get("video", ""), "link to the 3–5 minute video")
    document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # Contents, then the word count
    heading = document.add_paragraph()
    run = heading.add_run("Contents")
    run.bold = True
    run.font.size = Pt(18)
    run.font.color.rgb = DEEP
    contents(document, entries, pages, width=16.0)

    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(18)
    paragraph.paragraph_format.keep_with_next = True
    run = paragraph.add_run("Word count")
    run.bold = True
    run.font.size = Pt(14)
    run.font.color.rgb = DEEP
    note = document.add_paragraph()
    note.paragraph_format.keep_with_next = True
    add_runs(note, "Chapter titles, captions, code listings, placeholders, references and appendices are excluded; table text is included.", size=10.5, italic=True)
    table = document.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for cell, text in zip(table.rows[0].cells, ("Chapter", "Words", "Of which tables", "Limit")):
        cell.text = text
        cell_shade(cell, "DCEBD6")
        cell.paragraphs[0].runs[0].bold = True
    names = {1: "1 Introduction", 2: "2 Literature review", 3: "3 Project design", 4: "4 Implementation", 5: "5 Evaluation", 6: "6 Conclusion"}
    total = 0
    for chapter in range(1, 7):
        prose, tables = counts.get(chapter, [0, 0])
        total += prose + tables
        row = table.add_row().cells
        for cell, text in zip(row, (names[chapter], f"{prose + tables:,}", str(tables), f"{LIMITS[chapter]:,}")):
            cell.text = text
    row = table.add_row().cells
    for cell, text in zip(row, ("Total", f"{total:,}", "", f"{TOTAL_LIMIT:,}")):
        cell.text = text
        if text:
            cell.paragraphs[0].runs[0].bold = True
    for row in table.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(2)
                for r in p.runs:
                    r.font.size = Pt(11)
    keep_table_together(table)

    in_references = in_appendix = False
    marks = iter(entries)
    for kind, value in blocks:
        table_size = 9.5 if in_appendix else 10.5
        if kind == "h1":
            document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            heading = document.add_heading(value, level=1)
            _, _, mark = next(marks)
            bookmark(heading, mark, int(mark[4:]))
            in_references = value.startswith("References")
            in_appendix = value.startswith("Appendix")
            match = re.match(r"Chapter (\d)", value)
            if match:
                chapter = int(match.group(1))
                prose, tables = counts.get(chapter, [0, 0])
                line = document.add_paragraph()
                line.paragraph_format.keep_with_next = True
                add_runs(line, f"Word count: {prose + tables:,} (limit {LIMITS[chapter]:,})", size=10.5, italic=True)
        elif kind == "h2":
            heading = document.add_heading(value, level=2)
            _, _, mark = next(marks)
            bookmark(heading, mark, int(mark[4:]))
        elif kind == "h3":
            document.add_heading(value, level=3)
        elif kind == "para":
            paragraph = document.add_paragraph()
            if in_references:
                paragraph.paragraph_format.left_indent = Cm(1)
                paragraph.paragraph_format.first_line_indent = Cm(-1)
                add_runs(paragraph, value, size=11)
            else:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                add_runs(paragraph, value)
        elif kind == "quote":
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.left_indent = Cm(1.2)
            paragraph.paragraph_format.right_indent = Cm(1.2)
            add_runs(paragraph, value)
            for run in paragraph.runs:
                run.bold = True
                run.italic = True
        elif kind in ("bullets", "numbers"):
            for item in value:
                paragraph = document.add_paragraph(style="List Bullet" if kind == "bullets" else "List Number")
                add_runs(paragraph, item)
        elif kind == "caption":
            caption(document, value).paragraph_format.keep_with_next = True
        elif kind == "table":
            table = document.add_table(rows=0, cols=len(value[0]))
            table.style = "Table Grid"
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            for r, row in enumerate(value):
                cells = table.add_row().cells
                for cell, text in zip(cells, row):
                    cell.text = ""
                    add_runs(cell.paragraphs[0], text, size=table_size)
                    cell.paragraphs[0].paragraph_format.space_after = Pt(2)
                    cell.paragraphs[0].paragraph_format.line_spacing = 1.0
                    if r == 0:
                        cell_shade(cell, "DCEBD6")
                        for run in cell.paragraphs[0].runs:
                            run.bold = True
            keep_table_together(table)
            document.add_paragraph().paragraph_format.space_after = Pt(2)
        elif kind == "code":
            lines = value.splitlines() or [""]
            for index, line in enumerate(lines):
                paragraph = document.add_paragraph()
                paragraph.paragraph_format.space_after = Pt(0)
                paragraph.paragraph_format.line_spacing = 1.0
                paragraph.paragraph_format.keep_with_next = index < len(lines) - 1
                shade(paragraph, "F2F4F3")
                run = paragraph.add_run(line if line else " ")
                run.font.name = CODE_FONT
                run.element.rPr.rFonts.set(qn("w:eastAsia"), CODE_FONT)
                run.font.size = Pt(9 if max(len(l) for l in lines) > 84 else 9.5)
            document.add_paragraph().paragraph_format.space_after = Pt(4)
        elif kind == "figure":
            text, path = value
            image_path = ROOT / path
            with Image.open(image_path) as image:
                ratio = image.height / image.width
            width = 16.0
            if width * ratio > 20.5:
                width = 20.5 / ratio
            paragraph = document.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.keep_with_next = True
            paragraph.add_run().add_picture(str(image_path), width=Cm(width))
            caption(document, text).alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif kind == "slot":
            placeholder(document, "add this figure's image here.", centre=True).paragraph_format.keep_with_next = True
            caption(document, value).alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif kind == "placeholder":
            placeholder(document, value)

    # Ask Word and WPS to refresh the contents page numbers when the file opens.
    update = OxmlElement("w:updateFields")
    update.set(qn("w:val"), "true")
    document.settings.element.append(update)
    document.save(TARGET)
    print(f"wrote {TARGET.name}")
    for chapter in range(1, 7):
        prose, tables = counts.get(chapter, [0, 0])
        print(f"  Chapter {chapter}: {prose + tables:5d} words (tables {tables:4d}) / limit {LIMITS[chapter]}")
    print(f"  Total: {total} / {TOTAL_LIMIT}")


if __name__ == "__main__":
    measured = {}
    if "--pages" in sys.argv:
        measured = json.loads(Path(sys.argv[sys.argv.index("--pages") + 1]).read_text())
    build(measured)

"""Portable, deterministic study-bank renderer. No work occurs at import time.

Run ``python -m studypdf validate bank.json`` or
``python -m studypdf build bank.json --output guide.pdf``.
PDF page numbers in the audit and Markdown companion are one-based.
"""
from __future__ import annotations

import argparse
from collections import Counter
from html import escape
from io import BytesIO
import json
from pathlib import Path
import re
import sys

MARGIN = 48.41
NAVY = '#17324B'
TEAL = '#167B7F'
GOLD = '#A87324'
BODY = '#172435'
MUTED = '#5E6E7B'
LIGHT = '#EDF4F8'
BORDER = '#D7E3EB'
STATUSES = ('SOURCE KEY', 'STUDY ANSWER', 'SOURCE RECALL', 'UNRESOLVED')


class InputError(ValueError):
    """An invalid input bank or unrenderable supplied text."""


def validate(data):
    """Validate the JSON contract, retaining input order and exact strings."""
    def fail(path, message):
        raise InputError(f'{path}: {message}')

    def obj(value, path):
        if not isinstance(value, dict):
            fail(path, 'expected an object')

    def text(value, path, nonempty=False):
        if not isinstance(value, str):
            fail(path, 'expected a string')
        if nonempty and not value.strip():
            fail(path, 'must not be empty')
        if any(ord(ch) < 32 and ch not in '\n\r\t' for ch in value):
            fail(path, 'contains an unsupported control character')

    def array(value, path):
        if not isinstance(value, list):
            fail(path, 'expected an array')

    obj(data, 'input')
    for field in ('title', 'subtitle', 'description'):
        text(data.get(field), field, field == 'title')
    for field in ('categories', 'questions'):
        array(data.get(field), field)
        if not data[field]:
            fail(field, 'at least one entry is required')
    array(data.get('sections', []), 'sections')
    ids = set()
    category_ids = set()
    for kind in ('categories', 'questions', 'sections'):
        for i, item in enumerate(data.get(kind, [])):
            path = f'{kind}[{i}]'
            obj(item, path)
            text(item.get('id'), path + '.id', True)
            if item['id'] in ids:
                fail(path + '.id', f'duplicate ID {item["id"]!r}')
            ids.add(item['id'])
            if kind == 'categories':
                category_ids.add(item['id'])
                text(item.get('title'), path + '.title', True)
                array(item.get('related', []), path + '.related')
                for j, value in enumerate(item.get('related', [])):
                    text(value, f'{path}.related[{j}]', True)
                for field in ('note', 'empty_note'):
                    if field in item:
                        text(item[field], path + '.' + field)
            elif kind == 'questions':
                for field in ('category', 'prompt', 'answer', 'status', 'source'):
                    text(item.get(field), path + '.' + field, field in ('category', 'prompt'))
                if item['status'] not in STATUSES:
                    fail(path + '.status', 'expected one of ' + ', '.join(STATUSES))
                array(item.get('options'), path + '.options')
                for j, pair in enumerate(item['options']):
                    array(pair, f'{path}.options[{j}]')
                    if len(pair) != 2:
                        fail(f'{path}.options[{j}]', 'expected [letter, text]')
                    for k, value in enumerate(pair):
                        text(value, f'{path}.options[{j}][{k}]')
                if 'original_prompt' in item:
                    text(item['original_prompt'], path + '.original_prompt')
                array(item.get('notes', []), path + '.notes')
                for j, value in enumerate(item.get('notes', [])):
                    text(value, f'{path}.notes[{j}]')
            else:
                text(item.get('title'), path + '.title', True)
                array(item.get('paragraphs'), path + '.paragraphs')
                for j, value in enumerate(item['paragraphs']):
                    text(value, f'{path}.paragraphs[{j}]')
                if 'table' in item:
                    array(item['table'], path + '.table')
                    columns = None
                    for j, row in enumerate(item['table']):
                        array(row, f'{path}.table[{j}]')
                        if not row or (columns is not None and len(row) != columns):
                            fail(f'{path}.table[{j}]', 'table rows must be nonempty and rectangular')
                        columns = len(row)
                        for k, value in enumerate(row):
                            text(value, f'{path}.table[{j}][{k}]')
    for category in data['categories']:
        for ref in category.get('related', []):
            if ref not in category_ids:
                fail('related', f'{category["id"]!r} references unknown category {ref!r}')
    for question in data['questions']:
        if question['category'] not in category_ids:
            fail('category', f'{question["id"]!r} references unknown category {question["category"]!r}')
    return data


def load_input(path):
    try:
        return validate(json.loads(Path(path).read_text(encoding='utf-8-sig')))
    except json.JSONDecodeError as error:
        raise InputError(f'invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}') from error


def _renderer():
    """Import optional build dependencies and register bundled Inter fonts lazily."""
    import pymupdf as fitz
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    fontdir = Path(__file__).resolve().parent / 'assets' / 'fonts'
    for weight in ('Regular', 'Bold', 'SemiBold', 'Medium'):
        path = fontdir / f'Inter_18pt-{weight}.ttf'
        if not path.is_file():
            raise InputError(f'missing bundled font: {path}')
        name = 'Inter' + weight
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(path)))
    pdfmetrics.registerFontFamily('InterRegular', normal='InterRegular', bold='InterBold',
                                 italic='InterRegular', boldItalic='InterBold')
    styles = {}
    for name, weight, size, leading, color in (
        ('body', 'Regular', 9.25, 15.67, BODY),
        ('question', 'SemiBold', 9.25, 15.67, BODY),
        ('small', 'Regular', 8.2, 12.1, MUTED),
        ('label', 'Bold', 7.2, 10.5, TEAL),
        ('goldlabel', 'Bold', 7.2, 10.5, GOLD),
        ('heading', 'Bold', 21.5, 27.5, NAVY),
        ('cardtitle', 'Bold', 12, 16, '#23455E'),
        ('white', 'Regular', 10.5, 17, '#E4EFF5'),
        ('cover', 'Bold', 30, 38, '#FFFFFF'),
        ('subtitle', 'Regular', 21.5, 29, '#E4EFF5'),
    ):
        styles[name] = ParagraphStyle(name, fontName='Inter' + weight, fontSize=size,
                                      leading=leading, textColor=colors.HexColor(color),
                                      splitLongWords=True)
    return fitz, canvas, Paragraph, colors, A4, styles


def _literal(text):
    return escape(text).replace('\r\n', '\n').replace('\r', '\n').replace('\n', '<br/>')


def _numbered(data):
    by = {category['id']: [] for category in data['categories']}
    for question in data['questions']:
        by[question['category']].append(question)
    numbers = {}
    for ci, category in enumerate(data['categories'], 1):
        for qi, question in enumerate(by[category['id']], 1):
            numbers[question['id']] = f'{ci:02d}.{qi:02d}'
    return by, numbers


def _markdown(data, by, numbers, category_pages):
    rows = [f'# {data["title"]}', '', data['subtitle'], '', data['description'], '',
            f'{len(data["categories"])} categories · {len(data["questions"])} questions', '',
            '## Category overview', '', '| No. | Category | Questions | PDF page |',
            '|---|---|---:|---:|']
    for ci, category in enumerate(data['categories'], 1):
        title = category['title'].replace('|', '\\|').replace('\n', '<br>')
        rows.append(f'| {ci:02d} | {title} | {len(by[category["id"]])} | {category_pages[category["id"]]} |')
    for ci, category in enumerate(data['categories'], 1):
        rows += ['', f'## {ci:02d} — {category["title"]}', '', category.get('note', '')]
        if not by[category['id']]:
            rows += [category.get('empty_note', 'No source questions supplied for this topic.')]
        rows += ['Related topics: ' + ', '.join(category.get('related', []))]
        for question in by[category['id']]:
            rows += ['', f'### {numbers[question["id"]]} · {question["id"]}', '', question['prompt'], '']
            rows += [f'{letter}. {text}' for letter, text in question['options']]
            rows += ['', f'**{question["status"]}:** {question["answer"]}', '', 'Source: ' + question['source']]
            if 'original_prompt' in question:
                rows += ['Original prompt: ' + question['original_prompt']]
            rows += question.get('notes', [])
    for section in data.get('sections', []):
        rows += ['', '## ' + section['title'], ''] + section['paragraphs']
        if section.get('table'):
            for i, row in enumerate(section['table']):
                rows.append('| ' + ' | '.join(cell.replace('|', '\\|').replace('\n', '<br>') for cell in row) + ' |')
                if i == 0:
                    rows.append('| ' + ' | '.join('---' for _ in row) + ' |')
    return '\n'.join(rows) + '\n'


def build(data, output):
    """Render and verify a PDF plus exact-text Markdown and machine-readable audit."""
    validate(data)
    fitz, canvas, Paragraph, colors, A4, styles = _renderer()
    from reportlab.pdfbase import pdfmetrics

    # Fail clearly rather than silently rendering unsupported Unicode as empty glyphs.
    supported = pdfmetrics.getFont('InterRegular').face.charToGlyph
    def check_strings(value):
        if isinstance(value, str):
            missing = {ord(ch) for ch in value if not ch.isspace() and ord(ch) not in supported}
            if missing:
                raise InputError('bundled Inter font lacks characters: ' + ', '.join(f'U+{cp:04X}' for cp in sorted(missing)))
        elif isinstance(value, list):
            for item in value:
                check_strings(item)
        elif isinstance(value, dict):
            for item in value.values():
                check_strings(item)
    check_strings(data)
    by, numbers = _numbered(data)
    w, h = A4
    width = w - 2 * MARGIN
    bottom = MARGIN + 15

    def para(text, kind='body'):
        return Paragraph(_literal(text), styles[kind])

    class Writer:
        def __init__(self):
            self.buffer = BytesIO()
            self.c = canvas.Canvas(self.buffer, pagesize=A4, invariant=1)
            self.page = -1
            self.links = []
            self.question_pages = {}
            self.category_pages = {}
            self.section_pages = {}
            self.page_types = []
            self.y = 0

        def start(self, page_type='detail', size=A4):
            if self.page >= 0:
                self.c.showPage()
            self.page += 1
            self.page_types.append(page_type)
            self.c.setPageSize(size)
            self.w, self.h = size
            self.y = self.h - MARGIN
            if page_type == 'cover':
                return
            self.c.setFillColor(colors.HexColor(MUTED))
            self.c.setFont('InterRegular', 7.2)
            self.c.drawString(MARGIN, 22, 'STUDY GUIDE')
            self.c.setFillColor(colors.HexColor(TEAL))
            self.c.drawCentredString(self.w / 2, 22, 'Contents')
            self.links.append({'page': self.page, 'rect': [self.w / 2 - 22, self.h - 31,
                                                         self.w / 2 + 22, self.h - 17],
                               'target': ('contents', 'first'), 'kind': 'return'})

        def box(self, paragraph, fill=None, kind='body', pad=0, gap=5):
            """Split any paragraph across pages; never repeat the primary heading."""
            obj = paragraph if hasattr(paragraph, 'wrap') else para(paragraph, kind)
            while obj is not None:
                usable = self.y - bottom - 2 * pad
                _, hh = obj.wrap(width - 2 * pad, max(0, usable))
                if hh <= usable + .01:
                    part, tail = obj, None
                else:
                    parts = obj.split(width - 2 * pad, max(0, usable))
                    if not parts:
                        self.start()
                        continue
                    part = parts[0]
                    tail = parts[1] if len(parts) > 1 else None
                    _, hh = part.wrap(width - 2 * pad, usable)
                total = hh + 2 * pad
                if fill:
                    self.c.setFillColor(colors.HexColor(fill))
                    self.c.setStrokeColor(colors.HexColor(BORDER))
                    self.c.setLineWidth(.6)
                    self.c.roundRect(MARGIN, self.y - total, width, total, 6, fill=1, stroke=1)
                part.drawOn(self.c, MARGIN + pad, self.y - pad - hh)
                self.y -= total + gap
                obj = tail
                if obj is not None:
                    self.start()

        def heading(self, title, label):
            self.box(label, kind='label', gap=9)
            self.box(title, kind='heading', gap=16)
            if self.y < bottom + 10:
                self.start()
            self.c.setFillColor(colors.HexColor(TEAL))
            self.c.rect(MARGIN, self.y, width, 2.8, fill=1, stroke=0)
            self.y -= 17

        def finish(self):
            self.c.save()
            return self.buffer.getvalue()

    detail = Writer()
    category_lookup = {c['id']: (i, c) for i, c in enumerate(data['categories'], 1)}
    for ci, category in enumerate(data['categories'], 1):
        detail.start()
        detail.category_pages[category['id']] = detail.page
        detail.heading(category['title'], f'T O P I C {ci:02d} · A N S W E R E D R E V I S I O N')
        counts = Counter(q['status'] for q in by[category['id']])
        detail.box(f'Source occurrences: {len(by[category["id"]])} · Source-keyed answers: {counts["SOURCE KEY"]}\n'
                   f'Study answers: {counts["STUDY ANSWER"]} · Source recall: {counts["SOURCE RECALL"]} · Unresolved: {counts["UNRESOLVED"]}',
                   fill=LIGHT, kind='small', pad=10, gap=12)
        if category.get('note'):
            detail.box(category['note'], kind='small')
        for ref in category.get('related', []):
            ri, related = category_lookup[ref]
            label = f'Related topic: {ri:02d} {related["title"]}'
            # Use Paragraph's native link geometry; fix destinations after concatenation.
            # For split paragraphs, record each rendered line's link via PDF annotations.
            escaped_label = _literal(label)
            obj = Paragraph(f'<link href="studypdf-related:{ri}" color="{TEAL}">{escaped_label}</link>', styles['small'])
            detail.box(obj)
        if not by[category['id']]:
            detail.box(category.get('empty_note', 'No source questions supplied for this topic.'))
        for question in by[category['id']]:
            heading = f'{numbers[question["id"]]} · {question["id"]}'
            header = para(heading, 'cardtitle')
            _, hh = header.wrap(width - 24, h)
            if hh + 60 > h - MARGIN - bottom:
                raise InputError(f'question ID is too long for a card heading: {question["id"]!r}')
            if detail.y - bottom < hh + 60:
                detail.start()
            detail.question_pages[question['id']] = detail.page
            detail.box(header, fill=LIGHT, pad=12, gap=0)
            detail.box(question['prompt'], fill='#FFFFFF', kind='question', pad=12, gap=0)
            for letter, text in question['options']:
                detail.box(letter + '  ' + text, fill='#FFFFFF', pad=12, gap=0)
            detail.box(question['status'], fill='#F3F9F9', kind='label', pad=10, gap=0)
            detail.box(question['answer'], fill='#F3F9F9', pad=10, gap=8)
            detail.box('Source: ' + question['source'], kind='small')
            if 'original_prompt' in question:
                detail.box('Original prompt: ' + question['original_prompt'], kind='small')
            for note in question.get('notes', []):
                detail.box(note, kind='small')
            detail.y -= 10
    for section in data.get('sections', []):
        detail.start('section')
        detail.section_pages[section['id']] = detail.page
        detail.heading(section['title'], 'S T U D Y · S E C T I O N')
        for text in section['paragraphs']:
            detail.box(text, gap=9)
        if section.get('table'):
            from reportlab.platypus import Table, TableStyle
            table = Table([[para(cell) for cell in row] for row in section['table']],
                          colWidths=[width / len(section['table'][0])] * len(section['table'][0]),
                          repeatRows=1, splitByRow=1, splitInRow=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(LIGHT)),
                ('GRID', (0, 0), (-1, -1), .5, colors.HexColor(BORDER)),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]))
            remaining = table
            while remaining is not None:
                available = detail.y - bottom
                _, th = remaining.wrap(width, available)
                if th <= available:
                    first, remaining = remaining, None
                else:
                    parts = remaining.split(width, available)
                    if not parts:
                        if detail.y == h - MARGIN:
                            raise InputError('section table cannot fit even after row splitting')
                        detail.start('section')
                        continue
                    first, remaining = parts[0], parts[1]
                    _, th = first.wrap(width, available)
                first.drawOn(detail.c, MARGIN, detail.y - th)
                detail.y -= th + 9
                if remaining is not None:
                    detail.start('section')
    detail_bytes = detail.finish()

    # Measure navigation before rendering: page counts do not assume taxonomy size.
    entries = [{'kind': 'category', 'id': c['id'], 'title': f'{ci:02d} {c["title"]}',
                'count': len(by[c['id']])} for ci, c in enumerate(data['categories'], 1)]
    contents_entries = entries + [{'kind': 'section', 'id': s['id'], 'title': s['title']}
                                  for s in data.get('sections', [])]
    contents_entries += [{'kind': 'overview', 'id': 'first', 'title': 'Topic overview'}]

    def plan(rows, size, is_overview=False):
        rw, rh = size
        text_width = rw - 2 * MARGIN - (115 if is_overview else 70)
        pages = [[]]
        y = rh - 135
        for entry in rows:
            obj = para(entry['title'])
            _, ph = obj.wrap(text_width, rh)
            height = max(26, ph + 12)
            if height > rh - 135 - bottom:
                raise InputError(f'navigation title too long for one page: {entry["id"]!r}')
            if y - height < bottom:
                pages.append([])
                y = rh - 135
            pages[-1].append((entry, obj, height, y))
            y -= height
        return pages

    contents_plan = plan(contents_entries, A4)
    overview_plan = plan(entries, (h, w), True)
    front_count = 1 + len(contents_plan) + len(overview_plan)
    category_pages = {key: value + front_count + 1 for key, value in detail.category_pages.items()}
    section_pages = {key: value + front_count + 1 for key, value in detail.section_pages.items()}
    overview_start = 1 + len(contents_plan)
    targets = {('category', key): value - 1 for key, value in category_pages.items()}
    targets.update({('section', key): value - 1 for key, value in section_pages.items()})
    targets[('contents', 'first')] = 1
    targets[('overview', 'first')] = overview_start

    front = Writer()
    front.start('cover')
    c = front.c
    for i in range(300):
        frac = i / 299
        c.setFillColor(colors.Color((18 + 2 * frac) / 255, (43 + 73 * frac) / 255, (64 + 55 * frac) / 255))
        c.rect(0, h - (i + 1) * h / 300, w, h / 300 + 1, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor('#416571'))
    c.setLineWidth(.55)
    c.circle(w + 18, h - 93, 234)
    c.circle(42, 66, 147)
    c.setFillColor(colors.HexColor('#AED9DB'))
    c.setFont('InterRegular', 7.2)
    c.drawString(MARGIN, 22, 'Read · recall · trace the source')
    c.drawCentredString(w / 2, 22, 'Contents')
    front.links.append({'page': 0, 'rect': [w / 2 - 22, h - 31, w / 2 + 22, h - 17],
                        'target': ('contents', 'first'), 'kind': 'return'})
    front.y = h - 135
    front.box('A N S W E R E D · S T U D Y G U I D E', kind='white', gap=32)
    front.box(data['title'], kind='cover', gap=14)
    front.box(data['subtitle'], kind='subtitle', gap=23)
    front.box(data['description'], kind='white', gap=30)
    front.box(f'{len(data["questions"])} question entries · {len(data["categories"])} organized categories', kind='white', gap=12)
    # If unusually long cover text paginates, its extra pages must not invalidate targets.
    if front.page != 0:
        raise InputError('cover text is too long; shorten title, subtitle, or description')

    contents_links = []
    overview_links = []
    for is_overview, pages in ((False, contents_plan), (True, overview_plan)):
        for index, rows in enumerate(pages, 1):
            size = (h, w) if is_overview else A4
            front.start('overview' if is_overview else 'contents', size)
            front.box('A N A L Y S I S · T O P I C O V E R V I E W' if is_overview else 'N A V I G A T I O N',
                      kind='goldlabel' if is_overview else 'label', gap=8)
            front.box(('Topic overview' if is_overview else 'Contents') + f' · {index}', kind='heading', gap=10)
            front.box(f'{len(data["categories"])} categories · {len(data["questions"])} question entries · click a row to open it', kind='small')
            for entry, obj, rh, y in rows:
                front.c.setFillColor(colors.HexColor(LIGHT))
                front.c.roundRect(MARGIN, y - rh, size[0] - 2 * MARGIN, rh - 2, 4, fill=1, stroke=0)
                _, ph = obj.wrap(size[0] - 2 * MARGIN - (115 if is_overview else 70), rh)
                obj.drawOn(front.c, MARGIN + 8, y - 6 - ph)
                front.c.setFont('InterMedium', 8.2)
                front.c.setFillColor(colors.HexColor(TEAL))
                target = targets[(entry['kind'], entry['id'])]
                suffix = f'{entry["count"]} items · {target + 1}' if is_overview else str(target + 1)
                front.c.drawRightString(size[0] - MARGIN - 8, y - 16, suffix)
                rect = [MARGIN, size[1] - y, size[0] - MARGIN, size[1] - y + rh - 2]
                front.links.append({'page': front.page, 'rect': rect, 'target': (entry['kind'], entry['id']), 'kind': 'overview' if is_overview else 'contents'})
                record = {'page': front.page + 1, 'rect': rect, 'target_page': target + 1,
                          'kind': entry['kind'], 'id': entry['id']}
                (overview_links if is_overview else contents_links).append(record)
    front_bytes = front.finish()
    doc = fitz.open(stream=front_bytes, filetype='pdf')
    with fitz.open(stream=detail_bytes, filetype='pdf') as details:
        doc.insert_pdf(details)
    for writer, offset in ((front, 0), (detail, front_count)):
        for link in writer.links:
            doc[link['page'] + offset].insert_link({'kind': fitz.LINK_GOTO, 'from': fitz.Rect(link['rect']),
                                                  'page': targets[link['target']], 'to': fitz.Point(MARGIN, MARGIN)})
    # Replace the renderer's private related-topic URIs with true internal links.
    for page in doc:
        for link in page.get_links():
            uri = link.get('uri', '')
            if uri.startswith('studypdf-related:'):
                ci = int(uri.split(':')[1])
                category_id = data['categories'][ci - 1]['id']
                rect = link['from']
                page.delete_link(link)
                page.insert_link({'kind': fitz.LINK_GOTO, 'from': rect,
                                  'page': category_pages[category_id] - 1, 'to': fitz.Point(MARGIN, MARGIN)})
    bookmarks = [[1, f'Contents {i + 1}', 2 + i] for i in range(len(contents_plan))]
    bookmarks += [[1, f'Topic overview {i + 1}', overview_start + i + 1] for i in range(len(overview_plan))]
    for ci, category in enumerate(data['categories'], 1):
        bookmarks.append([1, f'{ci:02d} {category["title"]}', category_pages[category['id']]])
        for question in by[category['id']]:
            bookmarks.append([2, f'{numbers[question["id"]]} · {question["id"]}',
                              front_count + detail.question_pages[question['id']] + 1])
    bookmarks += [[1, section['title'], section_pages[section['id']]] for section in data.get('sections', [])]
    doc.set_toc(bookmarks)
    doc.set_metadata({'title': data['title'], 'subject': data['subtitle'], 'creator': 'studypdf'})
    footer_font = Path(__file__).resolve().parent / 'assets' / 'fonts' / 'Inter_18pt-Regular.ttf'
    for pi, page in enumerate(doc, 1):
        label = f'PAGE {pi}'
        label_width = pdfmetrics.stringWidth(label, 'InterRegular', 7.2)
        page.insert_font(fontname='InterPage', fontfile=str(footer_font))
        color = (0.68, 0.85, 0.86) if pi == 1 else (0.51, 0.56, 0.61)
        page.insert_text((page.rect.width - MARGIN - label_width, page.rect.height - 22),
                         label, fontname='InterPage', fontsize=7.2, color=color)
    output = Path(output)
    if output.suffix.lower() != '.pdf':
        raise InputError('--output must have a .pdf suffix')
    output.parent.mkdir(parents=True, exist_ok=True)
    pdf_bytes = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    audit = {
        'schema_version': 1, 'categories': len(data['categories']), 'questions': len(data['questions']),
        'status_counts': {status: sum(q['status'] == status for q in data['questions']) for status in STATUSES},
        'category_pages': category_pages, 'section_pages': section_pages,
        'question_pages': {key: value + front_count + 1 for key, value in detail.question_pages.items()},
        'contents_pages': list(range(2, 2 + len(contents_plan))),
        'overview_pages': list(range(overview_start + 1, front_count + 1)),
        'contents_links': contents_links, 'overview_links': overview_links,
    }
    with fitz.open(stream=pdf_bytes, filetype='pdf') as verified:
        _verify(verified, data, numbers, audit)
    output.write_bytes(pdf_bytes)
    output.with_suffix('.md').write_text(_markdown(data, by, numbers, category_pages), encoding='utf-8')
    output.with_suffix('.audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return audit


def _verify(doc, data, numbers, audit):
    """Audit primary entries, preserved answers/options, links, targets and geometry."""
    import pymupdf as fitz
    from reportlab.lib.pagesizes import A4
    norm = lambda value: re.sub(r'\s+', '', value)
    text = norm('\n'.join(page.get_text(clip=fitz.Rect(0, 0, page.rect.width, page.rect.height - 40))
                          for page in doc))
    for question in data['questions']:
        heading = norm(f'{numbers[question["id"]]} · {question["id"]}')
        if text.count(heading) != 1:
            raise InputError(f'PDF audit: primary heading must appear exactly once: {question["id"]}')
        for value in [question['prompt'], question['answer']] + [pair[1] for pair in question['options']]:
            if norm(value) not in text:
                raise InputError(f'PDF audit: missing preserved text for {question["id"]}')
    all_links = [link for page in doc for link in page.get_links()]
    if not all(link['kind'] == fitz.LINK_GOTO and 0 <= link['page'] < len(doc) for link in all_links):
        raise InputError('PDF audit: invalid internal link')
    for entry in audit['contents_links'] + audit['overview_links']:
        links = doc[entry['page'] - 1].get_links()
        matching = [link for link in links if abs(link['from'].x0 - entry['rect'][0]) < .2
                    and abs(link['from'].y0 - entry['rect'][1]) < .2]
        if len(matching) != 1 or matching[0]['page'] != entry['target_page'] - 1:
            raise InputError('PDF audit: incorrect navigation destination')
    for category in data['categories']:
        page = doc[audit['category_pages'][category['id']] - 1]
        if norm(category['title']) not in norm(page.get_text()):
            raise InputError('PDF audit: incorrect category target')
    for pi, page in enumerate(doc, 1):
        expected = tuple(reversed(A4)) if pi in audit['overview_pages'] else A4
        if abs(page.rect.width - expected[0]) > .1 or abs(page.rect.height - expected[1]) > .1:
            raise InputError('PDF audit: incorrect page orientation')
    audit.update({'pages': len(doc), 'internal_links': len(all_links), 'verified': True,
                  'checks': ['primary headings exactly once', 'prompts/options/answers preserved',
                             'contents and overview destinations', 'internal link validity', 'A4 orientations']})


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build linked study PDFs from a JSON bank.')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('validate', 'build'):
        command = commands.add_parser(name)
        command.add_argument('input', type=Path)
        if name == 'build':
            command.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_input(args.input)
        if args.command == 'validate':
            result = {'valid': True, 'categories': len(data['categories']), 'questions': len(data['questions']),
                      'sections': len(data.get('sections', []))}
        else:
            result = build(data, args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (InputError, OSError, ImportError, ValueError) as error:
        print(f'studypdf: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

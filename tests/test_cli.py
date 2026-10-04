"""Real subprocess/PDF acceptance tests; no source PDFs or network needed."""
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[1]


def sample():
    return {
        'title': 'Portable revision', 'subtitle': 'A study bank',
        'description': 'Preserve source material, not invented answers.',
        'categories': [
            {'id': 'alpha', 'title': 'First topic', 'related': ['beta']},
            {'id': 'beta', 'title': 'Second topic', 'related': ['alpha']},
            {'id': 'empty', 'title': 'Empty topic', 'related': [], 'empty_note': 'No items supplied.'}],
        'questions': [
            {'id': 'Q-1', 'category': 'alpha', 'prompt': 'Which statement?',
             'options': [['A', 'First choice'], ['B', 'Second choice']],
             'answer': 'A: First choice', 'status': 'SOURCE KEY', 'source': 'Source sheet 1'},
            {'id': 'Q-2', 'category': 'beta', 'prompt': 'Recall the route.', 'options': [],
             'answer': 'Unique preserved answer', 'status': 'SOURCE RECALL', 'source': 'Source sheet 2'}],
        'sections': [{'id': 'strategy', 'title': 'Study strategy', 'paragraphs': ['Review all topics.'],
                      'table': [['Topic', 'Action'], ['First topic', 'Recall']]}]}


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)

    def run_cli(self, data, command='build'):
        source = self.directory / 'input.json'
        source.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        output = self.directory / 'nested' / 'study.pdf'
        args = [sys.executable, '-m', 'studypdf', command, str(source)]
        if command == 'build':
            args += ['--output', str(output)]
        result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
        return result, output

    def assert_document(self, data, output):
        with fitz.open(output) as doc:
            # Pagination footers are not part of preserved source prose.
            texts = [p.get_text(clip=fitz.Rect(0, 0, p.rect.width, p.rect.height - 40)) for p in doc]
            text = '\n'.join(texts)
            norm = lambda s: re.sub(r'\s+', '', s)
            toc = doc.get_toc()
            audit = json.loads(output.with_suffix('.audit.json').read_text())
            self.assertEqual(audit['questions'], len(data['questions']))
            self.assertEqual(audit['categories'], len(data['categories']))
            self.assertTrue(audit['verified'])
            by = {c['id']: [] for c in data['categories']}
            for q in data['questions']:
                by[q['category']].append(q)
            for ci, c in enumerate(data['categories'], 1):
                target = audit['category_pages'][c['id']] - 1
                self.assertIn(norm(c['title']), norm(texts[target]))
                self.assertIn([1, f'{ci:02d} {c["title"]}', target + 1], toc)
                for qi, q in enumerate(by[c['id']], 1):
                    heading = f'{ci:02d}.{qi:02d} · {q["id"]}'
                    self.assertEqual(norm(text).count(norm(heading)), 1, heading)
                    self.assertIn(norm(q['answer']), norm(text))
                    for _, option in q['options']:
                        self.assertIn(norm(option), norm(text))
            for entry in audit['contents_links']:
                page = doc[entry['page'] - 1]
                matches = [link for link in page.get_links()
                           if abs(link['from'].x0 - entry['rect'][0]) < .2
                           and abs(link['from'].y0 - entry['rect'][1]) < .2]
                self.assertEqual(len(matches), 1)
                self.assertEqual(matches[0]['page'], entry['target_page'] - 1)
                if entry['kind'] == 'category':
                    self.assertEqual(entry['target_page'], audit['category_pages'][entry['id']])
            overview = set(audit['overview_pages'])
            for pi, page in enumerate(doc, 1):
                expected = (841.89, 595.28) if pi in overview else (595.28, 841.89)
                self.assertIn(f'PAGE {pi}', page.get_text())
                self.assertAlmostEqual(page.rect.width, expected[0], delta=.1)
                self.assertAlmostEqual(page.rect.height, expected[1], delta=.1)
                for link in page.get_links():
                    self.assertEqual(link['kind'], fitz.LINK_GOTO)
                    self.assertTrue(0 <= link['page'] < len(doc))
                if pi > 1:
                    returns = page.search_for('Contents')
                    self.assertTrue(returns)
                    self.assertTrue(any(l['page'] in [n - 1 for n in audit['contents_pages']]
                                        for l in page.get_links()))
            self.assertGreater(audit['internal_links'], len(data['categories']) * 2)
            md = output.with_suffix('.md').read_text()
            for q in data['questions']:
                self.assertIn(q['answer'], md)
                self.assertIn(q['prompt'], md)
            return text, audit

    def test_validate_is_dependency_free_and_portable(self):
        source = self.directory / 'input with spaces.json'
        source.write_text(json.dumps(sample()), encoding='utf-8')
        env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1')
        result = subprocess.run([sys.executable, '-S', '-m', 'studypdf', 'validate', str(source)],
                                cwd=self.directory, env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'valid': True, 'categories': 3, 'questions': 2, 'sections': 1})
        self.assertEqual(set(p.name for p in self.directory.iterdir()), {'input with spaces.json'})

    def test_unicode_missing_glyph_and_malformed_json_errors(self):
        data = sample()
        data['questions'][0]['prompt'] = 'An unsupported glyph: 漢'
        result, output = self.run_cli(data)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('font lacks characters: U+6F22', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertFalse(output.exists())
        source = self.directory / 'malformed.json'
        source.write_text('{invalid JSON', encoding='utf-8')
        result = subprocess.run([sys.executable, '-m', 'studypdf', 'validate', str(source)],
                                cwd=ROOT, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('invalid JSON at line 1', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_exact_related_topic_and_section_destinations(self):
        data = sample()
        result, output = self.run_cli(data)
        self.assertEqual(result.returncode, 0, result.stderr)
        audit = json.loads(output.with_suffix('.audit.json').read_text())
        with fitz.open(output) as doc:
            for category in data['categories']:
                page = doc[audit['category_pages'][category['id']] - 1]
                for related_id in category['related']:
                    ri = next(i for i, c in enumerate(data['categories'], 1) if c['id'] == related_id)
                    related_title = next(c['title'] for c in data['categories'] if c['id'] == related_id)
                    rects = page.search_for(f'Related topic: {ri:02d} {related_title}')
                    self.assertTrue(rects)
                    for rect in rects:
                        self.assertTrue(any(link['from'].intersects(rect)
                                            and link['page'] == audit['category_pages'][related_id] - 1
                                            for link in page.get_links()))
            section = data['sections'][0]
            record = next(e for e in audit['contents_links'] if e['id'] == section['id'])
            self.assertEqual(record['target_page'], audit['section_pages'][section['id']])
            self.assertIn(section['title'], doc[record['target_page'] - 1].get_text())

    def test_large_arbitrary_taxonomy_and_counts(self):
        data = sample()
        data['categories'] = [
            {'id': f'c-{i}', 'title': f'Topic {i}: ' + ('A deliberately wrapped category title ' * (i % 3)),
             'related': [f'c-{(i + 1) % 117}']}
            for i in range(117)]
        data['questions'] = []
        for i in range(141):
            q = copy.deepcopy(sample()['questions'][0])
            q.update(id=f'ENTRY-{i}', category=f'c-{i % 80}',
                     answer=f'Preserved source answer {i}', source=f'Source {i}',
                     status=('SOURCE KEY', 'STUDY ANSWER', 'SOURCE RECALL', 'UNRESOLVED')[i % 4])
            data['questions'].append(q)
        result, output = self.run_cli(data)
        self.assertEqual(result.returncode, 0, result.stderr)
        _, audit = self.assert_document(data, output)
        self.assertGreater(len(audit['contents_pages']), 1)
        self.assertGreater(len(audit['overview_pages']), 1)
        self.assertEqual(sum(audit['status_counts'].values()), 141)
        self.assertEqual(len(audit['contents_links']), 119)
        self.assertEqual(len(audit['overview_links']), 117)

    def test_questions_and_answers_split_across_pages(self):
        data = sample()
        q = data['questions'][0]
        q['prompt'] = 'START-PROMPT ' + ('Long question sentence with retained words. ' * 350) + ' END-PROMPT'
        q['options'][0][1] = 'START-OPTION ' + ('An extended answer choice. ' * 170) + ' END-OPTION'
        q['answer'] = 'START-ANSWER ' + ('Long source answer with precise content. ' * 350) + ' END-ANSWER'
        q['notes'] = ['Preserve this explanatory note.']
        q['original_prompt'] = 'Original <question> & exact wording.'
        result, output = self.run_cli(data)
        self.assertEqual(result.returncode, 0, result.stderr)
        text, audit = self.assert_document(data, output)
        self.assertGreaterEqual(audit['pages'], 15)
        self.assertIn('END-ANSWER', text)
        self.assertIn('Original <question> & exact wording.', text)
        with fitz.open(output) as doc:
            for page in doc:
                for block in page.get_text('dict')['blocks']:
                    if 'lines' not in block:
                        continue
                    for line in block['lines']:
                        for span in line['spans']:
                            self.assertGreaterEqual(span['bbox'][0], 48)
                            self.assertLessEqual(span['bbox'][2], page.rect.width - 48)
                            self.assertLessEqual(span['bbox'][3], page.rect.height - 12)

    def test_literal_markup_and_unicode_preserved(self):
        data = sample()
        exact = '<b>literal</b> & A < B > C; α β γ → ≥ ≤ ± µ café naïve — “quoted” | backslash \\.'
        q = data['questions'][0]
        q['prompt'] = exact
        q['answer'] = exact + '\nSecond preserved line.'
        q['options'] = [['A', exact], ['B', '<link href="https://invalid.example">not a link</link>']]
        q['original_prompt'] = exact
        q['notes'] = [exact]
        data['categories'][0]['note'] = exact
        data['sections'][0]['paragraphs'] = [exact]
        result, output = self.run_cli(data)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_document(data, output)

    def test_rejects_invalid_banks_without_writing_artifacts(self):
        mutations = [
            (lambda d: d['questions'].append(copy.deepcopy(d['questions'][0])), 'duplicate ID'),
            (lambda d: d['categories'].append(copy.deepcopy(d['categories'][0])), 'duplicate ID'),
            (lambda d: d['sections'].append(copy.deepcopy(d['sections'][0])), 'duplicate ID'),
            (lambda d: d['questions'][0].update(category='missing'), 'unknown category'),
            (lambda d: d['categories'][0].update(related=['missing']), 'unknown category'),
            (lambda d: d.update(categories=[]), 'at least one'),
            (lambda d: d.update(questions=[]), 'at least one'),
            (lambda d: d['questions'][0].update(status='MADE UP'), 'expected one of'),
            (lambda d: d['questions'][0].update(options=[['A']]), 'expected [letter, text]'),
            (lambda d: d['sections'][0].update(table=[['A', 'B'], ['C']]), 'rectangular'),
            (lambda d: d['questions'][0].update(prompt=42), 'expected a string'),
        ]
        for mutate, message in mutations:
            with self.subTest(message=message):
                data = sample()
                mutate(data)
                result, output = self.run_cli(data)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertFalse(output.exists())
                self.assertFalse(output.with_suffix('.md').exists())
                self.assertFalse(output.with_suffix('.audit.json').exists())

    def test_section_table_pagination_and_bookmarks(self):
        data = sample()
        data['sections'][0]['table'] = [['Label', 'Detail']] + [
            [f'Row {i}', f'Unique table cell {i}: ' + ('Extended retained text. ' * 30)]
            for i in range(75)]
        result, output = self.run_cli(data)
        self.assertEqual(result.returncode, 0, result.stderr)
        text, audit = self.assert_document(data, output)
        self.assertIn('Unique table cell 74', text)
        self.assertGreater(audit['pages'], 15)
        with fitz.open(output) as doc:
            self.assertIn([1, 'Study strategy', audit['section_pages']['strategy']], doc.get_toc())

    def test_theme_typography_and_margins(self):
        result, output = self.run_cli(sample())
        self.assertEqual(result.returncode, 0, result.stderr)
        with fitz.open(output) as doc:
            spans = [span for page in doc for block in page.get_text('dict')['blocks']
                     if 'lines' in block for line in block['lines'] for span in line['spans']]
            sizes = {round(span['size'], 2) for span in spans}
            self.assertTrue({21.5, 12.0, 9.25, 7.2}.issubset(sizes))
            self.assertTrue(all('Inter' in span['font'] for span in spans))
            colors = {span['color'] for span in spans}
            self.assertTrue({0x17324B, 0x167B7F, 0xA87324}.issubset(colors))
            for page in list(doc)[1:]:
                for block in page.get_text('dict')['blocks']:
                    if 'lines' not in block:
                        continue
                    for line in block['lines']:
                        for span in line['spans']:
                            self.assertGreaterEqual(span['bbox'][0], 48.0)
                            self.assertLessEqual(span['bbox'][2], page.rect.width - 48.0)
                            self.assertLessEqual(span['bbox'][3], page.rect.height - 12)

    def test_end_to_end(self):
        data = sample()
        result, output = self.run_cli(data)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_document(data, output)
        validated, _ = self.run_cli(data, 'validate')
        self.assertEqual(validated.returncode, 0, validated.stderr)


if __name__ == '__main__':
    unittest.main()

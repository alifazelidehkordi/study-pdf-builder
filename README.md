# Study PDF Builder

A reusable, local Python renderer adapted from the code used to make your linked Anatomy II study guide. It produces designed question-bank PDFs from structured JSON, with no API key, network request, or LLM required.

The bundled `examples/anatomy.json` reproduces the **content** of the final 206-question, 56-category bank. The portable renderer uses the same visual settings, but pagination can change because it is no longer hardcoded to one document.

## Quick start

Use Python 3.11 or newer from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m studypdf validate examples/demo.json
python -m studypdf build examples/demo.json --output output/demo.pdf
python -m studypdf build examples/anatomy.json --output output/anatomy.pdf
```

On Windows, activate with `.venv\Scripts\activate` instead of `source .venv/bin/activate`. If your executable is named `python3`, substitute that for `python`.

Each build writes a PDF, a matching Markdown companion, and a JSON verification audit beside the PDF. Generated outputs are ignored by Git.

## Make a similar PDF

1. Copy `examples/demo.json` to a new JSON file.
2. Set the document title, subtitle and description.
3. Replace the categories, in the order you want them to appear.
4. Add your questions with stable IDs and the appropriate category IDs.
5. Validate and build using the commands above.
6. Inspect the PDF before using or sharing it; the layout audit is not a medical or factual review.

### Minimal input

```json
{
  "title": "My Subject",
  "subtitle": "Answered Study Guide",
  "description": "Revision questions organized by topic.",
  "categories": [
    {"id": "topic-a", "title": "Topic A", "related": []}
  ],
  "questions": [
    {
      "id": "EXAM-01",
      "category": "topic-a",
      "prompt": "Write your question here.",
      "options": [["A", "First option"], ["B", "Second option"]],
      "answer": "B — Second option. Explain why here.",
      "status": "STUDY ANSWER",
      "source": "Your original source and question number",
      "notes": ["Any missing information or provenance caveat."]
    }
  ],
  "sections": []
}
```

Free-response questions use `"options": []`. Use `original_prompt` to preserve wording when you rewrite a prompt. Optional category fields are `note` and `empty_note`; optional planning sections have `id`, `title`, `paragraphs`, and an optional `table` of rows/cells. See [the input guide](docs/input-format.md).

## Design and navigation

- Bundled Inter Regular, Medium, Semibold and Bold fonts.
- Navy/teal/gold palette and gradient cover.
- A4 portrait revision pages and landscape overview pages.
- 21.5 pt topic headings, 12 pt card headings, 9.25 pt body text, 7.2 pt labels.
- Rounded question cards, answer panels and explicit answer provenance.
- Dynamic pagination; clickable contents and overview rows; bookmarks; related-topic links; return-to-contents links.
- Automatic category/item numbering without changing your source question IDs.

## Importing other PDFs

**This is a JSON-to-PDF builder, not an automatic arbitrary-PDF parser or medical answer generator.** PDF layouts vary, and the original extraction/classification/deduplication required review. Extract another PDF to structured records, check all choices and answer letters, assign categories, then build.

The anatomy example includes the complete import decision log from this session:

- 30 incoming MCQs reviewed.
- 3 equivalent duplicates skipped: incoming questions 2, 4 and 11.
- 27 added: 7 new tested details and 20 different MCQ variants.
- Existing answers and source keys were not overwritten.

`examples/anatomy-import-extracted.json` stores the extracted incoming questions, and `examples/anatomy-import-decisions.json` records every decision. `examples/anatomy-category-changes.json` records the earlier category expansion.

### Deduplication rule

A shared topic or correct answer does not make two questions duplicates. Compare the tested proposition **and all answer choices**, allowing harmless wording changes and reordering. Expand combined options (A+B) into their underlying statements before comparing; moving options can change what A+B means. Keep materially different distractors or new MCQ forms as variants if you want a question bank rather than a concept-only summary.

## Tests

```bash
python -m unittest discover -s tests -v
```

Tests exercise real PDF generation and inspect the resulting PDFs, including navigation, category counts and text preservation. No GitHub credentials are required to build or test.

## Provenance and privacy

`SOURCE KEY` means a key supplied by your source; it is not a guarantee the source is correct. `STUDY ANSWER` is a study/review answer that is not independently validated; `SOURCE RECALL` records an unverified recollection; `UNRESOLVED` marks insufficient source information. The anatomy content is preserved from supplied study materials and has not been independently medically fact-checked.

The repository contains code, structured anatomy data, small examples and fonts. **Raw uploaded PDFs, photographs, access tokens and local credentials are not included.** Keep this repository private if you do not want the anatomy dataset shared.

Inter font licensing is preserved in [`assets/fonts/OFL.txt`](assets/fonts/OFL.txt). Anatomy content provenance does not imply a grant of publication rights for the source exam materials.

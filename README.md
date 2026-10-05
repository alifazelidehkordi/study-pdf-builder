# Study PDF Builder

Turn a structured JSON question bank into a navigable study-guide PDF, a Markdown companion, and a machine-readable verification audit. Use it for course revision, certification practice, or any other text-based question bank—not just the bundled anatomy example.

The renderer runs locally with Python. Building and testing require no API key, GitHub credentials, network request, or LLM once dependencies are installed. You supply the questions, answers, categories, and source references; the tool handles layout and navigation.

[Quick start](#quick-start) · [Create your own bank](#create-a-bank-for-your-own-subject) · [Verification](#verification-and-limits) · [Troubleshooting](#troubleshooting)

## What it does—and does not do

- Renders multiple-choice and free-response questions with answers, source references, and provenance labels.
- Adds a cover, clickable contents, landscape topic overviews, bookmarks, related-topic links, and return-to-contents links.
- Paginates long questions and optional study-plan sections automatically; preserves source IDs while adding display numbering.
- Uses bundled Inter fonts and a fixed navy/teal/gold A4 layout.
- Checks selected text preservation and PDF navigation before writing outputs.

**It does not extract questions from PDFs, perform OCR, generate or fact-check answers, classify questions, or deduplicate a bank.** Prepare and review the JSON yourself or with a separate workflow. There is no GUI or configurable theme CLI.

## Quick start

### 1. Get the code and install dependencies

Use Python **3.11 or newer**, Git, and a terminal. Clone into a working directory, then run installation and CLI commands from the repository root. Access to this repository is required to clone it; an existing checkout or downloaded archive also works.

```bash
git clone https://github.com/alifazelidehkordi/study-pdf-builder.git
cd study-pdf-builder
python -m venv .venv
```

Activate the environment on **macOS / Linux**:

```bash
source .venv/bin/activate
```

On **Windows PowerShell**:

```powershell
.\.venv\Scripts\Activate.ps1
```

On **Windows Command Prompt**:

```bat
.venv\Scripts\activate.bat
```

Then install the pinned build dependencies:

```bash
python -m pip install -r requirements.txt
```

If your Python executable is named `python3`, use it to create the environment. Keep the checkout together: `studypdf.py` loads fonts from `assets/fonts/` beside it. This is a repository-based CLI, not a package installed by `pip install studypdf`.

### 2. Build the included demo

```bash
python -m studypdf validate examples/demo.json
python -m studypdf build examples/demo.json --output output/demo.pdf
```

Both commands print JSON to the terminal. Validation reports `"valid": true` and input counts; a successful build reports `"verified": true`, page counts, and audit details. Successful commands exit 0. Handled input/build errors print `studypdf:` to stderr and exit 1; invalid command-line arguments print usage information and exit 2.

Open `output/demo.pdf` in a PDF viewer. The build creates its output directory and writes:

| File | Purpose |
| --- | --- |
| `output/demo.pdf` | Linked study guide for reading or printing |
| `output/demo.md` | Text companion with questions, answers, sources, and category page references |
| `output/demo.audit.json` | Counts, one-based PDF page mappings, navigation records, and verification results |

**Reusing an output path overwrites all three matching files.** Use a different filename to keep an earlier build.

## Create a bank for your own subject

1. Copy [`examples/demo.json`](examples/demo.json) to `my-bank.json` in the repository root using your editor or file manager.
2. Change the title, subtitle, and short cover description.
3. Replace the categories and questions with your own material. Category array order controls topic order; questions retain their input order within each category.
4. Use globally unique IDs across categories, questions, and optional sections. Every question's `category` and each `related` reference must match an existing category ID.
5. Run:

   ```bash
   python -m studypdf validate my-bank.json
   python -m studypdf build my-bank.json --output output/my-guide.pdf
   ```

6. Inspect the PDF's layout and review the source content before sharing it. Re-run validation and build after each edit; no previous build or anatomy data is needed.

### Minimal complete input

Save this as `my-bank.json` to try a single-topic bank:

```json
{
  "title": "Project Management Revision",
  "subtitle": "Practice questions with explanations",
  "description": "A small example bank. Replace it with your own reviewed material.",
  "categories": [
    {"id": "risk", "title": "Risk Management", "related": []}
  ],
  "questions": [
    {
      "id": "PM-001",
      "category": "risk",
      "prompt": "What is the purpose of a risk register?",
      "options": [],
      "answer": "To record identified risks and track their assessment, responses, and ownership.",
      "status": "STUDY ANSWER",
      "source": "Illustrative example; not an official exam question"
    }
  ]
}
```

For multiple-choice questions, use pairs such as `"options": [["A", "First choice"], ["B", "Second choice"]]`. For free response, use `"options": []`. Answers are literal text: the renderer does not resolve an answer letter to an option or check that they agree.

The top-level `title`, `subtitle`, `description`, `categories`, and `questions` fields are required. Categories and questions must each contain at least one entry, but individual categories may be empty. Each question requires `id`, `category`, `prompt`, `options`, `answer`, `status`, and `source`. `sections`, question `notes` / `original_prompt`, and category `related` / `note` / `empty_note` are optional. In the PDF, input strings are rendered as literal text, not Markdown or HTML. The Markdown companion retains supplied markup, which a Markdown viewer may interpret as formatting or HTML.

See the [JSON input reference](docs/input-format.md) for category links, preserved original wording, and optional sections with tables.

### Answer provenance

Set `status` to exactly one of these values:

| Status | Intended meaning |
| --- | --- |
| `SOURCE KEY` | Answer supplied by the original source's key; not a guarantee of correctness |
| `STUDY ANSWER` | Study/review answer without independent validation |
| `SOURCE RECALL` | Unverified recollection of a source answer |
| `UNRESOLVED` | Insufficient information to establish an answer |

Use `source` and optional `notes` to record origins, uncertainty, missing figures, or editorial changes. These labels describe provenance; they do not certify an answer.

## Verification and limits

`validate` checks JSON structure, required types, unique IDs, category references, option-pair shape, allowed statuses, and rectangular section tables. It uses only the Python standard library and does **not** prove that the input can be rendered.

`build` also checks font coverage and rendering constraints, then audits the generated PDF for primary question headings appearing exactly once, preserved prompt/option/answer text, contents and overview destinations, internal-link validity, and A4 orientations. Prompt/answer/option checks search whitespace-normalized text across the PDF; they do not prove placement within each question card or independently verify option labels. Audit page numbers are one-based and refer to physical PDF pages.

A successful audit is **not** a complete visual inspection, a factual review, or proof that every source/notes/table field was checked for text preservation. Review the PDF yourself. The current input format is text-only: it has no image, figure, or equation-rendering fields. Characters missing from the bundled font cause an error rather than silent substitution. Page sizes, fonts, and colors are fixed in the renderer; changing them requires code changes.

If you start with a source PDF, extract its content separately, review wording and all answer choices, assign stable IDs and categories, and record provenance before rendering. Any classification or duplicate-removal decisions belong to that preparation workflow, not to this CLI.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `No module named studypdf` | Run from the repository root, where `studypdf.py` lives. |
| Missing `pymupdf` or `reportlab` | Activate the same environment you installed into, then run `python -m pip install -r requirements.txt`. |
| Invalid JSON with a line/column | Fix JSON syntax: double-quoted strings, no comments, no trailing commas. Save as UTF-8. |
| Duplicate ID or unknown category | Make IDs unique across all entry types and correct `category` / `related` references. |
| Invalid status or option pair | Use an exact status above; each option must be a two-string array. |
| `bundled Inter font lacks characters: U+…` | The font cannot render those characters. Use supported text, or adapt the renderer/fonts and test the result. Structural validation alone cannot detect this. |
| Missing bundled font | Restore `assets/fonts/` from the checkout; do not move `studypdf.py` alone. |
| Cover text or navigation title too long | Shorten the named title, subtitle, or description and rebuild. |
| `--output must have a .pdf suffix` | Provide an output filename ending in `.pdf`. Quote paths containing spaces. |
| PowerShell blocks activation | Skip activation and run `.\.venv\Scripts\python.exe` in place of `python` for installation and CLI commands. |

## Examples and repository layout

| Path | Role |
| --- | --- |
| [`studypdf.py`](studypdf.py) | Validation, rendering, verification, and CLI entry point |
| [`requirements.txt`](requirements.txt) | Pinned build dependencies |
| [`examples/demo.json`](examples/demo.json) | Small starter bank with MCQ, free response, related topics, and a study plan |
| [`docs/input-format.md`](docs/input-format.md) | Detailed JSON contract |
| [`tests/test_cli.py`](tests/test_cli.py) | Subprocess and PDF acceptance tests |
| `assets/fonts/` | Bundled Inter font files and their license |
| `examples/anatomy*.json` | Larger subject-specific bank and historical editorial records |

The anatomy files are **optional examples, not prerequisites or a prescribed taxonomy**. To render the larger bank:

```bash
python -m studypdf build examples/anatomy.json --output output/anatomy.pdf
```

`anatomy-import-extracted.json`, `anatomy-import-decisions.json`, and `anatomy-category-changes.json` document one dataset's manual preparation. They are not renderer inputs or automatic import/deduplication features. The anatomy content has not been independently medically fact-checked.

## Development and tests

With dependencies installed, run from the repository root:

```bash
python -m unittest discover -s tests -v
```

Tests generate and inspect real PDFs, including large taxonomies, multi-page text and tables, literal-text preservation, navigation, and invalid-input errors. To contribute a change, include a reproducible example and run the suite; add a test when changing validation or rendering behavior. For a bug report, include the command, Python version, error text, and a minimal sanitized JSON bank—not confidential study material.

## Privacy and licensing

Rendering is local; you control the input and generated files. PDFs and Markdown companions include supplied study content and source references, while audits include IDs and page mappings. Review all outputs before sharing them. The default `output/` directory is ignored by Git, as are `*.pdf` and `*.audit.json`. Markdown companions written elsewhere are not automatically ignored. **Ignore rules are not a privacy guarantee**: check `git status` and do not commit private banks, source documents, outputs, or credentials.

The bundled anatomy bank is study material, not permission to publish its underlying source content. Use only material you have permission to use and share; keep access restricted where appropriate.

Inter's font license is included in [`assets/fonts/OFL.txt`](assets/fonts/OFL.txt). This checkout does not include a project-wide code license; the font license does not grant rights to the code or study datasets.

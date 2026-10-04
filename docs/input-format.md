# JSON input format

Keep identifiers stable when changing display titles or category order. Category IDs and question IDs must be unique. Every question's `category` and every category's `related` entry must refer to an existing category ID.

## Document

| Field | Meaning |
|---|---|
| `title` | Document name and cover title |
| `subtitle` | Cover subtitle |
| `description` | Short cover introduction |
| `categories` | Ordered category array; at least one category |
| `questions` | Question array; at least one question |
| `sections` | Optional ordered planning/audit sections |

## Category

```json
{
  "id": "kidney",
  "title": "Kidney",
  "related": ["ureter", "bladder"],
  "note": "A brief note on this category's scope.",
  "empty_note": "No source question was available for this topic."
}
```

Categories can have no assigned questions. Do not invent questions merely to fill them. Their placement in the array controls PDF order, and their `related` references create navigation links.

## Question

```json
{
  "id": "SOURCE-01",
  "category": "kidney",
  "prompt": "Rewritten question wording",
  "original_prompt": "Optional original wording",
  "options": [["A", "An option"], ["B", "Another option"]],
  "answer": "B — Another option\n\nOptional rationale.",
  "status": "STUDY ANSWER",
  "source": "Source filename, question number and page",
  "notes": ["An answer-provenance or missing-figure caveat."]
}
```

Option letters are literal strings, not indexes. An absent option must be labelled as absent rather than guessed. For free response, use an empty option array. Answer strings are retained: the renderer does not select answers from their letters or correct factual mistakes.

Allowed status values:

- `SOURCE KEY`
- `STUDY ANSWER`
- `SOURCE RECALL`
- `UNRESOLVED`

## Planning section

```json
{
  "id": "study-plan",
  "title": "Suggested Study Priority",
  "paragraphs": ["First paragraph.", "Second paragraph."],
  "table": [["Topic", "Priority"], ["Kidney", "Review first"]]
}
```

Tables are optional. IDs must be globally unique across categories, questions and sections. Navigation depends on IDs, not a hardcoded anatomy topic count.

## Verification boundaries

Rendering and link checks verify the artifact, not the truth of its source content. Classification and semantic deduplication are editorial decisions. The anatomy import decision log is provided as an example, not an automatic rule for other material.

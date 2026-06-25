# Annotation Guidelines — PII Detection Benchmark Gold Standard

**Version:** 1.0
**Purpose:** Define a single, system-independent standard for ground-truth PII
annotation. Annotators apply these rules **blind to any detector's output**. The
goal is a gold standard a neutral third party (or a competitor) would accept —
not one tuned to make any particular system look good.

> **Independence principle.** Ground truth is decided by these rules and the text
> alone. It is never derived from, or reconciled against, what AmbientMeta,
> Presidio, spaCy, or any other system happens to detect. "Both models agree" is
> **not** evidence of correctness.

---

## 1. Span format

Each annotation is `{start, end, text, entity_type}` where `text == sample.text[start:end]`
exactly (including case and internal punctuation). Offsets are 0-based, end-exclusive.

- **No leading/trailing whitespace or punctuation** in a span.
- **Possessives:** exclude the trailing `'s` (annotate `Smith`, not `Smith's`).
- **One span per entity mention.** Do not merge two adjacent entities; do not split one.

---

## 2. Entity types

Only these nine types exist. Anything else is **not annotated** (it is not a
false positive — see §4 on scoring scope).

| Type | Definition | Include | Exclude |
|------|-----------|---------|---------|
| **PERSON** | A name denoting a specific human. | Given, family, or full names; fictional people. | Honorifics/titles (`Dr.`, `Mr.`, `Ms.`, `Prof.`), role words (`attending physician`). Annotate the name tokens only. |
| **EMAIL** | A syntactically valid email address. | Any `local@domain.tld`, including unusual TLDs (`.local`, `.internal`) and IDN domains (`société.fr`). | Bare domains or URLs without `@`. |
| **PHONE** | A telephone number. | US and international formats, with or without separators, extensions. | 10-digit numbers explicitly labeled as a different ID (NPI, account, order #). |
| **SSN** | A US SSN-format identifier: `XXX-XX-XXXX` (9 digits). | **Includes ITINs and any number labeled "tax number / income tax number / tax ID" that has SSN format** — structurally identical, equally sensitive, a redactor must catch it. | 9-digit numbers with no dashes and no SSN/tax context (treat as unknown ID → not annotated). |
| **CREDIT_CARD** | A payment-card number (13–19 digits, passes Luhn). | Spaced/dashed/grouped formats. | Numbers that fail Luhn unless explicitly labeled as a card. |
| **LOCATION** | A geographic place or address. | Cities, states, countries, streets, full addresses, real or clearly-fictional place names **used as a place in context**. | A canonical person name jammed into a place slot in incoherent synthetic text (see §3). |
| **NPI** | National Provider Identifier: 10-digit healthcare provider ID. | Any 10-digit number labeled `NPI` / `provider #` / in a provider-ID slot. | Phone numbers, MRNs. |
| **MRN** | Medical Record Number. | Numbers in an `MRN:` / `medical record #` slot. | NPIs, account numbers. |
| **ORGANIZATION** | A company, agency, institution, or team. | `Inc/LLC/Corp/& Sons`, agencies (`Defense Department`), institutions, metonyms for an institution (`the White House` = the administration; `the Pentagon` = DoD). | A **bare personal name** in a business context (a person can win a contract) unless it carries an org marker. |

---

## 3. The coherence rule (critical — fixes the fabricated-ambiguous problem)

Some synthetic samples force a famous person/place name into the wrong slot in a
way **no real writer would produce**. These are not "hard cases" — they are broken.

- *"the White House moved to Portland to start her new job as a software engineer"* → labeling "the White House" as **PERSON** is invalid.
- *"We drove through Jane Doe, a small town in rural Montana"* → labeling "Jane Doe" as **LOCATION** is invalid.

**Test:** Would a competent human reader, seeing only this text, naturally read the
span as the labeled type? If the sentence only "works" because a generator was told
to use the word as that type, the sample is **INCOHERENT**.

**Action for incoherent samples:** flag `disposition = "repair"` if it can be
rewritten into a genuinely plausible ambiguity (e.g., choose a name that really is
attested as both a person and a place — *Jordan*, *Austin*, *Madison*), else
`disposition = "delete"`. Do **not** silently keep them with their bad label.

Genuine ambiguity is encouraged and must be **kept**: *"Austin reviewed the deploy"*
(PERSON) vs *"the office is in Austin"* (LOCATION) are both coherent.

---

## 4. Scoring scope & comprehensiveness

Each category has a `scored_entity_types` set in its `metadata.json`. Within a
category, a detector is only scored on those types.

- **Comprehensiveness:** annotate **every** mention of a scored type that appears
  in the text. Leaving a scored-type entity unannotated turns a *correct* detection
  into a false positive — the single most common defect in the current dataset
  (e.g. an `NPI: 8404456690` left unlabeled in a referral letter).
- Entities whose type is **not** in `scored_entity_types` for that category should
  **not** be annotated (and detectors are not penalized for finding them — the
  runner filters predictions to scored types).
- Every annotated type **must** be in that category's `scored_entity_types`. If a
  correct annotation's type is not scored, the metadata is wrong, not the annotation
  — flag it.

---

## 5. Category-specific rules

### Standard
Clean, comprehensive annotation of all scored-type PII. Baseline.

### Ambiguous
Each sample centers on one **pivot** span whose type depends on context. The pivot
is annotation index `[0]`. Still annotate any *other* scored-type PII in the text
(comprehensiveness). Apply §3 — much of the current cleanup work is here.

### Contextual (drives the CSS metric)
Samples come in **pairs** linked by `context_pair`. For a valid pair:
1. **Same surface string** in both members (case/whitespace-insensitive). `"Grace"`
   vs `"Grace Hopper"` is **invalid**. `"4801845148"` vs `"4829371650"` is **invalid**
   — an NPI/PHONE pair must reuse the *same* digits in both contexts.
2. **Different ground-truth type** across the two members (that is the whole point).
3. The pivot span is annotation `[0]` in each member; it is the string being tested.
4. Back-references are bidirectional (`a.context_pair == b.id` and vice-versa).

Repair broken pairs by making the surface string identical and the types genuinely
divergent; delete pairs that cannot be made coherent.

### Adversarial
International formats, obfuscation, code blocks, noisy text. Annotate scored-type
PII even when formatting is unusual (e.g. `admin@internal.service.local` is a valid
EMAIL). Robustness is the point — do not drop hard-but-valid cases.

---

## 6. Tricky cases — rulings

| Case | Ruling |
|------|--------|
| `Income Tax Number: 311-58-4775` | **SSN** (ITIN/tax-ID, SSN format, sensitive). |
| `Dr. Olga Hill` | PERSON span = `Olga Hill` (title excluded). |
| `Chanakya Yutika Shukla has been awarded the contract` | **PERSON** (bare personal name; no org marker). |
| `the White House and the Defense Department` (policy stance) | both **ORGANIZATION** (metonymic institutions). |
| `the White House moved to Portland for her engineering job` | **INCOHERENT** → repair/delete. |
| `arrived in Jordan` / `Jordan presented results` | LOCATION / PERSON (genuine, keep). |
| `NPI 3433200375 — Dr. Daniel Kane` | annotate **NPI** `3433200375` **and** PERSON `Daniel Kane`. |
| `call 4829371650 and press 2` | **PHONE** (10 digits in a call slot). |
| 9-digit number, no dashes, no context | **not annotated** (unknown identifier). |

---

## 7. Disposition field (annotation output)

For each sample the annotator returns, alongside the gold spans:

- `disposition`: `"keep"` (text fine, annotations corrected) | `"repair"` (text must
  be rewritten — provide `repair_suggestion`) | `"delete"` (unsalvageable).
- `notes`: one line on any non-obvious ruling applied.

A change to an existing annotation (add / remove / re-type / re-span) is only
accepted after **independent adversarial verification** by a second annotator who is
prompted to challenge it against these rules.

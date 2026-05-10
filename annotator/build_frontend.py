#!/usr/bin/env python3
"""Build the Tauri frontend from the annotation tool generator.

Takes the existing annotation_tool.py output and patches it for Tauri:
1. Replaces localStorage with Tauri invoke calls
2. Replaces download exports with native file save dialogs
3. Adds auto-save to a state file
4. Adds native file open for import

Usage:
    python annotator/build_frontend.py --dataset data/generated/curated_dataset.jsonl
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

# Reuse entity types and fake PII from the annotation tool
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

ENTITY_TYPES = [
    "PERSON", "EMAIL", "PHONE", "SSN", "CREDIT_CARD",
    "LOCATION", "ORGANIZATION", "NPI", "MRN", "DEA",
    "ADDRESS", "DATE_OF_BIRTH", "IP_ADDRESS", "URL",
    "CREDENTIALS", "REFERENCE_ID",
]


def _generate_fake_pii(count=50):
    try:
        from faker import Faker
        fake = Faker()
        Faker.seed(2026)
        entries = []
        for _ in range(count):
            entries.append({
                "name": fake.name(),
                "first_name": fake.first_name(),
                "last_name": fake.last_name(),
                "ssn": fake.ssn(),
                "phone": fake.phone_number(),
                "email": fake.email(),
                "credit_card": fake.credit_card_number(card_type="visa16"),
                "address": fake.address().replace("\n", ", "),
                "street": fake.street_address(),
                "city": fake.city(),
                "state": fake.state_abbr(),
                "zip": fake.zipcode(),
                "company": fake.company(),
                "job": fake.job(),
                "dob": fake.date_of_birth(minimum_age=18, maximum_age=90).isoformat(),
                "ip": fake.ipv4(),
                "url": fake.url(),
            })
        return entries
    except ImportError:
        return []


def build(dataset_path: str | None, output_path: str):
    samples = []
    if dataset_path:
        for line in open(dataset_path):
            line = line.strip()
            if not line:
                continue
            sample = json.loads(line)
            if "_category" not in sample:
                sample["_category"] = sample.get("metadata", {}).get("category", "custom")
            # Compute hash
            content = sample["text"] + json.dumps(sample.get("annotations", []), sort_keys=True)
            sample["_hash"] = hashlib.md5(content.encode()).hexdigest()[:8]
            samples.append(sample)

    samples_json = json.dumps(samples, ensure_ascii=False)
    types_json = json.dumps(ENTITY_TYPES)
    fake_pii = _generate_fake_pii(50)
    fake_pii_json = json.dumps(fake_pii, ensure_ascii=False)

    # Read the HTML template
    template_path = Path(__file__).parent / "src" / "template.html"
    if not template_path.exists():
        print(f"Template not found at {template_path}")
        sys.exit(1)

    html = template_path.read_text()
    html = html.replace("__SAMPLES_JSON__", samples_json)
    html = html.replace("__TYPES_JSON__", types_json)
    html = html.replace("__FAKE_PII_JSON__", fake_pii_json)
    html = html.replace("__SAMPLE_COUNT__", str(len(samples)))

    Path(output_path).write_text(html, encoding="utf-8")
    print(f"Frontend built: {output_path} ({len(samples)} samples)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str, default=None)
    parser.add_argument("--output", default="annotator/src/index.html")
    args = parser.parse_args()
    build(args.dataset, args.output)

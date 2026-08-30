"""
training/build_dataset.py

Writes the labelled intent corpus to `training/datasets/intents.csv`.

    python -m training.build_dataset

External data is welcome: any CSV in `training/datasets/extra/` with `text`
and `intent` columns (or `sentence`/`utterance`/`query` and `label`/`category`)
is merged in. That is the supported path for Kaggle / HuggingFace exports --
download them yourself, drop them in that folder, re-run this script and then
`train_intents.py`. Nothing is fetched from the internet automatically, so a
fresh clone trains identically on any machine, online or offline.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATASET_DIR = ROOT / "datasets"
EXTRA_DIR = DATASET_DIR / "extra"
OUTPUT = DATASET_DIR / "intents.csv"

TEXT_COLUMNS = ("text", "sentence", "utterance", "query", "question", "prompt")
LABEL_COLUMNS = ("intent", "label", "category", "class", "target")


def _load_extra() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if not EXTRA_DIR.exists():
        return rows
    for path in sorted(EXTRA_DIR.glob("*.csv")):
        try:
            with path.open(newline="", encoding="utf-8", errors="replace") as handle:
                reader = csv.DictReader(handle)
                fields = [f.lower().strip() for f in (reader.fieldnames or [])]
                text_key = next((f for f in TEXT_COLUMNS if f in fields), None)
                label_key = next((f for f in LABEL_COLUMNS if f in fields), None)
                if not text_key or not label_key:
                    print(f"  skipped {path.name}: no recognised text/label columns")
                    continue
                added = 0
                for row in reader:
                    normalized = {k.lower().strip(): (v or "") for k, v in row.items() if k}
                    text = normalized.get(text_key, "").strip()
                    label = normalized.get(label_key, "").strip()
                    if text and label:
                        rows.append((text, label))
                        added += 1
                print(f"  merged {path.name}: {added} rows")
        except OSError as exc:
            print(f"  failed {path.name}: {exc}")
    return rows


def _assert_no_leakage(rows: list[tuple[str, str]]) -> None:
    """Fails loudly if any training row also appears in the held-out eval set.

    Without this guard the reported held-out accuracy could quietly become
    meaningless the moment someone adds a paraphrase that happens to match an
    eval utterance. A leaked benchmark is worse than no benchmark.
    """
    from training import eval_set

    def norm(text: str) -> str:
        return " ".join(text.lower().split()).strip(" ?.!,")

    held_out = {norm(text) for text, _ in eval_set.rows()}
    collisions = sorted({norm(text) for text, _ in rows} & held_out)
    if collisions:
        preview = ", ".join(repr(c) for c in collisions[:5])
        raise SystemExit(
            f"Dataset leakage: {len(collisions)} training row(s) appear in the held-out "
            f"eval set ({preview}). Reword them in templates.py or paraphrases.py."
        )
    print(f"leakage check : clean ({len(held_out)} held-out utterances unseen in training)")


def build() -> Path:
    sys.path.insert(0, str(ROOT.parent))
    from training.paraphrases import rows as paraphrase_rows
    from training.templates import generate

    rows = generate()
    print(f"generated {len(rows)} utterances from templates")

    # Hand-written paraphrases carry most of the real lexical diversity, so they
    # are repeated a few times to keep them influential against the much larger
    # template expansion rather than being drowned out by it.
    hand = paraphrase_rows()
    rows += hand * 4
    print(f"added {len(hand)} hand-written paraphrases (x4 weighting)")

    extra = _load_extra()
    if extra:
        rows += extra
        print(f"total after merging external data: {len(rows)}")

    _assert_no_leakage(rows)

    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    EXTRA_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["text", "intent"])
        writer.writerows(rows)
    print(f"wrote {OUTPUT} ({len(rows)} rows)")
    return OUTPUT


if __name__ == "__main__":
    build()

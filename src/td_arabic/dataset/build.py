"""Build ``data/dataset/`` from the final lexicon and the sentence bank.

    data/dataset/
      lexicon/entries.jsonl        une entrée lexicale par ligne (homographes séparés)
      corpus/sentences.jsonl       une paire de phrases par ligne
      annotations/issues.jsonl     erreurs détectées ou corrigées (audit)
      exports/sft/{train,dev,test,probe}.jsonl   exemples « messages » toutes tâches
      exports/mt/{train,dev,test}.jsonl          paires au format Hugging Face « translation »
      stats.json                   effectifs par tâche, découpage, type d'erreur

Everything in ``data/dataset`` is generated: fix the sources (``data/resources``, the sentence
bank) or close an issue, then rebuild. Command: ``td-arabic dataset``.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from td_arabic.config import PATHS
from td_arabic.dataset import quality, records, tasks
from td_arabic.utils.io import read_csv, write_json
from td_arabic.utils.log import get_logger

log = get_logger(__name__)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    """Atomically write one JSON object per line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(path)


def build(lexicon_csv: Path | None = None, sentences_csv: Path | None = None,
          corrections_csv: Path | None = None) -> dict:
    """Build every record, issue and export in memory.

    Args:
        lexicon_csv: Final lexicon; defaults to ``PATHS.lexicon_final_csv``.
        sentences_csv: Sentence bank; defaults to ``PATHS.sentences_csv``.
        corrections_csv: Hand-made corrections; defaults to ``PATHS.entry_corrections_csv``.

    Returns:
        ``{"entries", "sentences", "issues", "sft", "mt"}``.
    """
    entries = records.build_entries(read_csv(lexicon_csv or PATHS.lexicon_final_csv))
    issues = quality.check_entries(entries)
    corrections = corrections_csv or PATHS.entry_corrections_csv
    if corrections.exists():
        issues += quality.corrections_as_issues(read_csv(corrections), entries)
    for e in entries:
        for s in e["senses"]:
            if s["origin"] == "ajout":     # le lexique imprimé fait foi ; les ajouts sont vérifiés
                issues += quality.spelling_issues(e["lemma"][records.LANG_TD], e["id"], "lemma")

    sentences_path = sentences_csv or PATHS.sentences_csv
    sentences = []
    if sentences_path.exists():
        sentences = records.build_sentences(read_csv(sentences_path), records.lemma_index(entries))
        issues += quality.check_sentences(sentences)

    quality.attach(entries, issues)
    quality.attach(sentences, issues)
    sft = tasks.lexicon_examples(entries) + tasks.sentence_examples(sentences)
    return {"entries": entries, "sentences": sentences, "issues": issues, "sft": sft,
            "mt": tasks.mt_rows(entries, sentences)}


def stats(data: dict) -> dict:
    """Count records, issues and examples (written to ``stats.json``)."""
    return {
        "entrees": len(data["entries"]),
        "sens": sum(len(e["senses"]) for e in data["entries"]),
        "expressions": sum(len(e["expressions"]) for e in data["entries"]),
        "entrees_entrainables": sum(e["quality"]["trainable"] for e in data["entries"]),
        "phrases": len(data["sentences"]),
        "phrases_entrainables": sum(s["quality"]["trainable"] for s in data["sentences"]),
        "erreurs_par_type": dict(Counter(f"{i['type']} ({i['severity']}, {i['status']})" for i in data["issues"])
                                 .most_common()),
        "exemples_par_tache": dict(Counter(f"{x['task']}:{x['split']}" for x in data["sft"]).most_common()),
        "mt_par_split": dict(Counter(f"{r['unit']}:{r['split']}" for r in data["mt"])),
    }


def run(folder: Path | None = None) -> dict:
    """Build the dataset and write it to ``data/dataset``.

    Args:
        folder: Destination; defaults to ``PATHS.dataset``.

    Returns:
        The statistics.
    """
    folder = folder or PATHS.dataset
    data = build()
    write_jsonl(folder / "lexicon" / "entries.jsonl", data["entries"])
    write_jsonl(folder / "corpus" / "sentences.jsonl", data["sentences"])
    write_jsonl(folder / "annotations" / "issues.jsonl", data["issues"])
    for split in (*tasks.SPLITS, "probe"):
        write_jsonl(folder / "exports" / "sft" / f"{split}.jsonl", [x for x in data["sft"] if x["split"] == split])
    for split in tasks.SPLITS:
        write_jsonl(folder / "exports" / "mt" / f"{split}.jsonl", [r for r in data["mt"] if r["split"] == split])
    result = stats(data)
    write_json(folder / "stats.json", result)
    log.info("Jeu de données : %d entrées, %d phrases, %d problèmes, %d exemples -> %s", result["entrees"],
             result["phrases"], len(data["issues"]), len(data["sft"]), folder.relative_to(PATHS.root)
             if folder.is_relative_to(PATHS.root) else folder)
    return result

"""Training data for Unsloth, built from the corpus.

The model is trained with **Unsloth Studio** (see :mod:`td_arabic.finetune.unsloth`); this
module only prepares the files to load in it: ``data/finetune/train.jsonl`` and
``valid.jsonl``, one chat per line in the ChatML format (``{"messages": [...]}``) that
Unsloth recognises.

Every example is a short chat: a system prompt, the sentence to translate and its
translation. Two sources, both already reviewed by a person:

- the lexicon pairs (``data/processed/corpus_arabe_tchadien_francais.csv``, with the
  validated hand-made additions);
- the **validated** sentences of the sentence bank. Drafts are never used.

With ``data.source: dataset`` the examples are instead the multi-task examples of
``td-arabic dataset`` (``data/dataset/exports/sft``: translation, definition, morphology,
spelling), with the dataset's own split (see :func:`dataset_examples`).

The split between training and evaluation is made **per pair**, not per example: the
two directions of a pair (fr -> td and td -> fr) always land on the same side, so the
evaluation never contains a pair seen in the other direction during training. The split
is a hash of the pair id, hence stable when new pairs are added.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from td_arabic.config import PATHS
from td_arabic.utils.io import read_csv

INSTRUCTIONS = {"fr-ar": "Traduis en arabe tchadien : {text}", "ar-fr": "Traduis en français : {text}"}
DATASET_SPLITS = ("train", "dev", "probe")   # « test » reste hors de l'entraînement et de son suivi


def pair_examples(pair_id: str, fr: str, td: str, source: str, directions: list[str],
                  system_prompt: str) -> list[dict]:
    """Build the chat examples of one translation pair.

    Args:
        pair_id: Stable id of the pair (``lex:abad:1``, ``phr:mar-1a2b3c4d``).
        fr: French side.
        td: Chadian Arabic side (latin script).
        source: ``lexique`` or ``phrase``.
        directions: ``fr-ar`` and/or ``ar-fr``.
        system_prompt: Instruction given to the model.

    Returns:
        One dict per direction: ``{"messages": [...], "pair_id", "source", "direction"}``.
    """
    examples = []
    for direction in directions:
        question, answer = (fr, td) if direction == "fr-ar" else (td, fr)
        examples.append({
            "messages": [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": INSTRUCTIONS[direction].format(text=question)},
                         {"role": "assistant", "content": answer}],
            "pair_id": pair_id, "source": source, "direction": direction})
    return examples


def in_validation(pair_id: str, ratio: float) -> bool:
    """Tell whether a pair belongs to the evaluation set (stable hash split).

    Args:
        pair_id: Stable id of the pair.
        ratio: Share of pairs kept for evaluation, between 0 and 1.

    Returns:
        True for about ``ratio`` of the pairs, always the same ones.
    """
    bucket = int(hashlib.md5(pair_id.encode("utf-8")).hexdigest(), 16) % 10_000
    return bucket < ratio * 10_000


def collect_pairs(settings: dict, corpus_csv: Path | None = None,
                  sentences_csv: Path | None = None) -> list[tuple[str, str, str, str]]:
    """Read the translation pairs to learn from.

    Args:
        settings: The ``data`` section of the configuration.
        corpus_csv: Lexicon corpus; defaults to ``PATHS.corpus_csv``.
        sentences_csv: Sentence bank; defaults to ``PATHS.sentences_csv``.

    Returns:
        ``(pair_id, fr, td, source)`` tuples, without empty sides or duplicates.
    """
    pairs: dict[tuple[str, str], tuple[str, str, str, str]] = {}
    if settings.get("include_lexicon", True):
        corpus = read_csv(corpus_csv or PATHS.corpus_csv)
        if not settings.get("include_expressions", True):
            corpus = corpus[corpus["forms"] != "expr."]
        for row in corpus.itertuples():
            pair_id = f"lex:{row.src}:{row.sense_number}:{row.output}"
            pairs.setdefault((row.output.strip(), row.src.strip()), (pair_id, row.output, row.src, "lexique"))
    path = sentences_csv or PATHS.sentences_csv
    if settings.get("include_validated_sentences", True) and path.exists():
        bank = read_csv(path)
        for row in bank[bank["statut"] == "validee"].itertuples():
            pairs.setdefault((row.fr.strip(), row.td.strip()), (f"phr:{row.id}", row.fr, row.td, "phrase"))
    return [p for p in pairs.values() if p[1].strip() and p[2].strip()]


def choose_pairs(pairs: list[tuple], max_pairs: int) -> list[tuple]:
    """Keep ``max_pairs`` training pairs, chosen at random but always the same ones.

    The pairs are ordered by a hash of their id: the choice is reproducible and the subsets are
    **nested** (the 100 pairs are part of the 1 000), which makes runs on 100, 1 000… pairs
    comparable.

    Args:
        pairs: ``(pair_id, fr, td, source)`` tuples.
        max_pairs: Number of pairs to keep; 0 keeps them all.

    Returns:
        The chosen pairs.
    """
    if not max_pairs or max_pairs >= len(pairs):
        return pairs
    return sorted(pairs, key=lambda p: hashlib.md5(f"choix:{p[0]}".encode("utf-8")).hexdigest())[:max_pairs]


def load_dataset_exports(folder: Path | None = None) -> list[dict]:
    """Read the multi-task examples of ``td-arabic dataset`` (``exports/sft``).

    Args:
        folder: The ``exports/sft`` folder; defaults to ``PATHS.dataset / "exports" / "sft"``.

    Returns:
        Every example of every split. When the exports were never written, they are built in
        memory (without writing anything).
    """
    folder = folder or PATHS.dataset / "exports" / "sft"
    files = [folder / f"{split}.jsonl" for split in DATASET_SPLITS]
    if all(f.exists() for f in files):
        return [row for f in files for row in read_jsonl(f)]
    from td_arabic.dataset.build import build
    return build()["sft"]


def dataset_examples(settings: dict, examples: list[dict]) -> tuple[list[dict], list[dict]]:
    """Select and adapt the multi-task examples for training.

    The split is the dataset's (``dev`` and ``probe`` for evaluation, ``test`` never used here):
    it is made by lemma and by sentence template, so ``valid_ratio`` does not apply.

    Args:
        settings: The ``data`` section: ``tasks`` (empty = all), ``directions`` (applies to the
            translation tasks only), ``system_prompt`` and ``max_pairs``.
        examples: Output of :func:`load_dataset_exports`.

    Returns:
        ``(train, valid)``. Each example gets ``pair_id`` (its source records, so ``max_pairs``
        keeps or drops both directions of a pair together) and ``source`` (``phrase`` or
        ``lexique``, as with the corpus); the system message becomes ``system_prompt``, the one
        used at inference.
    """
    wanted = set(settings.get("tasks") or [])
    directions = set(settings.get("directions") or ["fr-ar", "ar-fr"])
    prompt = settings["system_prompt"].strip()
    train, valid = [], []
    for e in examples:
        if (wanted and e["task"] not in wanted) or e["split"] == "test":
            continue
        if e.get("direction") and e["direction"] not in directions:
            continue
        e = {**e, "messages": [{"role": "system", "content": prompt}, *e["messages"][1:]],
             "pair_id": "+".join(e["source_ids"]), "source": "phrase" if e["task"] == "traduction_phrase" else "lexique"}
        (train if e["split"] == "train" else valid).append(e)
    max_pairs = int(settings.get("max_pairs") or 0)
    if max_pairs:
        kept = {p for p, *_ in choose_pairs([(p,) for p in dict.fromkeys(e["pair_id"] for e in train)], max_pairs)}
        train = [e for e in train if e["pair_id"] in kept]
    return train, valid


def build_dataset(settings: dict, corpus_csv: Path | None = None,
                  sentences_csv: Path | None = None) -> tuple[list[dict], list[dict]]:
    """Build the training and evaluation examples.

    Args:
        settings: The ``data`` section of the configuration (``source``, ``directions``,
            ``valid_ratio``, ``system_prompt``, ``max_pairs``, the ``include_*`` switches, and
            ``tasks`` for the ``dataset`` source).
        corpus_csv: Lexicon corpus; defaults to ``PATHS.corpus_csv``.
        sentences_csv: Sentence bank; defaults to ``PATHS.sentences_csv``.

    Returns:
        ``(train, valid)`` lists of chat examples. ``max_pairs`` only reduces the training
        pairs: the evaluation set stays the same, so that runs remain comparable. With
        ``source: dataset`` the examples come from ``data/dataset/exports/sft`` (all tasks,
        see :func:`dataset_examples`); otherwise from the corpus and the sentence bank.
    """
    if settings.get("source", "corpus") == "dataset":
        return dataset_examples(settings, load_dataset_exports())
    train_pairs, valid_pairs = [], []
    for pair in collect_pairs(settings, corpus_csv, sentences_csv):
        (valid_pairs if in_validation(pair[0], settings.get("valid_ratio", 0.05)) else train_pairs).append(pair)
    train_pairs = choose_pairs(train_pairs, int(settings.get("max_pairs") or 0))
    directions = settings.get("directions", ["fr-ar"])
    prompt = settings["system_prompt"].strip()

    def examples(pairs):
        return [e for pair_id, fr, td, source in pairs
                for e in pair_examples(pair_id, fr.strip(), td.strip(), source, directions, prompt)]

    return examples(train_pairs), examples(valid_pairs)


def write_dataset(train: list[dict], valid: list[dict], folder: Path | None = None, seed: int = 3407) -> dict:
    """Write ``train.jsonl`` and ``valid.jsonl`` for Unsloth and return statistics.

    Each line holds only ``{"messages": [...]}`` (ChatML), the format Unsloth Studio detects
    without any column mapping; the ids, sources and tasks only feed the statistics.

    Args:
        train: Training examples.
        valid: Evaluation examples.
        folder: Destination; defaults to ``PATHS.finetune_data``.
        seed: Seed of the shuffle of the training examples.

    Returns:
        ``{"train": n, "valid": n, "par_source": {...}, "dossier": str}`` (plus
        ``par_tache`` for the ``dataset`` source).
    """
    import random
    folder = folder or PATHS.finetune_data
    folder.mkdir(parents=True, exist_ok=True)
    # Mélangés avec une graine fixe : dans l'ordre du corpus, les exemples sont alphabétiques.
    train = random.Random(seed).sample(train, len(train))
    for name, rows in (("train", train), ("valid", valid)):
        tmp = folder / f".{name}.jsonl.tmp"
        with tmp.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps({"messages": row["messages"]}, ensure_ascii=False) + "\n")
        tmp.replace(folder / f"{name}.jsonl")
    by_source: dict[str, int] = {}
    by_task: dict[str, int] = {}
    for row in train + valid:
        by_source[row["source"]] = by_source.get(row["source"], 0) + 1
        if "task" in row:
            by_task[row["task"]] = by_task.get(row["task"], 0) + 1
    stats = {"train": len(train), "valid": len(valid), "par_source": by_source, "dossier": str(folder)}
    return {**stats, "par_tache": by_task} if by_task else stats


def load_config(path: Path | None = None) -> dict:
    """Read ``configs/finetune.yaml``.

    Args:
        path: Configuration file; defaults to ``PATHS.finetune_config``.

    Returns:
        The configuration as a dict.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = path or PATHS.finetune_config
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def prepare(config: dict) -> dict:
    """Build and write the data to load in Unsloth Studio.

    Args:
        config: Full configuration (``data`` section, and ``seed``).

    Returns:
        Statistics from :func:`write_dataset`.
    """
    if config["data"].get("source", "corpus") == "dataset":
        from td_arabic.dataset.build import run as build_training_dataset
        build_training_dataset()     # data/dataset à jour avec le lexique et la banque de phrases
    train, valid = build_dataset(config["data"])
    return write_dataset(train, valid, seed=config.get("seed", 3407))


def read_jsonl(path: Path) -> list[dict]:
    """Read a JSON-lines file (one JSON object per line)."""
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

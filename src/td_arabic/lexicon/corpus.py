"""Step 2 — Lexicon structuring and bilingual corpus construction.

Replaces the ``explore_lexique_entries.ipynb`` notebook with a reproducible
process:

0. definitions wrongly extracted from the PDF are fixed with
   ``data/resources/corrections_entrees.csv`` (each correction states the extracted text it
   replaces, so it is ignored, with a warning, if the extraction changes);
1. definitions containing expressions (``expr.`` marker) are split using
   ``data/resources/expressions_manuelles.csv`` (hand-validated splits); an
   ``expr.`` entry missing from that file is listed in
   ``data/interim/expressions_a_verifier.csv``;
2. each expression becomes its own row, placed right after its parent entry
   (``type = expression``);
3. hand-made additions (``data/resources/ajouts_corpus.csv``: a new sense of a
   known word, or a new word) are appended with ``type = ajout``, right after
   the last row of the same headword. Only additions reviewed and set to
   ``valide`` are merged: proposals are never taken as correct;
4. the ``src -> output`` corpus (Chadian Arabic -> French) and its
   bidirectional version are derived from the final lexicon.

Homographs are kept through ``sense_number``: the ``src`` headword stays the
bare form (``abad``), with no added marker.
"""

from __future__ import annotations

import re
from collections import defaultdict

import pandas as pd

from td_arabic.config import PATHS
from td_arabic.utils.io import read_csv, read_json, write_csv
from td_arabic.utils.log import get_logger
from td_arabic.utils.text import collapse_spaces

log = get_logger(__name__)

EXPR_MARKER = re.compile(r"\bexpr\.", re.IGNORECASE)

LEXICON_COLUMNS = ["headword", "sense_number", "forms", "pos", "definition", "type",
                   "parent_headword", "expression_number", "section", "page", "column",
                   "ligature_reconstructed"]
CORPUS_COLUMNS = ["src", "pos", "output", "forms", "sense_number"]

# Typographic variants of part-of-speech tags found in the PDF
POS_ALIASES = {"n.f": "n.f."}

ManualKey = tuple[str, str]  # (headword, sense_number as text, "" if none)


def _sense(value) -> str:
    """Return a sense number as text (``""`` when missing)."""
    return "" if value in (None, "") else str(int(value))


def load_manual_expressions(path=None) -> dict[ManualKey, dict]:
    """Load the hand-validated expression splits.

    Args:
        path: CSV with columns ``headword, sense_number, definition_principale,
            expression, traduction``; defaults to
            ``PATHS.manual_expressions_csv``.

    Returns:
        A mapping ``{(headword, sense): {"main": str, "expressions":
        [(expression, translation), ...]}}``; empty if the file does not exist (every entry
        with ``expr.`` is then listed for review).
    """
    path = path or PATHS.manual_expressions_csv
    if not path.exists():
        return {}
    df = read_csv(path)
    table: dict[ManualKey, dict] = {}
    for row in df.itertuples(index=False):
        key = (row.headword, _sense(row.sense_number))
        item = table.setdefault(key, {"main": row.definition_principale, "expressions": []})
        item["expressions"].append((row.expression, row.traduction))
    return table


def load_entry_corrections(path=None) -> dict[ManualKey, dict]:
    """Load the hand-made corrections of extracted definitions.

    Args:
        path: CSV with columns ``headword, sense_number, avant, apres, note``; defaults to
            ``PATHS.entry_corrections_csv``.

    Returns:
        ``{(headword, sense): {"avant": extracted text, "apres": corrected text}}``;
        empty if the file does not exist.
    """
    path = path or PATHS.entry_corrections_csv
    if not path.exists():
        return {}
    df = read_csv(path)
    return {(r.headword, _sense(r.sense_number) if r.sense_number else ""): {"avant": collapse_spaces(r.avant),
                                                                              "apres": collapse_spaces(r.apres)}
            for r in df.itertuples(index=False)}


def build_lexicon(entries: list[dict], manual: dict[ManualKey, dict],
                  corrections: dict[ManualKey, dict] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the final lexicon from extracted entries.

    Args:
        entries: Structured entries produced by the PDF extraction.
        manual: Expression splits from :func:`load_manual_expressions`.
        corrections: Fixes of wrongly extracted definitions from :func:`load_entry_corrections`.

    Returns:
        A tuple ``(lexicon, review)``: the lexicon with ``LEXICON_COLUMNS``
        (each expression placed after its parent entry) and the entries
        containing ``expr.`` that have no manual split yet.
    """
    from td_arabic.lexicon.pdf_extract import forms_to_str

    rows, review = [], []
    for e in entries:
        definition = collapse_spaces(e["definition"])
        sense = _sense(e["sense_number"])
        fix = (corrections or {}).get((e["headword_base"], sense))
        if fix:
            if definition == fix["avant"]:
                definition = fix["apres"]
            else:
                log.warning("correction ignorée pour %s : la définition extraite a changé (%r)",
                            e["headword_base"], definition)
        base = {
            "headword": e["headword_base"], "sense_number": sense,
            "pos": POS_ALIASES.get(e["pos"] or "", e["pos"] or ""), "section": e["section"], "page": e["page"],
            "column": e["column"], "ligature_reconstructed": e["ligature_reconstructed"],
        }
        expressions = []
        if EXPR_MARKER.search(definition):
            item = manual.get((e["headword_base"], sense))
            if item:
                definition = item["main"]
                expressions = item["expressions"]
            else:
                review.append({"headword": e["headword_base"], "sense_number": sense,
                               "definition": definition, "page": e["page"]})

        rows.append({**base, "forms": forms_to_str(e["forms"]), "definition": definition,
                     "type": "entry", "parent_headword": "", "expression_number": ""})
        for n, (expression, translation) in enumerate(expressions, start=1):
            rows.append({**base, "headword": expression, "forms": "expr.",
                         "definition": translation, "type": "expression",
                         "parent_headword": e["headword_base"], "expression_number": n})

    return pd.DataFrame(rows, columns=LEXICON_COLUMNS), pd.DataFrame(review)


def apply_additions(lexicon: pd.DataFrame, additions: pd.DataFrame) -> pd.DataFrame:
    """Insert the hand-made additions into the lexicon.

    Each addition becomes a row ``type = ajout`` placed right after the last
    row of the same headword (at the end if the headword is new). As in the
    SIL lexicon, several senses of one addition are comma-separated in
    ``output`` (``"se disperser, se répandre"``).

    Args:
        lexicon: Output of :func:`build_lexicon`.
        additions: Rows with at least ``src``, ``pos``, ``output``, ``forms``.

    Returns:
        The lexicon with the additions inserted (index reset).
    """
    rows = lexicon.to_dict("records")
    for item in additions.itertuples(index=False):
        src, output = collapse_spaces(item.src), collapse_spaces(item.output)
        if not src or not output:
            continue
        new = {column: "" for column in LEXICON_COLUMNS}
        new.update({"headword": src, "pos": item.pos, "definition": output, "forms": item.forms,
                    "type": "ajout"})
        same = [i for i, r in enumerate(rows) if r["headword"] == src]
        rows.insert(same[-1] + 1 if same else len(rows), new)
    return pd.DataFrame(rows, columns=LEXICON_COLUMNS)


def build_corpus(lexicon: pd.DataFrame) -> pd.DataFrame:
    """Derive the Chadian Arabic -> French pairs from the lexicon.

    Args:
        lexicon: Output of :func:`build_lexicon`.

    Returns:
        A DataFrame with ``CORPUS_COLUMNS``; rows with an empty source or
        translation are dropped.
    """
    corpus = lexicon.rename(columns={"headword": "src", "definition": "output"})[CORPUS_COLUMNS]
    corpus = corpus.astype(str).apply(lambda s: s.str.strip())
    return corpus[(corpus["src"] != "") & (corpus["output"] != "")].reset_index(drop=True)


def build_bilingual(corpus: pd.DataFrame) -> pd.DataFrame:
    """Duplicate every pair in both directions.

    Args:
        corpus: Output of :func:`build_corpus`.

    Returns:
        The ``ar-fr`` rows followed by the swapped ``fr-ar`` rows, with a
        ``direction`` column.
    """
    ar_fr = corpus.assign(direction="ar-fr")
    fr_ar = corpus.rename(columns={"src": "output", "output": "src"}).assign(direction="fr-ar")
    return pd.concat([ar_fr, fr_ar[ar_fr.columns]], ignore_index=True)


def run() -> pd.DataFrame:
    """Run step 2 and write ``data/processed`` (plus the review list if needed).

    Returns:
        The corpus DataFrame.

    Raises:
        FileNotFoundError: If step 1 has not been run (no entries JSON).
    """
    data = read_json(PATHS.entries_json)
    if data is None:
        raise FileNotFoundError(
            f"{PATHS.entries_json} introuvable : lancez d'abord `td-arabic extract`.")
    lexicon, review = build_lexicon(data["entries"], load_manual_expressions(), load_entry_corrections())
    if PATHS.corpus_additions_csv.exists():
        from td_arabic.translation.additions import load_additions, validated_additions
        additions = validated_additions()
        pending = int((load_additions()["statut"] == "propose").sum())
        lexicon = apply_additions(lexicon, additions)
        log.info("%d ajouts validés fusionnés, %d proposition(s) en attente de relecture (%s)", len(additions),
                 pending, PATHS.corpus_additions_csv.relative_to(PATHS.root))
    corpus = build_corpus(lexicon)

    write_csv(PATHS.lexicon_final_csv, lexicon)
    write_csv(PATHS.corpus_csv, corpus)
    write_csv(PATHS.corpus_bilingual_csv, build_bilingual(corpus))
    if len(review):
        write_csv(PATHS.expressions_review_csv, review)
        log.warning("%d entrées avec expressions à découper à la main -> %s",
                    len(review), PATHS.expressions_review_csv.relative_to(PATHS.root))
    elif PATHS.expressions_review_csv.exists():
        PATHS.expressions_review_csv.unlink()

    counts = lexicon["type"].value_counts().to_dict()
    log.info("Lexique : %d entrées + %d expressions + %d ajouts ; corpus : %d paires",
             counts.get("entry", 0), counts.get("expression", 0), counts.get("ajout", 0), len(corpus))
    return corpus


def corpus_stats(corpus: pd.DataFrame) -> dict:
    """Compute descriptive statistics (used by the docs and the CLI).

    Args:
        corpus: The Chadian Arabic -> French corpus.

    Returns:
        A dict with the number of pairs, unique source words, homographs,
        expressions and the count per part of speech (largest first).
    """
    by_pos: dict[str, int] = defaultdict(int)
    for pos in corpus["pos"]:
        by_pos[pos or "(non précisé)"] += 1
    return {
        "paires": len(corpus),
        "mots_source_uniques": corpus["src"].str.lower().nunique(),
        "homographes": int((corpus["sense_number"] != "").sum()),
        "expressions": int((corpus["forms"] == "expr.").sum()),
        "par_categorie": dict(sorted(by_pos.items(), key=lambda kv: -kv[1])),
    }

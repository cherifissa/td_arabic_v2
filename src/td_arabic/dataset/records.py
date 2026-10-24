"""Normalised records of the dataset: lexical entries and parallel sentences.

The flat ``lexique_final.csv`` (one row = one headword + one definition) becomes a tree, as in
SIL's LIFT format, OntoLex-Lemon and the Wiktionary extracts (kaikki.org):

    entry (one per homograph)          td:abad#2
      ├── forms[]   (plural, feminine, imperfective… with normalised tags)
      ├── senses[]  (glosses_fr[], origin)       td:abad#2/s1
      └── expressions[] (multi-word expressions)  td:abad#2/x1

Sentences follow the parallel corpora (FLORES-200, MADAR, MAFAND-MT): one id, both languages
keyed by a language code, the domain, the provenance and the links to the lexicon (lemmas).

Every record has ``provenance`` (where it comes from) and ``quality`` (review status, flags
set by :mod:`td_arabic.dataset.quality`), so that a training export can keep only what is safe.
"""

from __future__ import annotations

import re
from collections import defaultdict

import pandas as pd

from td_arabic.utils.text import collapse_spaces, normalize_td

SOURCE_ID = "sil-tchad-2021"   # Lexique arabe tchadien – français, SIL Tchad, 11e éd.
LANG_TD = "shu_Latn"           # ISO 639-3 « shu » (arabe tchadien), écriture latine
LANG_TD_ARAB = "shu_Arab"      # même langue, écriture arabe (absente de l'extraction)
LANG_FR = "fra_Latn"

# Part of speech of the lexicon -> Universal Dependencies tag and grammatical features.
POS_INFO: dict[str, tuple[str, dict]] = {
    "n.m.": ("NOUN", {"gender": "m"}), "n.f.": ("NOUN", {"gender": "f"}),
    "n.coll.": ("NOUN", {"number": "coll"}), "n.coll.f.": ("NOUN", {"number": "coll", "gender": "f"}),
    "n.pl.": ("NOUN", {"number": "pl"}), "n.": ("NOUN", {}),
    "v.tr.": ("VERB", {"valency": "tr"}), "v.i.": ("VERB", {"valency": "intr"}),
    "adj.": ("ADJ", {}), "adv.": ("ADV", {}), "num.": ("NUM", {}), "prép.": ("ADP", {}),
    "pron.": ("PRON", {}), "interj.": ("INTJ", {}), "conj.": ("CCONJ", {}),
    "interg.": ("PRON", {"type": "int"}), "part.interg.": ("PART", {"type": "int"}),
    "art.déf.": ("DET", {"definite": True}), "neg.": ("PART", {"polarity": "neg"}),
    "expr.": ("X", {"type": "expr"}),
}

# Label of an inflected form in the lexicon -> normalised tags (kaikki.org vocabulary).
FORM_TAGS: dict[str, list[str]] = {
    "pl.": ["plural"], "f.": ["feminine"], "f.pl.": ["feminine", "plural"], "m.pl.": ["masculine", "plural"],
    "m.": ["masculine"], "dl.": ["dual"], "sg.": ["singulative"], "var.": ["variant"],
    "inacc.": ["imperfective", "third-person", "singular", "masculine"], "impr.": ["imperative"],
    "part.prs.": ["participle", "present"], "comp.": ["compound"],
}
_FORM_ITEM = re.compile(r"([a-zé.]+)\s+(.+)")
_GLOSS_SPLIT = re.compile(r",\s*(?![^()]*\))")   # virgules hors parenthèses


def entry_id(headword: str, homograph: str | int | None = None) -> str:
    """Build the stable id of a lexical entry.

    Args:
        headword: Latin headword, e.g. ``"abad"``.
        homograph: Homograph number of the lexicon (``abad1``, ``abad2``), if any.

    Returns:
        ``"td:abad"`` or ``"td:abad#2"``.
    """
    key = normalize_td(headword).replace(" ", "_")
    return f"td:{key}#{homograph}" if homograph not in (None, "") else f"td:{key}"


def parse_forms(forms: str) -> list[dict]:
    """Parse the ``forms`` column into tagged forms.

    Args:
        forms: E.g. ``"pl. abiid / var. abd"``.

    Returns:
        ``[{"form": "abiid", "tags": ["plural"], "label": "pl."}, ...]``. A value without a known
        label keeps the label ``""`` and no tag (and is reported by the quality checks).
    """
    items = []
    for chunk in (forms or "").split("/"):
        chunk = collapse_spaces(chunk)
        if not chunk or chunk == "expr.":
            continue
        m = _FORM_ITEM.match(chunk)
        if m and m.group(1) in FORM_TAGS:
            items.append({"form": m.group(2).strip(), "tags": FORM_TAGS[m.group(1)], "label": m.group(1)})
        else:
            items.append({"form": chunk, "tags": [], "label": ""})
    return items


def split_glosses(definition: str) -> list[str]:
    """Split a lexicon gloss into its synonymous French glosses.

    The lexicon separates near-synonyms of ONE sense with commas (``"grue, ibis"``,
    ``"se disperser, se répandre"``); commas inside parentheses are kept.

    Args:
        definition: The French definition.

    Returns:
        The non-empty glosses, in order.
    """
    return [g for g in (collapse_spaces(p) for p in _GLOSS_SPLIT.split(definition or "")) if g]


def _new_entry(row: dict, eid: str, origin: str) -> dict:
    """Create the skeleton of an entry from a lexicon row."""
    upos, feats = POS_INFO.get(row["pos"], ("X", {}))
    return {
        "id": eid,
        "lemma": {LANG_TD: row["headword"], LANG_TD_ARAB: None},
        "homograph": int(row["sense_number"]) if row["sense_number"] else None,
        "pos": row["pos"], "upos": upos, "features": feats,
        "forms": parse_forms(row["forms"]),
        "senses": [], "expressions": [],
        "provenance": {"source": SOURCE_ID if origin == "pdf" else "ajouts_corpus", "origin": origin,
                       "page": int(row["page"]) if row["page"] else None,
                       "column": row["column"] or None, "section": row["section"] or None},
        "quality": {"status": "extracted" if origin == "pdf" else "validated",
                    "ligature_reconstructed": row["ligature_reconstructed"] == "True", "flags": []},
    }


def _sense(eid: str, n: int, definition: str, origin: str) -> dict:
    """Create one sense of an entry."""
    return {"id": f"{eid}/s{n}", "definition_fr": definition, "glosses_fr": split_glosses(definition),
            "origin": origin, "examples": []}


def build_entries(lexicon: pd.DataFrame) -> list[dict]:
    """Turn the flat final lexicon into a list of entries.

    Args:
        lexicon: ``lexique_final.csv`` read as text (rows ``entry``, ``expression``, ``ajout``).

    Returns:
        Entries in lexicon order. ``expression`` rows go to the ``expressions`` of their parent;
        an ``ajout`` becomes a new sense of the entry with the same headword and part of speech
        when there is exactly one, otherwise a new entry.
    """
    entries: dict[str, dict] = {}
    by_head_pos: dict[tuple[str, str], list[str]] = defaultdict(list)
    last_entry: dict[str, str] = {}
    for row in lexicon.fillna("").astype(str).to_dict("records"):
        kind = row["type"]
        if kind == "expression":
            parent = entries.get(last_entry.get(row["parent_headword"], ""))
            if parent is not None:
                n = len(parent["expressions"]) + 1
                parent["expressions"].append({"id": f"{parent['id']}/x{n}", "text": row["headword"],
                                              "gloss_fr": row["definition"],
                                              "glosses_fr": split_glosses(row["definition"])})
            continue
        if kind == "ajout":
            same = by_head_pos.get((normalize_td(row["headword"]), row["pos"]), [])
            if len(same) == 1:
                entry = entries[same[0]]
                entry["senses"].append(_sense(entry["id"], len(entry["senses"]) + 1, row["definition"], "ajout"))
                continue
            eid, n = entry_id(row["headword"]), 1
            while eid in entries:
                n += 1
                eid = f"{entry_id(row['headword'])}+a{n}"
            entry = _new_entry(row, eid, "ajout")
        else:
            entry = _new_entry(row, entry_id(row["headword"], row["sense_number"]), "pdf")
        entry["senses"].append(_sense(entry["id"], 1, row["definition"], entry["provenance"]["origin"]))
        entries[entry["id"]] = entry
        by_head_pos[(normalize_td(row["headword"]), row["pos"])].append(entry["id"])
        last_entry[row["headword"]] = entry["id"]
    return list(entries.values())


def lemma_index(entries: list[dict]) -> dict[str, list[str]]:
    """Map every lemma key (``normalize_td``) to its entry ids (several for homographs)."""
    index: dict[str, list[str]] = defaultdict(list)
    for e in entries:
        index[normalize_td(e["lemma"][LANG_TD])].append(e["id"])
    return index


def build_sentences(bank: pd.DataFrame, lemmas: dict[str, list[str]]) -> list[dict]:
    """Turn the sentence bank into parallel units.

    Args:
        bank: ``data/sentences/phrases.csv`` read as text.
        lemmas: Output of :func:`lemma_index`, to link the lemmas to the lexicon.

    Returns:
        One record per sentence (drafts and rejected sentences included: the export decides).
    """
    status = {"validee": "validated", "brouillon": "draft", "rejetee": "rejected"}
    origin = {"gabarit": "template", "manuel": "human"}
    records = []
    for row in bank.fillna("").astype(str).to_dict("records"):
        links = []
        for lemma in (collapse_spaces(x) for x in row["lemmes"].split(";")):
            if lemma:
                links.append({"lemma": lemma, "entries": lemmas.get(normalize_td(lemma), [])})
        records.append({
            "id": f"phr:{row['id']}",
            "text": {LANG_TD: collapse_spaces(row["td"]), LANG_TD_ARAB: None, LANG_FR: collapse_spaces(row["fr"])},
            "domain": row["theme"] or None,
            "lemmas": links,
            "out_of_lexicon": [w for w in (collapse_spaces(x) for x in row["hors_lexique"].split(";")) if w],
            "provenance": {"origin": origin.get(row["source"], row["source"] or "unknown"),
                           "template_id": row["template_id"] or None,
                           "created": row["cree_le"] or None, "modified": row["modifie_le"] or None},
            "quality": {"status": status.get(row["statut"], row["statut"]), "flags": []},
            # Groupe de découpage : les phrases d'un même gabarit restent du même côté.
            "group": f"tpl:{row['template_id']}" if row["template_id"] else f"phr:{row['id']}",
        })
    return records

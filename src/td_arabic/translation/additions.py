"""Add words and senses to the corpus by hand, as proposals to review.

The corpus in ``data/processed/`` is rebuilt from the SIL lexicon by
``td-arabic build-corpus``: editing it directly would be lost at the next
rebuild. Additions therefore live in their own file,
``data/resources/ajouts_corpus.csv``, which the pipeline merges (rows marked
``type = ajout`` in ``lexique_final.csv``), so every added row stays traceable.

**What is typed is never taken as correct.** Every addition starts as a
``propose`` (proposal) and is ignored by the pipeline. It enters the corpus only
once reviewed and set to ``valide``; the spelling can be corrected before that
(``src_saisi`` keeps what was typed). A ``rejete`` row stays in the file as a
record but is never merged.

Two kinds of additions, both one row ``src -> output``:

- a **new sense of a known word** (``derib`` -> ``route``): ``src`` is already
  a headword;
- a **new word** (``daafi``'s opposite, a word missing from the lexicon).

Several senses of one addition are comma-separated in ``output``, as in the SIL
lexicon (``achchattat`` -> ``se disperser, se répandre``).
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from pathlib import Path

import pandas as pd

from td_arabic.config import PATHS
from td_arabic.translation.lexicon import FORM_LABEL_NAMES, Lexicon, french_keys, get_lexicon
from td_arabic.utils.io import read_csv, write_csv
from td_arabic.utils.text import collapse_spaces, normalize_glottal, normalize_td

ADDITION_COLUMNS = ["id", "src", "src_saisi", "pos", "output", "forms", "opposite_td", "note", "statut",
                    "added_on"]
STATUTS = ("propose", "valide", "rejete")
EDITABLE = ("src", "pos", "output", "forms", "opposite_td", "note", "statut")
# Default grammatical category of a word, from the category of the French word list.
# The French word gives the broad category only (noun, verb…). The gender of a noun and the
# transitivity of a verb belong to the ARABIC word, so they stay generic (``n.``, ``v.``) until the
# review, where the exact tag is chosen.
POS_FROM_CATEGORY = {"n": "n.", "v": "v.", "adj": "adj.", "adv": "adv.", "prep": "prép.", "pron": "pron.",
                     "conj": "conj.", "interj": "interj.", "num": "num."}
GENERIC_POS = ("", "n.", "v.")
POS_CHOICES = ["n.m.", "n.f.", "n.coll.", "n.pl.", "v.tr.", "v.i.", "adj.", "adv.", "prép.", "pron.",
               "conj.", "interj.", "num.", "n.", "v."]


class AdditionError(ValueError):
    """Raised when an addition is invalid or already in the corpus."""


# Labels typed without their dots, as people often do (« f jaara, pl jiiraan »).
_FORM_ALIASES = {"f": "f.", "pl": "pl.", "fpl": "f.pl.", "f.pl": "f.pl.", "mpl": "m.pl.", "m.pl": "m.pl.",
                 "dl": "dl.", "sg": "sg.", "var": "var.", "inacc": "inacc.", "impr": "impr.", "m": "m."}


def normalize_forms(text: str) -> str:
    """Write the typed forms in the lexicon format.

    Args:
        text: Forms as typed, e.g. ``"f jaara, pl jiiraan"`` or ``"f. jaara / pl. jiiraan"``.
            Separators ``/``, ``,`` or ``;`` are accepted; each form starts with its label:
            ``f.`` (feminine), ``pl.`` (plural), ``m.pl.``, ``f.pl.``, ``dl.`` (dual), and also
            ``sg.``, ``var.``, ``inacc.``, ``impr.``.

    Returns:
        ``"f. jaara / pl. jiiraan"``, the format of the ``forms`` column of the lexicon, with the
        glottal stop written ``ʼ``; empty if nothing was typed.

    Raises:
        AdditionError: If a form has no label or an unknown one.
    """
    out = []
    for chunk in (c.strip() for c in re.split(r"[/;,]", collapse_spaces(text or ""))):
        if not chunk:
            continue
        match = re.match(r"([A-Za-z.]+)\s+(.+)", chunk)
        if not match:
            raise AdditionError(f"Forme sans étiquette : « {chunk} ». Écrivez par exemple « f. jaara / pl. jiiraan ».")
        label = match.group(1).lower()
        label = label if label in FORM_LABEL_NAMES else _FORM_ALIASES.get(label.rstrip("."))
        if label is None:
            raise AdditionError(f"Étiquette inconnue « {match.group(1)} » : utilisez f., pl., m.pl., f.pl. ou dl.")
        out.append(f"{label} {normalize_glottal(match.group(2))}")
    return " / ".join(out)


def load_additions(path: Path | None = None) -> pd.DataFrame:
    """Load every addition (proposed, validated and rejected).

    Args:
        path: CSV file; defaults to ``PATHS.corpus_additions_csv``.

    Returns:
        The additions (``ADDITION_COLUMNS``); empty if the file does not exist.
        A file written before proposals existed has no ``statut`` column: its rows were
        merged directly, so they count as ``valide``.
    """
    path = path or PATHS.corpus_additions_csv
    if not path.exists():
        return pd.DataFrame(columns=ADDITION_COLUMNS)
    raw = read_csv(path)
    legacy = "statut" not in raw.columns
    df = raw.reindex(columns=ADDITION_COLUMNS, fill_value="")
    if legacy:
        df["statut"] = "valide"
    df["statut"] = df["statut"].replace("", "propose")
    df["src_saisi"] = df["src_saisi"].where(df["src_saisi"] != "", df["src"])
    missing = df["id"] == ""
    df.loc[missing, "id"] = [uuid.uuid4().hex[:8] for _ in range(int(missing.sum()))]
    return df


# Spelling rules of the course (chapter 6), checked against the 4,832 headwords of the lexicon:
# none of them contains « ou », « dj » or « gue / gui ».
SPELLING_RULES = [
    (re.compile(r"ou"), "« ou » : le cours écrit ce son avec u (ex. usum, pas ousoum)"),
    (re.compile(r"dj"), "« dj » : le cours écrit ce son avec j (ex. jadiid, pas djadiid)"),
    (re.compile(r"gu(?=[ei])"), "« gue / gui » : g est toujours dur, sans u (ex. gelbi, pas guelbi)"),
]


def _similarity(a: str, b: str) -> float:
    """Spelling similarity of two words, 0-100 (RapidFuzz if installed, else difflib)."""
    try:
        from rapidfuzz import fuzz
        return fuzz.ratio(a, b)
    except ImportError:
        from difflib import SequenceMatcher
        return SequenceMatcher(None, a, b).ratio() * 100


def spelling_warnings(src: str, lexicon: Lexicon | None = None, output: str = "") -> list[str]:
    """Point out what looks like a spelling mistake in a proposed Chadian Arabic word.

    Args:
        src: The word as proposed.
        lexicon: Lexicon to compare with; defaults to the shared one.
        output: The French translation proposed with it, used to find a lexicon word that
            already means the same thing and is written almost the same way.

    Returns:
        Messages (empty if nothing is suspicious): a broken rule of the course, or « jidd means
        grand-père already: did you mean jidd? » for ``idd`` proposed as « grand-père ».
    """
    lexicon = lexicon or get_lexicon()
    word = normalize_td(src)
    warnings = [message for pattern, message in SPELLING_RULES if pattern.search(word)]
    if output:
        same_meaning = []
        # The whole gloss of each sense, parentheses included: « cousin (fils de l'oncle paternel) »
        # and « cousin (fils de la tante paternelle) » are two meanings, not one.
        for part in clean_french(output).split(", "):
            key = french_keys(part)[0]
            same_meaning += [normalize_td(t.output) for t in lexicon.fr.get(key, []) if t.forms != "expr."]
        close = sorted({w for w in same_meaning if w != word and _similarity(word, w) >= 70},
                       key=lambda w: -_similarity(word, w))
        if close:
            warnings.append(f"« {close[0]} » veut déjà dire « {clean_french(output)} » dans le lexique : "
                            f"vouliez-vous écrire {close[0]} ?")
    return warnings


def validated_additions(path: Path | None = None) -> pd.DataFrame:
    """Return the additions the pipeline merges into the corpus.

    Args:
        path: CSV file; defaults to ``PATHS.corpus_additions_csv``.

    Returns:
        Only the rows whose ``statut`` is ``valide``.
    """
    df = load_additions(path)
    return df[df["statut"] == "valide"].reset_index(drop=True)


def clean_french(output: str) -> str:
    """Normalise a French gloss, keeping its comma-separated senses.

    Args:
        output: E.g. ``" route ,voie "``.

    Returns:
        ``"route, voie"``: trimmed items joined by ``", "``, empty items dropped.
    """
    parts = [collapse_spaces(part) for part in str(output).replace(";", ",").split(",")]
    return ", ".join(part for part in parts if part)


def known_senses(lexicon: Lexicon, src: str) -> set[str]:
    """Return the French keys already attached to a Chadian Arabic word.

    Args:
        lexicon: The lexicon to look in.
        src: Chadian Arabic word.

    Returns:
        The normalised French senses (each comma-separated part counted).
    """
    senses: set[str] = set()
    for translation in lexicon.ar.get(normalize_td(src), []):
        senses.update(french_keys(translation.output))
    return senses


def _already_there(lexicon: Lexicon, additions: pd.DataFrame, src: str, output: str,
                   ignore_id: str = "") -> bool:
    """Tell whether every French sense of ``output`` is already attached to ``src``.

    Args:
        lexicon: The lexicon (it already contains the validated additions).
        additions: Current additions; pending proposals count too, to avoid duplicates.
        src: Chadian Arabic word.
        output: French gloss, senses comma-separated.
        ignore_id: Id of the row being edited, which must not count against itself.
    """
    known = known_senses(lexicon, src)
    others = additions[(additions["id"] != ignore_id) & (additions["statut"] != "rejete")]
    for item in others[others["src"].map(normalize_td) == normalize_td(src)].itertuples():
        known.update(french_keys(item.output))
    new_senses = [french_keys(part)[0] for part in output.split(", ")]
    return all(sense in known for sense in new_senses)


def add_addition(src: str, output: str, pos: str = "", forms: str = "", opposite_td: str = "",
                 note: str = "", lexicon: Lexicon | None = None, path: Path | None = None,
                 statut: str = "propose", typed: str | None = None) -> dict:
    """Record one proposal in ``ajouts_corpus.csv``.

    Args:
        src: Chadian Arabic word (an existing headword or a new one), as typed.
        output: French gloss; separate several senses with commas.
        pos: Part of speech (``POS_CHOICES``); optional.
        forms: Inflected forms, in the lexicon's format (``pl. …``); optional.
        opposite_td: Chadian Arabic opposite, if known; optional.
        note: Free comment (who confirmed it, where it was heard); optional.
        lexicon: Lexicon used to detect duplicates; defaults to the shared one.
        path: CSV file; defaults to ``PATHS.corpus_additions_csv``.
        statut: ``propose`` (default: not merged until reviewed) or ``valide``.
        typed: What the person originally typed, if ``src`` was already corrected before
            the call; defaults to ``src``. Kept in ``src_saisi`` for traceability.

    Returns:
        The saved row, plus ``"is_new_word"`` (True if ``src`` was not in the
        lexicon) and ``"warnings"`` (list of messages, e.g. unknown opposite).

    Raises:
        AdditionError: If ``src`` or ``output`` is empty, if ``statut`` is unknown, or if
            every French sense is already attached to ``src``.
    """
    lexicon = lexicon or get_lexicon()
    path = path or PATHS.corpus_additions_csv
    if statut not in STATUTS:
        raise AdditionError(f"statut inconnu : {statut}")
    typed = collapse_spaces(typed if typed is not None else src)
    src, output = normalize_glottal(src), clean_french(output)
    if not src or not output:
        raise AdditionError("Le mot arabe tchadien et sa traduction française sont obligatoires.")
    if statut == "valide" and pos in GENERIC_POS:
        raise AdditionError(f"Précisez la catégorie de « {src} » (n.m., n.f., v.tr., v.i., adj., …) pour valider.")

    existing = load_additions(path)
    if _already_there(lexicon, existing, src, output):
        raise AdditionError(f"« {src} » a déjà ce sens dans le corpus ou dans les propositions : {output}.")

    warnings = [f"« {src} » : {w}" for w in spelling_warnings(src, lexicon, output)]
    opposite_td = normalize_glottal(opposite_td)
    if opposite_td and not lexicon.ar.get(normalize_td(opposite_td)):
        warnings.append(f"L'opposé « {opposite_td} » n'est pas dans le lexique : pensez à l'ajouter aussi.")

    row = {"id": uuid.uuid4().hex[:8], "src": src, "src_saisi": typed, "pos": pos, "output": output,
           "forms": normalize_forms(forms), "opposite_td": opposite_td, "note": collapse_spaces(note),
           "statut": statut, "added_on": date.today().isoformat()}
    write_csv(path, pd.concat([existing, pd.DataFrame([row])], ignore_index=True))
    return {**row, "is_new_word": not lexicon.ar.get(normalize_td(src)), "warnings": warnings}


def update_addition(addition_id: str, lexicon: Lexicon | None = None, path: Path | None = None,
                    **fields) -> dict:
    """Correct or review one proposal (spelling, translation, status).

    Args:
        addition_id: ``id`` of the row.
        lexicon: Lexicon used to detect duplicates; defaults to the shared one.
        path: CSV file; defaults to ``PATHS.corpus_additions_csv``.
        **fields: Any of ``EDITABLE``. ``src`` is normalised (glottal stop ``ʼ``) and
            ``output`` cleaned like at creation.

    Returns:
        The updated row.

    Raises:
        KeyError: If no row has this id.
        AdditionError: If a field is not editable, the status is unknown, ``src`` or
            ``output`` becomes empty, or a validated row would duplicate a sense.
    """
    lexicon = lexicon or get_lexicon()
    path = path or PATHS.corpus_additions_csv
    df = load_additions(path)
    mask = df["id"] == addition_id
    if not mask.any():
        raise KeyError(addition_id)
    unknown = set(fields) - set(EDITABLE)
    if unknown:
        raise AdditionError(f"champ(s) non modifiable(s) : {', '.join(sorted(unknown))}")
    if fields.get("statut", "propose") not in STATUTS:
        raise AdditionError(f"statut inconnu : {fields['statut']}")
    if "src" in fields:
        fields["src"] = normalize_glottal(fields["src"])
    if "output" in fields:
        fields["output"] = clean_french(fields["output"])
    if "opposite_td" in fields:
        fields["opposite_td"] = normalize_glottal(fields["opposite_td"])
    if "forms" in fields:
        fields["forms"] = normalize_forms(fields["forms"])
    before = df[mask].iloc[0].to_dict()
    for key, value in fields.items():
        df.loc[mask, key] = value
    row = df[mask].iloc[0]
    if not row["src"] or not row["output"]:
        raise AdditionError("Le mot arabe tchadien et sa traduction française sont obligatoires.")
    if row["statut"] == "valide" and row["pos"] in GENERIC_POS:
        raise AdditionError(f"Précisez la catégorie de « {row['src']} » avant de valider : n.m., n.f. ou n.coll. "
                            "pour un nom ; v.tr. ou v.i. pour un verbe (elle dépend du mot arabe).")
    # The duplicate check only matters when the row newly enters the corpus or changes sense:
    # an already merged row would otherwise be refused because the lexicon contains it.
    entering = row["statut"] == "valide" and (before["statut"] != "valide" or
                                              (before["src"], before["output"]) != (row["src"], row["output"]))
    if entering and _already_there(lexicon, df, row["src"], row["output"], addition_id):
        raise AdditionError(f"« {row['src']} » a déjà ce sens dans le corpus : {row['output']}.")
    write_csv(path, df[ADDITION_COLUMNS])
    return row.to_dict()


def propose_from_rows(rows: list[dict], lexicon: Lexicon | None = None,
                      path: Path | None = None) -> tuple[list[dict], list[str]]:
    """Record the proposals typed directly in the coverage table.

    Args:
        rows: One dict per table row, with ``mot`` (the French word) and optionally ``categorie``
            (category of the French word) and the typed cells ``arabe``, ``francais``, ``pos_choisi``,
            ``forms``, ``opposite``, ``note``. A row with an empty ``arabe`` cell is ignored.
            Several Arabic words for one French word are separated by ``;`` or ``,``
            (``derib; tariig``): each gets its own proposal.
        lexicon: Lexicon used to detect duplicates; defaults to the shared one.
        path: CSV file; defaults to ``PATHS.corpus_additions_csv``.

    Returns:
        ``(saved, errors)``: the saved rows (as returned by :func:`add_addition`, with their
        ``warnings``) and one message per proposal that was refused (duplicate sense, empty
        field…). The other proposals are still saved.

    The French gloss defaults to the French word and the category to the existing entry's
    (for a new sense) or to the one of the word list; every proposal is a ``propose``.
    """
    lexicon = lexicon or get_lexicon()
    saved: list[dict] = []
    errors: list[str] = []
    for row in rows:
        typed_words = [t.strip() for t in re.split(r"[;,]", row.get("arabe") or "") if t.strip()]
        if len(typed_words) > 1 and (row.get("forms") or "").strip():
            # One forms cell for several words would give each word the plural of the others
            # (« abba, abu, waalid » + « pl. abbahaat / dl. waaldeen »).
            errors.append(f"{', '.join(typed_words)} ({row['mot']}) : les formes ne valent que pour un seul mot. "
                          "Proposez un mot arabe à la fois quand vous indiquez ses formes.")
            continue
        for typed in typed_words:
            existing = lexicon.ar.get(normalize_td(normalize_glottal(typed)), [])
            known_pos = existing[0].pos if existing and existing[0].pos in POS_CHOICES else ""
            pos = row.get("pos_choisi") or known_pos or POS_FROM_CATEGORY.get(row.get("categorie", ""), "")
            try:
                saved.append(add_addition(typed, row.get("francais") or row["mot"], pos, row.get("forms") or "",
                                          row.get("opposite") or "", row.get("note") or "",
                                          lexicon=lexicon, path=path))
            except AdditionError as error:
                errors.append(f"{typed} ({row['mot']}) : {error}")
    return saved, errors

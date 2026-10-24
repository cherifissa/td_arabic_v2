"""In-memory lexicon index and word lookup (exact, by inflected form, fuzzy).

The corpus ``data/processed/corpus_arabe_tchadien_francais.csv`` is the single
source of truth. Three indexes are built at load time:

- ``ar``: Chadian Arabic word -> French senses;
- ``fr``: French gloss (and each of its parts split on , or ;)
  -> Chadian Arabic word;
- ``forms``: inflected form (plural, feminine, imperfective and its
  ``n-/t-/y-`` persons, imperative...) -> lemma.
  E.g. ``nachri`` -> ``chara`` (to buy).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

from td_arabic.config import FUZZY_LIMIT, FUZZY_THRESHOLD, PATHS
from td_arabic.utils.io import read_csv
from td_arabic.utils.text import normalize_fr, normalize_td, strip_article

Direction = Literal["auto", "ar-fr", "fr-ar"]

# French names of the form labels, used in the user-facing ``note`` field.
FORM_LABEL_NAMES = {
    "pl.": "pluriel", "f.": "féminin", "f.pl.": "féminin pluriel", "m.pl.": "masculin pluriel",
    "sg.": "singulatif", "dl.": "duel", "var.": "variante", "inacc.": "inaccompli",
    "impr.": "impératif", "m.": "masculin", "comp.": "composé", "part.prs.": "participe",
}
# Person prefixes of the imperfective (see the course, chapter 10):
# y- (he) -> n- (I), t- (you masc. / she).
INACCOMPLI_PERSONS = {"n": "1re pers. sg.", "t": "2e pers. sg. / 3e pers. f. sg."}
_FORM_ITEM = re.compile(r"([a-zé.]+)\s+(.+)")
_PAREN = re.compile(r"\([^)]*\)")


@dataclass(frozen=True)
class Translation:
    """One candidate translation of a word.

    Attributes:
        output: The translated word or gloss.
        pos: Part of speech from the lexicon (e.g. ``v.tr.``).
        sense_number: Homograph number, or None.
        forms: Inflected forms of the Chadian Arabic word, as in the lexicon.
        direction: ``"ar-fr"`` or ``"fr-ar"``.
        note: How the match was found (e.g. ``"pluriel de suug"``).
    """

    output: str
    pos: str
    sense_number: int | None
    forms: str
    direction: str
    note: str = ""

    def as_dict(self) -> dict:
        """Return the translation as a JSON-serialisable dict."""
        return asdict(self)


@dataclass
class LookupResult:
    """Result of :meth:`Lexicon.lookup`.

    Attributes:
        query: The searched text.
        status: ``exact_match``, ``form_match``, ``no_exact_match`` or ``no_match``.
        word: The matched key or lemma (exact and form matches only).
        translations: Candidate translations (exact and form matches only).
        suggestions: Fuzzy suggestions (``no_exact_match`` only).
    """

    query: str
    status: str
    word: str | None = None
    translations: list[Translation] = field(default_factory=list)
    suggestions: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        """Serialise in the API v1-compatible format.

        Returns:
            ``{query, status, word, translations}`` for a match,
            ``{query, status, message, suggestions}`` for fuzzy suggestions,
            ``{query, status, message}`` otherwise.
        """
        data = {"query": self.query, "status": self.status}
        if self.status in ("exact_match", "form_match"):
            data["word"] = self.word
            data["translations"] = [t.as_dict() for t in self.translations]
        elif self.status == "no_exact_match":
            data["message"] = "Aucun mot exact trouvé. Voici les suggestions les plus proches :"
            data["suggestions"] = self.suggestions
        else:
            data["message"] = "Aucune correspondance trouvée (même floue)."
        return data


def _fuzzy_extract(query: str, choices: list[str], limit: int, cutoff: int) -> list[tuple[str, float]]:
    """Return the best fuzzy matches of ``query`` among ``choices``.

    Uses RapidFuzz when installed, otherwise falls back to the slower
    ``difflib.SequenceMatcher`` (scores 0-100 in both cases).

    Args:
        query: Normalised query.
        choices: Normalised candidate keys.
        limit: Maximum number of matches.
        cutoff: Minimum similarity score (0-100).

    Returns:
        ``(choice, score)`` pairs, best first.
    """
    try:
        from rapidfuzz import fuzz, process
        return [(m, s) for m, s, _ in process.extract(
            query, choices, scorer=fuzz.ratio, limit=limit, score_cutoff=cutoff)]
    except ImportError:  # dependency-free fallback (slower)
        from difflib import SequenceMatcher
        scored = ((c, SequenceMatcher(None, query, c).ratio() * 100) for c in choices)
        return sorted((x for x in scored if x[1] >= cutoff), key=lambda x: -x[1])[:limit]


def french_keys(definition: str) -> list[str]:
    """Build the lookup keys of a French gloss.

    Args:
        definition: A French definition, e.g. ``"cher, coûteux"``.

    Returns:
        The whole normalised gloss, then each part split on ``,`` or ``;``
        with parentheses removed: ``["cher, coûteux", "cher", "coûteux"]``.
    """
    full = normalize_fr(definition)
    keys = [full]
    for part in re.split(r"[;,]", _PAREN.sub("", full)):
        part = part.strip(" .!?")
        if part and part not in keys:
            keys.append(part)
    return keys


def parse_forms(forms: str) -> list[tuple[str, str]]:
    """Parse the ``forms`` column of the lexicon.

    Args:
        forms: E.g. ``"inacc. yachri / impr. achri"``.

    Returns:
        ``(label, value)`` pairs with a known label, e.g.
        ``[("inacc.", "yachri"), ("impr.", "achri")]``.
    """
    items = []
    for chunk in forms.split("/"):
        m = _FORM_ITEM.match(chunk.strip())
        if m and m.group(1) in FORM_LABEL_NAMES:
            items.append((m.group(1), m.group(2).strip()))
    return items


def inaccompli_variants(form: str) -> dict[str, str]:
    """Derive the other singular persons of an imperfective form.

    Args:
        form: Imperfective in the 3rd person masculine singular (``y-``),
            as given by the lexicon, e.g. ``"yachri"``.

    Returns:
        ``{"nachri": "1re pers. sg.", "tachri": "2e pers. sg. / ..."}``; an
        empty dict if the form does not start with ``y``.
    """
    if not form.startswith("y") or len(form) < 3:
        return {}
    return {p + form[1:]: label for p, label in INACCOMPLI_PERSONS.items()}


class Lexicon:
    """In-memory bilingual lexicon with exact, form-based and fuzzy lookup.

    Attributes:
        rows: Raw corpus rows (``src``, ``pos``, ``output``, ``forms``,
            ``sense_number``).
        ar: Normalised Chadian Arabic key -> translations into French.
        fr: Normalised French key -> translations into Chadian Arabic.
        forms: Normalised inflected form -> list of ``(lemma, note)``.
    """

    def __init__(self, rows: list[dict]):
        """Index the given corpus rows.

        Args:
            rows: Corpus rows as dicts (all values as strings).
        """
        self.rows = rows
        self.ar: dict[str, list[Translation]] = defaultdict(list)
        self.fr: dict[str, list[Translation]] = defaultdict(list)
        self.forms: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for row in rows:
            self._index(row)
        self._by_src: dict[str, list[dict]] = defaultdict(list)     # rows by headword, for entries_for
        for row in rows:
            self._by_src[normalize_td(row["src"])].append(row)
        self._ar_keys = list(self.ar)
        self._fr_keys = list(self.fr)

    # -- construction ------------------------------------------------------
    @classmethod
    def from_csv(cls, path: Path | None = None) -> "Lexicon":
        """Load a lexicon from a corpus CSV.

        Args:
            path: CSV file; defaults to ``PATHS.corpus_csv``.

        Returns:
            The indexed lexicon.

        Raises:
            FileNotFoundError: If the CSV does not exist (run the pipeline first).
        """
        df = read_csv(path or PATHS.corpus_csv)
        return cls(df.to_dict("records"))

    @staticmethod
    def _add(index: dict, key: str, value) -> None:
        """Append ``value`` under ``key`` unless it is already there."""
        if value not in index[key]:
            index[key].append(value)

    def _index(self, row: dict) -> None:
        """Add one corpus row to the three indexes."""
        sense = int(float(row["sense_number"])) if row.get("sense_number") else None
        src, out = row["src"].strip(), row["output"].strip()
        pos, forms = row.get("pos", ""), row.get("forms", "")
        self._add(self.ar, normalize_td(src), Translation(out, pos, sense, forms, "ar-fr"))
        for key in french_keys(out):
            self._add(self.fr, key, Translation(src, pos, sense, forms, "fr-ar"))
        for label, value in parse_forms(forms):
            name = FORM_LABEL_NAMES[label]
            for variant in value.split(" ou "):
                key = normalize_td(variant)
                self._add(self.forms, key, (normalize_td(src), f"{name} de {src}"))
                if label == "inacc.":
                    for conj, person in inaccompli_variants(key).items():
                        self._add(self.forms, conj, (normalize_td(src), f"inaccompli ({person}) de {src}"))

    # -- lookup ------------------------------------------------------------
    def _indexes(self, direction: Direction) -> list[tuple[str, dict]]:
        """Return the ``(name, index)`` pairs to search for a direction."""
        if direction == "ar-fr":
            return [("ar", self.ar)]
        if direction == "fr-ar":
            return [("fr", self.fr)]
        return [("ar", self.ar), ("fr", self.fr)]

    def exact(self, phrase: str, direction: Direction = "auto") -> tuple[str, list[Translation]] | None:
        """Find an exact match, also trying without the article ``al-`` / ``l-``.

        Args:
            phrase: Word or multi-word expression.
            direction: ``"ar-fr"``, ``"fr-ar"`` or ``"auto"`` (both).

        Returns:
            ``(matched_key, translations)`` or None.
        """
        for name, index in self._indexes(direction):
            key = normalize_td(phrase) if name == "ar" else normalize_fr(phrase)
            if key in index:
                return key, list(index[key])
            if name == "ar":
                bare = strip_article(key)
                if bare != key and bare in index:
                    return bare, list(index[bare])
        return None

    def by_form(self, phrase: str, direction: Direction = "auto") -> tuple[str, list[Translation]] | None:
        """Find a Chadian Arabic inflected form and return its lemma's senses.

        Args:
            phrase: An inflected word, e.g. ``"aswaag"`` or ``"nachri"``.
            direction: Ignored unless ``"fr-ar"``, which always returns None.

        Returns:
            ``(lemma, translations)`` where each translation's ``note`` explains
            the form (e.g. ``"pluriel de suug"``), or None.
        """
        if direction == "fr-ar":
            return None
        key = strip_article(normalize_td(phrase))
        if key not in self.forms:
            return None
        results: list[Translation] = []
        lemma = None
        for lemma, note in self.forms[key]:
            results += [Translation(t.output, t.pos, t.sense_number, t.forms, t.direction, note)
                        for t in self.ar.get(lemma, [])]
        return lemma, results

    def fuzzy(self, phrase: str, direction: Direction = "auto",
              limit: int = FUZZY_LIMIT, threshold: int = FUZZY_THRESHOLD) -> list[dict]:
        """Return the closest keys by string similarity.

        Args:
            phrase: Text to approximate.
            direction: Which index(es) to search.
            limit: Maximum number of suggestions.
            threshold: Minimum similarity (0-100).

        Returns:
            Suggestions ``{"word", "translations", "similarity"}``, best first.
        """
        suggestions = []
        for name, index in self._indexes(direction):
            keys = self._ar_keys if name == "ar" else self._fr_keys
            query = normalize_td(phrase) if name == "ar" else normalize_fr(phrase)
            for word, score in _fuzzy_extract(query, keys, limit, threshold):
                suggestions.append({"word": word,
                                    "translations": [t.as_dict() for t in index[word]],
                                    "similarity": round(score, 1)})
        suggestions.sort(key=lambda s: -s["similarity"])
        return suggestions[:limit]

    def lookup(self, query: str, direction: Direction = "auto") -> LookupResult:
        """Translate a word: exact match, then inflected form, then fuzzy.

        Args:
            query: Word or expression to translate.
            direction: ``"auto"``, ``"ar-fr"`` or ``"fr-ar"``.

        Returns:
            The lookup result (see :class:`LookupResult` for the statuses).
        """
        hit = self.exact(query, direction)
        if hit:
            return LookupResult(query, "exact_match", hit[0], hit[1])
        hit = self.by_form(query, direction)
        if hit:
            return LookupResult(query, "form_match", hit[0], hit[1])
        suggestions = self.fuzzy(query, direction)
        return LookupResult(query, "no_exact_match" if suggestions else "no_match",
                            suggestions=suggestions)

    def entries_for(self, headword: str) -> list[dict]:
        """Return the raw corpus rows of a headword (used by sentence generation).

        Args:
            headword: Chadian Arabic headword.

        Returns:
            Every row whose ``src`` matches, one per sense.
        """
        return list(self._by_src.get(normalize_td(headword), []))

    def knows_td(self, token: str) -> bool:
        """Tell whether a Chadian Arabic token is in the lexicon.

        Args:
            token: A word, with or without the article.

        Returns:
            True if it is a headword or a known inflected form.
        """
        key = strip_article(normalize_td(token))
        return key in self.ar or key in self.forms

    def __len__(self) -> int:
        """Return the number of corpus rows."""
        return len(self.rows)


@lru_cache(maxsize=1)
def get_lexicon() -> Lexicon:
    """Return the shared lexicon, loaded once per process.

    Returns:
        The lexicon built from ``PATHS.corpus_csv``.

    Raises:
        FileNotFoundError: If the corpus CSV does not exist.
    """
    return Lexicon.from_csv()

"""Sentence translation through the lexicon (assisted word-by-word gloss).

This is NOT a machine translation system: the sentence is segmented by
longest match (multi-word expressions first), each segment gets its candidate
translations, and a draft gloss is proposed. It is meant to prepare sentences
that a speaker then validates (see docs/03-generation-traduction.md).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

from td_arabic.translation.french import lemma_candidates
from td_arabic.translation.lexicon import Lexicon, Translation, get_lexicon
from td_arabic.utils.text import capitalize_first, tokenize_fr, tokenize_td

SentenceDirection = Literal["fr-ar", "ar-fr"]
MAX_NGRAM = 4
FUZZY_MIN_SCORE = 80

# French function words with no direct equivalent in the lexicon: skipped in
# the gloss instead of being reported as unknown.
FR_FUNCTION_WORDS = {
    "le", "la", "les", "l'", "un", "une", "des", "du", "de", "d'", "au", "aux", "à",
    "est", "sont", "ce", "c'", "cet", "cette", "ces", "en", "y", "que", "qu'", "se",
    "s'", "ne", "n'", "pas", "suis", "es", "sommes", "êtes", "j'", "m'", "t'",
}


@dataclass
class Segment:
    """A piece of the source sentence and its candidate translations.

    Attributes:
        source: The source word or expression.
        match: How it was matched: ``exact``, ``forme`` (inflected form or
            French conjugated verb), ``approx`` (fuzzy), ``mot_outil``
            (skipped function word) or ``inconnu`` (unknown).
        candidates: Candidate translations ``{text, pos, sense_number, forms, note}``.
    """

    source: str
    match: str
    candidates: list[dict] = field(default_factory=list)

    @property
    def best(self) -> str | None:
        """The first candidate's text, or None if there is no candidate."""
        return self.candidates[0]["text"] if self.candidates else None


@dataclass
class SentenceTranslation:
    """Result of :func:`translate_sentence`.

    Attributes:
        source: The original sentence.
        direction: ``"fr-ar"`` or ``"ar-fr"``.
        segments: The segments, in sentence order.
    """

    source: str
    direction: str
    segments: list[Segment]

    @property
    def gloss(self) -> str:
        """Draft translation: best candidate per segment, unknown words in [brackets].

        Function words are skipped; the first letter is capitalised when the
        source sentence starts with a capital.
        """
        parts = []
        for seg in self.segments:
            if seg.match == "mot_outil":
                continue
            parts.append(seg.best if seg.best else f"[{seg.source}]")
        text = " ".join(parts)
        return capitalize_first(text) if self.source[:1].isupper() else text

    @property
    def coverage(self) -> float:
        """Share of content segments (function words excluded) found exactly or by form."""
        content = [s for s in self.segments if s.match != "mot_outil"]
        if not content:
            return 0.0
        return sum(s.match in ("exact", "forme") for s in content) / len(content)

    def as_dict(self) -> dict:
        """Return a JSON-serialisable dict (``source, direction, gloss, coverage, segments``)."""
        return {"source": self.source, "direction": self.direction, "gloss": self.gloss,
                "coverage": round(self.coverage, 3),
                "segments": [asdict(s) for s in self.segments]}


def _candidates(translations: list[Translation]) -> list[dict]:
    """Convert lexicon translations into segment candidates."""
    return [{"text": t.output, "pos": t.pos, "sense_number": t.sense_number,
             "forms": t.forms, "note": t.note} for t in translations]


def _match_single(token: str, direction: str, lexicon: Lexicon) -> Segment:
    """Match a single word that has no exact entry.

    Tries, in order: a Chadian Arabic inflected form, a French lemma
    (``achète`` -> ``acheter``), then a fuzzy match scoring at least
    ``FUZZY_MIN_SCORE``.

    Args:
        token: The word to match.
        direction: ``"fr-ar"`` or ``"ar-fr"``.
        lexicon: The lexicon to search.

    Returns:
        A segment whose ``match`` is ``forme``, ``approx`` or ``inconnu``.
    """
    hit = lexicon.by_form(token, direction)
    if hit:
        return Segment(token, "forme", _candidates(hit[1]))
    if direction == "fr-ar":
        for lemma in lemma_candidates(token):
            hit = lexicon.exact(lemma, direction)
            if hit:
                cands = _candidates(hit[1])
                for c in cands:
                    c["note"] = f"forme de « {lemma} »"
                return Segment(token, "forme", cands)
    fuzzy = [s for s in lexicon.fuzzy(token, direction, limit=3) if s["similarity"] >= FUZZY_MIN_SCORE]
    if fuzzy:
        cands = [{"text": c["output"], "pos": c["pos"], "sense_number": c["sense_number"],
                  "forms": c["forms"], "note": f"approx. de « {s['word']} » ({s['similarity']:.0f} %)"}
                 for s in fuzzy for c in s["translations"]]
        return Segment(token, "approx", cands)
    return Segment(token, "inconnu")


def _match_at(tokens: list[str], i: int, direction: str, lexicon: Lexicon) -> tuple[Segment, int]:
    """Find the longest exact match starting at ``tokens[i]``.

    Args:
        tokens: Tokenised sentence.
        i: Start position.
        direction: ``"fr-ar"`` or ``"ar-fr"``.
        lexicon: The lexicon to search.

    Returns:
        ``(segment, consumed)``: the segment and the number of tokens it covers
        (up to ``MAX_NGRAM``).
    """
    for n in range(min(MAX_NGRAM, len(tokens) - i), 0, -1):
        if n == 1 and direction == "fr-ar" and tokens[i] in FR_FUNCTION_WORDS:
            return Segment(tokens[i], "mot_outil"), 1
        phrase = " ".join(tokens[i:i + n]).replace("' ", "'")
        hit = lexicon.exact(phrase, direction)
        if hit:
            return Segment(phrase, "exact", _candidates(hit[1])), n
    return _match_single(tokens[i], direction, lexicon), 1


def translate_sentence(text: str, direction: SentenceDirection = "fr-ar",
                       lexicon: Lexicon | None = None) -> SentenceTranslation:
    """Gloss a sentence word by word using the lexicon.

    Args:
        text: Sentence to translate.
        direction: ``"fr-ar"`` (French -> Chadian Arabic) or ``"ar-fr"``.
        lexicon: Lexicon to use; defaults to the shared one.

    Returns:
        The segmented translation, with ``gloss`` and ``coverage``.

    Raises:
        FileNotFoundError: If no lexicon is given and the corpus CSV is missing.
    """
    lexicon = lexicon or get_lexicon()
    tokens = tokenize_fr(text) if direction == "fr-ar" else tokenize_td(text)
    segments: list[Segment] = []
    i = 0
    while i < len(tokens):
        segment, consumed = _match_at(tokens, i, direction, lexicon)
        segments.append(segment)
        i += consumed
    return SentenceTranslation(text, direction, segments)


def guess_direction(text: str, lexicon: Lexicon | None = None) -> SentenceDirection:
    """Guess the source language of a sentence.

    Args:
        text: Sentence in French or Chadian Arabic.
        lexicon: Lexicon to use; defaults to the shared one.

    Returns:
        ``"ar-fr"`` if the Chadian Arabic reading covers more of the sentence,
        otherwise ``"fr-ar"``.
    """
    lexicon = lexicon or get_lexicon()
    fr = translate_sentence(text, "fr-ar", lexicon).coverage
    ar = translate_sentence(text, "ar-fr", lexicon).coverage
    return "ar-fr" if ar > fr else "fr-ar"

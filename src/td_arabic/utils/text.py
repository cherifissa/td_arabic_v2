"""Text normalisation shared by the whole project.

Spelling conventions (see docs/annexes/cours-arabe-tchadien-latin.md):

- the glottal stop is written ``ʼ`` (U+02BC); keyboard variants
  (' ’ ʾ ʿ `) are mapped to it for Chadian Arabic;
- the definite article is written ``al-`` (``l-`` after a particle ending in
  a vowel: ``fi l-khariif``), as in the SIL lexicon.
"""

from __future__ import annotations

import re
import unicodedata

GLOTTAL = "ʼ"  # ʼ
_GLOTTAL_VARIANTS = "'’ʾʿ`´"
_GLOTTAL_TABLE = str.maketrans({c: GLOTTAL for c in _GLOTTAL_VARIANTS})

ARTICLE_PREFIXES = ("al-", "l-")

# French elision: l'eau -> l' + eau
_FR_ELISION = re.compile(r"\b(qu|[cdjlmnst])['’]", re.IGNORECASE)
_TOKEN_TD = re.compile(rf"[\w{GLOTTAL}]+(?:-[\w{GLOTTAL}]+)*", re.UNICODE)
_TOKEN_FR = re.compile(r"\w+(?:['-]\w+)*'?", re.UNICODE)


def nfc(text: str) -> str:
    """Apply Unicode NFC normalisation.

    Args:
        text: Input string.

    Returns:
        The NFC-normalised string.
    """
    return unicodedata.normalize("NFC", text)


def collapse_spaces(text: str) -> str:
    """Replace runs of whitespace with one space and trim both ends.

    Args:
        text: Input string.

    Returns:
        The string with collapsed whitespace.
    """
    return re.sub(r"\s+", " ", text).strip()


def normalize_glottal(text: str) -> str:
    """Write the glottal stop in the project's canonical form, keeping the case.

    Args:
        text: A Chadian Arabic word or phrase (proper nouns keep their capital).

    Returns:
        NFC text with every glottal-stop variant mapped to ``ʼ`` and whitespace
        collapsed (e.g. ``"Ga'ad"`` -> ``"Gaʼad"``).
    """
    return collapse_spaces(nfc(str(text)).translate(_GLOTTAL_TABLE))


def normalize_td(text: str) -> str:
    """Build the lookup key for latinised Chadian Arabic.

    Args:
        text: A Chadian Arabic word or phrase.

    Returns:
        NFC, lower-cased text with every glottal-stop variant mapped to ``ʼ``
        and whitespace collapsed (e.g. ``"Ga'ad"`` -> ``"gaʼad"``).
    """
    return collapse_spaces(nfc(str(text)).translate(_GLOTTAL_TABLE).lower())


def normalize_fr(text: str) -> str:
    """Build the lookup key for French.

    Args:
        text: A French word or phrase.

    Returns:
        NFC, lower-cased text with typographic apostrophes replaced by ``'``.
    """
    return collapse_spaces(nfc(str(text)).replace("’", "'").lower())


def normalize_any(text: str) -> str:
    """Build a language-neutral key (glottal stops unified, lower case).

    Args:
        text: Text in either language.

    Returns:
        The same key as :func:`normalize_td`.
    """
    return normalize_td(text)


def tokenize_td(text: str) -> list[str]:
    """Split Chadian Arabic text into normalised tokens.

    Hyphenated words (``al-suug``) and glottal stops stay inside a token;
    punctuation is dropped.

    Args:
        text: Latinised Chadian Arabic text.

    Returns:
        The list of tokens, e.g. ``["fi", "l-khariif", "al-matar"]``.
    """
    return _TOKEN_TD.findall(normalize_td(text))


def tokenize_fr(text: str) -> list[str]:
    """Split French text into normalised tokens, separating elisions.

    Args:
        text: French text.

    Returns:
        The list of tokens, e.g. ``"L'eau"`` -> ``["l'", "eau"]``; words such
        as ``aujourd'hui`` stay whole.
    """
    text = _FR_ELISION.sub(lambda m: m.group(1) + "' ", normalize_fr(text))
    return _TOKEN_FR.findall(text)


def strip_article(token: str) -> str:
    """Remove a leading definite article.

    Args:
        token: A normalised Chadian Arabic token.

    Returns:
        The token without ``al-`` / ``l-`` (``al-suug`` -> ``suug``); the token
        itself if it has no article.
    """
    for prefix in ARTICLE_PREFIXES:
        if token.startswith(prefix) and len(token) > len(prefix):
            return token[len(prefix):]
    return token


def capitalize_first(text: str) -> str:
    """Upper-case the first letter, skipping leading punctuation.

    Args:
        text: Input string.

    Returns:
        The string with its first alphabetic character in upper case.
    """
    for i, ch in enumerate(text):
        if ch.isalpha():
            return text[:i] + ch.upper() + text[i + 1:]
    return text


def tidy_punctuation(text: str, lang: str = "fr") -> str:
    """Normalise spaces around punctuation.

    Args:
        text: Sentence to tidy.
        lang: ``"fr"`` adds a space before ``? ! : ;`` (French typography);
            any other value removes it (Chadian Arabic, as in the SIL lexicon).

    Returns:
        The tidied sentence. No space is ever kept before ``.`` or ``,``.
    """
    text = collapse_spaces(text)
    text = re.sub(r"\s+([.,])", r"\1", text)
    if lang == "fr":
        text = re.sub(r"\s*([?!:;])", r" \1", text)
    else:
        text = re.sub(r"\s+([?!:;])", r"\1", text)
    return text.strip()

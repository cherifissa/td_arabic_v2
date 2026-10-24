"""Chadian Arabic morphology used by sentence generation.

Every form comes from the lexicon (``forms`` column): this module only picks
the right one and applies two rules documented in the course
(docs/annexes/cours-arabe-tchadien-latin.md):

- imperfective: the lexicon gives the 3rd person masculine singular
  (``y-`` prefix); 1st person singular -> ``n-``, 2nd person masculine
  singular and 3rd person feminine singular -> ``t-``;
- perfective (accompli): the lexicon headword is the 3rd person masculine singular;
  the other nine persons add one of the eight suffixes of the course (chapter 9);
- adjectives: feminine and masculine plural forms come from the lexicon (chapter 8);
- definite article: ``al-``; ``l-`` after a particle ending in a vowel
  (``fi l-khariif``, ``be l-aks``, ``ila l-abad`` in the SIL lexicon).
"""

from __future__ import annotations

import re

from td_arabic.translation.lexicon import Lexicon, parse_forms
from td_arabic.utils.text import capitalize_first

PERSON_PREFIX = {"ana": "n", "inta": "t", "hi": "t", "hu": "y"}

# Perfective suffixes, course chapter 9 (model verb `katab`): katabt, katabti, katab, katabat...
ACCOMPLI_SUFFIX = {"ana": "t", "inta": "t", "inti": "ti", "hu": "", "hi": "at",
                   "aniina": "na", "intu": "tu", "intan": "tan", "humman": "o", "hinna": "an"}
# Two documented limits of the course table: it only shows verbs whose base ends in a
# consonant and has no long vowel just before it. Verbs ending in a vowel (``macha``,
# ``chara``) or with a long vowel + final consonant (``chaaf``, ``zaar``, ``naam``)
# change their stem in speech; the course does not describe them, so they are not conjugated.
_VOWELS = "aeiou"
_LONG_VOWEL_BEFORE_LAST = re.compile(r"(aa|ii|uu|ee|oo)[^aeiou]$")
# Particles after which the article is elided to "l-" (examples from the lexicon)
ELIDING_PARTICLES = {"fi", "be", "le", "ila", "wa", "ma", "ya"}
DEFINITE_MARK = "@"


class MorphologyError(ValueError):
    """Raised when the lexicon does not provide the requested form."""


class UnsupportedFormError(MorphologyError):
    """Raised when a form exists but no documented rule gives it (e.g. weak verbs)."""


def lexicon_entry(lexicon: Lexicon, headword: str, sense: int | None = None,
                  pos_prefix: str | None = None) -> dict:
    """Return the corpus row of a headword.

    Args:
        lexicon: Lexicon to search.
        headword: Chadian Arabic headword, e.g. ``"chara"``.
        sense: Homograph number to select, if the word has several.
        pos_prefix: Keep only rows whose part of speech starts with it
            (``"v."``, ``"adj."``...).

    Returns:
        The first matching row (``src``, ``pos``, ``output``, ``forms``,
        ``sense_number``).

    Raises:
        MorphologyError: If no row matches.
    """
    rows = lexicon.entries_for(headword)
    if sense is not None:
        rows = [r for r in rows if r["sense_number"] and int(float(r["sense_number"])) == sense]
    if pos_prefix:
        rows = [r for r in rows if r["pos"].startswith(pos_prefix)]
    if not rows:
        detail = f" (sens {sense})" if sense else ""
        raise MorphologyError(f"« {headword} »{detail} absent du lexique"
                              + (f" comme {pos_prefix}" if pos_prefix else ""))
    return rows[0]


def forms_of(entry: dict, label: str) -> list[str]:
    """Return the values of one form label of an entry.

    Args:
        entry: A corpus row.
        label: Form label, e.g. ``"inacc."``, ``"f."``, ``"pl."``.

    Returns:
        The matching values, in lexicon order (possibly empty).
    """
    return [v for l, v in parse_forms(entry["forms"]) if l == label]


def inaccompli(entry: dict, person: str, preferred: str | None = None) -> str:
    """Conjugate a verb in the imperfective.

    Args:
        entry: Corpus row of the verb.
        person: ``"ana"``, ``"inta"``, ``"hu"`` or ``"hi"``.
        preferred: Imperfective form to use when the lexicon lists several
            (e.g. ``"yidoor"`` rather than ``"yidawwir"``).

    Returns:
        The conjugated form, e.g. ``yachri`` -> ``nachri`` for ``ana``.

    Raises:
        MorphologyError: If ``preferred`` is not among the lexicon forms, or
            the verb has no imperfective starting with ``y-``.
        KeyError: If ``person`` is not one of the four supported persons.
    """
    forms = forms_of(entry, "inacc.")
    if preferred:
        if preferred not in forms:
            raise MorphologyError(f"inaccompli « {preferred} » absent des formes de {entry['src']}")
        forms = [preferred]
    if not forms or not forms[0].startswith("y"):
        raise MorphologyError(f"pas d'inaccompli en y- pour « {entry['src']} »")
    return PERSON_PREFIX[person] + forms[0][1:]


def accompli_supported(base: str) -> bool:
    """Tell whether the course's perfective rule applies to a verb.

    Args:
        base: Headword of the verb (3rd person masculine singular perfective).

    Returns:
        True if the base ends in a consonant, without a long vowel just before it.
        False for vowel-final or hollow verbs, whose stem changes (not in the course).
    """
    base = base.lower()
    return bool(base) and base[-1] not in _VOWELS and not _LONG_VOWEL_BEFORE_LAST.search(base)


def accompli(entry: dict, person: str) -> str:
    """Conjugate a verb in the perfective (accompli).

    Args:
        entry: Corpus row of the verb; its ``src`` is the 3rd person masculine singular.
        person: One of the ten pronouns of ``ACCOMPLI_SUFFIX`` (``ana``, ``inta``, ``inti``,
            ``hu``, ``hi``, ``aniina``, ``intu``, ``intan``, ``humman``, ``hinna``).

    Returns:
        The base plus the person suffix, e.g. ``rajjaʼ`` -> ``rajjaʼat`` for ``hi``.

    Raises:
        UnsupportedFormError: If the verb is outside the documented rule.
        KeyError: If ``person`` is unknown.
    """
    base = entry["src"]
    if not accompli_supported(base):
        raise UnsupportedFormError(
            f"accompli de « {base} » non documenté (verbe terminé par une voyelle ou à voyelle longue)")
    return base + ACCOMPLI_SUFFIX[person]


FORM_LABELS = {"pl": "pl.", "sg": "sg.", "dl": "dl."}


def noun_form(entry: dict, key: str) -> str:
    """Return the plural, singulative or dual of a noun, as given by the lexicon.

    Args:
        entry: Corpus row of the noun.
        key: ``pl`` (plural), ``sg`` (singulative of a collective noun, course chapter 7) or
            ``dl`` (dual in ``-een``).

    Returns:
        The first form with that label (``abu`` -> ``abbahaat``, ``beed`` -> ``beedaay``,
        ``iid`` -> ``iideen``).

    Raises:
        UnsupportedFormError: If the lexicon gives no such form for this noun.
    """
    forms = forms_of(entry, FORM_LABELS[key])
    if not forms:
        raise UnsupportedFormError(f"pas de forme « {FORM_LABELS[key]} » pour « {entry['src']} »")
    return forms[0].split(" ou ")[0]


def adjective_plural(entry: dict) -> str:
    """Return the masculine plural of an adjective.

    Args:
        entry: Corpus row of the adjective.

    Returns:
        The first ``pl.`` form ending in ``-iin`` (course chapter 8), else the first ``pl.`` form.

    Raises:
        MorphologyError: If the lexicon gives no plural form.
    """
    plurals = forms_of(entry, "pl.")
    if not plurals:
        raise MorphologyError(f"pas de pluriel pour « {entry['src']} »")
    return next((p for p in plurals if p.endswith("iin")), plurals[0])


def feminine(entry: dict) -> str:
    """Return the feminine form of an adjective.

    Args:
        entry: Corpus row of the adjective.

    Returns:
        The first ``f.`` form of the lexicon, e.g. ``khaali`` -> ``khaaliye``.

    Raises:
        MorphologyError: If the lexicon gives no feminine form.
    """
    forms = forms_of(entry, "f.")
    if not forms:
        raise MorphologyError(f"pas de forme féminine pour « {entry['src']} »")
    return forms[0]


def noun_gender(entry: dict) -> str:
    """Return the grammatical gender of a noun.

    Args:
        entry: Corpus row of the noun.

    Returns:
        ``"m"`` for ``n.m.``, ``"f"`` for ``n.f.``.

    Raises:
        MorphologyError: For any other part of speech (e.g. ``n.coll.``).
    """
    if entry["pos"].startswith("n.m"):
        return "m"
    if entry["pos"].startswith("n.f"):
        return "f"
    raise MorphologyError(f"genre inconnu pour « {entry['src']} » ({entry['pos']})")


def resolve_articles(text: str) -> str:
    """Replace each ``@word`` with ``al-word`` or ``l-word``.

    Args:
        text: Chadian Arabic sentence with definite markers, e.g.
            ``"fi @khariif @matar katiir."``.

    Returns:
        The sentence with articles resolved and its first letter capitalised,
        e.g. ``"Fi l-khariif al-matar katiir."``.
    """
    out: list[str] = []
    for token in text.split(" "):
        if token.startswith(DEFINITE_MARK):
            prev = re.sub(r"[^\wʼ]", "", out[-1]).lower() if out else ""
            article = "l-" if prev in ELIDING_PARTICLES else "al-"
            token = article + token[len(DEFINITE_MARK):]
        out.append(token)
    return capitalize_first(" ".join(out))


# --- French passé composé (the French side of the perfective) ---------------
_AUX = {
    "avoir": {"je": "ai", "tu": "as", "il": "a", "elle": "a", "nous": "avons", "vous": "avez",
              "ils": "ont", "elles": "ont"},
    "etre": {"je": "suis", "tu": "es", "il": "est", "elle": "est", "nous": "sommes", "vous": "êtes",
             "ils": "sont", "elles": "sont"},
}
_REFLEXIVE = {"je": "me", "tu": "te", "il": "se", "elle": "se", "nous": "nous", "vous": "vous",
              "ils": "se", "elles": "se"}


def passe_compose(pronoun: str, genre: str, nombre: str, participle: str, aux: str = "avoir") -> str:
    """Build a French passé composé.

    Args:
        pronoun: French subject pronoun: ``je``, ``tu``, ``il``, ``elle``, ``nous``, ``vous``,
            ``ils`` or ``elles``.
        genre: ``m`` or ``f`` (agreement with ``être`` and reflexive verbs).
        nombre: ``sg`` or ``pl``.
        participle: Masculine singular past participle (``acheté``, ``allé``, ``levé``).
        aux: ``avoir`` (no agreement), ``etre``, or ``pronominal`` (reflexive, with ``être``).

    Returns:
        E.g. ``("elle", "f", "sg", "allé", "etre")`` -> ``"elle est allée"``;
        ``("tu", "m", "sg", "levé", "pronominal")`` -> ``"tu t'es levé"``.

    Raises:
        KeyError: If the pronoun or the auxiliary is unknown.
    """
    helper = _AUX["avoir" if aux == "avoir" else "etre"][pronoun]
    if aux == "avoir":
        text = f"{pronoun} {helper}"
        return f"j'{helper} {participle}" if pronoun == "je" else f"{text} {participle}"
    agreed = participle + ("e" if genre == "f" else "") + ("s" if nombre == "pl" else "")
    if aux == "pronominal":
        reflexive = _REFLEXIVE[pronoun]
        if reflexive in ("me", "te", "se") and helper[0] in "aeiouhâêéè":
            reflexive = reflexive[0] + "'"
            return f"{pronoun} {reflexive}{helper} {agreed}"
        return f"{pronoun} {reflexive} {helper} {agreed}"
    return f"{pronoun} {helper} {agreed}"

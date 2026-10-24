"""Minimal, dependency-free French lemmatiser.

Finds the infinitive or dictionary form of an inflected word
(« achète » -> « acheter ») so that conjugated French verbs can be matched
against the lexicon glosses.

Deliberately simple heuristic: frequent irregular verbs plus ending rules for
-er/-ir/-re verbs and plural/feminine forms.
"""

from __future__ import annotations

# Infinitive -> space-separated inflected forms of frequent irregular verbs.
IRREGULAR = {
    "aller": "vais vas va allons allez vont allé allée allés irai iras ira irons irez iront allait allais",
    "être": "suis es est sommes êtes sont été était étais",
    "avoir": "ai as a avons avez ont eu avait avais",
    "faire": "fais fait faisons faites font faisait",
    "vouloir": "veux veut voulons voulez veulent voulu voulait",
    "pouvoir": "peux peut pouvons pouvez peuvent pu pouvait",
    "venir": "viens vient venons venez viennent venu venue venait",
    "voir": "vois voit voyons voyez voient vu vue voyait",
    "dire": "dis dit disons dites disent disait",
    "prendre": "prends prend prenons prenez prennent pris prise prenait",
    "boire": "bois boit buvons buvez boivent bu buvait",
    "savoir": "sais sait savons savez savent su savait",
    "dormir": "dors dort dormons dormez dorment dormi dormait",
    "partir": "pars part partons partez partent parti partie partait",
    "lire": "lis lit lisons lisez lisent lu lue lisait",
    "écrire": "écris écrit écrivons écrivez écrivent écrite écrivait",
    "vendre": "vends vend vendons vendez vendent vendu vendue vendait",
    "comprendre": "comprends comprend comprenons comprenez comprennent compris comprenait",
    "acheter": "achète achètes achètent",
    "se lever": "lève lèves lèvent",
}
_IRREGULAR_INDEX = {form: lemma for lemma, forms in IRREGULAR.items() for form in forms.split()}

# (ending, possible replacements), tried in order
_SUFFIX_RULES = [
    ("ons", ["er", "ir", "re"]), ("ez", ["er", "ir", "re"]), ("ent", ["er", "ir", "re"]),
    ("ais", ["er", "ir", "re"]), ("ait", ["er", "ir", "re"]), ("ées", ["er"]), ("és", ["er"]),
    ("ée", ["er"]), ("é", ["er"]), ("es", ["er", "e", ""]), ("e", ["er", ""]), ("is", ["ir"]),
    ("it", ["ir"]), ("x", [""]), ("s", [""]), ("aux", ["al"]),
]


def lemma_candidates(word: str) -> list[str]:
    """Propose possible dictionary forms of a French word.

    Args:
        word: An inflected French word, e.g. ``"achète"`` or ``"froide"``.

    Returns:
        Candidate lemmas, most likely first and without duplicates (the word
        itself excluded), e.g. ``"vais"`` -> ``["aller", ...]``. Candidates are
        guesses: the caller keeps the first one found in the lexicon.
    """
    word = word.lower()
    out: list[str] = []
    if word in _IRREGULAR_INDEX:
        out.append(_IRREGULAR_INDEX[word])
    for suffix, replacements in _SUFFIX_RULES:
        if word.endswith(suffix) and len(word) > len(suffix) + 1:
            stem = word[: -len(suffix)]
            out += [stem + r for r in replacements]
    return [c for i, c in enumerate(out) if c != word and c not in out[:i]]

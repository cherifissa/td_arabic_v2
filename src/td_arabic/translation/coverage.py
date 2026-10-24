"""Which important French words have no Chadian Arabic translation yet?

The lexicon is Chadian Arabic -> French, so it has no list of French words to
cover. This module checks a list of important French words
(``data/resources/mots_francais_importants.csv``, with synonyms and antonyms)
against the French glosses of the lexicon and gives each word one status,
from the strongest evidence to the weakest:

- ``couvert``   : the word is a gloss of a lexicon entry, as is or in another form
  of the same word (plural *œuf* -> « oeufs », reflexive *disperser* ->
  « se disperser », missing accents), see :func:`word_variants`;
- ``proche``    : only a looser match: the verb in the reflexive form (*lever* ->
  « se lever », often another meaning) or a plural gloss on an ordinary noun
  (*fil* -> « fils », probably another word): to check;
- ``famille``   : not a gloss, but a word of the same family is (*naître* ->
  *naissance* -> ``mawlid``, the Arabic words of one root often come together:
  ``wilid`` « enfanter », ``mawlid`` « naissance », ``waalid`` « père »);
- ``synonyme``  : not a gloss, but one of its synonyms is (e.g. *route* ->
  *chemin* -> ``derib``): a lead to check with a speaker, not a translation;
- ``antonyme``  : only an antonym is a gloss (a hint: *froid* -> *chaud*);
- ``mentionne`` : the word only appears inside a longer definition or in an
  expression (e.g. *route* in "coupeur de route"): not a real translation;
- ``absent``    : nothing found, a word to collect.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from td_arabic.config import PATHS
from td_arabic.translation.lexicon import Lexicon, get_lexicon, parse_forms
from td_arabic.utils.io import read_csv
from td_arabic.utils.text import normalize_fr

STATUSES = ("absent", "mentionne", "antonyme", "famille", "synonyme", "proche", "couvert")  # to-do first
WORDLIST_COLUMNS = ["mot", "categorie", "theme", "synonymes", "antonymes"]
REPORT_COLUMNS = ["mot", "categorie", "theme", "statut", "traductions", "via_synonymes",
                  "via_famille", "via_antonymes", "mentions", "propositions"]
# A gloss may start with an article (« le lendemain ») : it still translates « lendemain ».
_LEADING_ARTICLE = re.compile(r"^(le |la |les |l'|un |une |des |du )")
EXPRESSION_FORMS = "expr."
# Grammatical words (« de », « et », « je »…) appear in almost every definition: a "mention" says nothing.
NO_MENTION_CATEGORIES = {"prep", "pron", "conj", "interj"}
# Same words: never match them across accents (« où » / « ou »).
STRICT_CATEGORIES = NO_MENTION_CATEGORIES | {"interr"}
_NON_WORD = re.compile(r"[^\w]+")


def _split(cell) -> list[str]:
    """Split a ``;``-separated cell into clean items.

    Args:
        cell: Cell value (may be empty or NaN).

    Returns:
        The non-empty items, stripped.
    """
    if cell is None or (not isinstance(cell, str) and pd.isna(cell)):
        return []
    return [item.strip() for item in str(cell).split(";") if item.strip()]


def _words_key(text: str) -> str:
    """Return ``text`` as space-padded lower-case words (for whole-word search).

    Args:
        text: A French word, phrase or definition.

    Returns:
        E.g. ``"L'huile, chaude"`` -> ``" l huile chaude "``.
    """
    return f" {_NON_WORD.sub(' ', normalize_fr(text)).strip()} "


def load_wordlist(path: Path | None = None) -> pd.DataFrame:
    """Load the important-words list.

    Args:
        path: CSV with columns ``mot, categorie, theme, synonymes, antonymes``
            (``;`` separates several synonyms); defaults to
            ``PATHS.french_wordlist_csv``.

    Returns:
        The list as a DataFrame of strings; empty (with ``WORDLIST_COLUMNS``) if the file
        does not exist.
    """
    path = path or PATHS.french_wordlist_csv
    if not path.exists():
        return pd.DataFrame(columns=WORDLIST_COLUMNS)
    return read_csv(path)


def load_families(path: Path | None = None) -> dict[str, list[tuple[str, str]]]:
    """Load the word families.

    Args:
        path: CSV with one family per line in a ``mots`` column, members as
            ``word:category`` separated by ``;`` (``naître:v;naissance:n``);
            defaults to ``PATHS.word_families_csv``.

    Returns:
        ``{word: [(other_member, category), ...]}``; empty if the file is missing.
    """
    path = path or PATHS.word_families_csv
    if not path.exists():
        return {}
    families: dict[str, list[tuple[str, str]]] = {}
    for line in read_csv(path)["mots"]:
        members = []
        for item in _split(line):
            word, _, category = item.partition(":")
            members.append((word.strip(), category.strip()))
        for word, _ in members:
            others = families.setdefault(word, [])
            others += [m for m in members if m[0] != word and m not in others]
    return families


def wordlist_from_text(text: str) -> pd.DataFrame:
    """Build a word list (no synonyms) from free text, one word per line.

    Args:
        text: Words separated by line breaks or commas.

    Returns:
        A DataFrame with the list columns; synonyms and antonyms are empty.
    """
    words = [w.strip() for w in re.split(r"[\n,;]+", text) if w.strip()]
    unique = list(dict.fromkeys(words))
    return pd.DataFrame({"mot": unique, "categorie": "", "theme": "", "synonymes": "", "antonymes": ""})

# Months and days are never put in the plural: « mai » must not become « mais ».
NEVER_PLURALIZED = frozenset("janvier février mars avril mai juin juillet août septembre octobre novembre "
                             "décembre lundi mardi mercredi jeudi vendredi samedi dimanche".split())
IRREGULAR_PLURALS = {"œil": "yeux", "ciel": "cieux", "bétail": "bestiaux"}
# Part of speech (prefix of the lexicon tag) compatible with each word category.
# Empty category (words typed in the app) accepts nouns and adjectives.
POS_PREFIXES = {"n": ("n.",), "adj": ("adj",), "v": ("v.",), "adv": ("adv",), "": ("n.", "adj")}
VOWELS = "aeiouyàâäéèêëîïôöùûüœh"


def fold(text: str) -> str:
    """Lower-case a French text and drop accents and ligatures.

    The lexicon writes some glosses without accents or with ``oe`` instead of
    ``œ`` (« oeufs », « epines »), so words are compared in this form.

    Args:
        text: A French word or phrase.

    Returns:
        E.g. ``"Œufs"`` -> ``"oeufs"``, ``"épine"`` -> ``"epine"``.
    """
    text = normalize_fr(text).replace("œ", "oe").replace("æ", "ae")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def _plurals(word: str) -> list[str]:
    """Return plausible plural forms of a French noun or adjective."""
    word = normalize_fr(word)
    if word in NEVER_PLURALIZED:
        return []
    if " " in word:  # « pomme de terre » -> « pommes de terre »
        first, rest = word.split(" ", 1)
        return [f"{p} {rest}" for p in _plurals(first)] if " de " in f" {rest}" or rest.startswith("à ") else []
    if word in IRREGULAR_PLURALS:
        return [IRREGULAR_PLURALS[word]]
    if word.endswith(("s", "x", "z")):
        return []
    forms = [word + "s"]
    if word.endswith("al"):
        forms.append(word[:-2] + "aux")
    if word.endswith(("au", "eu")):
        forms.append(word + "x")
    if word.endswith("ail"):
        forms.append(word[:-3] + "aux")
    return forms


def word_variants(word: str, category: str = "") -> list[tuple[str, str]]:
    """List the forms under which a French word may appear in the lexicon glosses.

    The SIL lexicon glosses collective nouns in the plural (``beed`` -> « oeufs »,
    ``suuf`` -> « poils, cheveux ») and reflexive verbs with « se »
    (``achchattat`` -> « se disperser »). Grammatical words are never varied:
    *mai* would become *mais* and *moi* would become *mois*.

    Args:
        word: The French word as written in the list (singular, infinitive).
        category: ``n``, ``adj``, ``v``, ``adv``, ``prep``…; empty if unknown.

    Returns:
        ``(form, kind)`` pairs, best first. ``kind`` is ``exact``, ``pluriel``
        (the word is singular, the gloss plural) or ``pronominal``. There is no
        singular variant: *fois* would match *foi* and *ciseaux* would match *ciseau*.
    """
    out = [(word, "exact")]
    if category in ("n", "adj", ""):
        out += [(p, "pluriel") for p in _plurals(word)]
    if category == "v":
        bare = re.sub(r"^(se |s')", "", normalize_fr(word))
        if bare != normalize_fr(word):
            out.append((bare, "pronominal"))
        else:
            out += [(f"s'{bare}" if bare[:1] in VOWELS else f"se {bare}", "pronominal")]
    return out


@dataclass(frozen=True)
class Match:
    """One lexicon entry whose French gloss matches a word.

    Attributes:
        src: Chadian Arabic headword.
        kind: How the word matched (see :func:`word_variants`); ``pluriel_incertain`` is a
            plural gloss on an ordinary (non-collective) entry.
        gloss: The French gloss key that matched.
        singulative: For a collective noun matched through its plural gloss,
            the singulative form of the lexicon (``beed`` -> ``beedaay``); else empty.
        forms: Gender and number forms of the entry, as in the lexicon
            (``"f. jaara, pl. jiiraan"``); empty if it gives none.
    """

    src: str
    kind: str
    gloss: str
    singulative: str = ""
    forms: str = ""

    def label(self) -> str:
        """Return the entry as shown in the report, with how it matched."""
        if self.kind == "pluriel" and self.singulative:
            return f"{self.singulative} (singulatif de {self.src}, gloss : {self.gloss})"
        if self.kind == "pluriel":
            return f"{self.src} (gloss au pluriel : {self.gloss})"
        if self.kind == "pluriel_incertain":
            return f"{self.src} (gloss au pluriel, autre mot possible : {self.gloss})"
        if self.kind == "pronominal":
            return f"{self.src} (gloss : {self.gloss})"
        return f"{self.src} ({self.forms})" if self.forms else self.src

    def arabic(self) -> str:
        """Return the Chadian Arabic word to attach this French word to."""
        return self.singulative or self.src


# Forms shown next to a translation: feminine, plurals, dual (not the verb forms).
GENDER_NUMBER_LABELS = ("f.", "pl.", "m.pl.", "f.pl.", "dl.")


def gender_number_forms(forms: str) -> str:
    """Summarise the feminine, plural and dual forms of a lexicon entry.

    Args:
        forms: The ``forms`` column, e.g. ``"f. jaara / pl. jiiraan / f.pl. jaaraat"``.

    Returns:
        ``"f. jaara, pl. jiiraan, f.pl. jaaraat"`` in the lexicon order; empty if none.
    """
    return ", ".join(f"{label} {value}" for label, value in parse_forms(forms) if label in GENDER_NUMBER_LABELS)


# Kinds that count as coverage. A plural gloss is only trusted for collective / plural entries
# (« oeufs », « poils »); on an ordinary noun it may be another word (« fils » for *fil*).
STRONG_KINDS = ("exact", "pluriel")


def _pos_matches(pos: str, category: str) -> bool:
    """Tell whether a lexicon part-of-speech tag fits a word category."""
    return pos.startswith(POS_PREFIXES.get(category, POS_PREFIXES[""]))


class _CoverageIndex:
    """Lookups of French words in the lexicon, built once per lexicon.

    Attributes:
        lexicon: The lexicon whose French glosses are searched.
    """

    def __init__(self, lexicon: Lexicon):
        """Index the lexicon rows for mention search.

        Args:
            lexicon: The lexicon to search.
        """
        self.lexicon = lexicon
        self._fold: dict[str, list[str]] = {}
        for key in lexicon.fr:
            self._fold.setdefault(fold(key), []).append(key)
            bare = _LEADING_ARTICLE.sub("", key)
            if bare != key:
                self._fold.setdefault(fold(bare), []).append(key)
        self._rows = [(r["src"].strip(), r["output"].strip(), r.get("forms", "") == EXPRESSION_FORMS,
                       _words_key(r["output"])) for r in lexicon.rows]
        self._tokens: dict[str, list[int]] = {}
        for i, (_, _, _, key) in enumerate(self._rows):
            for token in set(key.split()):
                self._tokens.setdefault(token, []).append(i)

    def glossed_by(self, word: str, category: str = "") -> tuple[list[Match], list[str]]:
        """Find the entries whose French gloss is ``word`` (or one of its variants).

        Args:
            word: A French word or phrase.
            category: Word category, used to choose the variants and to ignore
                entries of another part of speech for non-exact matches.

        Returns:
            ``(matches, expressions)``: the real entries, then the headwords of
            expressions (which do not count as coverage).
        """
        matches: list[Match] = []
        expressions: list[str] = []
        for variant, kind in word_variants(word, category):
            wanted = normalize_fr(variant).strip(" .!?")
            for key in self._fold.get(fold(variant).strip(" .!?"), []):
                # Accent-insensitive only towards a gloss written WITHOUT accents (« oeufs »,
                # « epines »): « mai » must not match « maïs », nor « ou » match « où ».
                bare = _LEADING_ARTICLE.sub("", key)
                if wanted not in (key, bare) and (key != fold(key) or category in STRICT_CATEGORIES):
                    continue
                for t in self.lexicon.fr[key]:
                    if t.forms == EXPRESSION_FORMS:
                        if t.output not in expressions and kind == "exact":
                            expressions.append(t.output)
                        continue
                    if kind != "exact" and not _pos_matches(t.pos, category):
                        continue
                    entry_kind = kind
                    if kind == "pluriel" and not t.pos.startswith(("n.coll", "n.pl")):
                        entry_kind = "pluriel_incertain"
                    if any(m.src == t.output for m in matches):
                        continue
                    singulative = ""
                    if entry_kind == "pluriel":
                        singles = [v.split(" ou ")[0] for label, v in parse_forms(t.forms) if label == "sg."]
                        singulative = singles[0] if singles else ""
                    matches.append(Match(t.output, entry_kind, key, singulative, gender_number_forms(t.forms)))
        return matches, expressions

    def mentions(self, word: str, limit: int) -> list[str]:
        """Find the definitions that contain ``word`` as a whole word.

        Args:
            word: A French word or phrase.
            limit: Maximum number of examples returned.

        Returns:
            Strings ``"src : definition"`` (``"[expr.]"`` marks expressions).
        """
        needle = _words_key(word)
        tokens = needle.split()
        if not tokens:
            return []
        candidates = self._tokens.get(tokens[0], [])
        found = []
        for i in candidates:
            src, definition, is_expression, key = self._rows[i]
            if needle in key:
                found.append(f"{src} : {definition}" + (" [expr.]" if is_expression else ""))
        return found[:limit]


def _via(index: _CoverageIndex, words: list[str], category: str = "") -> tuple[str, bool]:
    """Describe which of ``words`` are glosses of the lexicon.

    Args:
        index: The coverage index.
        words: Synonyms or antonyms to look up.

    Returns:
        ``("chemin → derib, tariig ; sentier → …", found_any)``.
    """
    parts = []
    for word in words:
        matches, _ = index.glossed_by(word, category)
        matches = [m for m in matches if m.kind in STRONG_KINDS]
        if matches:
            parts.append(f"{word} → {', '.join(dict.fromkeys(m.arabic() for m in matches))}")
    return " ; ".join(parts), bool(parts)


def arabic_candidates(via: str) -> list[str]:
    """List the Chadian Arabic words named in a ``via_synonymes`` / ``via_antonymes`` cell.

    Args:
        via: E.g. ``"chemin → derib, tariig ; sentier → ..."``.

    Returns:
        The Arabic words, without duplicates: ``["derib", "tariig", ...]``.
    """
    words: list[str] = []
    for part in via.split(" ; "):
        for word in part.partition(" → ")[2].split(", "):
            if word.strip() and word.strip() not in words:
                words.append(word.strip())
    return words


def proposals_by_word(additions: pd.DataFrame) -> dict[str, list[str]]:
    """Index the hand-made proposals by the French words they translate.

    Args:
        additions: Rows of ``ajouts_corpus.csv`` (see ``translation.additions.load_additions``).

    Returns:
        ``{normalised French word: ["jidd (à relire)", "wileed imm (validée)", ...]}``;
        rejected proposals are left out.
    """
    from td_arabic.translation.lexicon import french_keys
    labels = {"propose": "à relire", "valide": "validée"}
    index: dict[str, list[str]] = {}
    for row in additions.itertuples():
        if row.statut not in labels:
            continue
        for part in str(row.output).split(", "):
            for key in set(french_keys(part)[1:] or french_keys(part)):
                for k in {key, _LEADING_ARTICLE.sub("", key)}:
                    index.setdefault(fold(k), []).append(f"{row.src} ({labels[row.statut]})")
    return index


def build_report(words: pd.DataFrame, lexicon: Lexicon | None = None, max_mentions: int = 3,
                 families: dict[str, list[tuple[str, str]]] | None = None,
                 additions: pd.DataFrame | None = None) -> pd.DataFrame:
    """Give each French word a coverage status against the lexicon.

    Args:
        words: Word list (see :func:`load_wordlist`).
        lexicon: Lexicon to check against; defaults to the shared one.
        max_mentions: Maximum number of definition examples kept per word.
        families: Word families (see :func:`load_families`); defaults to the shipped file.
        additions: Hand-made proposals, shown in the ``propositions`` column so a word is not
            proposed twice; defaults to ``ajouts_corpus.csv`` (pass an empty frame to ignore it).

    Returns:
        One row per word with ``REPORT_COLUMNS``, sorted with the words to
        collect first (``STATUSES`` order), then in list order.
    """
    index = _CoverageIndex(lexicon or get_lexicon())
    families = load_families() if families is None else families
    if additions is None:
        from td_arabic.translation.additions import load_additions
        additions = load_additions()
    proposed = proposals_by_word(additions)
    rows = []
    for item in words.itertuples(index=False):
        matches, expressions = index.glossed_by(item.mot, item.categorie)
        entries = [m.label() for m in matches]
        via_syn, has_syn = _via(index, _split(item.synonymes), item.categorie)
        via_ant, has_ant = _via(index, _split(item.antonymes), item.categorie)
        via_fam, has_fam = _via(index, [word for word, _ in families.get(item.mot, [])])
        covered = any(m.kind in STRONG_KINDS for m in matches)
        skip_mentions = covered or item.categorie in NO_MENTION_CATEGORIES
        mentions = [] if skip_mentions else index.mentions(item.mot, max_mentions)
        if expressions and not matches:
            mentions = [f"{src} : {item.mot} [expr.]" for src in expressions][:max_mentions] + mentions

        if covered:
            status = "couvert"
        elif matches:                      # forme pronominale (« se lever ») ou pluriel douteux
            status = "proche"
        elif has_syn:
            status = "synonyme"
        elif has_fam:
            status = "famille"
        elif has_ant:
            status = "antonyme"
        elif mentions:
            status = "mentionne"
        else:
            status = "absent"
        rows.append({"mot": item.mot, "categorie": item.categorie, "theme": item.theme,
                     "statut": status, "traductions": ", ".join(entries),
                     "via_synonymes": via_syn, "via_famille": via_fam, "via_antonymes": via_ant,
                     "mentions": " | ".join(mentions[:max_mentions]),
                     "propositions": ", ".join(dict.fromkeys(proposed.get(fold(item.mot), [])))})

    report = pd.DataFrame(rows, columns=REPORT_COLUMNS)
    order = {status: i for i, status in enumerate(STATUSES)}
    return (report.assign(_o=report["statut"].map(order)).sort_values("_o", kind="stable")
                  .drop(columns="_o").reset_index(drop=True))


def summarize(report: pd.DataFrame) -> dict:
    """Count words per status and per theme.

    Args:
        report: Output of :func:`build_report`.

    Returns:
        ``{"total", "par_statut", "couverture_directe", "par_theme"}`` where
        ``par_theme`` maps each theme to its share of covered words.
    """
    counts = report["statut"].value_counts().to_dict()
    total = len(report)
    by_theme = (report.assign(c=report["statut"] == "couvert").groupby("theme")["c"].mean().round(3)
                .sort_values().to_dict())
    return {"total": total, "par_statut": {s: int(counts.get(s, 0)) for s in STATUSES},
            "couverture_directe": round(counts.get("couvert", 0) / total, 3) if total else 0.0,
            "par_theme": by_theme}

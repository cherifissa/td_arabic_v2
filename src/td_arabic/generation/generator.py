"""Theme-based generation of sentence pairs (latinised Chadian Arabic / French).

Templates are described in ``data/resources/themes.yaml``. Every generated
sentence is traceable: source template, lexicon words used and any word not
found in the lexicon. Initial status: ``brouillon`` (draft, to be validated by
a speaker before recording).
"""

from __future__ import annotations

import hashlib
import itertools
import random
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

import yaml

from td_arabic.config import PATHS
from td_arabic.generation.morphology import (
    ACCOMPLI_SUFFIX, FORM_LABELS, PERSON_PREFIX, UnsupportedFormError, accompli, adjective_plural, feminine,
    forms_of, inaccompli, lexicon_entry, noun_form, noun_gender, passe_compose, resolve_articles,
)
from td_arabic.translation.lexicon import Lexicon, get_lexicon
from td_arabic.utils.text import capitalize_first, normalize_fr, tidy_punctuation

_PLACEHOLDER = re.compile(r"\{(@?)(\w+)(?:\.(\w+))?\}")
DEFAULT_PERSONS = ["ana", "inta", "hu", "hi"]          # imperfective: persons documented in the course
ACCOMPLI_PERSONS = list(ACCOMPLI_SUFFIX)                # perfective: the ten persons of chapter 9
ASPECTS = ("inacc", "accompli", "impr")                 # impr: imperative, 2nd person masc. sg. (chapter 11)
OPTIONAL_FR_KEYS = FORM_LABELS.keys() | {"un"}         # French forms a vocabulary item may lack


@dataclass
class GeneratedSentence:
    """A generated sentence pair and its provenance.

    Attributes:
        id: Stable identifier (theme prefix + hash of the texts).
        theme: Theme key, e.g. ``"marche"``.
        template_id: Template it comes from (``<theme>-fixe-NN`` for fixed phrases).
        fr: French sentence.
        td: Chadian Arabic sentence.
        lemmes: Lexicon headwords used.
        hors_lexique: Chadian Arabic words not found in the lexicon.
        statut: ``brouillon``, ``validee`` or ``rejetee``.
        source: ``gabarit`` (template), ``manuel`` or ``traduction``.
    """

    id: str
    theme: str
    template_id: str
    fr: str
    td: str
    lemmes: list[str] = field(default_factory=list)
    hors_lexique: list[str] = field(default_factory=list)
    statut: str = "brouillon"
    source: str = "gabarit"

    def as_dict(self) -> dict:
        """Return the sentence as a JSON-serialisable dict."""
        return asdict(self)


def sentence_id(theme: str, td: str, fr: str) -> str:
    """Build a stable sentence identifier.

    Args:
        theme: Theme key (its first three letters prefix the id).
        td: Chadian Arabic text.
        fr: French text.

    Returns:
        E.g. ``"mar-1a2b3c4d"``; the same texts always give the same id.
    """
    digest = hashlib.sha1(f"{td}|{fr}".encode("utf-8")).hexdigest()[:8]
    return f"{theme[:3]}-{digest}"


@lru_cache(maxsize=4)
def load_themes(path: Path | None = None) -> dict[str, Any]:
    """Load the template file (cached).

    Args:
        path: YAML file; defaults to ``PATHS.themes_yaml``.

    Returns:
        The parsed configuration (``personnes``, ``verbes``, ``adjectifs``,
        ``vocabulaire``, ``themes``).

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the file is not valid YAML.
    """
    with open(path or PATHS.themes_yaml, encoding="utf-8") as f:
        return yaml.safe_load(f)


class SentenceGenerator:
    """Fill the theme templates with lexicon words.

    Attributes:
        config: Parsed ``themes.yaml``.
        lexicon: Lexicon used for morphology and out-of-lexicon checks.
        vocab: Named vocabulary lists from the configuration.
    """

    def __init__(self, config: dict[str, Any] | None = None, lexicon: Lexicon | None = None):
        """Create a generator.

        Args:
            config: Template configuration; defaults to :func:`load_themes`.
            lexicon: Lexicon; defaults to the shared one.
        """
        self.config = config or load_themes()
        self.lexicon = lexicon or get_lexicon()
        self.vocab: dict[str, list[dict]] = self.config["vocabulaire"]

    # -- information ---------------------------------------------------------
    def themes(self) -> dict[str, str]:
        """Return the available themes.

        Returns:
            ``{theme_key: title}``, e.g. ``{"marche": "Au marché", ...}``.
        """
        return {k: v["titre"] for k, v in self.config["themes"].items()}

    # -- slot resolution -----------------------------------------------------
    def _vocab_items(self, spec: str | list) -> list[dict]:
        """Resolve a slot specification into vocabulary items.

        Args:
            spec: Name of a vocabulary list, or a list of headwords written
                inline (looked up in every list to get their French forms).

        Returns:
            Items ``{"td": ..., "fr": {...}}``. An item written ``td_de: <French gloss>`` has
            no fixed Chadian Arabic word: it is resolved from the lexicon (``td_de: jeudi`` gives
            the word glossed « jeudi »). The spelling therefore follows what was validated, and the
            item disappears while no validated word carries that meaning (days of the week
            proposed but not reviewed yet).

        Raises:
            KeyError: If ``spec`` names an unknown vocabulary list.
        """
        if isinstance(spec, str):
            items = self.vocab[spec]
        else:
            items = []
            for td in spec:
                found = next((i for lst in self.vocab.values()
                              for i in lst if i.get("td") == td), None)
                items.append(found or {"td": td, "fr": {}})
        resolved: list[dict] = []
        for item in items:
            if "td_de" not in item:
                resolved.append(item)
                continue
            words = [t.output for t in self.lexicon.fr.get(normalize_fr(item["td_de"]), [])
                     if t.forms != "expr."]
            for word in dict.fromkeys(words):
                resolved.append({**{k: v for k, v in item.items() if k != "td_de"}, "td": word})
        return resolved

    def _entry(self, item: dict, pos_prefix: str | None = None) -> dict:
        """Return the lexicon row of a vocabulary item (honouring its ``sens``).

        Compound items ("fi @leel", "kulla yoom") are not single entries and
        must not be passed here.
        """
        return lexicon_entry(self.lexicon, item["td"], item.get("sens"), pos_prefix)

    def _combinations(self, tpl: dict) -> Iterator[dict]:
        """Enumerate every filling of a template.

        Args:
            tpl: One template (``td``, ``fr``, and optional ``personnes``,
                ``verbes``, ``adjectifs``, ``slots``, ``aspects``, ``distinct``). ``aspects`` lists
                the verb aspects to generate: ``inacc`` (default), ``accompli`` and/or ``impr``
                (imperative, 2nd person masculine singular only). ``distinct`` names slots that
                must not receive the same word (``[N1, N2]`` for « du riz et de la viande »).

        Yields:
            Dicts ``{"P": person, "V": verb, "A": adjective, "T": aspect, <slot>: item...}``
            covering the Cartesian product of all choices. Without ``personnes``,
            the imperfective uses the 4 persons of ``DEFAULT_PERSONS`` and the
            perfective the 10 persons of ``ACCOMPLI_PERSONS``.
        """
        verbs = tpl.get("verbes", [None])
        adjs = tpl.get("adjectifs", [None])
        slot_names = list(tpl.get("slots", {}))
        slot_values = [self._vocab_items(tpl["slots"][n]) for n in slot_names]
        needs_person = "{P}" in tpl["td"] or "{V}" in tpl["td"]
        for aspect in (tpl.get("aspects", ["inacc"]) if tpl.get("verbes") else ["inacc"]):
            persons = tpl.get("personnes")
            if aspect == "impr":
                persons = ["inta"]                        # the lexicon gives the imperative of one person
            elif persons is None:
                persons = (ACCOMPLI_PERSONS if aspect == "accompli" else DEFAULT_PERSONS) if needs_person else [None]
            elif aspect == "inacc":
                persons = [p for p in persons if p is None or p in PERSON_PREFIX]  # no documented form for the others
            for person, verb, adj, *values in itertools.product(persons, verbs, adjs, *slot_values):
                combo = {"P": person, "V": verb, "A": adj, "T": aspect, **dict(zip(slot_names, values))}
                names = tpl.get("distinct", [])
                if names and len({combo[n]["td"] for n in names}) < len(names):
                    continue
                yield combo

    def _render(self, tpl: dict, combo: dict) -> tuple[str, str, list[str], list[str]]:
        """Render one template filling in both languages.

        The verb is conjugated from the lexicon imperfective; the adjective
        agrees with the noun named by ``accord`` (Chadian Arabic gender from
        the lexicon, French gender from the vocabulary item) or with the
        fixed ``accord_td`` / ``accord_fr`` genders.

        Args:
            tpl: The template.
            combo: One filling from :meth:`_combinations`.

        Returns:
            ``(td, fr, lemmas, derived)``: both sentences, the headwords used and the
            Chadian Arabic forms built by a documented rule (perfective), which are
            not in the lexicon as such.

        Raises:
            UnsupportedFormError: If the perfective of the verb is not documented.
            MorphologyError: If the lexicon lacks a needed form.
            KeyError: If the template uses a placeholder or key that is not
                defined for this filling.
        """
        person = combo["P"]
        lemmas: list[str] = []
        derived: list[str] = []
        td_values: dict[str, str] = {}
        fr_values: dict[str, dict[str, str]] = {}

        if person:
            td_values["P"] = person
            fr_values["P"] = {"fr": self.config["personnes"][person]["fr"]}
        if combo["V"]:
            verb = self.config["verbes"][combo["V"]]
            entry = self._entry(verb, "v.")
            if combo["T"] == "impr":
                forms = forms_of(entry, "impr.")
                word = self.config.get("imperatif", {}).get(combo["V"])
                if not forms or not word:
                    raise UnsupportedFormError(f"pas d'impératif pour « {combo['V']} »")
                td_values["V"] = forms[0]
                fr_values["V"] = {"": word}
            elif combo["T"] == "accompli":
                td_values["V"] = accompli(entry, person)
                derived.append(td_values["V"])
                fr_values["V"] = {"": self._past_french(combo["V"], person)}
            else:
                td_values["V"] = inaccompli(entry, person, verb.get("inacc"))
                fr_values["V"] = {"": verb["fr"][person]}
            lemmas.append(entry["src"])
        for name, item in combo.items():
            if name in ("P", "V", "A", "T") or item is None:
                continue
            td_values[name] = item["td"]
            fr_values[name] = item.get("fr", {})
            lemmas.append(item["td"])
        if combo["A"]:
            adj = self.config["adjectifs"][combo["A"]]
            entry = self._entry(adj, "adj.")
            target = tpl.get("accord")
            if target:
                g_td = noun_gender(self._entry(combo[target]))
                g_fr = combo[target]["fr"]["genre"]
            else:
                g_td, g_fr = tpl.get(
                    "accord_td", "m"), tpl.get("accord_fr", "m")
            if tpl.get("accord_nb") == "pl":              # plural subject (aniina, intu, humman)
                td_values["A"] = adjective_plural(entry)
                fr_values["A"] = {"": adj["fr"]["mp"]}
            else:
                td_values["A"] = feminine(entry) if g_td == "f" else entry["src"]
                fr_values["A"] = {"": adj["fr"][g_fr]}
            lemmas.append(entry["src"])

        def td_sub(m: re.Match) -> str:
            definite, name, key = m.groups()
            value = td_values[name]
            if key in FORM_LABELS:                        # {@N.pl}, {N.sg}, {@N.dl}: forms of the lexicon
                value = noun_form(self._entry(combo[name]), key)
            return ("@" if definite else "") + value

        def fr_sub(m: re.Match) -> str:
            _, name, key = m.groups()
            try:
                return fr_values[name][key or ""]
            except KeyError:
                if key in OPTIONAL_FR_KEYS:               # item without that French form: skip the sentence
                    raise UnsupportedFormError(f"forme française « {key} » absente pour « {name} »") from None
                raise

        td = resolve_articles(tidy_punctuation(
            _PLACEHOLDER.sub(td_sub, tpl["td"]), "td"))
        fr = tidy_punctuation(_PLACEHOLDER.sub(fr_sub, tpl["fr"]))
        fr = re.sub(r"\bEst-ce que (il|ils|elle|elles|on)\b", r"Est-ce qu'\1", fr)   # elision of the question
        return td, capitalize_first(fr), lemmas, derived

    def _past_french(self, verb_key: str, person: str) -> str:
        """Build the French passé composé of a verb for a person.

        Args:
            verb_key: Key of ``verbes`` in the configuration.
            person: One of ``ACCOMPLI_PERSONS``.

        Returns:
            E.g. ``"j'ai acheté"``, ``"elle est allée"``.

        Raises:
            UnsupportedFormError: If the verb has no ``passe`` entry (participle) in the configuration.
        """
        spec = self.config.get("passe", {}).get(verb_key)
        if not spec:
            raise UnsupportedFormError(f"pas de participe passé configuré pour « {verb_key} »")
        who = self.config["personnes"][person]
        return passe_compose(who["fr"], who.get("genre", "m"), who.get("nombre", "sg"),
                             spec["pp"], spec.get("aux", "avoir"))

    def _out_of_lexicon(self, td: str, derived: list[str] | None = None) -> list[str]:
        """Return the Chadian Arabic words of ``td`` not found in the lexicon.

        Args:
            td: The Chadian Arabic sentence.
            derived: Forms built by a documented rule from a lexicon headword (perfective);
                they are not listed in the lexicon and must not be reported.
        """
        from td_arabic.translation.sentence import translate_sentence
        from td_arabic.utils.text import normalize_td
        skip = {normalize_td(w) for w in derived or []}
        result = translate_sentence(td, "ar-fr", self.lexicon)
        return [s.source for s in result.segments
                if s.match not in ("exact", "forme") and normalize_td(s.source) not in skip]

    def _make(self, theme: str, template_id: str, td: str, fr: str, lemmas: list[str],
              derived: list[str] | None = None) -> GeneratedSentence:
        """Wrap rendered texts into a :class:`GeneratedSentence`."""
        return GeneratedSentence(sentence_id(theme, td, fr), theme, template_id, fr, td,
                                 sorted(set(lemmas)), self._out_of_lexicon(td, derived))

    # -- generation ----------------------------------------------------------
    def all_sentences(self, theme: str) -> list[GeneratedSentence]:
        """Generate every possible sentence of a theme.

        Args:
            theme: Theme key.

        Returns:
            All template fillings followed by the theme's fixed phrases,
            without duplicates.

        Raises:
            KeyError: If the theme does not exist.
            MorphologyError: If a template needs a form the lexicon lacks.
                Perfective forms with no documented rule are skipped, not raised.
        """
        spec = self.config["themes"][theme]
        out: list[GeneratedSentence] = []
        for tpl in spec.get("gabarits", []):
            for combo in self._combinations(tpl):
                try:
                    td, fr, lemmas, derived = self._render(tpl, combo)
                except UnsupportedFormError:
                    continue          # e.g. perfective of a verb the course does not describe
                out.append(self._make(theme, tpl["id"], td, fr, lemmas, derived))
        for i, phrase in enumerate(spec.get("phrases", []), start=1):
            td = resolve_articles(tidy_punctuation(phrase["td"], "td"))
            out.append(self._make(
                theme, f"{theme[:3]}-fixe-{i:02d}", td, phrase["fr"], []))
        unique = {s.id: s for s in out}
        return list(unique.values())

    def generate(self, themes: list[str] | None = None, n: int = 20,
                 seed: int | None = None, exclude: set[str] | None = None) -> list[GeneratedSentence]:
        """Sample sentences from one or several themes.

        Args:
            themes: Theme keys; defaults to every theme.
            n: Number of sentences per theme (fewer if the theme has fewer).
            seed: Random seed; the same seed gives the same sentences.
            exclude: Ids of sentences not to generate (already validated or rejected, see
                :meth:`SentenceStore.settled_ids`).

        Returns:
            Up to ``n`` sentences per theme, drawn without replacement.

        Raises:
            KeyError: If a theme does not exist.
        """
        rng = random.Random(seed)
        result: list[GeneratedSentence] = []
        for theme in themes or list(self.config["themes"]):
            pool = [s for s in self.all_sentences(theme) if s.id not in (exclude or ())]
            rng.shuffle(pool)
            result.extend(pool[:n])
        return result

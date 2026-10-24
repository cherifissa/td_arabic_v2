"""Training examples by task, built from the normalised records.

A model that "understands" Chadian Arabic needs more than word -> gloss pairs. As in the
instruction collections (FLAN, Aya), the same data feeds several tasks, each with a few
instruction wordings:

====================  =========================================  ==========================
task                  example                                    split by
====================  =========================================  ==========================
traduction_mot        « blanc » -> abyad ; abyad -> « blanc »    probe (memorisation)
definition            abyad -> « adj. blanc (f. beeda, pl. …) »  probe (memorisation)
flexion               pluriel de abyad -> buyud                  lemma (generalisation)
lemmatisation         buyud -> abyad (pluriel)                   lemma (generalisation)
orthographe           djambah -> jambah                          lemma (generalisation)
traduction_phrase     phrase fr <-> td                           template (generalisation)
====================  =========================================  ==========================

A word cannot be translated if it was never seen: the lexicon tasks are all trained on, and
their evaluation (``probe``) is a fixed sample of the training examples, which measures
memorisation. Morphology, spelling and sentences are split by group (lemma, template), so that
``dev`` and ``test`` measure generalisation to unseen lemmas and unseen sentence patterns.

The French -> Chadian Arabic examples are grouped by gloss: when several words share a gloss
(``témoigner`` -> chahad, chihid), the answer lists them all instead of giving the model two
contradicting targets.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from td_arabic.dataset.records import LANG_FR, LANG_TD
from td_arabic.utils.text import normalize_fr, normalize_td

SYSTEM_PROMPT = ("Tu es un assistant spécialiste de l'arabe tchadien écrit en alphabet latin (orthographe "
                 "SIL Tchad). Réponds brièvement.")
SPLITS = ("train", "dev", "test")
# Parts des gabarits gardées pour dev et test : peu de gabarits (une centaine), de tailles très
# inégales, donc une part plus grande que pour les lemmes pour que dev et test soient fournis.
SENTENCE_HOLDOUT = (0.1, 0.1)
# Tag -> (nom, avec article) pour les consignes de flexion et les réponses de lemmatisation.
TAG_NAMES = {"plural": ("pluriel", "le pluriel"), "feminine": ("féminin", "le féminin"), "dual": ("duel", "le duel"),
             "singulative": ("singulatif", "le singulatif"), "imperfective": ("inaccompli", "l'inaccompli"),
             "imperative": ("impératif", "l'impératif"), "participle": ("participe", "le participe"),
             "variant": ("variante", "une variante")}

# Plusieurs formulations par tâche (choisie par hachage : toujours la même pour un exemple).
PROMPTS = {
    "traduction_mot:fr-ar": ["Traduis en arabe tchadien : {x}", "Comment dit-on « {x} » en arabe tchadien ?"],
    "traduction_mot:ar-fr": ["Traduis en français : {x}", "Que veut dire « {x} » ?"],
    "definition": ["Donne la catégorie, le sens et les formes de « {x} ».", "Article de dictionnaire pour : {x}"],
    "flexion": ["Donne {tag} de « {x} ».", "Quel est {tag} de {x} ?"],
    "lemmatisation": ["Quelle est la forme de base de « {x} » ?", "Sous quel mot du lexique chercher « {x} » ?"],
    "orthographe": ["Corrige l'orthographe : {x}", "Écris correctement en orthographe SIL : {x}"],
    "traduction_phrase:fr-ar": ["Traduis en arabe tchadien : {x}"],
    "traduction_phrase:ar-fr": ["Traduis en français : {x}"],
}

# Fautes typiques, à l'inverse des règles du préambule (p. iii-iv) : (correct, fautif).
_MISSPELLINGS = [(re.compile(r"j"), "dj"), (re.compile(r"(?<!u)u(?!u)"), "ou"), (re.compile(r"g(?=[ei])"), "gu"),
                 (re.compile(r"ʼ"), "'"), (re.compile(r"([aeiou])\1"), r"\1")]


def _hash(text: str) -> int:
    return int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16)


def split_of(group: str, dev: float = 0.05, test: float = 0.05) -> str:
    """Assign a group to ``train``, ``dev`` or ``test`` (stable hash: new data never moves old data)."""
    bucket = _hash(f"split:{group}") % 10_000 / 10_000
    return "test" if bucket < test else "dev" if bucket < test + dev else "train"


def _prompt(key: str, uid: str, **values) -> str:
    options = PROMPTS[key]
    return options[_hash(uid) % len(options)].format(**values)


def _example(uid: str, task: str, split: str, user: str, answer: str, sources: list[str], **meta) -> dict:
    return {"id": uid, "task": task, "split": split,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user},
                         {"role": "assistant", "content": answer}],
            "source_ids": sources, **meta}


def _lemma_group(entry: dict) -> str:
    return "lem:" + normalize_td(entry["lemma"][LANG_TD])


def _forms_text(entry: dict) -> str:
    parts = [f"{f['label']} {f['form']}" for f in entry["forms"] if f["label"]]
    return f" ({', '.join(parts)})" if parts else ""


def misspell(word: str) -> list[str]:
    """Return the typical misspellings of a correct word (one per applicable rule, at most two)."""
    out = []
    for pattern, wrong in _MISSPELLINGS:
        bad = pattern.sub(wrong, word, count=1)
        if bad != word and bad not in out:
            out.append(bad)
    return out[:2]


def lexicon_examples(entries: list[dict], probe: float = 0.05) -> list[dict]:
    """Build the word-level examples (translation, definition, morphology, spelling)."""
    out = []
    probe_of = lambda uid: "probe" if _hash(f"probe:{uid}") % 10_000 < probe * 10_000 else "train"  # noqa: E731
    by_gloss: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for e in entries:
        if not e["quality"]["trainable"]:
            continue
        lemma, group = e["lemma"][LANG_TD], _lemma_group(e)
        senses = [s for s in e["senses"] if s["trainable"]]
        glosses = [g for s in senses for g in s["glosses_fr"]]
        uid = f"{e['id']}:ar-fr"
        out.append(_example(uid, "traduction_mot", probe_of(uid), _prompt("traduction_mot:ar-fr", uid, x=lemma),
                            ", ".join(dict.fromkeys(glosses)), [e["id"]], direction="ar-fr"))
        uid = f"{e['id']}:def"
        out.append(_example(uid, "definition", probe_of(uid), _prompt("definition", uid, x=lemma),
                            f"{e['pos']} {', '.join(dict.fromkeys(glosses))}{_forms_text(e)}".strip(), [e["id"]]))
        for g in dict.fromkeys(glosses):
            by_gloss[normalize_fr(g)].append((g, lemma, e["id"]))
        for x in e["expressions"]:
            uid = f"{x['id']}:ar-fr"
            out.append(_example(uid, "traduction_mot", probe_of(uid), _prompt("traduction_mot:ar-fr", uid, x=x["text"]),
                                x["gloss_fr"], [x["id"]], direction="ar-fr"))
        split = split_of(group)
        for f in e["forms"]:
            tag = next((TAG_NAMES[t] for t in f["tags"] if t in TAG_NAMES), None)
            if not tag:
                continue
            uid = f"{e['id']}:{f['label']}{f['form']}"
            name, with_article = tag
            out.append(_example(uid + ":flex", "flexion", split, _prompt("flexion", uid, x=lemma, tag=with_article),
                                f["form"], [e["id"]]))
            out.append(_example(uid + ":lem", "lemmatisation", split, _prompt("lemmatisation", uid, x=f["form"]),
                                f"{lemma} ({name} de {lemma})", [e["id"]]))
        for bad in misspell(lemma):
            uid = f"{e['id']}:orth:{bad}"
            out.append(_example(uid, "orthographe", split, _prompt("orthographe", uid, x=bad), lemma, [e["id"]]))
    for key, items in by_gloss.items():
        gloss = items[0][0]
        lemmas = list(dict.fromkeys(lemma for _, lemma, _ in items))
        uid = f"gloss:{key}:fr-ar"
        out.append(_example(uid, "traduction_mot", probe_of(uid), _prompt("traduction_mot:fr-ar", uid, x=gloss),
                            " / ".join(lemmas), list(dict.fromkeys(i for _, _, i in items)), direction="fr-ar"))
    return out


def sentence_examples(sentences: list[dict]) -> list[dict]:
    """Build the sentence translation examples (both directions, split by template)."""
    out = []
    for s in sentences:
        if not s["quality"]["trainable"]:
            continue
        split = split_of(s["group"], *SENTENCE_HOLDOUT)
        td, fr = s["text"][LANG_TD], s["text"][LANG_FR]
        for direction, x, y in (("fr-ar", fr, td), ("ar-fr", td, fr)):
            uid = f"{s['id']}:{direction}"
            out.append(_example(uid, "traduction_phrase", split, _prompt(f"traduction_phrase:{direction}", uid, x=x),
                                y, [s["id"]], direction=direction, domain=s["domain"]))
    return out


def mt_rows(entries: list[dict], sentences: list[dict]) -> list[dict]:
    """Parallel rows in the Hugging Face ``translation`` format (FLORES-style language codes)."""
    rows = []
    for e in entries:
        if e["quality"]["trainable"]:
            for s in e["senses"]:
                if s["trainable"]:
                    rows.append({"id": s["id"], "unit": "word", "split": "train", "domain": None,
                                 "translation": {LANG_FR: s["definition_fr"], LANG_TD: e["lemma"][LANG_TD]}})
    for s in sentences:
        if s["quality"]["trainable"]:
            rows.append({"id": s["id"], "unit": "sentence", "split": split_of(s["group"], *SENTENCE_HOLDOUT), "domain": s["domain"],
                         "translation": {LANG_FR: s["text"][LANG_FR], LANG_TD: s["text"][LANG_TD]}})
    return rows

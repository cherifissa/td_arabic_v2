"""Quality issues: the errors of the data, kept as data.

The lexicon extracted from the PDF has errors (two entries glued in one definition, words cut
at the end of a line, an entry filed under the wrong letter…). Instead of fixing them silently,
every problem becomes an **issue** stored in ``annotations/issues.jsonl``:

    {"id", "target", "field", "type", "severity", "evidence", "suggestion", "status", "detector"}

- ``severity``: ``error`` (the record must not be used for training), ``warning`` (usable, to
  review), ``info``;
- ``status``: ``open``, ``fixed`` (corrected automatically or by hand, ``suggestion`` applied).

Hand-made corrections (``corrections_entrees.csv``) are recorded as ``fixed`` issues, so the
whole history of the data can be audited. An export keeps a record unless it has an open
``error`` issue.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict

import pandas as pd

from td_arabic.dataset.records import LANG_FR, LANG_TD
from td_arabic.utils.text import normalize_fr, normalize_td

# Abréviations de catégorie à l'intérieur d'une définition : deux entrées fusionnées.
_POS_IN_DEF = re.compile(r"(?:^|\s)(n\.m\.|n\.f\.|v\.tr\.|v\.i\.|adj\.|adv\.|conj\.|prép\.|n\.pl\.|interj\.|expr\.)(?:\s|$)")
_CUT_WORD = re.compile(r"(\w)- (\w)")                     # « chauve- souris » (coupure de ligne)
# Lettres de l'alphabet du lexique, digraphes d'abord (préambule, p. iv).
_LETTERS = ("tch", "ch", "kh", "a", "b", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p",
            "r", "s", "t", "u", "w", "y", "z", "ʼ")
# Graphies françaises interdites par le préambule du lexique (p. iii) : écrire j, u, g.
SPELLING_RULES = [
    (re.compile(r"dj"), "j", "« dj » s'écrit « j » (jambah et non djambah)"),
    (re.compile(r"ou"), "u", "« ou » s'écrit « u » (guffa et non gouffa)"),
    (re.compile(r"gu(?=[ei])"), "g", "« gu » devant e/i s'écrit « g » (gelbi et non guelbi)"),
    (re.compile(r"[’'`]"), "ʼ", "la coupure de gorge s'écrit « ʼ »"),
]


def initial_letter(word: str) -> str:
    """Return the first letter of a word in the lexicon's alphabet (``ch``, ``kh``, ``tch`` count as one)."""
    w = normalize_td(word)
    return next((letter for letter in _LETTERS if w.startswith(letter)), w[:1])


def issue(target: str, field: str, type_: str, severity: str, evidence: str, detector: str,
          suggestion: str | None = None, status: str = "open", note: str | None = None) -> dict:
    """Build one issue with a stable id (same problem -> same id from one build to the next)."""
    key = f"{target}|{field}|{type_}|{evidence}"
    return {"id": "iss:" + hashlib.md5(key.encode("utf-8")).hexdigest()[:10], "target": target, "field": field,
            "type": type_, "severity": severity, "evidence": evidence, "suggestion": suggestion,
            "status": status, "detector": detector, "note": note}


def check_entries(entries: list[dict], fix: bool = True) -> list[dict]:
    """Detect the extraction errors of the lexical entries.

    Args:
        entries: Output of :func:`td_arabic.dataset.records.build_entries`; modified in place
            when ``fix`` is true (safe automatic fixes only: cut words, wrong section).
        fix: Apply the safe fixes and record them as ``fixed`` issues.

    Returns:
        The issues found.
    """
    found = []
    for e in entries:
        eid = e["id"]
        for s in e["senses"]:
            d = s["definition_fr"]
            m = _POS_IN_DEF.search(d)
            if m:
                found.append(issue(s["id"], "definition_fr", "merged_entries", "error", d, "auto:pos_in_definition",
                                   note=f"La définition contient « {m.group(1)} » : plusieurs entrées ou sens fusionnés."))
            if _CUT_WORD.search(d):
                fixed = _CUT_WORD.sub(r"\1-\2", d)
                found.append(issue(s["id"], "definition_fr", "line_break_hyphen", "warning", d, "auto:cut_word",
                                   suggestion=fixed, status="fixed" if fix else "open"))
                if fix:
                    s["definition_fr"] = fixed
                    s["glosses_fr"] = [_CUT_WORD.sub(r"\1-\2", g) for g in s["glosses_fr"]]
        if e["upos"] == "X" and e["pos"] != "expr.":
            found.append(issue(eid, "pos", "unknown_pos", "warning", e["pos"] or "(vide)", "auto:pos"))
        for f in e["forms"]:
            if not f["label"]:
                found.append(issue(eid, "forms", "unlabelled_form", "warning", f["form"], "auto:forms"))
        if e["quality"]["ligature_reconstructed"]:
            found.append(issue(eid, "definition_fr", "ligature_reconstructed", "info",
                               " | ".join(s["definition_fr"] for s in e["senses"]), "auto:pdf_extract",
                               note="Ligature (fi, ff, fl…) reconstruite à l'extraction : à vérifier sur le PDF."))
        section = e["provenance"]["section"]
        if section and e["provenance"]["origin"] == "pdf":
            expected = initial_letter(e["lemma"][LANG_TD])
            if section.split()[0].lower() != expected:
                right = next((s for s in _section_names(entries) if s.split()[0].lower() == expected), None)
                found.append(issue(eid, "provenance.section", "wrong_section", "info", section, "auto:section",
                                   suggestion=right, status="fixed" if fix and right else "open",
                                   note="Pages où deux lettres se suivent : l'ordre des colonnes a mêlé les sections."))
                if fix and right:
                    e["provenance"]["section"] = right
    return found


def _section_names(entries: list[dict]) -> list[str]:
    """Return the distinct section titles (``"A a"``, ``"Ch ch"``…)."""
    return sorted({e["provenance"]["section"] for e in entries if e["provenance"]["section"]})


def corrections_as_issues(corrections: pd.DataFrame, entries: list[dict]) -> list[dict]:
    """Record the hand-made corrections of ``corrections_entrees.csv`` as fixed issues."""
    ids = {(e["lemma"][LANG_TD], str(e["homograph"] or "")): e["id"] for e in entries}
    return [issue(ids.get((r.headword, str(r.sense_number or "")), f"td:{r.headword}") + "/s1", "definition_fr",
                  "merged_entries", "error", r.avant, "manuel:corrections_entrees", suggestion=r.apres,
                  status="fixed", note=r.note)
            for r in corrections.fillna("").itertuples(index=False)]


def spelling_issues(text: str, target: str, field: str) -> list[dict]:
    """Check a Chadian Arabic text against the spelling rules of the lexicon's preamble."""
    found = []
    for pattern, replacement, rule in SPELLING_RULES:
        if pattern.search(text):
            found.append(issue(target, field, "spelling", "warning", text, "auto:orthographe_sil",
                               suggestion=pattern.sub(replacement, text), note=rule))
    return found


def check_sentences(sentences: list[dict]) -> list[dict]:
    """Detect the problems of the sentence bank.

    - ``duplicate``: same pair (both sides) already seen -> ``error`` on the copy;
    - ``ambiguous_source``: one French sentence with several Chadian Arabic translations
      (gender, number…) -> ``info``, kept: both are correct but the model needs to know it;
    - ``unknown_lemma``: a lemma not found in the lexicon -> ``warning``;
    - ``spelling``: a forbidden spelling (dj, ou, gu+e/i, ' ) -> ``warning``.
    """
    found, seen = [], {}
    by_fr: dict[str, set[str]] = defaultdict(set)
    for s in sentences:
        td, fr = s["text"][LANG_TD], s["text"][LANG_FR]
        if not td or not fr:
            found.append(issue(s["id"], "text", "empty_side", "error", f"{fr} || {td}", "auto:empty"))
            continue
        key = (normalize_fr(fr), normalize_td(td))
        if key in seen:
            found.append(issue(s["id"], "text", "duplicate", "error", f"{fr} || {td}", "auto:duplicate",
                               note=f"Même paire que {seen[key]}."))
            continue
        seen[key] = s["id"]
        by_fr[key[0]].add(td)
        for link in s["lemmas"]:
            if not link["entries"]:
                found.append(issue(s["id"], "lemmas", "unknown_lemma", "warning", link["lemma"], "auto:lemmas"))
        found.extend(spelling_issues(td, s["id"], f"text.{LANG_TD}"))
    for s in sentences:
        variants = by_fr.get(normalize_fr(s["text"][LANG_FR]), set())
        if len(variants) > 1:
            found.append(issue(s["id"], f"text.{LANG_FR}", "ambiguous_source", "info", s["text"][LANG_FR],
                               "auto:ambiguity", note=f"{len(variants)} traductions : " + " / ".join(sorted(variants))))
    return found


def attach(records: list[dict], issues: list[dict]) -> None:
    """Copy the issue types onto their records (``quality.flags``) and set ``quality.trainable``.

    A record is trainable unless one of its open issues (on itself or one of its senses) is an
    ``error``. A sense with an open error is also marked ``trainable: false`` on its own.
    """
    by_target: dict[str, list[dict]] = defaultdict(list)
    for i in issues:
        by_target[i["target"]].append(i)
    for r in records:
        own = list(by_target.get(r["id"], []))
        for s in r.get("senses", []):
            s_issues = by_target.get(s["id"], [])
            s["trainable"] = not any(i["severity"] == "error" and i["status"] == "open" for i in s_issues)
            own += s_issues
        r["quality"]["flags"] = sorted({i["type"] for i in own})
        blocking = any(i["severity"] == "error" and i["status"] == "open" for i in by_target.get(r["id"], []))
        if "senses" in r:
            blocking = blocking or not any(s["trainable"] for s in r["senses"])
        r["quality"]["trainable"] = not blocking and r["quality"]["status"] not in ("draft", "rejected")

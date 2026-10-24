"""Tests of the training dataset: records, quality issues, task examples and splits."""

import pandas as pd

from td_arabic.dataset import build, quality, records, tasks

LEXICON = [
    # headword, sense_number, forms, pos, definition, type, parent_headword, section
    ("abad", "1", "inacc. yaʼabud / impr. aʼabud", "v.tr.", "adorer Dieu", "entry", "", "A a"),
    ("abad", "2", "", "n.m.", "pour toujours", "entry", "", "A a"),
    ("ila l-abad", "2", "expr.", "n.m.", "pour toujours", "expression", "abad", "A a"),
    ("abyad", "", "f. beeda / pl. buyud", "adj.", "blanc", "entry", "", "A a"),
    ("abunrigeeʼ", "", "", "n.m.", "chauve- souris", "entry", "", "A a"),
    ("durr", "", "", "n.m.", "mal fait délibérément", "entry", "", "D d"),
    ("duwaane", "", "pl. dawaayin", "n.f.", "canari", "entry", "", "F f"),     # rangé sous F dans le PDF
    ("malika", "", "pl. malikaat", "n.f.", "reine malika al-umm n.f. reine mère", "entry", "", "M m"),
    ("chahad", "", "inacc. yachhad", "v.tr.", "témoigner", "entry", "", "Ch ch"),
    ("chihid", "", "inacc. yachhad", "v.tr.", "témoigner", "entry", "", "Ch ch"),
    ("jambah", "", "", "prép.", "à côté de lui", "entry", "", "J j"),
    ("abyad", "", "", "adj.", "pur", "ajout", "", ""),
]


def _lexicon(tmp_path):
    rows = [dict(zip(["headword", "sense_number", "forms", "pos", "definition", "type", "parent_headword",
                      "section"], r), expression_number="", page="15", column="left", ligature_reconstructed="False")
            for r in LEXICON]
    path = tmp_path / "lexique_final.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _bank(tmp_path):
    base = {"theme": "marche", "hors_lexique": "", "source": "gabarit", "cree_le": "", "modifie_le": ""}
    rows = [{**base, "id": "mar-1", "template_id": "mar-a", "fr": "C'est blanc.", "td": "Hu abyad.",
             "lemmes": "abyad", "statut": "validee"},
            {**base, "id": "mar-2", "template_id": "mar-b", "fr": "C'est blanc.", "td": "Hi beeda.",
             "lemmes": "abyad", "statut": "validee"},
            {**base, "id": "mar-3", "template_id": "mar-b", "fr": "C'est blanc.", "td": "Hu abyad.",
             "lemmes": "abyad", "statut": "validee"},
            {**base, "id": "mar-4", "template_id": "mar-c", "fr": "Brouillon.", "td": "Brouillon.",
             "lemmes": "kalib", "statut": "brouillon"}]
    path = tmp_path / "phrases.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _data(tmp_path):
    return build.build(_lexicon(tmp_path), _bank(tmp_path), tmp_path / "absent.csv")


def test_entries_are_trees_with_homographs_forms_expressions_and_additions(tmp_path):
    entries = {e["id"]: e for e in _data(tmp_path)["entries"]}
    assert {"td:abad#1", "td:abad#2", "td:abyad"} <= entries.keys()
    assert entries["td:abad#2"]["expressions"][0]["text"] == "ila l-abad"
    assert entries["td:abad#1"]["forms"][0] == {"form": "yaʼabud", "tags": ["imperfective", "third-person",
                                                                            "singular", "masculine"], "label": "inacc."}
    abyad = entries["td:abyad"]
    assert [s["definition_fr"] for s in abyad["senses"]] == ["blanc", "pur"]      # l'ajout devient un 2e sens
    assert abyad["senses"][1]["origin"] == "ajout" and abyad["upos"] == "ADJ"


def test_glosses_split_on_commas_outside_parentheses():
    assert records.split_glosses("se disperser, se répandre") == ["se disperser", "se répandre"]
    assert records.split_glosses("mettre (un os, une dent)") == ["mettre (un os, une dent)"]


def test_extraction_errors_become_issues_and_safe_ones_are_fixed(tmp_path):
    data = _data(tmp_path)
    entries = {e["id"]: e for e in data["entries"]}
    by_type = {}
    for i in data["issues"]:
        by_type.setdefault(i["type"], []).append(i)
    assert entries["td:abunrigeeʼ"]["senses"][0]["definition_fr"] == "chauve-souris"
    assert by_type["line_break_hyphen"][0]["status"] == "fixed"
    assert entries["td:duwaane"]["provenance"]["section"] == "D d"
    assert by_type["wrong_section"][0]["evidence"] == "F f" and by_type["wrong_section"][0]["status"] == "fixed"
    merged = by_type["merged_entries"][0]
    assert merged["target"] == "td:malika/s1" and merged["severity"] == "error" and merged["status"] == "open"
    assert not entries["td:malika"]["quality"]["trainable"]           # erreur ouverte -> exclue
    assert entries["td:abyad"]["quality"]["trainable"]


def test_sentence_issues_duplicates_ambiguity_and_drafts(tmp_path):
    data = _data(tmp_path)
    sentences = {s["id"]: s for s in data["sentences"]}
    types = {(i["target"], i["type"]) for i in data["issues"]}
    assert ("phr:mar-3", "duplicate") in types and not sentences["phr:mar-3"]["quality"]["trainable"]
    assert ("phr:mar-1", "ambiguous_source") in types and sentences["phr:mar-1"]["quality"]["trainable"]
    assert ("phr:mar-4", "unknown_lemma") in types
    assert not sentences["phr:mar-4"]["quality"]["trainable"]          # brouillon : jamais entraîné
    assert sentences["phr:mar-1"]["lemmas"] == [{"lemma": "abyad", "entries": ["td:abyad"]}]


def test_french_to_arabic_lists_every_word_of_a_shared_gloss(tmp_path):
    sft = {x["id"]: x for x in _data(tmp_path)["sft"]}
    assert sft["gloss:témoigner:fr-ar"]["messages"][2]["content"] == "chahad / chihid"


def test_tasks_and_spelling_rules(tmp_path):
    sft = _data(tmp_path)["sft"]
    tasks_found = {x["task"] for x in sft}
    assert tasks_found == {"traduction_mot", "definition", "flexion", "lemmatisation", "orthographe",
                           "traduction_phrase"}
    lem = next(x for x in sft if x["task"] == "lemmatisation" and "buyud" in x["messages"][1]["content"])
    assert lem["messages"][2]["content"] == "abyad (pluriel de abyad)"
    assert "djambah" in tasks.misspell("jambah")
    assert tasks.misspell("juu") == ["djuu", "ju"]                      # pas de « juou »
    assert all(x["messages"][0]["content"] == tasks.SYSTEM_PROMPT for x in sft)
    assert quality.spelling_issues("akou", "td:akou", "lemma")[0]["suggestion"] == "aku"


def test_splits_are_stable_and_keep_a_lemma_on_one_side(tmp_path):
    assert tasks.split_of("lem:abyad") == tasks.split_of("lem:abyad")
    sft = _data(tmp_path)["sft"]
    for task in ("flexion", "lemmatisation", "orthographe"):
        sides = {}
        for x in sft:
            if x["task"] == task:
                sides.setdefault(x["source_ids"][0], set()).add(x["split"])
        assert all(len(s) == 1 for s in sides.values())
    assert {x["split"] for x in sft if x["task"] in ("traduction_mot", "definition")} <= {"train", "probe"}


def test_initial_letter_uses_the_lexicon_alphabet():
    assert quality.initial_letter("tchiki") == "tch" and quality.initial_letter("khalla") == "kh"
    assert quality.initial_letter("chahad") == "ch" and quality.initial_letter("abad") == "a"

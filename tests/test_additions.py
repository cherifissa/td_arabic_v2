"""Tests of hand-made corpus additions and their merge into the lexicon."""

import pandas as pd
import pytest

from td_arabic.lexicon.corpus import LEXICON_COLUMNS, apply_additions, build_bilingual, build_corpus
from td_arabic.translation.additions import (AdditionError, add_addition, clean_french, load_additions,
                                             update_addition, validated_additions)
from td_arabic.translation.lexicon import Lexicon


def _row(src, output, pos="n.m."):
    return {"src": src, "pos": pos, "output": output, "forms": "", "sense_number": ""}


def _lexicon():
    return Lexicon([_row("derib", "chemin"), _row("tariig", "chemin"),
                    _row("achchattat", "se disperser, se répandre", "v.i."), _row("daafi", "chaud", "adj.")])


def test_clean_french_keeps_comma_separated_senses():
    assert clean_french("  route ,voie;  piste ") == "route, voie, piste"
    assert clean_french(" , ") == ""


def test_new_sense_of_known_word_is_saved_and_reported(tmp_path):
    path = tmp_path / "ajouts.csv"
    saved = add_addition("derib", "route, voie", "n.m.", lexicon=_lexicon(), path=path)
    assert saved["is_new_word"] is False and saved["warnings"] == []
    rows = load_additions(path)
    assert list(rows["src"]) == ["derib"] and list(rows["output"]) == ["route, voie"]
    assert rows.iloc[0]["added_on"]


def test_new_word_with_unknown_opposite_warns_and_normalises_glottal(tmp_path):
    saved = add_addition("bardaaʾn", "froid", "adj.", opposite_td="daafi", lexicon=_lexicon(), path=tmp_path / "a.csv")
    assert saved["src"] == "bardaaʼn" and saved["is_new_word"] is True and saved["warnings"] == []
    saved = add_addition("taʼbaan", "fatigué", opposite_td="mustariih", lexicon=_lexicon(), path=tmp_path / "a.csv")
    assert len(saved["warnings"]) == 1 and "mustariih" in saved["warnings"][0]


def test_duplicate_sense_is_refused_in_lexicon_and_in_additions(tmp_path):
    path = tmp_path / "ajouts.csv"
    with pytest.raises(AdditionError):
        add_addition("achchattat", "se répandre", lexicon=_lexicon(), path=path)  # déjà un sens du lexique
    add_addition("derib", "route", lexicon=_lexicon(), path=path)
    with pytest.raises(AdditionError):
        add_addition("derib", "route", lexicon=_lexicon(), path=path)             # déjà ajouté
    with pytest.raises(AdditionError):
        add_addition("", "route", lexicon=_lexicon(), path=path)
    assert len(load_additions(path)) == 1


def test_apply_additions_places_rows_after_their_word_and_feeds_the_corpus():
    lexicon = pd.DataFrame([
        {**{c: "" for c in LEXICON_COLUMNS}, "headword": h, "definition": d, "pos": "n.m.", "type": "entry"}
        for h, d in [("aab", "avoir honte"), ("derib", "chemin"), ("tariig", "chemin")]])
    additions = pd.DataFrame([{"src": "derib", "pos": "n.m.", "output": "route", "forms": ""},
                              {"src": "nouveau", "pos": "adj.", "output": "neuf", "forms": ""}])
    merged = apply_additions(lexicon, additions)
    assert list(merged["headword"]) == ["aab", "derib", "derib", "tariig", "nouveau"]
    assert list(merged["type"]) == ["entry", "entry", "ajout", "entry", "ajout"]
    corpus = build_corpus(merged)
    assert ("derib", "route") in set(zip(corpus["src"], corpus["output"]))
    assert len(build_bilingual(corpus)) == 2 * len(corpus)
    assert Lexicon(corpus.to_dict("records")).lookup("route", "fr-ar").translations[0].output == "derib"


# --- proposals: what is typed is never taken as correct ----------------------------------------

def test_new_additions_are_proposals_and_keep_what_was_typed(tmp_path):
    path = tmp_path / "a.csv"
    saved = add_addition("itneen", "lundi", "n.m.", lexicon=_lexicon(), path=path, typed="it'neen")
    assert saved["statut"] == "propose" and saved["src_saisi"] == "it'neen"
    assert len(validated_additions(path)) == 0                      # rien n'entre dans le corpus
    assert list(load_additions(path)["statut"]) == ["propose"]
    with pytest.raises(AdditionError):
        add_addition("x", "y", lexicon=_lexicon(), path=path, statut="ok")


def test_review_corrects_the_spelling_then_validates(tmp_path):
    path = tmp_path / "a.csv"
    row = add_addition("talata", "mardi", "n.m.", lexicon=_lexicon(), path=path)
    corrected = update_addition(row["id"], src="talaata", lexicon=_lexicon(), path=path)
    assert corrected["src"] == "talaata" and corrected["src_saisi"] == "talata"   # la saisie reste tracée
    assert len(validated_additions(path)) == 0
    update_addition(row["id"], statut="valide", lexicon=_lexicon(), path=path)
    merged = validated_additions(path)
    assert list(merged["src"]) == ["talaata"] and list(merged["output"]) == ["mardi"]
    update_addition(row["id"], statut="rejete", lexicon=_lexicon(), path=path)
    assert len(validated_additions(path)) == 0                                    # rejetée : jamais fusionnée


def test_review_normalises_glottal_and_refuses_bad_input(tmp_path):
    path = tmp_path / "a.csv"
    row = add_addition("arba'a", "mercredi", lexicon=_lexicon(), path=path)
    assert row["src"] == "arbaʼa"
    assert update_addition(row["id"], src="arba'a", lexicon=_lexicon(), path=path)["src"] == "arbaʼa"
    with pytest.raises(AdditionError):
        update_addition(row["id"], statut="inconnu", lexicon=_lexicon(), path=path)
    with pytest.raises(AdditionError):
        update_addition(row["id"], src="", lexicon=_lexicon(), path=path)
    with pytest.raises(AdditionError):
        update_addition(row["id"], id="x", lexicon=_lexicon(), path=path)         # champ non modifiable
    with pytest.raises(KeyError):
        update_addition("introuvable", note="x", lexicon=_lexicon(), path=path)


def test_editing_a_validated_row_is_not_refused_as_duplicate(tmp_path):
    path = tmp_path / "a.csv"
    row = add_addition("derib", "route", "n.m.", lexicon=_lexicon(), path=path)
    update_addition(row["id"], statut="valide", lexicon=_lexicon(), path=path)
    merged = Lexicon([_row("derib", "chemin"), _row("derib", "route")])           # le corpus reconstruit la contient
    update_addition(row["id"], note="confirmé par un locuteur", lexicon=merged, path=path)
    assert load_additions(path).iloc[0]["note"] == "confirmé par un locuteur"


def test_proposal_blocks_the_same_sense_proposed_twice(tmp_path):
    path = tmp_path / "a.csv"
    add_addition("derib", "route", lexicon=_lexicon(), path=path)
    with pytest.raises(AdditionError):
        add_addition("derib", "route", lexicon=_lexicon(), path=path)


def test_file_written_before_proposals_counts_as_validated(tmp_path):
    path = tmp_path / "a.csv"
    path.write_text("src,pos,output,forms,opposite_td,note,added_on\nderib,n.m.,route,,,,2026-01-01\n", encoding="utf-8")
    assert list(validated_additions(path)["output"]) == ["route"]


# --- proposals typed straight into the coverage table ------------------------------------------

def test_table_rows_become_proposals_one_per_arabic_word(tmp_path):
    from td_arabic.translation.additions import propose_from_rows
    path = tmp_path / "a.csv"
    rows = [{"mot": "route", "categorie": "n", "arabe": "derib; tariig", "francais": "", "pos_choisi": ""},
            {"mot": "tard", "categorie": "adv", "arabe": "", "francais": "tard"},                  # vide : ignorée
            {"mot": "froid", "categorie": "adj", "arabe": "bardaan", "francais": "froid, glacial",
             "pos_choisi": "", "opposite": "daafi", "note": "entendu au marché"}]
    saved, errors = propose_from_rows(rows, lexicon=_lexicon(), path=path)
    assert errors == [] and [s["src"] for s in saved] == ["derib", "tariig", "bardaan"]
    table = load_additions(path)
    assert list(table["statut"]) == ["propose"] * 3                                    # jamais validées d'office
    assert list(table["output"]) == ["route", "route", "froid, glacial"]               # français par défaut = le mot
    assert list(table["pos"]) == ["n.m.", "n.m.", "adj."]                              # pos du mot connu, sinon de la liste
    assert table.iloc[2]["opposite_td"] == "daafi" and table.iloc[2]["note"] == "entendu au marché"
    assert len(validated_additions(path)) == 0


def test_table_rows_report_refused_proposals_but_keep_the_others(tmp_path):
    from td_arabic.translation.additions import propose_from_rows
    rows = [{"mot": "chaud", "categorie": "adj", "arabe": "daafi", "francais": "chaud"},      # déjà un sens du lexique
            {"mot": "route", "categorie": "n", "arabe": "derib", "francais": "route"}]
    saved, errors = propose_from_rows(rows, lexicon=_lexicon(), path=tmp_path / "a.csv")
    assert [s["src"] for s in saved] == ["derib"]
    assert len(errors) == 1 and "daafi" in errors[0] and "chaud" in errors[0]


def test_table_row_typed_with_apostrophe_is_normalised_and_traced(tmp_path):
    from td_arabic.translation.additions import propose_from_rows
    saved, _ = propose_from_rows([{"mot": "mercredi", "categorie": "n", "arabe": "arba'a", "francais": "mercredi"}],
                                 lexicon=_lexicon(), path=tmp_path / "a.csv")
    assert saved[0]["src"] == "arbaʼa" and saved[0]["src_saisi"] == "arba'a"


def test_french_word_gives_only_the_broad_category(tmp_path):
    from td_arabic.translation.additions import GENERIC_POS, POS_FROM_CATEGORY, propose_from_rows
    # le genre d'un nom et la transitivité d'un verbe dépendent du mot ARABE : on ne les devine pas
    assert POS_FROM_CATEGORY["n"] == "n." and POS_FROM_CATEGORY["v"] == "v." and POS_FROM_CATEGORY["adj"] == "adj."
    rows = [{"mot": "cousin", "categorie": "n", "arabe": "ibn amm"}, {"mot": "courir", "categorie": "v", "arabe": "jara"}]
    saved, _ = propose_from_rows(rows, lexicon=_lexicon(), path=tmp_path / "a.csv")
    assert [s["pos"] for s in saved] == ["n.", "v."] and set(GENERIC_POS) >= {"n.", "v.", ""}


def test_a_proposal_cannot_be_validated_with_a_generic_category(tmp_path):
    from td_arabic.translation.additions import propose_from_rows
    path = tmp_path / "a.csv"
    saved, _ = propose_from_rows([{"mot": "cousin", "categorie": "n", "arabe": "ibn amm"}], lexicon=_lexicon(), path=path)
    with pytest.raises(AdditionError, match="Précisez la catégorie"):
        update_addition(saved[0]["id"], statut="valide", lexicon=_lexicon(), path=path)
    assert len(validated_additions(path)) == 0
    update_addition(saved[0]["id"], pos="n.m.", statut="valide", lexicon=_lexicon(), path=path)   # catégorie précisée : OK
    assert list(validated_additions(path)["pos"]) == ["n.m."]
    with pytest.raises(AdditionError):
        add_addition("x", "y", "", lexicon=_lexicon(), path=tmp_path / "b.csv", statut="valide")


def test_forms_are_written_in_the_lexicon_format():
    from td_arabic.translation.additions import normalize_forms
    assert normalize_forms("f jaara, pl jiiraan") == "f. jaara / pl. jiiraan"
    assert normalize_forms("f. jaara / pl. jiiraan / f.pl. jaaraat") == "f. jaara / pl. jiiraan / f.pl. jaaraat"
    assert normalize_forms("fpl jaaraat; mpl jiiraan ; dl ruuseen") == "f.pl. jaaraat / m.pl. jiiraan / dl. ruuseen"
    assert normalize_forms("pl. ta'aamiir") == "pl. taʼaamiir"                    # coupure de gorge du cours
    assert normalize_forms("  ") == ""
    with pytest.raises(AdditionError, match="sans étiquette"):
        normalize_forms("jiiraan")
    with pytest.raises(AdditionError, match="inconnue"):
        normalize_forms("pluriel jiiraan")


def test_forms_typed_in_the_table_are_saved_and_readable_by_the_lexicon(tmp_path):
    from td_arabic.translation.additions import propose_from_rows
    from td_arabic.translation.lexicon import parse_forms
    saved, errors = propose_from_rows(
        [{"mot": "cousin", "categorie": "n", "arabe": "wileed imm", "forms": "pl awlaad imm"},
         {"mot": "voisin", "categorie": "n", "arabe": "jaarr", "forms": "pluriel jiiraan"}],      # étiquette inconnue
        lexicon=_lexicon(), path=tmp_path / "a.csv")
    assert saved[0]["forms"] == "pl. awlaad imm" and parse_forms(saved[0]["forms"]) == [("pl.", "awlaad imm")]
    assert len(errors) == 1 and "pluriel" in errors[0]


# --- spelling checks on proposals ---------------------------------------------------------------

def test_spelling_rules_of_the_course():
    from td_arabic.translation.additions import spelling_warnings
    lex = _lexicon()
    assert any("ou" in w for w in spelling_warnings("akou", lex))
    assert any("dj" in w for w in spelling_warnings("djadiid", lex))
    assert any("gue" in w for w in spelling_warnings("guelbi", lex))
    assert spelling_warnings("gelbi", lex) == [] and spelling_warnings("jadiid", lex) == []


def test_close_word_with_the_same_meaning_is_flagged():
    from td_arabic.translation.additions import spelling_warnings
    lex = Lexicon([_row("jidd", "grand-père"), _row("idd", "point d’eau"), _row("akhu", "frère"),
                   _row("wileed imme", "cousin (fils de la tante paternelle)")])
    assert "vouliez-vous écrire jidd" in spelling_warnings("idd", lex, "grand-père")[0]   # idd existe, autre sens
    assert "akhu" in spelling_warnings("akou", lex, "frère")[-1]
    assert spelling_warnings("abu", lex, "grand-père") == []                           # trop différent : pas d'alerte
    # deux cousins différents (précision entre parenthèses) ne sont pas confondus
    assert spelling_warnings("wileed imm", lex, "cousin (fils de l'oncle paternel)") == []


def test_proposal_returns_the_spelling_warnings(tmp_path):
    lex = Lexicon([_row("ahal", "famille")])
    saved = add_addition("ahah", "famille", "n.m.", lexicon=lex, path=tmp_path / "a.csv")
    assert any("ahal" in w for w in saved["warnings"])


def test_forms_with_several_arabic_words_are_refused(tmp_path):
    from td_arabic.translation.additions import propose_from_rows
    lex = Lexicon([_row("abu", "père", "pl. abbahaat"), _row("waalid", "père", "dl. waaldeen")])
    saved, errors = propose_from_rows(
        [{"mot": "père", "categorie": "n", "arabe": "abba, abu, waalid", "forms": "pl. abbahaat / dl. waaldeen"}],
        lexicon=lex, path=tmp_path / "a.csv")
    assert saved == [] and len(errors) == 1 and "un seul mot" in errors[0]
    # sans formes, plusieurs mots restent possibles (et les doublons sont refusés un par un)
    saved, errors = propose_from_rows([{"mot": "père", "categorie": "n", "arabe": "abba, abu, waalid"}],
                                      lexicon=lex, path=tmp_path / "a.csv")
    assert [s["src"] for s in saved] == ["abba"] and len(errors) == 2 and all("déjà ce sens" in e for e in errors)

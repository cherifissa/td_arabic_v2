"""Tests of corpus construction, word lookup and sentence gloss."""

from td_arabic.lexicon.corpus import build_bilingual, build_corpus, build_lexicon
from td_arabic.translation.french import lemma_candidates
from td_arabic.translation.lexicon import Lexicon, french_keys, get_lexicon, parse_forms
from td_arabic.translation.sentence import guess_direction, translate_sentence


def _entry(headword, definition, sense=None, forms=(), pos="n.m."):
    return {"headword_base": headword, "sense_number": sense, "pos": pos, "definition": definition,
            "forms": [{"label": l, "value": v} for l, v in forms], "section": "A a",
            "page": 15, "column": "left", "ligature_reconstructed": False}


def test_build_lexicon_splits_manual_expressions_after_parent():
    entries = [_entry("abad", "adorer Dieu", 1, [("inacc.", "yaʼabud")], "v.tr."),
               _entry("abad", "pour toujours ila l-abad expr. pour toujours", 2),
               _entry("aks", "contraire be l-aks expr. au contraire")]
    manual = {("abad", "2"): {"main": "pour toujours", "expressions": [("ila l-abad", "pour toujours")]}}
    lexicon, review = build_lexicon(entries, manual)
    assert list(lexicon["headword"]) == ["abad", "abad", "ila l-abad", "aks"]
    assert list(lexicon["type"]) == ["entry", "entry", "expression", "entry"]
    assert lexicon.iloc[1]["definition"] == "pour toujours"
    assert lexicon.iloc[2]["forms"] == "expr." and lexicon.iloc[2]["parent_headword"] == "abad"
    assert list(review["headword"]) == ["aks"]  # pas de découpage manuel -> à vérifier

    corpus = build_corpus(lexicon)
    assert list(corpus.columns) == ["src", "pos", "output", "forms", "sense_number"]
    bilingual = build_bilingual(corpus)
    assert len(bilingual) == 2 * len(corpus)
    assert set(bilingual["direction"]) == {"ar-fr", "fr-ar"}


def test_french_keys_and_forms():
    assert french_keys("cher, coûteux") == ["cher, coûteux", "cher", "coûteux"]
    assert french_keys("toi (masc)") == ["toi (masc)", "toi"]
    assert parse_forms("inacc. yidawwir / inacc. yidoor") == [("inacc.", "yidawwir"), ("inacc.", "yidoor")]


def test_lookup_statuses():
    lex = Lexicon([
        {"src": "chara", "pos": "v.tr.", "output": "acheter", "forms": "inacc. yachri", "sense_number": ""},
        {"src": "suug", "pos": "n.m.", "output": "marché", "forms": "pl. aswaag", "sense_number": ""},
    ])
    assert lex.lookup("suug").status == "exact_match"
    assert lex.lookup("al-suug").word == "suug"
    hit = lex.lookup("nachri")
    assert hit.status == "form_match" and hit.translations[0].output == "acheter"
    assert "1re pers." in hit.translations[0].note
    assert lex.lookup("aswaag").translations[0].note == "pluriel de suug"
    assert lex.lookup("marché", "fr-ar").translations[0].output == "suug"
    assert lex.lookup("suuk").status == "no_exact_match"
    assert lex.lookup("zzzzzzzz").status == "no_match"


def test_real_corpus_homographs_are_reachable():
    lex = get_lexicon()
    assert len(lex) > 4000
    outputs = {t.output for t in lex.lookup("abad").translations}
    assert {"adorer Dieu", "pour toujours"} <= outputs
    # ancien bug : « hatta » sens 2 n'était accessible que via « hattaʾ »
    assert len(lex.lookup("hatta").translations) >= 2


def test_french_lemmatizer():
    assert "aller" in lemma_candidates("vais")
    assert "acheter" in lemma_candidates("achète")
    assert "froid" in lemma_candidates("froide")


def test_sentence_gloss_both_directions():
    fr = translate_sentence("Je vais acheter de la viande au marché", "fr-ar")
    assert fr.gloss == "Ana macha chara laham suug" and fr.coverage == 1.0
    ar = translate_sentence("Ana nachri laham fi l-suug", "ar-fr")
    assert [s.match for s in ar.segments] == ["exact", "forme", "exact", "exact", "exact"]
    assert translate_sentence("Elle mange xyzzyq", "fr-ar").segments[-1].match == "inconnu"
    assert guess_direction("Ana nachri laham") == "ar-fr"
    assert guess_direction("Elle achète du lait") == "fr-ar"


def test_entry_corrections_fix_a_wrongly_extracted_definition(caplog):
    from td_arabic.lexicon.corpus import build_lexicon, load_entry_corrections
    entries = [_entry("ambaakir", "demain ambaakirtah adv. le lendemain", pos="adv."),
               _entry("abad", "adorer Dieu", 1, pos="v.tr.")]
    fixes = {("ambaakir", ""): {"avant": "demain ambaakirtah adv. le lendemain", "apres": "demain"}}
    lexicon, _ = build_lexicon(entries, {}, fixes)
    assert list(lexicon["definition"]) == ["demain", "adorer Dieu"]
    # si l'extraction change, la correction n'est plus appliquée (et on le signale)
    stale = {("abad", "1"): {"avant": "ancien texte", "apres": "autre"}}
    with caplog.at_level("WARNING"):
        lexicon, _ = build_lexicon(entries, {}, stale)
    assert lexicon.iloc[1]["definition"] == "adorer Dieu" and "correction ignorée" in caplog.text
    assert load_entry_corrections()[("ambaakir", "")]["apres"] == "demain"           # le fichier fourni


def test_processed_csv_files_are_well_formed():
    """Les sorties du pipeline ne doivent jamais être modifiées à la main (virgule non protégée = colonne en trop)."""
    import csv
    from td_arabic.config import PATHS
    for path in (PATHS.corpus_csv, PATHS.corpus_bilingual_csv, PATHS.lexicon_final_csv):
        rows = list(csv.reader(path.open(encoding="utf-8")))
        bad = [i + 1 for i, row in enumerate(rows) if len(row) != len(rows[0])]
        assert not bad, f"{path.name} : lignes mal formées {bad[:5]}"

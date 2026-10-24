"""Tests of text normalisation and PDF word/entry parsing."""

from td_arabic.lexicon.pdf_extract import clean_word, parse_entry, repair_ligatures
from td_arabic.utils.text import (
    GLOTTAL, normalize_td, strip_article, tidy_punctuation, tokenize_fr, tokenize_td,
)

BOLD = "GXQVTB+CharisSIL,Bold"
ROMAN = "ABCDEF+TimesNewRoman"
ARABIC = "FUZMGM+ScheherazadeNew"


def w(text, font=BOLD, size=11.04, x0=43.0, top=100.0):
    return {"text": text, "fontname": font, "size": size, "x0": x0, "top": top}


def test_glottal_variants_are_unified():
    assert normalize_td("Ga'ad") == f"ga{GLOTTAL}ad"
    assert normalize_td("ga’ad") == normalize_td("gaʾad") == f"ga{GLOTTAL}ad"


def test_tokenizers():
    assert tokenize_fr("L'eau d'aujourd'hui") == ["l'", "eau", "d'", "aujourd'hui"]
    assert tokenize_td("Fi l-khariif, al-matar!") == ["fi", "l-khariif", "al-matar"]
    assert strip_article("al-suug") == "suug" and strip_article("l-suug") == "suug"


def test_tidy_punctuation_depends_on_language():
    assert tidy_punctuation("Tu vas bien?") == "Tu vas bien ?"
    assert tidy_punctuation("Inta aafe ?", "td") == "Inta aafe?"


def test_ligatures_are_repaired():
    assert repair_ligatures("abdal(cid:19)teen") == ("abdalfiteen", True)
    assert repair_ligatures("kha)a", BOLD) == ("khafla", True)
    assert repair_ligatures("rose (couleur)", ROMAN) == ("rose (couleur)", False)


def test_clean_word_drops_arabic_script():
    assert clean_word(w("(cid:22)", ARABIC)) is None
    assert clean_word(w("/", ARABIC))["text"] == "/"
    assert clean_word(w("kha)aan"))["ligature_reconstructed"] is True


def test_parse_entry_with_homograph_forms_and_pos():
    tokens = [w("abad"), w("1", size=7.0), w("inacc.", ROMAN, 9.96), w("yaʼabud", size=9.96),
              w("/", ARABIC), w("impr.", ROMAN, 9.96), w("aʼabud", size=9.96),
              w("v.tr.", ROMAN, 9.96), w("adorer", ROMAN), w("Dieu", ROMAN)]
    entry = parse_entry({"tokens": tokens, "page": 15, "column": "left", "section": "A a"})
    assert entry["headword"] == "abad1" and entry["headword_base"] == "abad"
    assert entry["sense_number"] == 1
    assert entry["forms"] == [{"label": "inacc.", "value": "yaʼabud"},
                              {"label": "impr.", "value": "aʼabud"}]
    assert entry["pos"] == "v.tr." and entry["definition"] == "adorer Dieu"


def test_load_env_reads_dotenv_without_overwriting(tmp_path, monkeypatch):
    import os
    from td_arabic.utils.env import load_env
    env = tmp_path / ".env"
    env.write_text("# commentaire\nHF_TOKEN=\"hf_test\"\nexport API_KEY=deja\nVIDE\n\nAUTRE='x=y'\n", encoding="utf-8")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("AUTRE", raising=False)
    monkeypatch.setenv("API_KEY", "existante")
    assert sorted(load_env(env)) == ["AUTRE", "HF_TOKEN"]
    assert os.environ["HF_TOKEN"] == "hf_test" and os.environ["AUTRE"] == "x=y"
    assert os.environ["API_KEY"] == "existante"                       # l'environnement l'emporte
    assert load_env(tmp_path / "absent") == []

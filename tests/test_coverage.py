"""Tests of the French-word coverage report."""

import pandas as pd

from td_arabic.translation.coverage import (STATUSES, build_report, load_wordlist, summarize,
                                            wordlist_from_text)
from td_arabic.translation.lexicon import Lexicon


def _row(src, output, forms="", pos="n.m."):
    return {"src": src, "pos": pos, "output": output, "forms": forms, "sense_number": ""}


def _lexicon():
    return Lexicon([
        _row("derib", "chemin"), _row("tariig", "chemin"),
        _row("rabbaat al-duruub", "coupeur de route", "expr."),
        _row("zaad", "provisions de route"),
        _row("daafi", "chaud"),
        _row("matar", "pluie"),
        _row("hamsa", "pain de sucre", "expr."),
    ])


def _words(*rows):
    return pd.DataFrame(rows, columns=["mot", "categorie", "theme", "synonymes", "antonymes"])


def _status(report, word):
    return report.set_index("mot").loc[word, "statut"]


def test_direct_synonym_antonym_mention_and_absent():
    words = _words(
        ("chemin", "n", "lieux", "", ""),
        ("route", "n", "lieux", "chemin;sentier", ""),       # synonyme présent -> piste
        ("froid", "adj", "qualites", "glacial", "chaud"),     # antonyme présent -> indice
        ("sucre", "n", "nourriture", "", ""),                 # seulement dans une expression
        ("lune", "n", "nature", "", ""),                      # rien
    )
    report = build_report(words, _lexicon())
    assert _status(report, "chemin") == "couvert"
    assert _status(report, "route") == "synonyme"
    assert _status(report, "froid") == "antonyme"
    assert _status(report, "sucre") == "mentionne"
    assert _status(report, "lune") == "absent"


def test_synonym_report_names_the_arabic_entries():
    report = build_report(_words(("route", "n", "lieux", "chemin", "")), _lexicon()).set_index("mot")
    assert report.loc["route", "via_synonymes"] == "chemin → derib, tariig"
    assert report.loc["route", "traductions"] == ""
    # « route » n'apparaît que dans des définitions : montré, mais ne compte pas comme couvert
    assert "coupeur de route" in report.loc["route", "mentions"]


def test_expression_only_gloss_is_not_coverage():
    report = build_report(_words(("coupeur de route", "n", "", "", "")), _lexicon()).set_index("mot")
    assert report.loc["coupeur de route", "statut"] == "mentionne"
    assert "[expr.]" in report.loc["coupeur de route", "mentions"]


def test_whole_word_match_only():
    # « chemin » ne doit pas être trouvé dans « cheminée » ni « pluie » dans « pluvieux »
    lex = Lexicon([_row("x", "cheminée"), _row("y", "pluvieux")])
    report = build_report(_words(("chemin", "", "", "", ""), ("pluie", "", "", "", "")), lex)
    assert set(report["statut"]) == {"absent"}


def test_report_lists_words_to_collect_first_and_summary_counts():
    words = _words(("chemin", "", "t", "", ""), ("lune", "", "t", "", ""), ("pluie", "", "u", "", ""))
    report = build_report(words, _lexicon())
    assert report.iloc[0]["mot"] == "lune"
    summary = summarize(report)
    assert summary["total"] == 3
    assert summary["par_statut"] == {"absent": 1, "mentionne": 0, "antonyme": 0, "famille": 0, "synonyme": 0, "proche": 0,
                                     "couvert": 2}
    assert summary["couverture_directe"] == round(2 / 3, 3)
    assert list(summary["par_statut"]) == list(STATUSES)


def test_wordlist_from_text_dedups_and_accepts_commas():
    assert list(wordlist_from_text("route, chemin\nroute;lune")["mot"]) == ["route", "chemin", "lune"]


def test_shipped_wordlist_is_well_formed():
    words = load_wordlist()
    assert list(words.columns) == ["mot", "categorie", "theme", "synonymes", "antonymes"]
    assert words["mot"].is_unique and (words["mot"].str.strip() != "").all()
    # un mot n'est jamais son propre synonyme/antonyme
    for row in words.itertuples():
        related = {w.strip() for w in f"{row.synonymes};{row.antonymes}".split(";") if w.strip()}
        assert row.mot not in related, row.mot


def test_arabic_candidates_from_via_cell():
    from td_arabic.translation.coverage import arabic_candidates
    assert arabic_candidates("chemin → derib, tariig ; sentier → derib, mamar") == ["derib", "tariig", "mamar"]
    assert arabic_candidates("") == []


def test_grammatical_words_get_no_noisy_mentions():
    lex = Lexicon([_row("x", "marche de nuit"), _row("y", "arbre de la forêt")])
    report = build_report(_words(("de", "prep", "grammaire", "", ""), ("nuit", "n", "temps", "", "")), lex)
    assert _status(report, "de") == "absent"          # « de » est dans les définitions, sans intérêt
    assert _status(report, "nuit") == "mentionne"


def _status_of(report, word):
    return report.set_index("mot").loc[word]


def test_plural_gloss_of_a_collective_noun_covers_the_singular_word():
    lex = Lexicon([_row("beed", "oeufs", "sg. beedaay", "n.coll."),
                   _row("suuf", "poils, cheveux", "sg. suufaay", "n.coll.")])
    report = build_report(_words(("œuf", "n", "nourriture", "", ""), ("cheveu", "n", "corps", "", ""),
                                 ("poil", "n", "animaux", "", "")), lex)
    egg = _status_of(report, "œuf")
    assert egg["statut"] == "couvert"
    assert egg["traductions"] == "beedaay (singulatif de beed, gloss : oeufs)"   # le singulatif, pas le collectif
    assert _status_of(report, "cheveu")["statut"] == "couvert"                    # « cheveux » après la virgule
    assert "suufaay" in _status_of(report, "poil")["traductions"]


def test_plural_gloss_without_singulative_is_still_reported():
    lex = Lexicon([_row("zuruuf", "circonstances", "", "n.pl.")])
    row = _status_of(build_report(_words(("circonstance", "n", "", "", "")), lex), "circonstance")
    assert row["statut"] == "couvert" and "gloss au pluriel : circonstances" in row["traductions"]


def test_plural_gloss_on_an_ordinary_noun_is_only_a_close_form():
    # « fils » (garçon) n'est pas le pluriel de « fil » (fil à coudre) ; « fois » ≠ « foi »
    lex = Lexicon([_row("wileed", "fils", "", "n.m."), _row("iimaan", "foi", "", "n.f.")])
    report = build_report(_words(("fil", "n", "", "", ""), ("fois", "n", "", "", "")), lex)
    assert _status(report, "fil") == "proche"
    assert "autre mot possible" in _status_of(report, "fil")["traductions"]
    assert _status(report, "fois") == "absent"        # pas de variante au singulier


def test_reflexive_verb_gloss_covers_the_bare_verb_and_the_reverse():
    lex = Lexicon([_row("achchattat", "se disperser, se répandre", "inacc. yichchattat", "v.i."),
                   _row("gamma", "lever", "", "v.i.")])
    report = build_report(_words(("disperser", "v", "actions", "", ""), ("répandre", "v", "actions", "", ""),
                                 ("se lever", "v", "actions", "", "")), lex)
    # « disperser » n'a que la forme pronominale : à vérifier, pas couvert
    assert _status(report, "disperser") == "proche"
    assert _status(report, "répandre") == "proche"
    assert _status(report, "se lever") == "proche"       # le lexique n'a que « lever » (sens différent)
    assert "gloss : se disperser" in _status_of(report, "disperser")["traductions"]


def test_exact_reflexive_gloss_is_covered():
    lex = Lexicon([_row("gamma", "se lever", "", "v.i.")])
    assert _status(build_report(_words(("se lever", "v", "actions", "", "")), lex), "se lever") == "couvert"


def test_accent_and_ligature_differences_do_not_hide_a_word():
    lex = Lexicon([_row("x", "epine", "", "n.f."), _row("y", "cloture", "", "n.f.")])
    report = build_report(_words(("épine", "n", "", "", ""), ("clôture", "n", "", "", "")), lex)
    assert set(report["statut"]) == {"couvert"}


def test_variants_respect_the_part_of_speech_and_grammatical_words():
    # « mais » (conjonction) ne couvre pas « mai » ; « mois » (nom) ne couvre pas le pronom « moi »
    lex = Lexicon([_row("lakin", "mais", "", "conj."), _row("chahar", "mois", "", "n.m.")])
    report = build_report(_words(("mai", "n", "temps", "", ""), ("moi", "pron", "grammaire", "", "")), lex)
    assert _status(report, "mai") == "absent"
    assert _status(report, "moi") == "absent"


def test_synonym_lead_names_the_singulative_for_the_add_form():
    lex = Lexicon([_row("beed", "oeufs", "sg. beedaay", "n.coll.")])
    report = build_report(_words(("ovule", "n", "", "œuf", "")), lex).set_index("mot")
    assert report.loc["ovule", "statut"] == "synonyme"
    assert report.loc["ovule", "via_synonymes"] == "œuf → beedaay"


def test_word_variants_rules():
    from td_arabic.translation.coverage import word_variants
    assert ("oeufs", "pluriel") not in word_variants("œuf", "n")           # la forme est « œufs »
    assert all(kind != "singulier" for _, kind in word_variants("fois", "n"))
    assert ("œufs", "pluriel") in word_variants("œuf", "n")
    assert ("animaux", "pluriel") in word_variants("animal", "n")
    assert ("yeux", "pluriel") in word_variants("œil", "n")
    assert ("pommes de terre", "pluriel") in word_variants("pomme de terre", "n")
    assert [k for _, k in word_variants("de", "prep")] == ["exact"]
    assert ("s'asseoir", "pronominal") in word_variants("asseoir", "v")


def test_homographs_are_never_confused():
    """mai/mais, moi/mois, ou/où : des mots différents, quelle que soit la graphie du lexique."""
    lex = Lexicon([_row("lakin", "mais", "", "conj."), _row("zurraa", "maïs", "", "n.m."),
                   _row("chahar", "mois", "", "n.m."), _row("wain", "où", "", "adv."),
                   _row("kamaan", "ou", "", "conj.")])
    report = build_report(_words(
        ("mai", "n", "temps", "", ""),        # ni « mais » (conj.), ni « maïs » (autre mot)
        ("moi", "pron", "grammaire", "", ""),  # ni « mois »
        ("ou", "conj", "grammaire", "", ""),   # « ou » ≠ « où »
        ("où", "interr", "grammaire", "", ""),
        ("mois", "n", "temps", "", ""),        # lui est bien couvert
    ), lex)
    assert _status(report, "mai") == "absent"
    assert _status(report, "moi") == "absent"
    assert _status(report, "ou") == "couvert" and "kamaan" in _status_of(report, "ou")["traductions"]
    assert "wain" not in _status_of(report, "ou")["traductions"]
    assert _status(report, "où") == "couvert" and "kamaan" not in _status_of(report, "où")["traductions"]
    assert _status(report, "mois") == "couvert"


def test_months_and_days_are_not_pluralized():
    from td_arabic.translation.coverage import word_variants
    assert word_variants("mai", "n") == [("mai", "exact")]
    assert word_variants("lundi", "n") == [("lundi", "exact")]


def test_family_lead_links_a_missing_verb_to_its_covered_noun():
    from td_arabic.translation.coverage import load_families
    lex = Lexicon([_row("mawlid", "naissance"), _row("miilaad", "naissance"),
                   _row("wilid", "enfanter", "inacc. yalda", "v.tr.")])
    families = {"naître": [("naissance", "n"), ("enfanter", "v")], "naissance": [("naître", "v")]}
    report = build_report(_words(("naître", "v", "famille", "", ""), ("naissance", "n", "famille", "", "")),
                          lex, families=families).set_index("mot")
    assert report.loc["naître", "statut"] == "famille"
    assert report.loc["naître", "via_famille"] == "naissance → mawlid, miilaad ; enfanter → wilid"
    assert report.loc["naissance", "statut"] == "couvert"          # la famille ne remplace pas une vraie traduction


def test_synonym_is_stronger_than_family_and_family_stronger_than_antonym():
    lex = Lexicon([_row("derib", "chemin"), _row("bardaan", "froid")])
    families = {"voie": [("chemin", "n")], "tiède": [("froid", "adj")]}
    report = build_report(_words(("voie", "n", "", "chemin", ""), ("tiède", "adj", "", "", "froid"),
                                 ("x", "n", "", "", "")), lex, families=families)
    assert _status(report, "voie") == "synonyme"
    assert _status(report, "tiède") == "famille"   # famille avant antonyme


def test_shipped_families_file_is_well_formed():
    from td_arabic.translation.coverage import load_families
    families = load_families()
    assert "naître" in families and ("naissance", "n") in families["naître"]
    cats = {c for members in families.values() for _, c in members}
    assert cats <= {"n", "v", "adj", "adv", "interj"}
    for word, members in families.items():
        assert word not in [m for m, _ in members]


def test_translations_show_feminine_and_plural_forms():
    from td_arabic.translation.coverage import gender_number_forms
    assert gender_number_forms("f. jaara / pl. jiiraan / f.pl. jaaraat") == "f. jaara, pl. jiiraan, f.pl. jaaraat"
    assert gender_number_forms("inacc. yachri / impr. achri") == ""                 # pas les formes verbales
    lex = Lexicon([_row("jaar", "voisin", "f. jaara / pl. jiiraan"), _row("galam", "stylo")])
    report = build_report(_words(("voisin", "n", "", "", ""), ("stylo", "n", "", "", "")), lex).set_index("mot")
    assert report.loc["voisin", "traductions"] == "jaar (f. jaara, pl. jiiraan)"
    assert report.loc["stylo", "traductions"] == "galam"                            # aucune forme : le mot seul


def test_report_shows_pending_and_validated_proposals_and_ignores_rejected():
    additions = pd.DataFrame([
        {"src": "jidd", "output": "aïeul, ancêtre", "statut": "propose"},
        {"src": "wileed imm", "output": "cousin (fils de l'oncle paternel)", "statut": "valide"},
        {"src": "xx", "output": "lune", "statut": "rejete"}])
    report = build_report(_words(("ancêtre", "n", "", "", ""), ("cousin", "n", "", "", ""), ("lune", "n", "", "", "")),
                          _lexicon(), additions=additions).set_index("mot")
    assert report.loc["ancêtre", "propositions"] == "jidd (à relire)"
    assert report.loc["cousin", "propositions"] == "wileed imm (validée)"
    assert report.loc["lune", "propositions"] == ""


def test_gloss_with_an_article_still_covers_the_word():
    lex = Lexicon([_row("ambaakirtah", "le lendemain", "", "adv."), _row("x", "l'école")])
    report = build_report(_words(("lendemain", "n", "", "", ""), ("école", "n", "", "", "")), lex,
                          additions=pd.DataFrame(columns=["src", "output", "statut"]))
    assert set(report["statut"]) == {"couvert"}

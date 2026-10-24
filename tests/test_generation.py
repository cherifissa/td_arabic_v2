"""Tests of sentence generation, morphology rules and the sentence bank."""

import pytest

from td_arabic.generation.generator import SentenceGenerator, load_themes
from td_arabic.generation.morphology import MorphologyError, inaccompli, resolve_articles
from td_arabic.generation.store import SentenceStore

# Words deliberately outside the lexicon (fixed formulas), to be documented.
ALLOWED_OUT_OF_LEXICON = {"aleekum"}


@pytest.fixture(scope="module")
def gen():
    generator = SentenceGenerator()
    cache: dict[str, list] = {}
    compute = generator.all_sentences          # generating a theme is slow: do it once per test module

    def cached(theme):
        if theme not in cache:
            cache[theme] = compute(theme)
        return list(cache[theme])           # a copy: `generate` shuffles its pool in place

    generator.all_sentences = cached
    return generator


def test_every_theme_renders_without_error(gen):
    for theme in gen.themes():
        sentences = gen.all_sentences(theme)
        assert sentences, theme
        for s in sentences:
            assert s.td and s.fr and s.statut == "brouillon"
            assert "{" not in s.td + s.fr and "@" not in s.td


def test_arabic_side_only_uses_lexicon_words(gen):
    unknown = {w for t in gen.themes() for s in gen.all_sentences(t) for w in s.hors_lexique}
    assert unknown <= ALLOWED_OUT_OF_LEXICON


def test_vocabulary_references_exist_in_lexicon(gen):
    config = load_themes()
    for group in ("verbes", "adjectifs"):
        for name, item in config[group].items():
            assert gen.lexicon.entries_for(item["td"]), f"{group}.{name}: {item['td']}"
    for name, items in config["vocabulaire"].items():
        for item in items:
            if "td_de" in item:        # résolu par son sens français : peut être absent tant que non validé
                continue
            assert gen.lexicon.knows_td(item["td"].split()[-1].lstrip("@")), f"{name}: {item['td']}"


def test_generation_is_reproducible(gen):
    a = [s.id for s in gen.generate(n=5, seed=7)]
    b = [s.id for s in gen.generate(n=5, seed=7)]
    assert a == b and len(a) == len(set(a))


def test_morphology_rules():
    entry = {"src": "chara", "forms": "inacc. yachri"}
    assert [inaccompli(entry, p) for p in ("ana", "inta", "hu", "hi")] == \
        ["nachri", "tachri", "yachri", "tachri"]
    with pytest.raises(MorphologyError):
        inaccompli({"src": "x", "forms": ""}, "ana")
    assert resolve_articles("ana namchi @suug.") == "Ana namchi al-suug."
    assert resolve_articles("fi @khariif @matar katiir.") == "Fi l-khariif al-matar katiir."


def test_sentence_store_lifecycle(tmp_path, gen):
    store = SentenceStore(tmp_path / "phrases.csv")
    sentences = gen.generate(["marche"], n=3, seed=1)
    assert store.add(sentences) == 3
    assert store.add(sentences) == 0  # pas de doublons
    sid = sentences[0].id
    store.update(sid, statut="validee", td="Ana nachri laham.")
    assert list(store.by_status("validee")["id"]) == [sid]
    with pytest.raises(ValueError):
        store.update(sid, statut="inconnu")


def test_each_verb_key_matches_the_lexicon_gloss(gen):
    """Garde contre les homographes : `nazar` a un sens « se consacrer » avant « regarder »."""
    from td_arabic.generation.morphology import lexicon_entry
    from td_arabic.translation.coverage import fold
    for name, verb in load_themes()["verbes"].items():
        entry = lexicon_entry(gen.lexicon, verb["td"], verb.get("sens"), "v.")
        assert fold(entry["output"]) == fold(name.replace("_", " ")), \
            f"{name}: « {verb['td']} » signifie « {entry['output']} » (ajouter `sens:` ?)"


def test_new_themes_generate_many_distinct_sentences(gen):
    for theme, minimum in {"famille": 100, "ecole": 40, "sante": 30, "animaux": 100,
                           "campagne": 20, "maison": 25, "programme": 100}.items():
        sentences = gen.all_sentences(theme)
        assert len(sentences) >= minimum, theme
        # le français ne distingue pas inta/inti ni intu/intan : des doublons français sont normaux
        assert len({s.fr for s in sentences}) >= len(sentences) * 0.6, f"{theme}: trop de doublons français"


# --- perfective (accompli), course chapter 9 --------------------------------------------------

COURSE_KATAB = {"ana": "katabt", "inta": "katabt", "inti": "katabti", "hu": "katab", "hi": "katabat",
                "aniina": "katabna", "intu": "katabtu", "intan": "katabtan", "humman": "katabo",
                "hinna": "kataban"}


def test_accompli_reproduces_the_course_table():
    from td_arabic.generation.morphology import accompli
    assert {p: accompli({"src": "katab"}, p) for p in COURSE_KATAB} == COURSE_KATAB
    # exemples du cours : rajjaʼ, daʼʼak, ajjan
    assert accompli({"src": "rajjaʼ"}, "ana") == "rajjaʼt" and accompli({"src": "rajjaʼ"}, "hi") == "rajjaʼat"
    assert accompli({"src": "ajjan"}, "hi") == "ajjanat"


def test_accompli_refuses_verbs_the_course_does_not_describe():
    from td_arabic.generation.morphology import UnsupportedFormError, accompli, accompli_supported
    for weak in ("macha", "chara", "gamma", "chaaf", "zaar", "naam", "baaʼ", "raad"):   # voyelle finale / creux
        assert not accompli_supported(weak), weak
        with pytest.raises(UnsupportedFormError):
            accompli({"src": weak}, "ana")
    for regular in ("katab", "aawan", "gaabal", "dafaʼ", "khasal", "fattach"):
        assert accompli_supported(regular), regular


def test_french_passe_compose():
    from td_arabic.generation.morphology import passe_compose
    assert passe_compose("je", "m", "sg", "acheté") == "j'ai acheté"
    assert passe_compose("elles", "f", "pl", "venu", "etre") == "elles sont venues"
    assert passe_compose("tu", "m", "sg", "levé", "pronominal") == "tu t'es levé"
    assert passe_compose("nous", "m", "pl", "levé", "pronominal") == "nous nous sommes levés"
    assert passe_compose("elle", "f", "sg", "levé", "pronominal") == "elle s'est levée"


def test_generator_produces_the_ten_persons_in_the_past_and_four_in_the_present(gen):
    sentences = gen.all_sentences("famille")
    aider = [s for s in sentences if s.template_id == "fam-verbe" and "aawan" in s.td.lower()
             and "al-abu" in s.td.lower()]
    assert {s.td.split()[0].lower() for s in aider} == set(COURSE_KATAB)
    assert {s.td for s in aider} >= {"Inti aawanti al-abu.", "Hinna aawanan al-abu.", "Aniina aawanna al-abu."}
    assert "Hinna aawanan al-abu." in {s.td for s in aider}
    by_td = {s.td: s.fr for s in aider}
    assert by_td["Hinna aawanan al-abu."] == "Elles ont aidé le père."
    assert by_td["Intu aawantu al-abu."] == "Vous avez aidé le père."
    # présent : seules les 4 personnes documentées pour l'inaccompli
    present = [s for s in sentences if s.template_id == "fam-verbe" and "tiʼaawin" in s.td.lower()
               or s.td.lower().startswith(("ana niʼaawin", "hu yiʼaawin"))]
    assert not any(s.td.lower().startswith(("inti ", "aniina ", "intu ", "intan ", "humman ", "hinna "))
                   and "iʼaawin" in s.td for s in sentences)


def test_weak_verbs_get_no_perfective_but_keep_the_present(gen):
    sentences = gen.all_sentences("marche")
    chara = [s for s in sentences if "chara" in s.lemmes or "nachri" in s.td.lower()]
    assert any("nachri" in s.td.lower() for s in chara)                       # présent conservé
    assert not any(s.td.lower().startswith(("aniina", "intu", "humman")) and "chara" in s.lemmes
                   for s in sentences)                                         # pas de passé inventé


def test_derived_forms_are_not_reported_as_outside_the_lexicon(gen):
    assert all(not s.hors_lexique or set(s.hors_lexique) <= ALLOWED_OUT_OF_LEXICON
               for t in gen.themes() for s in gen.all_sentences(t))


def test_plural_and_feminine_adjective_agreement(gen):
    by_td = {s.td: s.fr for s in gen.all_sentences("sante")}
    assert by_td["Intu mardaaniin."] == "Vous êtes malades."
    assert by_td["Humman ayyaaniin."] == "Ils sont fatigués."
    assert by_td["Inti mardaane."] == "Tu es malade."
    assert by_td["Hi ayyaane."] == "Elle est fatiguée."


# --- validated sentences are not generated again --------------------------------------------

def test_settled_sentences_are_excluded_from_generation(gen, tmp_path):
    store = SentenceStore(tmp_path / "phrases.csv")
    first = gen.generate(["marche"], n=20, seed=3)
    store.add(first)
    store.update(first[0].id, statut="validee", td="Texte corrigé par un locuteur.")   # le texte a changé, pas l'id
    store.update(first[1].id, statut="rejetee")
    assert store.settled_ids() == {first[0].id, first[1].id}
    assert store.settled_ids(include_rejected=False) == {first[0].id}
    again = gen.generate(["marche"], n=5000, seed=3, exclude=store.settled_ids())
    ids = {s.id for s in again}
    assert first[0].id not in ids and first[1].id not in ids
    assert len(ids) == len(gen.all_sentences("marche")) - 2                      # tout le reste est encore possible
    assert first[0].id in {s.id for s in gen.generate(["marche"], n=5000, seed=3)}  # sans exclusion : revient


def test_words_resolved_by_meaning_follow_the_validated_spelling():
    from td_arabic.translation.lexicon import Lexicon
    config = {"personnes": {}, "verbes": {}, "adjectifs": {},
              "vocabulaire": {"jours": [{"td_de": "jeudi", "fr": {"txt": "jeudi"}},
                                        {"td_de": "dimanche", "fr": {"txt": "dimanche"}}],
                              "reperes": [{"td": "ambaakir", "fr": {"txt": "demain"}}]},
              "themes": {"semaine": {"titre": "Semaine", "gabarits": [
                  {"id": "sem", "td": "{M} {J}.", "fr": "{M.txt}, c'est {J.txt}.",
                   "slots": {"M": "reperes", "J": "jours"}}]}}}
    row = lambda src, out: {"src": src, "pos": "n.m.", "output": out, "forms": "", "sense_number": ""}
    before = SentenceGenerator(config, Lexicon([row("ambaakir", "demain"), row("ahad", "dimanche")]))
    assert [s.td for s in before.all_sentences("semaine")] == ["Ambaakir ahad."]        # jeudi pas encore validé
    after = SentenceGenerator(config, Lexicon([row("ambaakir", "demain"), row("ahad", "dimanche"),
                                               row("khamiis", "jeudi")]))                 # graphie corrigée à la relecture
    assert {s.td: s.fr for s in after.all_sentences("semaine")} == {
        "Ambaakir ahad.": "Demain, c'est dimanche.", "Ambaakir khamiis.": "Demain, c'est jeudi."}
    assert not any(s.hors_lexique for s in after.all_sentences("semaine"))


# --- more constructions: imperative, questions, plural / singulative / dual, coordination, « hier » ---------

def _by_td(gen, theme, template_id):
    return {s.td: s.fr for s in gen.all_sentences(theme) if s.template_id == template_id}


def test_imperative_uses_the_lexicon_imperative_forms(gen):
    from td_arabic.generation.morphology import forms_of, lexicon_entry
    assert forms_of(lexicon_entry(gen.lexicon, "akal", None, "v."), "impr.") == ["aakul"]      # cours, chap. 11
    assert _by_td(gen, "marche", "mar-ordre")["Aakul al-rizz!"] == "Mange le riz !"
    assert _by_td(gen, "famille", "fam-ordre")["Aawin al-akhu!"] == "Aide le frère !"
    assert _by_td(gen, "maison", "mai-ordre")["Addil al-baab!"] == "Répare la porte !"
    for theme in ("marche", "famille", "maison", "ecole"):        # 2e personne seulement : pas d'autre pronom
        assert all(td.split()[0].lower() in {"aakul", "aawin", "addil", "antahi"}
                   for td in _by_td(gen, theme, {"marche": "mar-ordre", "famille": "fam-ordre", "maison": "mai-ordre",
                                                 "ecole": "eco-ordre"}[theme]))


def test_yes_no_questions_with_french_elision(gen):
    questions = _by_td(gen, "marche", "mar-question")
    assert questions["Hi tachri rizz?"] == "Est-ce qu'elle achète du riz ?"
    assert questions["Hu yidoor mileh?"] == "Est-ce qu'il veut du sel ?"
    assert questions["Ana nachri rizz?"] == "Est-ce que j'achète du riz ?"
    assert questions["Inta tachri rizz?"] == "Est-ce que tu achètes du riz ?"
    assert not any("Est-ce que il" in fr or "Est-ce que elle" in fr for fr in questions.values())


def test_plural_singulative_and_dual_come_from_the_lexicon(gen):
    assert _by_td(gen, "famille", "fam-pluriel-ou")["Al-akhwaan ween?"] == "Où sont les frères ?"
    assert _by_td(gen, "animaux", "ani-pluriel")["Al-kheel ween?"] == "Où sont les chevaux ?"
    assert _by_td(gen, "marche", "mar-singulatif")["Inta tachri tamaatimaay."] == "Tu achètes une tomate."
    assert _by_td(gen, "marche", "mar-singulatif")["Ana nachri beedaay."] == "J'achète un œuf."
    assert _by_td(gen, "famille", "fam-duel")["Al-waaldeen fi l-beet."] == "Les deux parents sont à la maison."
    assert _by_td(gen, "corps", "cor-duel")["Hu yakhsil al-iideen."] == "Il lave les deux mains."
    # un nom sans pluriel dans le lexique (galam) ne donne pas de phrase au pluriel, au lieu d'en inventer une
    assert "Al-galam ween?" in _by_td(gen, "ecole", "eco-ou")
    assert not any(td.startswith("Al-galam") for td in _by_td(gen, "ecole", "eco-pluriel"))
    assert not any("galam" in td for td in _by_td(gen, "marche", "mar-singulatif"))


def test_coordination_never_repeats_the_same_noun(gen):
    both = _by_td(gen, "marche", "mar-et")
    assert both["Ana naakul rizz wa laham."] == "Je mange du riz et de la viande."
    assert not any(td.split()[-2:] in (["rizz", "wa"],) for td in both)
    for td in both:
        words = td.rstrip(".").split()
        assert words[words.index("wa") - 1] != words[words.index("wa") + 1], td


def test_yesterday_goes_with_the_perfective_only(gen):
    hier = _by_td(gen, "programme", "pro-hier-manger")
    assert hier["Amis inti akalti rizz."] == "Hier, tu as mangé du riz."
    assert hier["Albaareh humman akalo laham."] == "Hier soir, ils ont mangé de la viande."
    assert not any(td.split()[1] in ("ana", "inta", "hu", "hi") and "n" == td.split()[2][0] for td in hier)
    assert all(fr.startswith(("Hier,", "Hier soir,")) for fr in hier.values())


def test_no_absurd_verb_object_pairs(gen):
    french = [s.fr for t in gen.themes() for s in gen.all_sentences(t)]
    assert not any("chaise" in fr and "ouvr" in fr for fr in french)          # on n'ouvre pas une chaise
    assert not any(("bu des" in fr or "boit des" in fr or "bois des" in fr) for fr in french)   # on boit du thé, pas des haricots
    assert not any("deux têtes" in fr and "lave" in fr for fr in french)

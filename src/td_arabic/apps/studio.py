"""Corpus studio (Streamlit): generate, translate, validate and record sentences.

Tabs (labels are in French in the UI):
  1. Générer      — theme sentences built from the lexicon (templates)
  2. Traduire     — gloss of a French <-> Chadian Arabic sentence
  3. Couverture   — important French words still missing from the lexicon
  4. Phrases      — sentence bank: correction and validation
  5. Locuteurs    — profiles, consent and audio settings of each speaker
  6. Enregistrer  — read aloud and record with the microphone, one by one
  7. Corpus audio — statistics and playback

Training is not here: it happens in Unsloth Studio (``td-arabic finetune studio``).

Run with ``td-arabic studio``.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace

import pandas as pd
import streamlit as st

from td_arabic.config import PATHS
from td_arabic.utils.env import load_env
from td_arabic.lexicon import corpus as corpus_pipeline
from td_arabic.generation.generator import GeneratedSentence, SentenceGenerator
from td_arabic.generation.store import LIST_SEP, STATUSES, SentenceStore
from td_arabic.recording.audio import SAMPLE_RATES, AudioError
from td_arabic.recording.dataset import AudioDataset, ConsentError
from td_arabic.recording.speakers import GENRES, TRANCHES_AGE, Speaker, SpeakerRegistry
from td_arabic.translation.additions import (POS_CHOICES, STATUTS, AdditionError, load_additions,
                                             propose_from_rows, spelling_warnings, update_addition)
from td_arabic.translation.coverage import (STATUSES as COVERAGE_STATUSES, build_report,
                                            load_wordlist, summarize, wordlist_from_text)
from td_arabic.translation.lexicon import get_lexicon
from td_arabic.translation.sentence import translate_sentence

STATUS_LABELS = {"brouillon": "Brouillon",
                 "validee": "Validée", "rejetee": "Rejetée"}
COVERAGE_LABELS = {"absent": "Absent", "mentionne": "Seulement mentionné", "antonyme": "Via un antonyme",
                   "famille": "Via la même famille", "synonyme": "Via un synonyme", "proche": "Forme proche",
                   "couvert": "Couvert"}
COVERAGE_HELP = {
    "absent": "Aucune trace dans le lexique : mot à collecter.",
    "mentionne": "Apparaît seulement dans une définition ou une expression, pas comme traduction.",
    "antonyme": "Son contraire est traduit : un indice, pas une traduction.",
    "famille": "Un mot de la même famille est traduit (naître → naissance → mawlid) : les mots arabes "
               "d'une même racine vont souvent ensemble, piste à valider.",
    "synonyme": "Un synonyme est traduit (ex. route → chemin → derib) : piste à valider avec un locuteur.",
    "proche": "Seulement la forme pronominale (« se lever » pour « lever ») : souvent un autre sens, à vérifier.",
    "couvert": "Le mot est une traduction d'une entrée du lexique, au singulier, au pluriel (« oeufs » pour « œuf ») "
               "ou sans accents.",
}
ADDITION_LABELS = {"propose": "À relire", "valide": "Validée", "rejete": "Rejetée"}


@st.cache_resource
def generator() -> SentenceGenerator:
    """Return the sentence generator, shared across reruns (Streamlit cache)."""
    return SentenceGenerator()


store, speakers, audio = SentenceStore(), SpeakerRegistry(), AudioDataset()


# --------------------------------------------------------------------------
# 1. Generate
# --------------------------------------------------------------------------

@st.cache_data(max_entries=4, show_spinner=False)
def available_sentences(themes_mtime: float, corpus_mtime: float) -> dict[str, list[str]]:
    """List the ids of the sentences each theme can produce (cached).

    Args:
        themes_mtime: Modification time of ``themes.yaml``; editing the file refreshes the lists.
        corpus_mtime: Modification time of the corpus: validated words (days of the week…) add sentences.

    Returns:
        ``{theme_key: [sentence ids]}``.
    """
    gen = generator()
    return {key: [s.id for s in gen.all_sentences(key)] for key in gen.themes()}


def tab_generate() -> None:
    """Tab 1: generate sentences, edit them and add the kept ones to the bank."""
    gen = generator()
    themes = gen.themes()
    available = available_sentences(PATHS.themes_yaml.stat().st_mtime, PATHS.corpus_csv.stat().st_mtime)
    skip_settled = st.toggle("Ne pas regénérer les phrases déjà validées ou rejetées", value=True,
                             help="Une phrase déjà relue dans la banque n'est plus proposée.")
    settled = store.settled_ids() if skip_settled else set()
    left = {key: len([i for i in ids if i not in settled]) for key, ids in available.items()}
    c1, c2, c3 = st.columns([3, 1, 1])
    chosen = c1.multiselect("Thèmes", list(themes), default=list(themes),
                            format_func=lambda key: f"{themes[key]} ({left[key]})",
                            help="Entre parenthèses : nombre de phrases encore possibles dans le thème.")
    n = c2.number_input("Phrases par thème", 1, 5000, 10,
                        help="Maximum par thème : un thème ne peut pas donner plus que ses phrases possibles.")
    seed = c3.number_input("Graine", 0, 10_000, 42,
                           help="Même graine = mêmes phrases")
    if st.button("Générer", type="primary"):
        st.session_state.generated = [
            s.as_dict() for s in gen.generate(chosen, int(n), int(seed), exclude=settled)]
        st.session_state.generated_short = [themes[k] for k in chosen if left[k] < int(n)]

    rows = st.session_state.get("generated")
    if not rows:
        st.info("Choisissez des thèmes puis cliquez sur « Générer ». Les phrases sont des "
                "brouillons à relire : le français est correct, l'arabe tchadien suit le lexique.")
        return
    short = st.session_state.get("generated_short")
    if short:
        st.info(f"{len(rows)} phrases générées. Thèmes avec moins de phrases possibles que demandé, "
                f"donc entièrement générés : {', '.join(short)}. Pour en avoir plus, ajoutez des mots "
                "ou des gabarits dans `data/resources/themes.yaml` (docs, section 3.3).")
    df = pd.DataFrame(rows)
    df.insert(0, "garder", True)
    df["hors_lexique"] = df["hors_lexique"].map(LIST_SEP.join)
    edited = st.data_editor(
        df[["garder", "theme", "td", "fr", "hors_lexique", "template_id", "id"]],
        hide_index=True, width="stretch", key="gen_editor",
        column_config={"td": st.column_config.TextColumn("Arabe tchadien", width="large"),
                       "fr": st.column_config.TextColumn("Français", width="large")},
        disabled=["theme", "hors_lexique", "template_id", "id"],
    )
    if st.button(f"Ajouter {int(edited['garder'].sum())} phrase(s) à la banque"):
        by_id = {r["id"]: r for r in rows}
        kept = [{**by_id[r.id], "td": r.td, "fr": r.fr}
                for r in edited[edited["garder"]].itertuples()]
        added = _add_rows(kept)
        st.success(
            f"{added} phrase(s) ajoutée(s) (les doublons sont ignorés).")


def _add_rows(rows: list[dict]) -> int:
    """Add generated sentences (as dicts) to the bank.

    Args:
        rows: Dicts carrying every :class:`GeneratedSentence` field.

    Returns:
        The number of sentences added (duplicates are skipped).
    """
    fields = GeneratedSentence.__dataclass_fields__
    return store.add([GeneratedSentence(**{k: r[k] for k in fields}) for r in rows])


# --------------------------------------------------------------------------
# 2. Translate
# --------------------------------------------------------------------------

def tab_translate() -> None:
    """Tab 2: gloss a sentence, show its segments and save a corrected pair."""
    direction = st.radio("Sens", ["fr-ar", "ar-fr"], horizontal=True,
                         format_func={"fr-ar": "Français → arabe tchadien",
                                      "ar-fr": "Arabe tchadien → français"}.get)
    text = st.text_area(
        "Phrase", placeholder="Je vais acheter de la viande au marché")
    if not text.strip():
        return
    result = translate_sentence(text, direction)
    st.markdown(f"**Glose proposée :** {result.gloss}")
    st.caption(f"Couverture lexicale : {result.coverage:.0%} — les mots entre [crochets] "
               "sont absents du lexique. Il s'agit d'une glose mot à mot à corriger.")
    st.dataframe(pd.DataFrame([{
        "segment": s.source, "correspondance": s.match,
        "candidats": " | ".join(f"{c['text']} ({c['pos']})" + (f" — {c['note']}" if c["note"] else "")
                                for c in s.candidates[:4]),
    } for s in result.segments]), hide_index=True, width="stretch")

    with st.form("to_bank"):
        st.markdown("**Ajouter à la banque de phrases** (après correction)")
        fr_default, td_default = (
            text, result.gloss) if direction == "fr-ar" else (result.gloss, text)
        fr = st.text_input("Français", fr_default)
        td = st.text_input("Arabe tchadien", td_default)
        if st.form_submit_button("Ajouter comme brouillon"):
            sid = store.add_manual(td.strip(), fr.strip(), source="traduction")
            st.success(f"Phrase {sid} ajoutée.")


# --------------------------------------------------------------------------
# 3. Coverage of important French words
# --------------------------------------------------------------------------

@st.cache_data(max_entries=4, show_spinner=False)
def coverage_report(wordlist_mtime: float, additions_mtime: float, corpus_mtime: float) -> pd.DataFrame:
    """Return the coverage report of the shipped word list (cached).

    Args:
        wordlist_mtime: Modification time of the word list.
        additions_mtime: Modification time of ``ajouts_corpus.csv`` (0 if absent): a new proposal
            appears in the « Vos propositions » column.
        corpus_mtime: Modification time of the corpus: validated words become « couvert ».

    Returns:
        The report from :func:`td_arabic.translation.coverage.build_report`.
    """
    return build_report(load_wordlist())


def _mtime(path) -> float:
    """Modification time of a file, 0 if it does not exist (cache key)."""
    return path.stat().st_mtime if path.exists() else 0.0


def rebuild_corpus() -> None:
    """Rebuild ``data/processed`` (with the additions) and refresh every cache."""
    corpus_pipeline.run()
    get_lexicon.cache_clear()
    generator.clear()
    coverage_report.clear()


def proposals_panel() -> None:
    """Review the proposals: correct the spelling, then validate or reject.

    What is typed in the add form is a proposal, never taken as correct. Here each row can
    be edited (spelling, translation, category, note) and set to « Validée » (merged into the
    corpus) or « Rejetée ». ``src_saisi`` keeps what was originally typed.
    """
    additions = load_additions()
    pending = int((additions["statut"] == "propose").sum())
    with st.expander(f"Propositions à relire ({pending})", expanded=pending > 0):
        if additions.empty:
            st.caption("Aucune proposition. Sélectionnez un mot du tableau ci-dessus pour en faire une.")
            return
        st.caption("Corrigez l'écriture si besoin (cours : `ʼ` pour la coupure de gorge, voyelles longues "
                   "doublées `aa` `ii` `uu`, `kh`) et **précisez la catégorie** (`n.m.` / `n.f.`, `v.tr.` / `v.i.`), "
                   "puis passez le statut à « Validée » pour que la ligne entre dans le corpus, ou « Rejetée ».")
        shown = st.segmented_control("Afficher", list(STATUTS), selection_mode="multi", default=["propose"],
                                     format_func=ADDITION_LABELS.get, key="proposal_filter")
        view = additions[additions["statut"].isin(shown or STATUTS)].copy()
        view["alertes"] = [" · ".join(spelling_warnings(src, output=out)) for src, out in zip(view["src"], view["output"])]
        flagged = int((view["alertes"] != "").sum())
        if flagged:
            st.warning(f"{flagged} écriture(s) à vérifier : voir la colonne « Alertes » (règles du cours, mot "
                       "très proche d'un mot du lexique).")
        edited = st.data_editor(
            view.assign(statut=view["statut"].map(ADDITION_LABELS)), hide_index=True, width="stretch",
            key=f"proposal_editor_{st.session_state.get('proposal_version', 0)}",
            column_order=["statut", "src", "alertes", "src_saisi", "output", "pos", "forms", "opposite_td", "note",
                          "added_on"],
            disabled=["src_saisi", "added_on", "alertes"],
            column_config={
                "statut": st.column_config.SelectboxColumn("Statut", options=list(ADDITION_LABELS.values()),
                                                           required=True),
                "src": st.column_config.TextColumn("Arabe tchadien (à corriger)", required=True),
                "alertes": st.column_config.TextColumn("Alertes", width="medium"),
                "src_saisi": "Saisi à l'origine", "output": st.column_config.TextColumn("Français", required=True),
                "pos": st.column_config.SelectboxColumn(
                    "Catégorie", options=POS_CHOICES,
                    help="À préciser avant de valider : n.m. / n.f. / n.coll. pour un nom, v.tr. / v.i. pour un "
                         "verbe. Elle dépend du mot arabe (genre, transitivité), pas du mot français."),
                "forms": st.column_config.TextColumn("Formes", help="Ex. pl. …  /  f. …"),
                "opposite_td": st.column_config.TextColumn("Opposé en arabe tchadien"),
                "note": "Note", "added_on": "Date"})
        if st.button("Enregistrer la relecture", type="primary"):
            back = {label: key for key, label in ADDITION_LABELS.items()}
            errors, merged, changed = [], False, 0
            original = view.set_index("id")
            for row in edited.itertuples():
                before = original.loc[row.id]
                fields = {k: getattr(row, k) for k in ("src", "output", "pos", "forms", "opposite_td", "note")
                          if getattr(row, k) != before[k]}
                if back[row.statut] != before["statut"]:
                    fields["statut"] = back[row.statut]
                if not fields:
                    continue
                try:
                    update_addition(row.id, **fields)
                except AdditionError as error:
                    errors.append(f"{row.src} : {error}")
                    continue
                changed += 1
                merged |= "valide" in (back[row.statut], before["statut"])
            for error in errors:
                st.error(error)
            if changed and merged:
                rebuild_corpus()
            if changed:
                st.session_state["proposal_version"] = st.session_state.get("proposal_version", 0) + 1
                st.toast(f"{changed} ligne(s) mise(s) à jour" + (" ; corpus reconstruit." if merged else "."))
                if not errors:
                    st.rerun()


def _leads(row) -> str:
    """Summarise the leads of a coverage row on one line (synonym, same family, opposite)."""
    parts = []
    if row.via_synonymes:
        parts.append(f"synonyme : {row.via_synonymes}")
    if row.via_famille:
        parts.append(f"même famille : {row.via_famille}")
    if row.via_antonymes:
        parts.append(f"contraire : {row.via_antonymes}")
    return "  ·  ".join(parts)


def tab_coverage() -> None:
    """Tab 3: show which important French words have no Chadian Arabic translation."""
    st.caption("Mots français courants confrontés au lexique. Les synonymes et antonymes de la liste "
               "(`data/resources/mots_francais_importants.csv`) sont des propositions à valider : "
               "ils servent à repérer des pistes, jamais à traduire automatiquement.")
    messages = st.session_state.pop("coverage_msgs", None)
    if messages:
        if messages["saved"]:
            st.success(f"{len(messages['saved'])} proposition(s) enregistrée(s), à relire plus bas : "
                       + " · ".join(messages["saved"]))
        for text in messages["warnings"]:
            st.warning(text)
        for text in messages["errors"]:
            st.error(text)
    if not PATHS.french_wordlist_csv.exists():
        st.info("Aucune liste de mots français : créez `data/resources/mots_francais_importants.csv` (colonnes "
                "`mot, categorie, theme, synonymes, antonymes`) pour voir la couverture du lexique.",
                icon=":material/info:")
        return
    report = coverage_report(_mtime(PATHS.french_wordlist_csv), _mtime(PATHS.corpus_additions_csv),
                             _mtime(PATHS.corpus_csv))
    summary = summarize(report)

    cols = st.columns(len(COVERAGE_STATUSES))
    for col, status in zip(cols, COVERAGE_STATUSES):
        col.metric(COVERAGE_LABELS[status], summary["par_statut"]
                   [status], help=COVERAGE_HELP[status])

    todo = [s for s in COVERAGE_STATUSES if s != "couvert"]
    chosen = st.pills("Statut", COVERAGE_STATUSES, selection_mode="multi", default=todo,
                      format_func=COVERAGE_LABELS.get)
    f1, f2 = st.columns([2, 1])
    themes = f1.multiselect("Thème", sorted(report["theme"].unique()))
    query = f2.text_input("Chercher un mot")

    view = report[report["statut"].isin(chosen or COVERAGE_STATUSES)]
    if themes:
        view = view[view["theme"].isin(themes)]
    if query.strip():
        view = view[view["mot"].str.contains(
            query.strip(), case=False, regex=False)]

    st.caption("**Écrivez directement dans le tableau**, puis cliquez sur « Proposer les lignes remplies » : "
               "une ligne avec un mot arabe tchadien devient une proposition (jamais prise pour correcte, à "
               "relire plus bas, où l'on précise la catégorie, les formes, l'opposé et la note). Plusieurs mots "
               "arabes : séparez-les par `;`. Les propositions saisies sont perdues si vous changez de filtre "
               "avant de les envoyer.")
    table = view.assign(statut=view["statut"].map(COVERAGE_LABELS))
    table["arabe"] = ""
    table["forms"] = ""
    table["pistes"] = [_leads(row) for row in table.itertuples()]
    signature = hash((tuple(chosen or ()), tuple(themes), query.strip()))
    edited = st.data_editor(
        table, hide_index=True, width="stretch", num_rows="fixed",
        key=f"coverage_editor_{st.session_state.get('coverage_version', 0)}_{signature}",
        column_order=["mot", "statut", "arabe", "forms", "propositions", "pistes", "traductions", "mentions"],
        disabled=["mot", "statut", "propositions", "pistes", "traductions", "mentions"],
        column_config={
            "mot": "Mot français", "statut": "Statut",
            "arabe": st.column_config.TextColumn("Arabe tchadien (à proposer)", width="medium",
                                                 help="Le mot arabe tchadien. Plusieurs : séparés par « ; »."),
            "forms": st.column_config.TextColumn(
                "Formes (f. / pl. / f.pl. / dl.)", width="medium",
                help="Facultatif. Comme dans le lexique : « f. jaara / pl. jiiraan ». Étiquettes : f. (féminin), "
                     "pl. (pluriel), m.pl. (masculin pluriel), f.pl. (féminin pluriel), dl. (duel). "
                     "« f jaara, pl jiiraan » est aussi accepté et remis au bon format."),
            "propositions": st.column_config.TextColumn(
                "Vos propositions", width="medium",
                help="Ce que vous avez déjà proposé pour ce mot (à relire) ou validé : évite de le proposer deux fois."),
            "pistes": st.column_config.TextColumn("Pistes", width="large",
                                                  help="Mots déjà traduits qui peuvent aider : synonyme, même "
                                                       "famille, contraire (jamais une traduction automatique)."),
            "traductions": st.column_config.TextColumn("Déjà dans le lexique", width="medium"),
            "mentions": st.column_config.TextColumn("Mentionné dans", width="large")})
    filled = edited[edited["arabe"].fillna("").str.strip() != ""].fillna("")
    left, right = st.columns([1, 3], vertical_alignment="center")
    if left.button(f"Proposer les lignes remplies ({len(filled)})", type="primary", disabled=filled.empty):
        saved, errors = propose_from_rows(filled.to_dict("records"))
        st.session_state["coverage_msgs"] = {
            "saved": [f"{i['src']} = {i['output']}" for i in saved],
            "warnings": [w for i in saved for w in i["warnings"]], "errors": errors}
        st.session_state["coverage_version"] = st.session_state.get("coverage_version", 0) + 1
        st.rerun()
    right.download_button("Télécharger cette vue (CSV)", view.to_csv(index=False).encode("utf-8-sig"),
                          file_name="couverture_mots_francais.csv", mime="text/csv")
    proposals_panel()

    with st.expander("Tester mes propres mots"):
        text = st.text_area(
            "Mots français (un par ligne ou séparés par des virgules)", key="coverage_text")
        if text.strip():
            own = build_report(wordlist_from_text(text))
            st.dataframe(own.assign(statut=own["statut"].map(COVERAGE_LABELS)).drop(columns=["categorie", "theme"]),
                         hide_index=True, width="stretch")
            st.caption(
                "Sans synonymes ni antonymes : seuls les mots exacts et les mentions sont détectés.")


# --------------------------------------------------------------------------
# 4. Sentence bank
# --------------------------------------------------------------------------

def tab_sentences() -> None:
    """Tab 3: filter, edit and validate the sentences of the bank."""
    df = store.load()
    if df.empty:
        st.info("La banque est vide : générez ou traduisez des phrases d'abord.")
        return
    counts = df["statut"].value_counts()
    cols = st.columns(len(STATUSES))
    for col, status in zip(cols, STATUSES):
        col.metric(STATUS_LABELS[status], int(counts.get(status, 0)))

    f1, f2 = st.columns(2)
    statuses = f1.multiselect("Statut", STATUSES, default=[
                              "brouillon"], format_func=STATUS_LABELS.get)
    themes = f2.multiselect("Thème", sorted(df["theme"].unique()))
    view = df[df["statut"].isin(statuses or STATUSES)]
    if themes:
        view = view[view["theme"].isin(themes)]

    edited = st.data_editor(
        view[["id", "theme", "td", "fr", "statut", "hors_lexique"]], hide_index=True,
        width="stretch", key="bank_editor", disabled=["id", "theme", "hors_lexique"],
        column_config={"statut": st.column_config.SelectboxColumn(options=list(STATUSES)),
                       "td": st.column_config.TextColumn("Arabe tchadien", width="large"),
                       "fr": st.column_config.TextColumn("Français", width="large")},
    )
    b1, b2 = st.columns(2)
    if b1.button("Enregistrer les modifications", type="primary"):
        changed = 0
        original = view.set_index("id")
        for r in edited.itertuples():
            before = original.loc[r.id]
            fields = {k: getattr(r, k) for k in (
                "td", "fr", "statut") if getattr(r, k) != before[k]}
            if fields:
                store.update(r.id, **fields)
                changed += 1
        st.toast(f"{changed} phrase(s) mise(s) à jour.")
        st.rerun()
    if b2.button("Valider toutes les phrases affichées"):
        for sid in edited["id"]:
            store.update(sid, statut="validee")
        st.rerun()


# --------------------------------------------------------------------------
# 5. Speakers
# --------------------------------------------------------------------------

def tab_speakers() -> None:
    """Tab 4: create or edit a speaker profile, its consent and audio settings."""
    existing = {s.id: s for s in speakers.all()}
    choice = st.selectbox("Locuteur", ["(nouveau)", *existing],
                          format_func=lambda k: k if k == "(nouveau)" else f"{k} — {existing[k].pseudo}")
    sp = existing.get(choice) or Speaker(id=speakers.next_id(), pseudo="")

    with st.form("speaker"):
        st.markdown(
            f"**Profil `{sp.id}`** — n'indiquez pas de nom réel : utilisez un pseudonyme.")
        c1, c2 = st.columns(2)
        pseudo = c1.text_input("Pseudonyme", sp.pseudo)
        genre = c2.selectbox("Genre", GENRES, index=GENRES.index(
            sp.genre) if sp.genre in GENRES else 2)
        age = c1.selectbox("Tranche d'âge", ("", *TRANCHES_AGE),
                           index=(("", *TRANCHES_AGE).index(sp.tranche_age)
                                  if sp.tranche_age in TRANCHES_AGE else 0))
        region = c2.text_input("Ville / région d'origine", sp.region,
                               help="Utile pour étudier la variation dialectale")
        l1 = c1.text_input("Langue première", sp.langue_premiere)
        others = c2.text_input("Autres langues parlées", sp.autres_langues)
        notes = st.text_area(
            "Notes (matériel, conditions d'enregistrement…)", sp.notes)
        consent = st.checkbox("Le locuteur a donné son consentement éclairé (enregistrement, "
                              "usage pour la recherche et diffusion anonymisée)", sp.consentement)

        st.markdown("**Réglages audio**")
        r = sp.reglages
        a1, a2, a3 = st.columns(3)
        rate = a1.selectbox("Fréquence d'échantillonnage (Hz)", SAMPLE_RATES,
                            index=SAMPLE_RATES.index(r.sample_rate),
                            help="16 000 Hz : standard ASR. 22 050 / 44 100 Hz : synthèse vocale.")
        trim = a2.checkbox("Couper les silences début/fin", r.trim_silence)
        norm = a3.checkbox("Normaliser le volume", r.normalize)
        threshold = a1.slider("Seuil de silence (dB)", -70, -10, int(r.silence_threshold_db),
                              help="Plus bas = garde les sons faibles. Montez-le si le lieu est bruyant.")
        padding = a2.slider("Marge conservée (ms)", 0,
                            1000, r.padding_ms, step=50)
        peak = a3.slider("Crête cible (dBFS)", -12.0, 0.0,
                         float(r.peak_dbfs), step=0.5)

        if st.form_submit_button("Enregistrer le profil", type="primary"):
            if not pseudo.strip():
                st.error("Le pseudonyme est obligatoire.")
            else:
                speakers.save(Speaker(
                    id=sp.id, pseudo=pseudo.strip(), genre=genre, tranche_age=age, region=region,
                    langue_premiere=l1, autres_langues=others, consentement=consent,
                    date_consentement=sp.date_consentement if consent else "", notes=notes,
                    reglages=replace(r, sample_rate=rate, trim_silence=trim,
                                     silence_threshold_db=float(threshold), padding_ms=padding,
                                     normalize=norm, peak_dbfs=peak)))
                st.toast(f"Profil {sp.id} enregistré.")
                st.rerun()


# --------------------------------------------------------------------------
# 6. Record
# --------------------------------------------------------------------------

def tab_record() -> None:
    """Tab 5: show sentences one by one and save each microphone take.

    Each take is processed with the speaker's settings and written to the
    audio corpus; a take is processed only once even if Streamlit reruns.
    """
    ready = [s for s in speakers.all() if s.consentement]
    if not ready:
        st.warning(
            "Créez d'abord un profil de locuteur avec consentement (onglet Locuteurs).")
        return
    by_id = {s.id: s for s in ready}
    c1, c2, c3 = st.columns([2, 2, 1])
    speaker = by_id[c1.selectbox("Locuteur", list(by_id),
                                 format_func=lambda k: f"{k} — {by_id[k].pseudo}")]
    statuses = ["validee"] if c3.toggle("Validées seulement", True) else [
        "validee", "brouillon"]
    pool = store.by_status(*statuses)
    themes = c2.multiselect("Thèmes", sorted(pool["theme"].unique()))
    if themes:
        pool = pool[pool["theme"].isin(themes)]
    if pool.empty:
        st.info("Aucune phrase disponible : validez des phrases dans l'onglet Phrases.")
        return

    done = audio.recorded_ids(speaker.id)
    remaining_only = st.toggle("Masquer les phrases déjà enregistrées", True)
    sentences = pool[~pool["id"].isin(done)] if remaining_only else pool
    st.progress(len(done & set(pool["id"])) / len(pool),
                text=f"{len(done & set(pool['id']))}/{len(pool)} phrases enregistrées par {speaker.pseudo}")
    if sentences.empty:
        st.success("Toutes les phrases de cette sélection sont enregistrées.")
        return

    # Navigate by sentence id: a recorded (then hidden) sentence leaves the
    # list, so the current index already points to the next sentence.
    ids = list(sentences["id"])
    prev_id = st.session_state.get("rec_id")
    vanished = prev_id is not None and prev_id not in ids
    idx = ids.index(prev_id) if prev_id in ids else min(
        st.session_state.get("rec_idx", 0), len(ids) - 1)
    row = sentences.iloc[idx].to_dict()
    st.session_state.rec_id, st.session_state.rec_idx = row["id"], idx
    st.markdown(f"<div style='font-size:2rem;font-weight:600;margin:1rem 0 .2rem'>{row['td']}</div>"
                f"<div style='font-size:1.1rem;opacity:.7'>{row['fr']}</div>",
                unsafe_allow_html=True)
    st.caption(f"Phrase {idx + 1}/{len(sentences)} · {row['id']} · thème : {row['theme']} · "
               f"{speaker.reglages.sample_rate} Hz")

    key = f"rec_{speaker.id}_{row['id']}"
    take = st.audio_input("Lisez la phrase en arabe tchadien", key=key)
    if take is not None:
        data = take.getvalue()
        fingerprint = (key, hashlib.sha1(data).hexdigest())
        try:
            # never process the same take twice
            if st.session_state.get("last_take") != fingerprint:
                saved = audio.save_take(speaker, row, data)
                st.session_state.last_take = fingerprint
                st.success(f"Enregistré : {saved.row['file_name']} — {saved.clip.duration:.2f} s, "
                           f"crête {saved.clip.peak_dbfs:.1f} dBFS")
            path = audio.root / audio.relative_path(speaker.id, row["id"])
            st.audio(path.read_bytes(), format="audio/wav")
        except (AudioError, ConsentError) as exc:
            st.error(str(exc))

    n1, n2 = st.columns(2)
    target = None
    if n1.button("Phrase précédente", disabled=idx == 0, width="stretch"):
        target = idx - 1
    if n2.button("Phrase suivante", type="primary", width="stretch",
                 disabled=idx >= len(ids) - 1 and not vanished):
        target = idx if vanished else idx + 1
    if target is not None:
        target = max(0, min(target, len(ids) - 1))
        st.session_state.rec_id, st.session_state.rec_idx = ids[target], target
        st.rerun()


# --------------------------------------------------------------------------
# 7. Audio corpus
# --------------------------------------------------------------------------

def tab_corpus() -> None:
    """Tab 6: show audio-corpus statistics, the manifest and a player."""
    stats = audio.stats()
    c1, c2, c3 = st.columns(3)
    c1.metric("Enregistrements", stats["enregistrements"])
    c2.metric("Durée totale (min)", stats["duree_totale_min"])
    c3.metric("Locuteurs", stats["locuteurs"])
    df = audio.load()
    if df.empty:
        return
    st.dataframe(pd.DataFrame(stats["par_locuteur"]).T, width="stretch")
    st.dataframe(df, hide_index=True, width="stretch")
    choice = st.selectbox("Écouter", df["file_name"])
    if choice:
        st.audio((PATHS.audio / choice).read_bytes(), format="audio/wav")
    st.caption(f"Manifeste : {PATHS.audio_metadata_csv.relative_to(PATHS.root)} — chargeable avec "
               "`datasets.load_dataset('audiofolder', data_dir='data/audio')`.")


def main() -> None:
    """Render the studio page and its seven tabs (training happens in Unsloth Studio)."""
    st.set_page_config(page_title="Studio arabe tchadien", layout="wide")
    load_env()                       # variables de .env (API_KEY…)
    st.title("Studio du corpus arabe tchadien – français")
    tabs = st.tabs(["Générer", "Traduire", "Couverture",
                   "Phrases", "Locuteurs", "Enregistrer", "Corpus audio"])
    for tab, render in zip(tabs, (tab_generate, tab_translate, tab_coverage, tab_sentences, tab_speakers,
                                  tab_record, tab_corpus)):
        with tab:
            render()


if __name__ == "__main__":
    main()

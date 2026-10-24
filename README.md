# td-arabic — Corpus bilingue arabe tchadien (latinisé) – français

Projet de recherche doctorale de **MAHAMAT Cherif Issa** : constitution d'un corpus
**multimodal (texte + voix)** pour l'arabe tchadien, langue peu dotée, en vue de la
traduction automatique et de la reconnaissance vocale.

Le dépôt couvre toute la chaîne, de la source imprimée jusqu'au corpus audio :

```
Lexique SIL (PDF) ──► extraction ──► validation humaine ──► lexique structuré ──► corpus bilingue
                                                                      │
                     API REST ◄── traduction (mots, phrases) ◄────────┤
                                                                      ▼
            corpus audio ◄── enregistrement multi-locuteurs ◄── phrases thématiques (gabarits)
```

| Chiffres clés (v0.2)                                        |                                                                               |
| ----------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Paires lexicales arabe tchadien → français                  | 4 909 (4 832 entrées + 77 expressions)                                        |
| Mots-vedettes distincts                                     | 4 734 (dont 353 homographes numérotés)                                        |
| Formes fléchies indexées (pluriels, féminins, inaccomplis…) | 3 617 entrées en portent                                                      |
| Thèmes de génération                                        | 5 (salutations, marché, journée, temps, déplacements) — 492 phrases possibles |

## Démarrage rapide

Prérequis : [uv](https://docs.astral.sh/uv/) et Python 3.11+.

```bash
uv sync --extra all             # projet + extraction PDF, API et applications
cp .env.example .env            # puis choisir une clé API

uv run td-arabic stats          # statistiques du corpus
uv run td-arabic translate abad
uv run td-arabic translate "Je vais acheter de la viande au marché"
uv run td-arabic generate -t marche -n 5 --seed 42
uv run td-arabic validate       # relire l'extraction page par page (navigateur)
uv run td-arabic studio         # générer, traduire, valider, enregistrer (navigateur)
uv run td-arabic serve          # API REST sur http://127.0.0.1:8000/docs
uv run pytest                   # tests
```

Fine-tuning d'un modèle de traduction avec **Unsloth Studio** (Mac, Windows et Linux) :

```bash
uv run td-arabic finetune install   # installe Unsloth Studio selon le système (installeur officiel)
uv run td-arabic finetune prepare   # data/finetune/train.jsonl et valid.jsonl (format ChatML)
uv run td-arabic finetune studio    # lance Unsloth Studio : charger train.jsonl dans l'onglet « Local »
```

Voir [docs/08-fine-tuning.md](docs/08-fine-tuning.md).

Pour reconstruire le corpus depuis le PDF : `uv run td-arabic pipeline`.

## Toutes les commandes

| Commande                                                            | Rôle                                                                | Option `uv sync` requise |
| ------------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------ |
| `td-arabic extract [--pdf CHEMIN]`                                  | PDF du lexique → `data/interim/`                                    | `--extra extract`        |
| `td-arabic build-corpus`                                            | `data/interim/` → `data/processed/` (lexique final, corpus)         | —                        |
| `td-arabic pipeline`                                                | `extract` puis `build-corpus`                                       | `--extra extract`        |
| `td-arabic validate`                                                | application de relecture de l'extraction                            | `--extra apps`           |
| `td-arabic stats`                                                   | statistiques du corpus texte et audio                               | —                        |
| `td-arabic translate TEXTE [-d auto\|ar-fr\|fr-ar] [-s] [-v]`       | traduire un mot ou une phrase                                       | —                        |
| `td-arabic generate [-t THÈME] [-n N] [--seed S] [--save] [--list]` | générer des phrases thématiques                                     | —                        |
| `td-arabic studio`                                                  | studio : génération, traduction, phrases, locuteurs, enregistrement | `--extra apps`           |
| `td-arabic serve [--host H] [--port P] [--reload]`                  | API REST                                                            | `--extra api`            |
| `td-arabic finetune check\|prepare\|install\|studio [--dry-run] [--port N]` | données pour Unsloth, installation et lancement d'Unsloth Studio | — |

Préfixer chaque commande par `uv run`. Aide détaillée : `uv run td-arabic <commande> --help`.
Les applications Streamlit acceptent des options après `--`, par exemple
`uv run td-arabic validate -- --server.port 8502`.

## Valider l'extraction du lexique

L'application de validation affiche côte à côte la page du PDF original et le texte extrait,
modifiable, pour corriger les erreurs d'extraction page par page (pages 15 à 171).

```bash
uv sync --extra apps            # une seule fois : Streamlit + pdfplumber
uv run td-arabic extract        # si data/interim/pdf_pages_brutes.json n'existe pas encore
uv run td-arabic validate       # ouvre http://localhost:8501
```

- **Sauvegarder et passer à la suivante** enregistre la page corrigée et avance.
- **Première page non corrigée** saute à la prochaine page à relire.
- **Accès rapide aux pages** (en bas) : les pages déjà corrigées sont marquées ✓.
- La position de reprise est mémorisée : l'application rouvre à la dernière page enregistrée.
- Arrêter : `Ctrl + C` dans le terminal.

Fichiers utilisés :

| Fichier                                            | Contenu                                 |
| -------------------------------------------------- | --------------------------------------- |
| `data/raw/SHU_Lexique_arabe_francais_11e_2021.pdf` | PDF affiché à gauche                    |
| `data/interim/pdf_pages_brutes.json`               | texte extrait (point de départ)         |
| `data/validation/pages_corrigees.json`             | pages corrigées (`[{"page", "texte"}]`) |
| `data/validation/progression.json`                 | dernière page enregistrée               |

Récupérer des corrections supprimées par erreur (elles restent dans l'historique Git) :

```bash
git log --oneline -- data/pdf_pages_corrigees.json        # trouver le commit
git show <commit>:data/pdf_pages_corrigees.json > data/validation/pages_corrigees.json
```

## Fonctionnalités

**Extraction du lexique** — lecture directe de la couche texte du PDF (sans OCR), gestion
des deux colonnes à marges miroir, des homographes en exposant, des ligatures mal encodées,
exclusion du texte arabe dont l'encodage est cassé. → [docs/01-methodologie.md](docs/01-methodologie.md)

**Traduction** — recherche exacte, par forme fléchie (`nachri` → _chara_, acheter, 1re pers.)
et floue ; glose de phrases dans les deux sens par correspondance la plus longue.
→ [docs/03-generation-traduction.md](docs/03-generation-traduction.md)

**Génération de phrases** — gabarits thématiques remplis avec les mots du lexique ; la
conjugaison et l'accord viennent des formes du lexique, jamais inventées. Chaque phrase
indique les mots utilisés et signale les mots hors lexique.

**Enregistrement audio** — studio web multi-locuteurs : profils pseudonymisés, consentement,
réglages par personne (fréquence, coupe des silences, normalisation), manifeste compatible
Hugging Face `audiofolder`. → [docs/04-enregistrement-audio.md](docs/04-enregistrement-audio.md)

**API REST** — FastAPI, clé d'accès, documentation Swagger. → [docs/06-api.md](docs/06-api.md)

## Organisation du dépôt

```
.
├── src/td_arabic/
│   ├── config.py              # chemins et constantes (source unique)
│   ├── cli.py                 # commande `td-arabic`
│   ├── utils/                 # E/S atomiques, normalisation du texte, journaux
│   ├── lexicon/               # étape 1 : pdf_extract.py — étape 2 : corpus.py
│   ├── translation/           # lexicon.py (index), sentence.py (phrases), french.py
│   ├── generation/            # generator.py, morphology.py, store.py (banque de phrases)
│   ├── recording/             # audio.py, speakers.py, dataset.py
│   ├── api/app.py             # API REST
│   └── apps/                  # studio.py, validation.py (Streamlit)
├── data/
│   ├── raw/                   # PDF source (non redistribuable, voir licences)
│   ├── interim/               # sorties brutes de l'extraction
│   ├── processed/             # lexique final et corpus (CSV)
│   ├── resources/             # expressions validées à la main, gabarits (themes.yaml)
│   ├── sentences/phrases.csv  # banque de phrases (brouillon / validée / rejetée)
│   ├── audio/                 # locuteurs.json, metadata.csv, wavs/<locuteur>/*.wav
│   └── validation/            # corrections manuelles de l'extraction
├── docs/                      # documentation scientifique et technique
├── notebooks/                 # exploration historique (remplacée par lexicon/corpus.py)
└── tests/
```

## Documentation

1. [Méthodologie et reproductibilité](docs/01-methodologie.md)
2. [Fiche descriptive du corpus (datasheet)](docs/02-corpus-datasheet.md)
3. [Génération et traduction de phrases](docs/03-generation-traduction.md)
4. [Protocole d'enregistrement audio](docs/04-enregistrement-audio.md)
5. [Éthique, consentement et licences](docs/05-ethique-licences.md)
6. [Référence de l'API](docs/06-api.md)
7. [Feuille de route de recherche](docs/07-feuille-de-route.md)
8. [Fine-tuning avec Unsloth Studio](docs/08-fine-tuning.md)
9. [Architecture des données pour l'entraînement](docs/09-architecture-donnees.md)

- Annexe : [orthographe et grammaire de l'arabe tchadien latinisé](docs/annexes/cours-arabe-tchadien-latin.md)

## Citer ce travail

```bibtex
@misc{mahamat2026tdarabic,
  author = {MAHAMAT Cherif Issa},
  title  = {td-arabic : corpus bilingue arabe tchadien latinisé -- français, texte et voix},
  year   = {2026},
  note   = {Version 0.2. Données lexicales dérivées de : SIL Tchad, Lexique arabe tchadien -- français, 2021}
}
```

## Licence

Code sous licence MIT. Les données lexicales sont dérivées du _Lexique arabe tchadien –
français_ (SIL Tchad, 2021) : leur diffusion est soumise à l'accord de SIL — voir
[docs/05-ethique-licences.md](docs/05-ethique-licences.md) avant toute publication.

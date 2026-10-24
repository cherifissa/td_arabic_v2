# td-arabic — Corpus bilingue arabe tchadien (latinisé) – français, texte et voix

Projet de recherche de **MAHAMAT Cherif Issa**, destiné à une thèse de doctorat :
constituer un corpus **multimodal (texte + voix)** pour l'arabe tchadien (ISO 639-3 `shu`),
langue véhiculaire majeure du Tchad mais très peu dotée en ressources numériques, en vue de
la **traduction automatique** et de la **reconnaissance vocale**.

Ce dépôt public contient **le code de toute la chaîne**, la documentation scientifique, un
**petit échantillon** des données et le **protocole éthique**. Le corpus complet n'est pas
publié : il est dérivé du *Lexique arabe tchadien – français* de SIL Tchad (2021), dont la
redistribution attend l'accord de SIL (voir [Données et licences](#données-et-licences)).

## Objectif

```
Lexique SIL (PDF) ──► extraction ──► validation humaine ──► lexique structuré ──► corpus bilingue
                                                                      │
                     API REST ◄── traduction (mots, phrases) ◄────────┤
                                                                      ▼
            corpus audio ◄── enregistrement multi-locuteurs ◄── phrases thématiques (gabarits)
```

1. Transformer un lexique imprimé en un **lexique bilingue structuré** et réutilisable.
2. S'en servir pour produire des **phrases parallèles** arabe tchadien ↔ français, contrôlées
   par le lexique (aucune forme inventée).
3. Faire lire ces phrases par **plusieurs locuteurs** pour obtenir un corpus parole ↔ texte.
4. Évaluer ce que ces ressources apportent aux modèles de traduction et de reconnaissance
   vocale pour une langue peu dotée.

## Chiffres clés

| Corpus textuel (lexique)                                    |                                                    |
| ----------------------------------------------------------- | -------------------------------------------------- |
| Paires lexicales arabe tchadien → français                  | **4 909** (4 832 entrées + 77 expressions)         |
| Mots-vedettes distincts                                     | **4 734** (dont 353 homographes numérotés)         |
| Entrées avec formes fléchies (pluriels, féminins, inaccomplis…) | 3 617                                          |

| Phrases générées (banque de phrases)                        |                                                    |
| ----------------------------------------------------------- | -------------------------------------------------- |
| Phrases                                                     | **4 858** (4 401 validées, 457 brouillons)         |
| Thèmes                                                      | **14** — salutations, marché, journée, temps, déplacements, famille, école, santé, animaux, campagne, maison, programme, semaine, corps |

Voir [docs/03-generation-traduction.md](docs/03-generation-traduction.md).

## Questions de recherche

1. Dans quelle mesure un lexique bilingue d'apprentissage (~4 700 mots-vedettes) permet-il
   d'**amorcer un corpus parallèle de phrases** pour une langue peu dotée ?
2. Quel gain apporte l'**adaptation de modèles multilingues de reconnaissance vocale**
   (MMS, Whisper) avec quelques heures de parole en arabe tchadien, multi-locuteurs ?
3. Quelle est l'**influence de la variation régionale** et du profil des locuteurs sur ces
   performances ?

## Feuille de route

| Étape                                                     | État                                   |
| --------------------------------------------------------- | -------------------------------------- |
| Extraction et structuration du lexique SIL                | fait (v0.2)                            |
| Traduction de mots et de phrases, API REST                | fait (v0.2)                            |
| Génération de phrases thématiques (gabarits)              | fait — 14 thèmes, 4 858 phrases        |
| Studio d'enregistrement multi-locuteurs                   | fait (v0.2)                            |
| Préparation des données de fine-tuning (format ChatML)    | fait                                   |
| Protocole éthique : formulaire de consentement, pseudonymisation | rédigé, à faire valider par un comité d'éthique |
| Relecture complète de l'extraction (pages 15 à 171)       | en cours                               |
| Autorisation de diffusion de SIL Tchad                    | à faire                                |
| Collecte audio pilote (5 à 10 locuteurs)                  | à venir                                |
| Validation des phrases par plusieurs locuteurs (accord inter-annotateurs) | à venir                |
| Expériences de reconnaissance vocale (MMS / Whisper) — WER, CER | à venir                          |
| Expériences de traduction (NLLB, mT5 + lexique) — BLEU, chrF | à venir                             |

Détails : [docs/07-feuille-de-route.md](docs/07-feuille-de-route.md).

## Contenu du dépôt

| Élément                         | Où                                                         |
| ------------------------------- | ---------------------------------------------------------- |
| Extraction du lexique (PDF → entrées) | `src/td_arabic/lexicon/pdf_extract.py`                |
| Structuration et corpus bilingue | `src/td_arabic/lexicon/corpus.py`                         |
| Application de validation       | `src/td_arabic/apps/validation.py`                         |
| Génération de phrases           | `src/td_arabic/generation/`, gabarits dans `data/resources/themes.yaml` |
| Traduction (mots, phrases)      | `src/td_arabic/translation/`                               |
| API REST                        | `src/td_arabic/api/app.py`                                 |
| Outil d'enregistrement audio    | `src/td_arabic/recording/`, `src/td_arabic/apps/studio.py` |
| Fine-tuning                     | `src/td_arabic/finetune/`, `configs/finetune.yaml`         |
| Échantillon de données          | [`data/samples/`](data/samples/)                           |
| Fiche de données (data card)    | [docs/02-corpus-datasheet.md](docs/02-corpus-datasheet.md) |
| Protocole éthique               | [docs/05-ethique-licences.md](docs/05-ethique-licences.md), [formulaire de consentement](docs/ethique/formulaire-consentement.md), [pseudonymisation](docs/ethique/pseudonymisation.md) |
| Tests                           | `tests/`                                                   |

```
.
├── src/td_arabic/
│   ├── config.py        # chemins et constantes (source unique)
│   ├── cli.py           # commande `td-arabic`
│   ├── lexicon/         # extraction du PDF, structuration du corpus
│   ├── translation/     # index du lexique, glose de phrases
│   ├── generation/      # gabarits, morphologie, banque de phrases
│   ├── recording/       # traitement audio, locuteurs, manifeste
│   ├── dataset/         # jeu de données d'entraînement
│   ├── finetune/        # données et lancement d'Unsloth Studio
│   ├── api/             # API REST (FastAPI)
│   └── apps/            # studio et validation (Streamlit)
├── data/
│   ├── resources/themes.yaml   # gabarits de phrases
│   └── samples/                # échantillon public
├── docs/                # documentation scientifique et technique
└── tests/
```

## Échantillon de données

[`data/samples/phrases_echantillon.csv`](data/samples/) contient 24 phrases générées
(2 par thème) pour montrer le format sans le corpus complet.

```csv
id,theme,template_id,fr,td,lemmes,hors_lexique,statut,source
```

Aucune paire du lexique SIL n'est publiée tant que SIL Tchad n'a pas donné son accord ; le
format des paires est décrit dans la [fiche de données](docs/02-corpus-datasheet.md).

## Démarrage rapide

Prérequis : [uv](https://docs.astral.sh/uv/) et Python 3.11+.

```bash
uv sync --extra all             # projet + extraction PDF, API et applications
cp .env.example .env            # puis choisir une clé API
uv run pytest                   # tests
```

Le corpus complet se reconstruit à partir du PDF du lexique, à se procurer auprès de SIL
Tchad et à placer dans `data/raw/SHU_Lexique_arabe_francais_11e_2021.pdf` :

```bash
uv run td-arabic pipeline       # extraction + construction du corpus
uv run td-arabic stats          # statistiques du corpus
uv run td-arabic translate abad
uv run td-arabic translate "Je vais acheter de la viande au marché"
uv run td-arabic generate -t marche -n 5 --seed 42
uv run td-arabic validate       # relire l'extraction page par page (navigateur)
uv run td-arabic studio         # générer, traduire, valider, enregistrer (navigateur)
uv run td-arabic serve          # API REST sur http://127.0.0.1:8000/docs
```

| Commande                                                            | Rôle                                                                | Option `uv sync` requise |
| ------------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------ |
| `td-arabic extract [--pdf CHEMIN]`                                  | PDF du lexique → `data/interim/`                                    | `--extra extract`        |
| `td-arabic build-corpus`                                            | `data/interim/` → `data/processed/` (lexique final, corpus)         | —                        |
| `td-arabic pipeline`                                                | `extract` puis `build-corpus`                                       | `--extra extract`        |
| `td-arabic validate`                                                | application de relecture de l'extraction                            | `--extra apps`           |
| `td-arabic stats`                                                   | statistiques du corpus texte et audio                               | —                        |
| `td-arabic dataset`                                                 | jeu de données d'entraînement (`data/dataset/`)                     | —                        |
| `td-arabic translate TEXTE [-d auto\|ar-fr\|fr-ar] [-s] [-v]`       | traduire un mot ou une phrase                                       | —                        |
| `td-arabic generate [-t THÈME] [-n N] [--seed S] [--save] [--list]` | générer des phrases thématiques                                     | —                        |
| `td-arabic studio`                                                  | studio : génération, traduction, phrases, locuteurs, enregistrement | `--extra apps`           |
| `td-arabic serve [--host H] [--port P] [--reload]`                  | API REST                                                            | `--extra api`            |
| `td-arabic finetune check\|prepare\|install\|studio`                | données pour Unsloth, installation et lancement d'Unsloth Studio    | —                        |

Préfixer chaque commande par `uv run`. Aide : `uv run td-arabic <commande> --help`.

## Documentation

1. [Méthodologie et reproductibilité](docs/01-methodologie.md)
2. [Fiche de données (data card)](docs/02-corpus-datasheet.md)
3. [Génération et traduction de phrases](docs/03-generation-traduction.md)
4. [Protocole d'enregistrement audio](docs/04-enregistrement-audio.md)
5. [Éthique, consentement et licences](docs/05-ethique-licences.md)
   - [Formulaire de consentement](docs/ethique/formulaire-consentement.md)
   - [Méthode de pseudonymisation](docs/ethique/pseudonymisation.md)
6. [Référence de l'API](docs/06-api.md)
7. [Feuille de route de recherche](docs/07-feuille-de-route.md)
8. [Fine-tuning avec Unsloth Studio](docs/08-fine-tuning.md)
9. [Architecture des données pour l'entraînement](docs/09-architecture-donnees.md)

- Annexe : [orthographe et grammaire de l'arabe tchadien latinisé](docs/annexes/cours-arabe-tchadien-latin.md)

## Données et licences

- **Code** : licence MIT ([LICENSE](LICENSE)).
- **Données lexicales** : dérivées du *Lexique arabe tchadien – français* (SIL Tchad, 11e
  édition, 2021). Le corpus complet n'est pas publié tant que SIL Tchad n'a pas donné son
  accord. Cela inclut le fichier des découpages d'expressions
  (`data/resources/expressions_manuelles.csv`), lui aussi dérivé du lexique.
- **Données vocales** : jamais publiées sans consentement écrit des locuteurs ; aucun
  enregistrement n'est présent dans ce dépôt.

## Citer ce travail

```bibtex
@misc{mahamat2026tdarabic,
  author = {MAHAMAT Cherif Issa},
  title  = {td-arabic : corpus bilingue arabe tchadien latinisé -- français, texte et voix},
  year   = {2026},
  note   = {Version 0.2. Données lexicales dérivées de : SIL Tchad, Lexique arabe tchadien -- français, 2021}
}
```

## Contact

MAHAMAT Cherif Issa — [cherifissa.me](https://cherifissa.me)

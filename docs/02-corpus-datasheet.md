# 2. Fiche descriptive du corpus (datasheet)

Format inspiré de *Datasheets for Datasets* (Gebru et al., 2021).

## Motivation

- **Pourquoi ?** Fournir une ressource lexicale et parallèle ouverte à la recherche pour
  l'arabe tchadien, base d'un futur corpus parole-texte.
- **Par qui ?** MAHAMAT Cherif Issa, dans le cadre d'un projet de doctorat.

## Composition

### Corpus textuel (`data/processed/`)

| Fichier | Lignes | Description |
| --- | --- | --- |
| `lexique_final.csv` | 4 909 | lexique complet, une ligne par entrée ou expression, avec page et colonne d'origine |
| `corpus_arabe_tchadien_francais.csv` | 4 909 | paires `src` (arabe tchadien) → `output` (français) |
| `corpus_bilingue.csv` | 9 818 | les mêmes paires dans les deux sens (`direction` = `ar-fr` / `fr-ar`) |

Colonnes de `corpus_arabe_tchadien_francais.csv` :

| Colonne | Contenu | Exemple |
| --- | --- | --- |
| `src` | mot-vedette ou expression, arabe tchadien latinisé | `abad` |
| `pos` | catégorie grammaticale du lexique | `v.tr.` |
| `output` | traduction française | `adorer Dieu` |
| `forms` | formes fléchies, séparées par ` / ` ; `expr.` pour une expression | `inacc. yaʼabud / impr. aʼabud` |
| `sense_number` | numéro d'homographe (vide sinon) | `1` |

Colonnes supplémentaires de `lexique_final.csv` : `type` (`entry` / `expression` / `ajout`, ce dernier
pour les ajouts manuels de [3.5](03-generation-traduction.md)),
`parent_headword`, `expression_number`, `section`, `page`, `column`, `ligature_reconstructed`.

### Répartition par catégorie

| Catégorie | Paires | Catégorie | Paires |
| --- | --- | --- | --- |
| n.m. (nom masc.) | 1 385 | n.coll. (collectif) | 141 |
| v.tr. (verbe trans.) | 917 | adv. | 55 |
| adj. | 907 | num. | 40 |
| n.f. (nom fém.) | 780 | prép. | 38 |
| v.i. (verbe intrans.) | 537 | pron., interj., conj., … | 109 |

### Formes fléchies documentées

| Étiquette | Occurrences | Étiquette | Occurrences |
| --- | --- | --- | --- |
| `pl.` pluriel | 2 002 | `f.pl.` fém. pluriel | 81 |
| `inacc.` inaccompli | 1 457 | `var.` variante | 51 |
| `f.` féminin | 928 | `dl.` duel | 49 |
| `sg.` singulatif | 121 | `impr.` impératif | 25 |

### Corpus de phrases et corpus audio

- `data/sentences/phrases.csv` : phrases générées, traduites ou saisies, avec statut
  (`brouillon`, `validee`, `rejetee`), thème, gabarit d'origine, lemmes utilisés et mots
  hors lexique.
- `data/audio/metadata.csv` : une ligne par enregistrement (`file_name`, `sentence_id`,
  `speaker_id`, `td`, `fr`, `theme`, `duration_s`, `sample_rate`, `genre`, `tranche_age`,
  `region`, `recorded_at`). WAV mono PCM 16 bits, 16 kHz par défaut.

## Processus de collecte

Extraction automatique depuis le PDF du lexique (cf. [méthodologie](01-methodologie.md)),
découpage manuel des expressions, puis phrases construites par gabarits et lues par des
locuteurs volontaires ayant donné leur consentement.

## Orthographe

- Coupure glottale : `ʼ` (U+02BC). Les saisies `'`, `’`, `ʾ` sont normalisées à la recherche.
- Voyelles longues doublées (`aa`, `ii`, `uu`) ; `kh`, `ch`, `tch` = une seule lettre.
- Article défini `al-`, élidé en `l-` après une particule (`fi l-khariif`).
- Contexte : le ʿayn classique est réalisé comme coupure glottale en arabe tchadien et la
  langue est rarement écrite, d'où cette transcription latinisée (cf.
  [méthodologie, 1.2](01-methodologie.md)).

## Qualité et limites

- 209 entrées ont une ligature reconstruite automatiquement (colonne `ligature_reconstructed`).
- Quelques définitions incluent une sous-entrée non séparée (ex. `ambaakir`, `beet`).
- Le texte arabe (écriture arabe) du lexique n'est pas récupérable depuis ce PDF.
- La couverture lexicale est celle d'un lexique d'apprentissage (~4 700 mots) : vocabulaire
  courant, peu de termes techniques.
- Variation dialectale non représentée dans le texte ; elle est documentée côté audio
  (région du locuteur).

## Usages prévus

Recherche lexicale, amorçage de systèmes de traduction (dictionnaire bilingue,
augmentation de données), création de prompts d'enregistrement, évaluation de modèles
de reconnaissance vocale. **Non adapté** à l'entraînement direct d'un traducteur de phrases
sans corpus parallèle de phrases complémentaire.

## Diffusion et maintenance

Voir [éthique et licences](05-ethique-licences.md). Versionnement via Git ; toute
modification des données passe par le pipeline (pas d'édition manuelle des CSV de
`data/processed/`).

Les fichiers de `data/processed/` sont **générés** : une modification à la main y est écrasée
à la reconstruction et peut casser le format (une virgule non protégée ajoute une colonne et
`pandas` refuse alors de lire le fichier). Les routes prévues pour intervenir sur les données :

| Je veux… | Où |
| --- | --- |
| ajouter un mot ou un sens | onglet *Couverture* → proposition → relecture (`data/resources/ajouts_corpus.csv`, cf. [3.5](03-generation-traduction.md)) |
| corriger une définition mal extraite du PDF | `data/resources/corrections_entrees.csv` (`headword`, `avant`, `apres`) |
| découper une définition contenant `expr.` | `data/resources/expressions_manuelles.csv` |

Ensuite : `td-arabic build-corpus`.

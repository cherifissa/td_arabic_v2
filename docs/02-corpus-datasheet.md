# 2. Fiche de données (data card)

Format inspiré de *Datasheets for Datasets* (Gebru et al., 2021).

| | |
| --- | --- |
| Nom | td-arabic — corpus arabe tchadien latinisé ↔ français (texte, puis voix) |
| Version | 0.2 |
| Langues | arabe tchadien (`shu`, écriture latine) ; français (`fra`) |
| Auteur | MAHAMAT Cherif Issa |
| Licence | code MIT ; données lexicales soumises à l'accord de SIL Tchad (voir §7) |
| Échantillon public | [`data/samples/`](../data/samples/) (24 phrases) |

## 1. Motivation

- **Pourquoi ?** L'arabe tchadien est la principale langue véhiculaire du Tchad mais
  presque aucune ressource numérique n'existe pour la traduction automatique ou la
  reconnaissance vocale. Ce corpus doit servir de base à un futur corpus parole ↔ texte.
- **Par qui ?** MAHAMAT Cherif Issa, dans le cadre d'un projet de doctorat.
- **Financement** : aucun à ce jour.

## 2. Provenance des données

| Composant | Origine |
| --- | --- |
| Lexique bilingue | *Lexique arabe tchadien – français*, SIL Tchad, 11e édition, 2021 (PDF de 171 pages, pages 15 à 171) |
| Expressions | découpées à la main dans les définitions du lexique qui contiennent `expr.` (77 expressions) |
| Ajouts | mots ou sens ajoutés par l'auteur, marqués `type = ajout` et séparables des données SIL |
| Phrases | générées par l'auteur à partir de gabarits (`data/resources/themes.yaml`) remplis avec les mots du lexique |
| Audio (à venir) | lectures des phrases validées par des locuteurs volontaires ayant signé le [formulaire de consentement](ethique/formulaire-consentement.md) |

Le lexique décrit surtout le parler de N'Djamena. Le texte en écriture arabe du PDF n'est
pas récupérable (encodage de police cassé) : seule la translittération latine est utilisée.

## 3. Composition

### Corpus textuel (`data/processed/`, non publié)

| Fichier | Lignes | Description |
| --- | --- | --- |
| `lexique_final.csv` | 4 909 | une ligne par entrée ou expression, avec page et colonne d'origine |
| `corpus_arabe_tchadien_francais.csv` | 4 909 | paires `src` (arabe tchadien) → `output` (français) |
| `corpus_bilingue.csv` | 9 818 | les mêmes paires dans les deux sens (`direction` = `ar-fr` / `fr-ar`) |

- 4 734 mots-vedettes distincts, dont 353 homographes numérotés.
- 3 617 entrées portent des formes fléchies.

Colonnes de `corpus_arabe_tchadien_francais.csv` :

| Colonne | Contenu | Exemple |
| --- | --- | --- |
| `src` | mot-vedette ou expression, arabe tchadien latinisé | `abad` |
| `pos` | catégorie grammaticale du lexique | `v.tr.` |
| `output` | traduction française | `adorer Dieu` |
| `forms` | formes fléchies, séparées par ` / ` ; `expr.` pour une expression | `inacc. yaʼabud / impr. aʼabud` |
| `sense_number` | numéro d'homographe (vide sinon) | `1` |

Colonnes supplémentaires de `lexique_final.csv` : `type` (`entry` / `expression` / `ajout`),
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

### Phrases (`data/sentences/phrases.csv`, non publié)

Une ligne par phrase : `id`, `theme`, `template_id`, `fr`, `td`, `lemmes`, `hors_lexique`,
`statut` (`brouillon`, `validee`, `rejetee`), `source`, dates de création et de modification.
La banque compte **4 858 phrases** sur **14 thèmes** (4 401 au statut `validee`, 457 en
`brouillon`), toutes produites par gabarits.

### Audio (`data/audio/`, à venir, jamais publié sans consentement)

`metadata.csv` : une ligne par enregistrement (`file_name`, `sentence_id`, `speaker_id`,
`td`, `fr`, `theme`, `duration_s`, `sample_rate`, `genre`, `tranche_age`, `region`,
`recorded_at`). WAV mono PCM 16 bits, 16 kHz par défaut. Format compatible Hugging Face
`audiofolder`.

## 4. Méthode de collecte et de traitement

1. **Extraction sans OCR** : lecture de la couche texte du PDF (pdfplumber). La police, la
   taille et la position des mots servent de balisage (mot-vedette, sous-entrée, numéro
   d'homographe, forme fléchie). Détails : [méthodologie](01-methodologie.md).
2. **Structuration** : découpage des expressions à partir d'un fichier de découpages
   validés à la main ; toute nouvelle expression non couverte est listée pour vérification
   au lieu d'être découpée automatiquement.
3. **Génération de phrases** : gabarits thématiques remplis avec les mots du lexique ; la
   conjugaison et l'accord viennent des formes du lexique ou de règles documentées, jamais
   inventés. Chaque phrase garde la trace des mots utilisés et des mots hors lexique.

## 5. Méthode de validation

| Niveau | Méthode | État |
| --- | --- | --- |
| Extraction | application `td-arabic validate` : page du PDF à côté du texte extrait, corrigé page par page | en cours (pages 15 à 171) |
| Ligatures | 209 entrées à ligature reconstruite, marquées `ligature_reconstructed = True` pour relecture | marquées |
| Non-régression | l'extraction v0.2 retrouve les 4 832 entrées de la v0.1 ; seules 5 corrections de ligature diffèrent | vérifié |
| Phrases | relecture dans le studio, statut `brouillon` → `validee` / `rejetee` | un seul relecteur à ce jour |
| Phrases (à venir) | relecture par plusieurs locuteurs natifs, mesure de l'accord inter-annotateurs | à faire |
| Audio | contrôle automatique de durée (0,5 à 30 s) et réécoute de chaque prise | prévu dans le studio |
| Tests | 9 fichiers de tests automatisés (`uv run pytest`) | en place |

## 6. Limites connues

- **Couverture** : celle d'un lexique d'apprentissage (~4 700 mots) : vocabulaire courant,
  peu de termes techniques.
- **Variation dialectale** absente du texte (parler de N'Djamena surtout) ; elle sera
  documentée côté audio par la région du locuteur.
- **Écriture arabe** non récupérable depuis le PDF.
- **Sous-entrées non séparées** dans quelques définitions (ex. `ambaakir`, `beet`, `abad` 2).
- **Conjugaison** : le lexique ne donne que la 3e pers. masc. sg. de l'inaccompli ; les
  autres personnes sont dérivées par règle et restent à confirmer pour les verbes
  irréguliers.
- **Phrases générées** : grammaticalement contrôlées mais parfois peu naturelles (le gabarit
  ignore le contexte), d'où la relecture humaine obligatoire avant enregistrement.
- **Un seul relecteur** à ce jour pour les phrases : pas encore de mesure d'accord.
- **Pas adapté** à l'entraînement direct d'un traducteur de phrases sans corpus parallèle
  de phrases complémentaire.

## 7. Usages prévus et diffusion

- **Usages prévus** : recherche lexicale, amorçage de systèmes de traduction (dictionnaire
  bilingue, augmentation de données), création de phrases à enregistrer, évaluation de
  modèles de reconnaissance vocale.
- **Usages à éviter** : usage commercial des données lexicales sans accord de SIL Tchad ;
  identification de locuteurs à partir de leur voix.
- **Diffusion** : code public (MIT) ; corpus complet non publié tant que SIL Tchad n'a pas
  donné son accord, y compris les découpages d'expressions ; seul un échantillon de
  24 phrases est publié. Voir
  [éthique et licences](05-ethique-licences.md).

## 8. Maintenance

Versionnement via Git. Les fichiers de `data/processed/` sont **générés** : toute
modification passe par le pipeline (`td-arabic build-corpus`), jamais par une édition à la
main des CSV.

| Je veux… | Où |
| --- | --- |
| ajouter un mot ou un sens | onglet *Couverture* du studio → proposition → relecture (`data/resources/ajouts_corpus.csv`) |
| corriger une définition mal extraite | `data/resources/corrections_entrees.csv` (`headword`, `avant`, `apres`) |
| découper une définition contenant `expr.` | `data/resources/expressions_manuelles.csv` |

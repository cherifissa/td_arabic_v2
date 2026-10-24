# Documentation complète — Projet arabe tchadien

Ce document regroupe l’ensemble des documents du dossier `docs/`.

## Sommaire

- [1. Méthodologie et reproductibilité](#1-methodologie-et-reproductibilite)

- [2. Fiche descriptive du corpus](#2-fiche-descriptive-du-corpus-datasheet)

- [3. Génération et traduction de phrases](#3-generation-et-traduction-de-phrases)

- [4. Protocole d’enregistrement audio](#4-protocole-denregistrement-audio)

- [5. Éthique, consentement et licences](#5-ethique-consentement-et-licences)

- [6. Référence de l’API REST](#6-reference-de-lapi-rest)

- [7. Feuille de route de recherche](#7-feuille-de-route-de-recherche)

- [8. Fine-tuning avec Unsloth Studio](#8-fine-tuning-avec-unsloth-studio)

- [9. Architecture des données pour l'entraînement](#9-architecture-des-donnees-pour-lentrainement)

- [Cours complet : Lire, écrire et conjuguer l'arabe tchadien](#cours-complet-lire-ecrire-et-conjuguer-larabe-tchadien-alphabet-latin)

---

# 1. Méthodologie et reproductibilité

## 1.1 Objectif

Constituer, pour l'arabe tchadien (code ISO 639-3 `shu`), un corpus aligné
**arabe tchadien latinisé ↔ français** puis un corpus **parole ↔ texte**, exploitables
pour la traduction automatique et la reconnaissance vocale. L'arabe tchadien est une
langue véhiculaire majeure du Tchad mais reste très peu dotée en ressources numériques.

Le choix de l'**écriture latine** suit le lexique source et le cours de référence
(annexe) : elle est stable, transcriptible au clavier et sert de pont vers le français.

## 1.2 Contexte : l'arabe tchadien

L'arabe tchadien (`shu`) est la principale langue véhiculaire du Tchad, où le français
et l'arabe littéraire sont les langues officielles. Il sert de langue de communication
entre les ethnies, notamment dans les marchés (Ouaddaï, Guéra, N'Djamena) et dans le
nord et le centre du pays.

- **Locuteurs.** On l'estime parlé par environ 60 % de la population : 10 % comme
  langue maternelle (environ 1,32 million de locuteurs natifs en 2013) et 50 % comme
  langue seconde ou véhiculaire. Ces chiffres sont des estimations sans source primaire
  datée ; d'autres synthèses donnent une fourchette de 40 à 60 %.
- **Statut écrit.** La langue est rarement écrite, et la Constitution de 1996 mentionne
  « l'arabe » sans préciser la variété. Cela justifie le recours à une transcription
  latinisée (cf. 1.1).
- **Variation.** Les variétés régionales diffèrent : certaines se rapprochent de l'arabe
  libyen, d'autres de l'arabe soudanais. Le lexique source décrit surtout le parler de
  N'Djamena.
- **Phonologie.** Par rapport à l'arabe classique, /ʕ/ devient /ʔ/ (coupure glottale,
  notée `ʼ` dans ce projet) et les pharyngales /ħ/ et /ʕ/ disparaissent. Quelques
  emphatiques propres (/lˤ/, /rˤ/, /mˤ/) existent.
- **Emprunts.** Le français (*bīk* « stylo à bille », *watīr* « voiture ») et le béja
  sont documentés ; les emprunts aux langues locales (sara, etc.) restent à sourcer.

**À ne pas confondre avec le turku.** Le *turku* est un pidgin arabe aujourd'hui éteint,
issu de l'arabe bimbashi, apparu après l'abolition de l'esclavage au Soudan
anglo-égyptien en 1879 avec des soldats déplacés vers le Tchad. C'est une variété
distincte, ancêtre de l'arabe de Bongor et peut-être d'autres pidgins ; ce n'est pas un
ancien nom de l'arabe tchadien.

**Références** (à vérifier sur les ouvrages avant dépôt) :

- Jullien de Pommerol, P. (1997). *L'arabe tchadien : émergence d'une langue véhiculaire*. Karthala.
- Jullien de Pommerol, P. (1999). *Grammaire pratique de l'arabe tchadien*. Karthala.
- Jullien de Pommerol, P. (1999). *Dictionnaire arabe tchadien-français*. Karthala.
- Owens, J. (2006). *A Linguistic History of Arabic*. Oxford University Press.
- Tosco, M. et Owens, J. (1994). « Turku – A Descriptive and Comparative Study », dans *Arabs and Arabic in the Lake Chad Region*, SUGIA 14.
- Manfredi, S. et Lucas, C. (2019). *Arabic and Contact-induced Change*. Language Science Press, pp. 323-325.
- Université Laval, [L'aménagement linguistique dans le monde : Tchad](https://www.axl.cefan.ulaval.ca/afrique/tchad.htm).
- [Langues au Tchad](https://fr.wikipedia.org/wiki/Langues_au_Tchad), Wikipédia.
- [Turku Arabic](https://en.wikipedia.org/wiki/Turku_Arabic), Wikipédia.

## 1.3 Source

_Lexique arabe tchadien – français_, SIL Tchad, 11e édition, 2021 (PDF de 171 pages) :

| Pages  | Contenu                                                                            | Traitement                                   |
| ------ | ---------------------------------------------------------------------------------- | -------------------------------------------- |
| 1–14   | Préambule, notes de prononciation et de grammaire                                  | texte conservé (`lexique_texte_complet.txt`) |
| 15–171 | Dictionnaire sur deux colonnes, 25 sections alphabétiques (A, B, Ch, …, Tch, …, Z) | entrées structurées                          |

Format d'une entrée : `motvedette[n°] (formes) catégorie définition`, par exemple
`abad¹ (inacc. yaʼabud / impr. aʼabud) v.tr. adorer Dieu`.

## 1.4 Chaîne de traitement

```
data/raw/…pdf
   │  td-arabic extract          (src/td_arabic/lexicon/pdf_extract.py)
   ▼
data/interim/  lexique_entries.{json,csv} · lexique_texte_complet.txt · pdf_pages_brutes.json
   │  td-arabic validate         (relecture humaine page par page, optionnelle)
   │  td-arabic build-corpus     (src/td_arabic/lexicon/corpus.py)
   ▼
data/processed/  lexique_final.csv · corpus_arabe_tchadien_francais.csv · corpus_bilingue.csv
```

### Étape 1 — Extraction (sans OCR)

Le PDF possède une couche texte : chaque mot est lu avec sa police, sa taille et sa
position (pdfplumber). C'est plus fiable qu'un OCR sur image et cela permet d'exploiter la
typographie comme balisage :

| Indice typographique                                 | Interprétation                                  |
| ---------------------------------------------------- | ----------------------------------------------- |
| CharisSIL,Bold ~11 pt **sur la marge** de la colonne | début d'une nouvelle entrée                     |
| même police, **indentée**                            | sous-entrée / expression (rattachée à l'entrée) |
| chiffre < 9 pt collé au mot-vedette                  | numéro d'homographe (`abad¹`, `abad²`)          |
| CharisSIL,Bold ~10 pt après `pl.`, `f.`, `inacc.`…   | valeur d'une forme fléchie                      |
| police ≥ 13 pt                                       | titre de section (« A a », « Tch tch »)         |
| `top` < 45 pt                                        | en-tête de page (ignoré)                        |

Difficultés résolues :

- **Colonnes à marges miroir** : les pages paires sont décalées de 13,9 pt. La frontière
  est recalculée par page à partir des deux positions `x0` les plus fréquentes des
  mots-vedettes.
- **Texte arabe inexploitable** : la police ScheherazadeNew a un mappage CID → Unicode
  cassé ; le texte arabe est écarté (seule la translittération latine est utilisée).
- **Ligatures latines** sans Unicode : `(cid:19)` → _fi_, `(cid:30)` → _ff_,
  `(cid:31)` → _ffi_, `)` au milieu d'un mot gras → _fl_ (`kha)a` → _khafla_).
  209 entrées concernées, marquées `ligature_reconstructed = True` pour vérification.

### Étape 2 — Validation humaine (optionnelle)

`td-arabic validate` ouvre une application qui affiche la page du PDF à côté du texte
extrait, éditable. Les corrections sont stockées dans `data/validation/pages_corrigees.json`
avec la position de reprise.

### Étape 3 — Structuration et corpus

- Les 66 entrées dont la définition contient des expressions (`expr.`) sont découpées
  grâce à `data/resources/expressions_manuelles.csv` (77 expressions validées à la main).
  Toute nouvelle entrée `expr.` non couverte est listée dans
  `data/interim/expressions_a_verifier.csv` au lieu d'être découpée au hasard.
- Chaque expression devient une ligne `type = expression`, placée après son entrée mère.
- Les homographes gardent la **forme nue** en `src` (`abad`) et leur numéro dans
  `sense_number`.
- `corpus_bilingue.csv` duplique chaque paire dans le sens `fr-ar`.

## 1.5 Reproductibilité

- Une seule commande reconstruit tout : `uv run td-arabic pipeline`.
- Versions figées par `uv.lock` ; chemins centralisés dans `src/td_arabic/config.py`.
- Écritures atomiques (fichier temporaire puis remplacement).
- La génération de phrases est déterministe avec `--seed`.
- **Vérification de non-régression** effectuée lors de la refonte (v0.1 → v0.2) :
  l'extraction refactorisée produit exactement les 4 832 entrées de l'ancien script ;
  les seules différences sont les 5 corrections de ligature _fl_. Le corpus final contient
  les mêmes 4 909 paires que celui produit par l'ancien notebook, une fois retirés les
  marqueurs artificiels d'homographes (voir ci-dessous).

## 1.6 Changements par rapport à la v0.1 (notebook)

| v0.1                                                                                | v0.2                                                 | Raison                                                              |
| ----------------------------------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------- |
| homographe 2 noté par un `ʾ` final (`abadʾ`), le 3 gardait son chiffre (`tchakka3`) | `src = abad`, `sense_number = 2`                     | les sens 2 et 3 étaient introuvables par l'API (ex. `hatta` sens 2) |
| découpage des expressions dans le notebook (code automatique jamais utilisé)        | fichier CSV de découpages validés + liste à vérifier | traçabilité, pas de code mort                                       |
| `)` → `fl` corrigé seulement si le mot-vedette en contenait                         | correction à l'extraction, partout                   | `fiilim` pl. `a)aam` → `aflaam`                                     |
| `n.f` et `n.f.` coexistaient                                                        | catégorie normalisée `n.f.`                          | cohérence                                                           |
| expressions ajoutées en fin de fichier                                              | expressions placées après leur entrée mère           | lisibilité                                                          |

## 1.7 Limites connues

- Quelques définitions contiennent encore une sous-entrée non séparée
  (ex. `ambaakir` : « demain ambaakirtah adv. le lendemain », `beet` : « maison comp. … »).
- Les pages 15–171 n'ont pas toutes été relues avec l'application de validation.
- Le lexique ne donne que la 3e pers. masc. sg. de l'inaccompli ; les autres personnes sont
  dérivées par règle (préfixes `n-`, `t-`) et restent à confirmer par un locuteur pour les
  verbes irréguliers.

# 2. Fiche descriptive du corpus (datasheet)

Format inspiré de _Datasheets for Datasets_ (Gebru et al., 2021).

## Motivation

- **Pourquoi ?** Fournir une ressource lexicale et parallèle ouverte à la recherche pour
  l'arabe tchadien, base d'un futur corpus parole-texte.
- **Par qui ?** MAHAMAT Cherif Issa, dans le cadre d'un projet de doctorat.

## Composition

### Corpus textuel (`data/processed/`)

| Fichier                              | Lignes | Description                                                                         |
| ------------------------------------ | ------ | ----------------------------------------------------------------------------------- |
| `lexique_final.csv`                  | 4 909  | lexique complet, une ligne par entrée ou expression, avec page et colonne d'origine |
| `corpus_arabe_tchadien_francais.csv` | 4 909  | paires `src` (arabe tchadien) → `output` (français)                                 |
| `corpus_bilingue.csv`                | 9 818  | les mêmes paires dans les deux sens (`direction` = `ar-fr` / `fr-ar`)               |

Colonnes de `corpus_arabe_tchadien_francais.csv` :

| Colonne        | Contenu                                                         | Exemple                         |
| -------------- | --------------------------------------------------------------- | ------------------------------- |
| `src`          | mot-vedette ou expression, arabe tchadien latinisé              | `abad`                          |
| `pos`          | catégorie grammaticale du lexique                               | `v.tr.`                         |
| `output`       | traduction française                                            | `adorer Dieu`                   |
| `forms`        | formes fléchies, séparées par `/` ; `expr.` pour une expression | `inacc. yaʼabud / impr. aʼabud` |
| `sense_number` | numéro d'homographe (vide sinon)                                | `1`                             |

Colonnes supplémentaires de `lexique_final.csv` : `type` (`entry` / `expression` / `ajout`, ce dernier
pour les ajouts manuels de [3.5](03-generation-traduction.md)),
`parent_headword`, `expression_number`, `section`, `page`, `column`, `ligature_reconstructed`.

### Répartition par catégorie

| Catégorie             | Paires | Catégorie                | Paires |
| --------------------- | ------ | ------------------------ | ------ |
| n.m. (nom masc.)      | 1 385  | n.coll. (collectif)      | 141    |
| v.tr. (verbe trans.)  | 917    | adv.                     | 55     |
| adj.                  | 907    | num.                     | 40     |
| n.f. (nom fém.)       | 780    | prép.                    | 38     |
| v.i. (verbe intrans.) | 537    | pron., interj., conj., … | 109    |

### Formes fléchies documentées

| Étiquette           | Occurrences | Étiquette            | Occurrences |
| ------------------- | ----------- | -------------------- | ----------- |
| `pl.` pluriel       | 2 002       | `f.pl.` fém. pluriel | 81          |
| `inacc.` inaccompli | 1 457       | `var.` variante      | 51          |
| `f.` féminin        | 928         | `dl.` duel           | 49          |
| `sg.` singulatif    | 121         | `impr.` impératif    | 25          |

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

# 3. Génération et traduction de phrases

## 3.1 Traduction de mots

`td-arabic translate <mot>` · API `GET /translate?q=…&direction=auto|ar-fr|fr-ar`

Recherche en cascade (`src/td_arabic/translation/lexicon.py`) :

| Étape                                                   | Statut renvoyé   | Exemple                               |
| ------------------------------------------------------- | ---------------- | ------------------------------------- |
| 1. exacte (avec ou sans article `al-`/`l-`)             | `exact_match`    | `al-suug` → marché                    |
| 2. forme fléchie du lexique                             | `form_match`     | `aswaag` → marché (_pluriel de suug_) |
| 2b. inaccompli conjugué (`n-`, `t-` à la place de `y-`) | `form_match`     | `nachri` → acheter (_1re pers. sg._)  |
| 3. floue (RapidFuzz, ratio ≥ 50, 5 suggestions)         | `no_exact_match` | `oogid` → `oogiid` allumette          |
| —                                                       | `no_match`       |                                       |

Côté français, chaque glose est indexée entière et par parties (`cher, coûteux` → `cher`,
`coûteux`), sans les parenthèses (`toi (masc)` → `toi`).

## 3.2 Traduction de phrases (glose assistée)

`td-arabic translate "phrase"` · API `GET /translate/sentence` · onglet _Traduire_ du studio

Ce n'est **pas** un traducteur automatique : la phrase est découpée par correspondance la
plus longue (jusqu'à 4 mots, pour reconnaître `kulla yoom`, `in cha Allah`…), chaque segment
reçoit ses traductions candidates et une **glose brouillon** est proposée.

```
$ td-arabic translate "Je vais acheter de la viande au marché"
[fr-ar] Ana macha chara laham suug  (couverture 100%)

$ td-arabic translate "Ana nachri laham fi l-suug"
[ar-fr] Je acheter viande dans marché  (couverture 100%)
```

Types de segments : `exact`, `forme` (forme fléchie ou mot français conjugué ramené à
l'infinitif), `approx` (similarité ≥ 80 %), `mot_outil` (article, auxiliaire… ignoré),
`inconnu` (affiché entre crochets). La **couverture** (part des segments reconnus) mesure
ce que le lexique sait traduire. La glose ne conjugue pas : elle sert de point de départ
à une phrase corrigée par un locuteur.

## 3.3 Génération de phrases thématiques

`td-arabic generate -t <thème> -n <nombre> --seed <graine> [--save]` · onglet _Générer_

### Principe

Des **gabarits** bilingues (`data/resources/themes.yaml`) sont remplis avec des mots du
lexique. Règle de conception : **aucun mot arabe tchadien n'est inventé**.

- Chaque mot td d'un gabarit ou d'une liste de vocabulaire est un mot-vedette du lexique
  (vérifié par les tests).
- L'**inaccompli** conjugué vient de la forme `inacc.` du lexique (3e pers. masc. sg.), à
  laquelle on applique la règle des préfixes personnels (cours, chap. 10) :
  `yachri` → _ana_ **n**achri, _inta_ / _hi_ **t**achri, _hu_ **y**achri.
- Le **féminin** des adjectifs est la forme `f.` du lexique, choisie selon le genre du nom
  (`n.m.` / `n.f.`) : `al-dihin khaali` mais `al-wata haamiye`.
- L'article `al-` s'élide en `l-` après une particule (`fi l-leel`), comme dans le lexique.
- L'**accompli** (le passé) utilise les dix pronoms du cours (chap. 9) : *ana*, *inta*, *inti*,
  *hu*, *hi*, *aniina*, *intu*, *intan*, *humman*, *hinna*. On part du mot-vedette (3e pers.
  masc. sg.) et on ajoute le suffixe de la personne : `-t`, `-t`, `-ti`, *(aucun)*, `-at`, `-na`,
  `-tu`, `-tan`, `-o`, `-an`. Exemple avec `aawan` (aider) : *Ana* **aawant**, *Inti* **aawanti**,
  *Hi* **aawanat**, *Aniina* **aawanna**, *Humman* **aawano**, *Hinna* **aawanan**.
- **Limite documentée** : le cours montre cette règle sur des verbes dont la base se termine
  par une consonne. Les verbes terminés par une voyelle (`macha`, `chara`, `gamma`) ou à voyelle
  longue avant la consonne finale (`chaaf`, `zaar`, `naam`) changent de radical à l'oral, et le
  cours ne décrit pas ce cas : leur accompli **n'est pas généré** (le présent l'est).
- L'**inaccompli** n'est généré que pour *ana*, *inta*, *hu*, *hi* ; les formes du pluriel et de
  *inti* ne sont pas documentées.
- Les **adjectifs** s'accordent (cours, chap. 8) : féminin pour *hi* / *inti*, masculin pluriel
  (`-iin`) pour *aniina* / *intu* / *humman* (*Intu mardaaniin*, « Vous êtes malades »).
- Le français est écrit à la main dans le fichier (infinitifs, conjugaison au présent, participes
  passés ; le passé composé et ses accords sont calculés : *j'ai aidé*, *elle est allée*).

Une phrase **déjà validée (ou rejetée)** dans la banque n'est plus générée : son identifiant, stable même
si un locuteur corrige le texte, est exclu du tirage (interrupteur dans l'onglet *Générer* ;
`td-arabic generate --include-settled` pour l'ignorer). Les nombres entre parenthèses indiquent les
phrases encore possibles.

Chaque phrase porte : identifiant stable (`mar-1a2b3c4d`), thème, gabarit, lemmes utilisés
et **mots hors lexique** (ex. `aleekum` dans _Salaam aleekum_). Statut initial : `brouillon`.

### Constructions de phrases disponibles

Chaque thème combine ces constructions (toutes fondées sur le cours et le lexique, rien n'est
inventé) :

| Construction | Exemple | Source |
| --- | --- | --- |
| présent (inaccompli) | *Ana nachri sukkar.* — J'achète du sucre. | chap. 10 |
| passé (accompli), 10 personnes | *Hinna aawanan al-abu.* — Elles ont aidé le père. | chap. 9 |
| impératif (2e pers. masc. sg.) | *Aakul al-rizz!* — Mange le riz ! | chap. 11, formes `impr.` du lexique |
| question oui/non (intonation) | *Hi tachri rizz?* — Est-ce qu'elle achète du riz ? | gabarit |
| pluriel d'un nom | *Al-akhwaan ween?* — Où sont les frères ? | chap. 7, formes `pl.` |
| singulatif d'un collectif | *Ana nachri beedaay.* — J'achète un œuf. | chap. 7, formes `sg.` |
| duel | *Al-waaldeen fi l-beet.* — Les deux parents sont à la maison. | chap. 7, formes `dl.` |
| coordination | *Ana naakul rizz wa laham.* — Je mange du riz et de la viande. | `wa` (« et ») du lexique |
| intensif | *Al-abu gawi bilheen.* — Le père est très fort. | `bilheen` (« très ») du lexique |
| repères de temps | *Amis ana akalt rizz.* — Hier, j'ai mangé du riz. | `amis`, `albaareh`, `ambaakir`, `alyoom` |

Une forme qui manque dans le lexique pour un mot (par exemple le pluriel de `galam`) **n'est jamais
inventée** : la phrase n'est simplement pas générée. Le français est calculé pour les accords et le
passé composé ; les noms du vocabulaire portent leurs formes françaises (`pl`, `un`, `dl`).

**Pas encore utilisés**, faute de règle documentée : la négation, les possessifs, les mots
interrogatifs (`chunu`, `yaatu`, `maala` : leur place dans la phrase n'est pas décrite), le pluriel du
présent, l'accord des adjectifs avec un nom pluriel de chose, et l'impératif d'autres personnes.

### Thèmes disponibles

| Thème          | Exemples                                                                                   | Phrases possibles |
| -------------- | ------------------------------------------------------------------------------------------ | ----------------- |
| `salutations`  | _Inta aafe?_ — Tu vas bien ? · _Kikkeef al-ahal?_ — Comment va la famille ?                | 17                |
| `marche`       | _Hi tachri sukkar._ — Elle achète du sucre. · _Al-rizz be kam?_ — Combien coûte le riz ?   | 244               |
| `journee`      | _Ana nakhdim fajur._ — Je travaille tôt le matin. · _Hu yachrab almi._ — Il boit de l'eau. | 172               |
| `temps`        | _Al-wata haamiye._ — Il fait chaud. · _Ambaakir al-matar yaji._ — Demain, il va pleuvoir.  | 11                |
| `deplacements` | _Inta tamchi al-hille._ — Tu vas au village. · _Al-suug ween?_ — Où est le marché ?        | 48                |
| `famille` | *Al-abu ween?* — Où est le père ? · *Al-jidd kabiir.* — Le grand-père est grand. | 1043 |
| `ecole` | *Ana nagri al-kaaye.* — Je lis le cahier. · *Al-kitaab be kam?* — Combien coûte le livre ? | 245 |
| `sante` | *Hi mardaane.* — Elle est malade. · *Al-wirde gawiiye.* — La fièvre est forte. | 67 |
| `animaux` | *Al-juwaad ween?* — Où est le cheval ? · *Inta tiʼayyich al-humaar.* — Tu nourris l'âne. | 873 |
| `campagne` | *Ana nahfir al-biir.* — Je creuse le puits. · *Al-khaaba kabiire.* — La forêt est grande. | 86 |
| `maison` | *Ana naftah al-baab.* — J'ouvre la porte. · *Al-tarabeeza nadiife.* — La table est propre. | 204 |
| `programme` | *Ambaakir ana nachri khalla.* — Demain, j'achète du mil. · *Hassaʼ hu yamchi al-suug.* — Maintenant, il va au marché. | 556 |
| `semaine` | *Ambaakir sabit.* — Demain, c'est samedi. | 2 |
| `corps` | *Al-iid nadiife.* — La main est propre. · *Al-rijileen ween?* — Où sont les deux jambes ? | 126 |

Les thèmes `famille` à `programme` utilisent des mots vérifiés dans le lexique (formes d'inaccompli, féminins, genres). Le genre français des noms est donné à part : `kursi` est masculin en td mais « la chaise » est féminin, d'où des accords différents (*Al-kursi nadiif* / La chaise est propre). Un test vérifie que chaque verbe du YAML correspond bien au sens annoncé (un homographe comme `nazar` « se consacrer » / « regarder » demande `sens: 2`).

### Ajouter un thème ou des mots

Dans `themes.yaml` :

```yaml
vocabulaire:
  fruits:
    - { td: tamur, fr: { part: "des dattes", def: "les dattes" } }

themes:
  cuisine:
    titre: À la cuisine
    gabarits:
      - id: cui-manger
        td: "{P} {V} {N}." # pronom, verbe conjugué, nom
        fr: "{V} {N.part}." # le verbe français inclut son sujet
        verbes: [manger]
        slots: { N: fruits }
    phrases: # phrases figées validées
      - { td: "…", fr: "…" }
```

Puis `uv run pytest tests/test_generation.py` : les tests vérifient que chaque mot existe
dans le lexique et que chaque gabarit se génère sans erreur.

## 3.4 Cycle de validation

```
gabarit / traduction / saisie ──► brouillon ──(relecture par un locuteur)──► validee ──► enregistrement
                                       └──────────────────────────────────► rejetee
```

L'onglet _Phrases_ du studio permet de corriger le texte td ou fr et de changer le statut.
Seules les phrases `validee` sont proposées par défaut à l'enregistrement.

## 3.5 Couverture du lexique et ajouts au corpus

Le lexique va de l'arabe tchadien vers le français : il n'indique pas quels mots français
courants n'ont **pas** de traduction. L'onglet *Couverture* du studio compare une liste de
mots français importants (`data/resources/mots_francais_importants.csv`, environ 2 700 mots
avec synonymes et antonymes) aux traductions françaises du lexique. Chaque mot reçoit un
statut :

| Statut | Signification | Exemple |
| --- | --- | --- |
| Couvert | le mot est une traduction d'une entrée | `chemin` → `derib`, `tariig` |
| Forme proche | seulement la forme pronominale (`lever` → « se lever ») ou un pluriel douteux (`fil` → « fils ») : souvent un autre sens, **à vérifier** | `disperser` → `achchattat` (« se disperser ») |
| Via un synonyme | un synonyme est traduit : **piste à valider** | `route` → `chemin` → `derib` |
| Via un antonyme | le contraire est traduit : indice, pas une traduction | `tard` → `tôt` → `badri` |
| Seulement mentionné | présent dans une définition ou une expression, pas comme traduction | `route` dans « coupeur de route » |
| Absent | aucune trace : mot à collecter | |

**Les synonymes et antonymes de cette liste ont été proposés par Claude et n'ont pas été
validés** : ils servent à repérer des pistes, jamais à traduire automatiquement. La liste
n'est pas un inventaire exhaustif : tous les mots n'ont pas d'usage en arabe tchadien.

### Comment un mot français est reconnu

Le lexique glose les noms collectifs au **pluriel** et note leur singulatif dans les formes
(`beed`, `n.coll.`, « oeufs », `sg. beedaay`). Le mot `œuf` est donc reconnu par « oeufs » et
la traduction affichée est le **singulatif** `beedaay`, pas le collectif `beed`.

- **Pluriel** : un mot est cherché au singulier puis au pluriel (`cheveu` → « cheveux »,
  `animal` → « animaux »), mais ce pluriel n'est fiable que sur une entrée collective ou
  plurielle (`n.coll.`, `n.pl.`) ; sur un nom ordinaire il donne une « forme proche »
  (`fil` ne doit pas être couvert par « fils »).
- **Accents** : la comparaison ignore les accents et la ligature `œ` seulement face à une
  traduction écrite sans accents (« epines », « oeufs »). `mai` ne correspond donc pas à « maïs ».
- **Verbes pronominaux** : `disperser` ↔ « se disperser » donne une « forme proche ».
- **Jamais variés** : les mots grammaticaux (`moi` ≠ « mois », `ou` ≠ « où », `mai` ≠ « mais »),
  les noms de mois et de jours, et aucun passage du pluriel vers le singulier (`fois` ≠ « foi »).
- La catégorie grammaticale doit concorder (un nom ne se couvre pas par un verbe).

### Proposer un mot ou un sens

On écrit **directement dans le tableau** de l'onglet *Couverture*, sur la ligne du mot français, puis
on clique sur *Proposer les lignes remplies*. Le tableau ne garde que l'essentiel :

| Colonne | Rôle |
| --- | --- |
| Mot français, Statut | le mot et son état de couverture |
| **Arabe tchadien (à proposer)** | **la colonne à remplir** ; plusieurs mots arabes se séparent par `;` (`derib; tariig`), une proposition par mot |
| Formes (f. / pl. / f.pl. / dl.) | facultatif, au format du lexique : `f. jaara / pl. jiiraan`. Étiquettes : `f.` féminin, `pl.` pluriel, `m.pl.` masculin pluriel, `f.pl.` féminin pluriel, `dl.` duel. `f jaara, pl jiiraan` est accepté et remis au bon format ; une étiquette inconnue est refusée avec un message |
| Pistes | synonyme, même famille, contraire déjà traduits (aide, jamais une traduction automatique) |
| Déjà dans le lexique, Mentionné dans | ce que le lexique contient déjà sur ce mot |

La **traduction française** est reprise du mot, et la **catégorie** vient de la liste de mots, mais
seulement dans sa forme large (`n.`, `v.`, `adj.`, `adv.`) : le genre d'un nom (`n.m.` / `n.f.`) et la
transitivité d'un verbe (`v.tr.` / `v.i.`) dépendent du **mot arabe** et non du français. Si le mot arabe
existe déjà dans le lexique, sa catégorie exacte est reprise. Le panneau *Propositions à relire* permet de
préciser la catégorie, les formes, l'opposé et la note, et il **refuse de valider** une proposition dont la
catégorie reste générique.

Si le mot arabe existe déjà, la proposition est **un nouveau sens** de ce mot (`derib` signifie aussi
*route*) ; sinon c'est **un nouveau mot**. Les propositions saisies sont perdues si l'on change de filtre
avant de les envoyer.

**Ce qui est saisi n'est jamais pris pour correct.** Une saisie devient une *proposition* « à
relire » : elle est enregistrée mais **ignorée par le pipeline**. Elle n'entre dans le corpus
qu'après relecture, dans le panneau *Propositions à relire* de l'onglet *Couverture* :

1. corriger l'écriture si besoin (cours, chap. 6 : `ʼ` pour la coupure de gorge, voyelles longues
   doublées `aa` `ii` `uu`, `kh`). L'apostrophe saisie est convertie en `ʼ` ; ce qui avait été
   tapé reste conservé dans la colonne *Saisi à l'origine* ;
2. passer le statut à **Validée** (la ligne entre dans le corpus, qui est reconstruit) ou
   **Rejetée** (elle reste dans le fichier comme trace, sans jamais être fusionnée).

Les propositions sont écrites dans `data/resources/ajouts_corpus.csv` (colonnes `id`, `src`,
`src_saisi`, `pos`, `output`, `forms`, `opposite_td`, `note`, `statut`, `added_on`), jamais dans
les CSV de `data/processed/`, qui sont reconstruits par le pipeline. `td-arabic build-corpus`
fusionne **seulement les lignes `valide`** : chaque ajout devient une ligne `type = ajout` de
`lexique_final.csv`, placée après les lignes du même mot, et une paire du corpus. Un sens déjà
présent dans le lexique ou dans les propositions est refusé. Un ancien fichier sans colonne
`statut` compte comme validé (ses lignes étaient fusionnées directement).

Les lignes `ajout` restent distinguables des données du lexique SIL, ce qui permet de les
retirer ou de les citer séparément.

### Les jours de la semaine et « aujourd'hui »

Le lexique a `sabit` (samedi) et `ahad` (dimanche). Lundi à mercredi reprennent les chiffres
`itneen`, `talaata`, `arbaʼa` (2, 3, 4), mais comme noms de jours ils ne figurent pas dans le
lexique ; `khamis` (jeudi), `juuma` (vendredi) et « aujourd'hui » (`alyoom`, de `yoom`, « jour »)
non plus. Ils sont donc des **propositions** à relire. Les thèmes retrouvent ces mots par leur
**sens français** (`td_de: jeudi` dans `themes.yaml`), et non par une écriture figée : tant
qu'un jour n'est pas validé, il n'apparaît pas dans les phrases ; une fois validé, la phrase utilise
l'écriture **corrigée à la relecture** (*Ambaakir khamiis* — « Demain, c'est jeudi »).

# 4. Protocole d'enregistrement audio

Objectif : obtenir, pour chaque phrase validée, des lectures par **plusieurs locuteurs**
dans un format standard pour la reconnaissance vocale (ASR) et la synthèse (TTS).

## 4.1 Lancer le studio

```bash
uv run td-arabic studio      # ouvre http://localhost:8501
```

Le micro est demandé par le navigateur. Fonctionne sur ordinateur et sur téléphone
(même réseau : `uv run td-arabic studio -- --server.address 0.0.0.0`).

## 4.2 Étapes

1. **Locuteurs** — créer un profil par personne : identifiant automatique (`spk001`),
   pseudonyme, genre, tranche d'âge, ville/région d'origine, langues parlées, notes.
   **Cocher le consentement** (obligatoire : sans lui, aucun enregistrement n'est possible).
2. **Réglages audio** du profil (chaque personne a les siens) :

   | Réglage                       | Défaut    | Conseil                                                                 |
   | ----------------------------- | --------- | ----------------------------------------------------------------------- |
   | Fréquence d'échantillonnage   | 16 000 Hz | 16 kHz pour l'ASR ; 22 050 ou 44 100 Hz pour la synthèse vocale         |
   | Couper les silences début/fin | oui       |                                                                         |
   | Seuil de silence              | −40 dB    | monter vers −30 dB dans un lieu bruyant, descendre pour une voix faible |
   | Marge conservée               | 150 ms    | silence laissé avant et après la parole                                 |
   | Normaliser le volume          | oui       | crête ramenée à −1 dBFS                                                 |

3. **Phrases** — valider les phrases à lire.
4. **Enregistrer** — choisir le locuteur (et éventuellement des thèmes). La phrase s'affiche
   en grand en arabe tchadien, la traduction en dessous. Cliquer sur le micro, lire, arrêter :
   la prise est traitée et sauvegardée, puis réécoutable. _Phrase suivante_ pour continuer.
   Réenregistrer une phrase remplace la prise précédente.
5. **Corpus audio** — durée totale, prises par locuteur, écoute.

## 4.3 Traitement appliqué à chaque prise

`src/td_arabic/recording/audio.py` : décodage WAV → mono → rééchantillonnage
(polyphase, scipy) → coupe des silences (énergie RMS par trames de 20 ms) → contrôle de durée
(0,5 à 30 s) → normalisation de crête → WAV PCM 16 bits.

## 4.4 Format produit

```
data/audio/
├── locuteurs.json                 # profils + réglages
├── metadata.csv                   # manifeste
└── wavs/spk001/mar-1a2b3c4d.wav
```

Chargement direct avec Hugging Face :

```python
from datasets import load_dataset
ds = load_dataset("audiofolder", data_dir="data/audio")
```

## 4.5 Bonnes pratiques de collecte

- Pièce calme, pas de ventilateur ; même micro et même distance (≈ 20 cm) pour une séance.
- Lire naturellement, sans accentuer la lecture « à la française » des lettres
  (voir l'annexe : `kh`, `ʼ`, `g` toujours dur, `j` = « dj », `u` = « ou »).
- Viser l'équilibre : genres, tranches d'âge et régions (N'Djamena, Abéché, Mongo, …).
- Noter dans le profil le matériel utilisé et les conditions particulières.
- Ordre de grandeur utile pour l'ASR : quelques heures par locuteur ne suffisent pas ;
  mieux vaut **beaucoup de locuteurs** avec 15 à 30 minutes chacun.

# 5. Éthique, consentement et licences

## 5.1 Données lexicales : droits de SIL Tchad

Le corpus textuel est **dérivé** du _Lexique arabe tchadien – français_ (SIL Tchad, 2021).
Ce document est protégé par le droit d'auteur. Avant toute diffusion publique du PDF ou des
fichiers de `data/interim/` et `data/processed/` :

1. vérifier la licence indiquée dans le PDF (pages de garde) ;
2. demander une autorisation écrite à SIL Tchad pour la redistribution d'un corpus dérivé
   à des fins de recherche, en précisant la licence envisagée (ex. CC BY-NC-SA 4.0) ;
3. citer systématiquement la source.

En attendant, le dépôt peut être partagé **en privé** avec le laboratoire ; pour un dépôt
public, exclure `data/raw/`, `data/interim/` et `data/processed/` (voir `.gitignore`,
section « publication ») et fournir le pipeline permettant de les régénérer à partir du PDF.

Le code est sous licence MIT.

## 5.2 Données vocales : consentement et vie privée

La voix est une donnée personnelle (RGPD si la collecte ou le traitement a lieu dans l'UE).

- **Consentement éclairé écrit** avant la première séance : objectif de la recherche,
  usages (entraînement et évaluation de modèles), diffusion envisagée, durée de conservation,
  droit de retrait à tout moment.
- **Pseudonymisation** : le corpus ne contient qu'un identifiant (`spk001`) et un pseudonyme ;
  les noms réels et formulaires signés sont conservés à part, hors dépôt.
- **Métadonnées minimales** : tranche d'âge (pas de date de naissance), région (pas
  d'adresse), genre facultatif.
- **Droit de retrait** : supprimer `data/audio/wavs/<id>/` et les lignes correspondantes de
  `metadata.csv`.
- Faire valider le protocole par le comité d'éthique / le DPO de l'établissement d'accueil.

## 5.3 Contenu des phrases

Les gabarits évitent les sujets sensibles (religion, politique, santé, personnes réelles) en
dehors des formules de politesse courantes (_in cha Allah_, _hamdulillah_). Les phrases
générées sont relues avant d'être enregistrées.

# 6. Référence de l'API REST

```bash
cp .env.example .env     # définir API_KEY
uv run td-arabic serve   # http://127.0.0.1:8000 — Swagger : /docs, ReDoc : /redoc
```

Toutes les routes sauf `/health`, `/docs`, `/redoc` et `/openapi.json` exigent l'en-tête
`X-API-Key`. Sans `API_KEY` configurée, l'API refuse les requêtes (pas de clé par défaut).

| Méthode | Route                 | Paramètres                                      | Rôle                                    |
| ------- | --------------------- | ----------------------------------------------- | --------------------------------------- |
| GET     | `/health`             | —                                               | état et nombre d'entrées                |
| GET     | `/translate`          | `q`, `direction` = `auto` \| `ar-fr` \| `fr-ar` | traduction d'un mot ou d'une expression |
| GET     | `/translate/sentence` | `text`, `direction` = `fr-ar` \| `ar-fr`        | glose d'une phrase                      |
| GET     | `/generation/themes`  | —                                               | thèmes disponibles                      |
| GET     | `/generation`         | `theme` (répétable), `n` (1-200), `seed`        | phrases générées                        |

## `/translate`

Format compatible avec la v0.1 ; ajouts : statut `form_match`, champs `direction` et `note`.

```bash
curl -H "X-API-Key: $API_KEY" "http://127.0.0.1:8000/translate?q=nachri"
```

```json
{
  "query": "nachri",
  "status": "form_match",
  "word": "chara",
  "translations": [
    {
      "output": "acheter",
      "pos": "v.tr.",
      "sense_number": null,
      "forms": "inacc. yachri",
      "direction": "ar-fr",
      "note": "inaccompli (1re pers. sg.) de chara"
    }
  ]
}
```

`status` : `exact_match`, `form_match`, `no_exact_match` (avec `suggestions` : `word`,
`translations`, `similarity`) ou `no_match`.

## `/translate/sentence`

```json
{
  "source": "Ana nachri laham",
  "direction": "ar-fr",
  "gloss": "Je acheter viande",
  "coverage": 1.0,
  "segments": [
    {
      "source": "ana",
      "match": "exact",
      "candidates": [{ "text": "je", "pos": "pron.", "...": "..." }]
    },
    { "source": "nachri", "match": "forme", "candidates": ["..."] }
  ]
}
```

## `/generation`

```bash
curl -H "X-API-Key: $API_KEY" "http://127.0.0.1:8000/generation?theme=marche&n=2&seed=42"
```

```json
[
  {
    "id": "mar-…",
    "theme": "marche",
    "template_id": "mar-achat",
    "fr": "Elle achète du sucre.",
    "td": "Hi tachri sukkar.",
    "lemmes": ["chara", "sukkar"],
    "hors_lexique": [],
    "statut": "brouillon",
    "source": "gabarit"
  }
]
```

## Codes d'erreur

| Code | Cas                      |
| ---- | ------------------------ |
| 403  | clé absente ou invalide  |
| 404  | thème inconnu            |
| 422  | paramètre invalide       |
| 500  | `API_KEY` non configurée |

## Migration depuis l'ancienne API (`chad_arabic_translation`)

- `GET /translate?q=` : inchangé pour les clients existants (mêmes champs).
- Plus de clé par défaut `default_api_key` ; route de test `/test-error` supprimée.
- Lancement : `uv run td-arabic serve` au lieu de `uvicorn main:app`.

# 7. Feuille de route de recherche

## Questions de recherche envisagées

1. Dans quelle mesure un lexique bilingue d'apprentissage (~4 700 entrées) permet-il
   d'amorcer un corpus parallèle de phrases pour une langue peu dotée ?
2. Quel gain apporte l'adaptation de modèles multilingues de reconnaissance vocale
   (ex. MMS, Whisper) avec quelques heures de parole en arabe tchadien multi-locuteurs ?
3. Quelle est l'influence de la variation régionale et du profil des locuteurs sur ces
   performances ?

## Étapes

| Étape                                                                     | Livrable                   | État                           |
| ------------------------------------------------------------------------- | -------------------------- | ------------------------------ |
| Extraction et structuration du lexique SIL                                | `data/processed/`          | fait (v0.2)                    |
| Outils : traduction de mots / phrases, API                                | `td-arabic translate`, API | fait (v0.2)                    |
| Génération de phrases thématiques                                         | `themes.yaml`, studio      | fait (v0.2) — thèmes à étendre |
| Relecture complète de l'extraction (pages 15–171)                         | `data/validation/`         | en cours                       |
| Autorisation de diffusion SIL Tchad                                       | accord écrit               | à faire                        |
| Protocole éthique et formulaire de consentement                           | document validé            | à faire                        |
| Collecte audio pilote (5 à 10 locuteurs)                                  | `data/audio/`              | à faire                        |
| Validation des phrases par plusieurs locuteurs (accord inter-annotateurs) | statistiques               | à faire                        |
| Expériences ASR (MMS / Whisper, ajustement fin)                           | WER / CER                  | à faire                        |
| Expériences de traduction (NLLB, mT5 + lexique)                           | BLEU / chrF                | à faire                        |

## Dépendances pour les expériences

`uv sync --extra ml` installe transformers, datasets, evaluate, sacrebleu, sentencepiece,
accelerate et scikit-learn.

# Cours complet : Lire, écrire et conjuguer l'arabe tchadien (alphabet latin)

_Basé sur le Lexique arabe tchadien – français (SIL Tchad) et sur le corpus bilingue de l'app_

---

## Sommaire

- Chapitre 1 — Découvrir l'arabe tchadien
- Chapitre 2 — Les deux sons qui n'existent pas en français (kh, ʼ)
- Chapitre 3 — Les lettres à prononciation piégeuse (g, j, h, u)
- Chapitre 4 — L'alphabet complet et le classement des mots
- Chapitre 5 — Lecture : comprendre une fiche de mot
- Chapitre 6 — Écriture : les règles orthographiques essentielles
- Chapitre 7 — Les noms : singulier, pluriel, duel, collectif
- Chapitre 8 — Les adjectifs et leur accord
- Chapitre 9 — Conjugaison : l'accompli (l'action terminée)
- Chapitre 10 — Conjugaison : l'inaccompli (l'action en cours)
- Chapitre 11 — Conjugaison : l'impératif (donner un ordre)
- Chapitre 12 — Un mot, plusieurs sens : homographes et polysémie
- Chapitre 13 — Récapitulatif et auto-évaluation

---

## Chapitre 1 — Découvrir l'arabe tchadien

L'arabe tchadien est parlé comme langue maternelle par plus de 10 % de la population du Tchad, et compris par plus de la moitié du pays. C'est un vrai dialecte arabe : sa grammaire, sa phonologie et son vocabulaire ressemblent à l'arabe littéraire, mais il a évolué de façon propre au Tchad, en empruntant des mots aux langues voisines.

Le Tchad étant bilingue (français / arabe littéraire), l'arabe tchadien peut s'écrire avec deux alphabets : les lettres arabes (sémitiques) et les lettres latines (celles du français). Ce cours enseigne l'écriture en **lettres latines**, car elle sert de tremplin : une fois qu'on sait lire l'arabe tchadien ainsi, il devient plus facile d'apprendre l'arabe littéraire ou de progresser en français, et inversement.

**Ce que tu vas apprendre dans ce cours :**

- Lire n'importe quel mot écrit en arabe tchadien latinisé, même si tu ne connais pas encore son sens.
- Écrire correctement un mot que tu entends, sans faire les fautes typiques des débutants.
- Reconnaître un verbe conjugué et retrouver sa forme de base pour le chercher dans un dictionnaire.

---

## Chapitre 2 — Les deux sons qui n'existent pas en français

Deux sons de l'arabe tchadien n'ont pas d'équivalent en français : **kh** et **ʼ**.

### Le son `kh`

Il se produit à l'arrière de la bouche, juste avant la luette — un son rauque, un peu comme si tu raclais légèrement ta gorge. Il correspond aux lettres arabes خ et غ.

**Exemples à lire à voix haute :**

| Mot       | Sens               |
| --------- | ------------------ |
| khalla    | mil                |
| khabar    | information        |
| khidime   | travail            |
| khiyaate  | couture            |
| khazaala  | gazelle            |
| khammaama | cuillère à charbon |
| akhad     | épouser            |

### Le son `ʼ` (la glottale)

C'est une vraie lettre de l'alphabet, pas un signe de ponctuation ! Elle se prononce par une petite coupure du son au niveau de la gorge, comme le "coup de glotte" qu'on entend entre les deux syllabes de "oh-oh" en anglais. Elle correspond aux lettres arabes ء et ع.

**Exemples à lire à voix haute :**

| Mot     | Sens              |
| ------- | ----------------- |
| gaaʼid  | être là           |
| naʼaal  | sandale           |
| naʼarif | je sais           |
| gaʼʼad  | héberger          |
| naʼaam  | autruche          |
| abad    | adorer Dieu       |
| udu     | membre (du corps) |

> **Piège fréquent :** ce caractère est parfois tapé comme une apostrophe droite (`'`) et parfois comme une apostrophe courbe (`ʼ`) selon les claviers. Dans ton app, choisis un seul symbole officiel (par exemple `ʼ`) et reste cohérent partout — mot, exemples, exercices.

**Exercice de lecture :** fais lire à voix haute la liste suivante et vérifie que l'apprenant marque bien la coupure de souffle : _gaaʼid, naʼarif, abad, udu, khabar, khazaala._

---

## Chapitre 3 — Les lettres à prononciation piégeuse

Quatre lettres existent en français, mais se prononcent différemment en arabe tchadien : **g, j, h, u**. Ce sont les fautes les plus fréquentes des débutants.

### `g` — toujours dure

La lettre **g** se prononce toujours comme dans "guitare", même devant **e** et **i**. Il ne faut donc **jamais** écrire "gu" devant e/i.

| Mot correct | Sens          | Faute fréquente à éviter                |
| ----------- | ------------- | --------------------------------------- |
| gelbi       | mon cœur      | ~~guelbi~~                              |
| girbe       | outre en peau | ~~guirbe~~                              |
| gechch      | paille        | ~~guechch~~                             |
| girgiit     | gros          | ~~guirguiit~~                           |
| guffa       | panier        | (ici "gu" est correct car suivi de "u") |

### `j` — se prononce "dj"

Le **j** correspond toujours au son français "dj". Il ne faut jamais écrire "dj" en toutes lettres.

| Mot correct | Sens      | Faute fréquente à éviter |
| ----------- | --------- | ------------------------ |
| jadiid      | neuf      | ~~djadiid~~              |
| jidaade     | poule     | ~~djidaade~~             |
| juwaad      | cheval    | ~~djouwaad~~             |
| jahal       | ignorance | ~~djahal~~               |
| Jibriin     | (prénom)  | ~~Djibrine~~             |

### `h` — toujours aspiré, jamais muet

La lettre **h** se prononce dans la gorge, comme un souffle net — contrairement au h muet du français.

| Mot   | Sens    |
| ----- | ------- |
| hatab | fagot   |
| habil | corde   |
| hille | village |
| huut  | poisson |
| haami | chaud   |

### `u` — se prononce "ou"

Il ne faut jamais écrire "ou" à la place du **u**.

| Mot correct | Sens       | Faute fréquente à éviter |
| ----------- | ---------- | ------------------------ |
| usum        | nom        | ~~ousoum~~               |
| umur        | âge        | ~~oumour~~               |
| umma        | communauté | ~~oumma~~                |
| suug        | marché     | ~~soug~~                 |
| juwaad      | cheval     | ~~jouwaad~~              |

**Exercice d'écriture :** dictée de 10 mots mêlant g/j/h/u, à corriger automatiquement dans l'app en comparant à l'orthographe attendue.

---

## Chapitre 4 — L'alphabet complet et le classement des mots

L'ordre alphabétique de l'arabe tchadien suit celui du français, avec des lettres composées insérées à des endroits précis :

```
a, b, ch, d, e, f, g, h, i, j, k, kh, l, m, n, o, p, r, s, t, tch, u, w, y, z, ʼ
```

**Règles de classement :**

- Les voyelles doublées (aa, ii, uu…) comptent comme une voyelle simple pour le tri (ex. _aafe_ se classe entre _afdal_ et _affan_).
- **ch** est traité comme une seule lettre, classée juste après **b**.
- **kh** est traité comme une seule lettre, classée juste après **k**.
- **tch** est traité comme une seule lettre, classée juste après **t**.
- **ʼ** est une lettre à part entière, classée en tout dernier, après **z**.

**Pourquoi c'est important pour ton app :** si tu affiches une liste alphabétique de mots ou un index, respecte cet ordre plutôt que l'ordre français standard — sinon un locuteur natif trouvera le classement bizarre (par exemple, un mot commençant par "ch" ne doit pas se retrouver mélangé avec les mots en "c" puisqu'il n'y a pas de "c" seul dans cette langue).

---

## Chapitre 5 — Lecture : comprendre une fiche de mot

Dans un lexique ou dans ton app, chaque mot est présenté avec sa catégorie grammaticale (abrégée) puis son sens en français.

**Principales abréviations à connaître :**

| Abréviation | Signification     |
| ----------- | ----------------- |
| n.m.        | nom masculin      |
| n.f.        | nom féminin       |
| n.pl.       | nom pluriel       |
| n.coll.     | nom collectif     |
| adj.        | adjectif          |
| v.tr.       | verbe transitif   |
| v.i.        | verbe intransitif |
| inacc.      | inaccompli        |
| impr.       | impératif         |
| pl.         | pluriel           |
| sg.         | singulatif        |
| dl.         | duel              |
| f.          | féminin           |
| adv.        | adverbe           |
| prép.       | préposition       |

**Exemples de fiches réelles à faire lire et commenter :**

```
abad        v.tr.   adorer Dieu       (inacc. yaʼabud / impr. aʼabud)
sirr        n.m.    secret            (pl. asraar)
muhimm      adj.    important         (f. muhimme / pl. muhimmiin / f.pl. muhimmaat)
adaan       n.f.    oreille           (dl. udunneen / pl. udne)
warag       n.coll. feuilles          (sg. waraga)
```

_Question de compréhension à poser dans l'app :_ « Dans la fiche du mot **adaan**, comment dit-on "deux oreilles" ? » → réponse : _udunneen_ (le duel).

---

## Chapitre 6 — Écriture : les règles orthographiques essentielles

Voici la synthèse à afficher comme "fiche mémo" et à réutiliser dans tous les exercices d'écriture :

1. **kh** pour le son guttural (khabar, khidime).
2. **ʼ** pour la coupure de gorge (gaaʼid, abad) — jamais oubliée, même au milieu d'un mot.
3. **g** toujours dur, jamais "gu" devant e/i (gelbi, pas guelbi).
4. **j** jamais "dj" (jadiid, pas djadiid).
5. **h** toujours prononcé, jamais muet (hatab, habil).
6. **u** = "ou" en français, jamais écrit "ou" (usum, pas ousoum).
7. Les voyelles doublées (aa, ii, uu) notent un son long — bien les distinguer d'une voyelle simple, car cela peut changer le sens du mot.

**Exercice d'écriture guidée :** propose une phrase orale simple (ex. _"Il a acheté du sel au marché"_) et demande à l'apprenant de l'écrire lui-même en s'appuyant sur cette fiche, puis compare avec la bonne orthographe.

---

## Chapitre 7 — Les noms : singulier, pluriel, duel, collectif

### Singulier et pluriel

Le pluriel **n'est jamais** une entrée séparée dans un dictionnaire : il faut retrouver la forme de base (singulier) pour chercher le sens. Les consonnes restent en général les mêmes, seules les voyelles changent.

| Singulier | Pluriel | Sens                            |
| --------- | ------- | ------------------------------- |
| sirr      | asraar  | secret(s)                       |
| jiraah    | juruuh  | blessure(s)                     |
| arnab     | araanib | lapin(s)                        |
| satur     | sutuur  | ligne(s) / vers                 |
| mara      | awiin   | femme(s) _(pluriel irrégulier)_ |

Certains mots ont **plusieurs pluriels** :

- **alif** (mille) → pluriel **aalaaf** _ou_ **uluuf**.
- **chuwaal** (sac) → pluriel **chawaawiil** _ou_ **chuwaalaat**.

### Le duel : parler de deux éléments exactement

Le duel se forme avec le suffixe **-een** et indique qu'il y a exactement deux éléments.

| Mot (singulier) | Duel       | Sens du duel      |
| --------------- | ---------- | ----------------- |
| adaan           | udunneen   | les deux oreilles |
| alif            | alfeen     | deux mille        |
| bahar           | bahreen    | deux fleuves      |
| bakaan          | bakaanteen | deux lieux        |
| chahar          | chahareen  | deux mois         |
| duraaʼ          | duraaʼeen  | deux bras         |

### Les noms collectifs et leur singulatif

Un nom collectif désigne un ensemble (espèce, matière, groupe de personnes). Pour parler d'un seul élément du groupe, on utilise le **singulatif**, formé avec le suffixe **-aay** ou **-a**.

| Collectif | Sens du collectif | Singulatif | Sens du singulatif     |
| --------- | ----------------- | ---------- | ---------------------- |
| warag     | feuilles          | waraga     | une feuille            |
| maal      | biens             | maalaay    | un bien                |
| faarʾ     | rats              | faaraay    | un rat                 |
| gazzaaz   | bouteilles        | gazzaaza   | une bouteille          |
| khanam    | moutons, chèvres  | khanamaay  | une chèvre / un mouton |

_Exercice pour l'app :_ un jeu « relie le collectif à son singulatif » (glisser-déposer) avec les paires ci-dessus, puis d'autres tirées du corpus complet.

---

## Chapitre 8 — Les adjectifs et leur accord

L'adjectif a jusqu'à 4 formes : masculin (forme de base), féminin, masculin pluriel, féminin pluriel.

| Forme de base (masc.) | Sens        | Féminin   | Masc. pluriel     | Fém. pluriel |
| --------------------- | ----------- | --------- | ----------------- | ------------ |
| muhimm                | important   | muhimme   | muhimmiin         | muhimmaat    |
| gawi                  | fort        | gawiiye   | gawiyiin          | —            |
| halu                  | doux        | haluuwe   | haluwiin          | —            |
| zaki                  | intelligent | zakiiye   | zakiyiin / azkiya | —            |
| garmaan               | nostalgique | garmaane  | garmaaniin        | —            |
| musardab              | bossu       | musardaba | musardabiin       | —            |

**Ce qu'il faut retenir :**

- Le féminin pluriel (colonne -aat) est rare en usage courant ; beaucoup d'adjectifs n'ont que 3 formes.
- Pour trouver le sens d'un adjectif accordé dans un texte, on enlève le suffixe pour retomber sur le masculin singulier, puis on cherche cette forme dans le dictionnaire.

_Exercice :_ donner une phrase avec un adjectif accordé (ex. _"la fille est gawiiye"_) et demander à l'apprenant d'identifier la forme de base (_gawi_) et son sens (_fort_).

---

## Chapitre 9 — Conjugaison : l'accompli (l'action terminée)

L'arabe tchadien ne fonctionne pas avec des "temps" (passé/présent/futur) mais avec deux **aspects** : l'accompli et l'inaccompli. Ce chapitre couvre l'accompli.

**L'accompli** indique que l'action est terminée. C'est la forme de base du verbe, toujours donnée à la 3ᵉ personne masculin singulier dans un dictionnaire.

### Tableau de conjugaison — verbe modèle `katab` (écrire)

| Personne             | Pronom | Forme conjuguée | Suffixe ajouté |
| -------------------- | ------ | --------------- | -------------- |
| 1 sg (je)            | ana    | katab**t**      | -t             |
| 2 masc sg (tu, m.)   | inta   | katab**t**      | -t             |
| 2 fém sg (tu, f.)    | inti   | katab**ti**     | -ti            |
| 3 masc sg (il)       | hu     | **katab**       | (aucun)        |
| 3 fém sg (elle)      | hi     | katab**at**     | -at            |
| 1 pl (nous)          | aniina | katab**na**     | -na            |
| 2 masc pl (vous, m.) | intu   | katab**tu**     | -tu            |
| 2 fém pl (vous, f.)  | intan  | katab**tan**    | -tan           |
| 3 masc pl (ils)      | humman | katab**o**      | -o             |
| 3 fém pl (elles)     | hinna  | katab**an**     | -an            |

**Règle d'or :** on part toujours de la forme de base (3ᵉ pers. masc. sg., sans suffixe) et on ajoute l'un des 8 suffixes : _-t, -ti, -at, -na, -tu, -tan, -o, -an_. Pour retrouver un verbe dans un dictionnaire à partir d'un texte, on enlève ce suffixe.

### S'entraîner avec d'autres verbes

Applique le même tableau de suffixes à ces verbes réels du corpus :

| Verbe (accompli, 3 masc. sg.) | Sens                | 1 sg (ana)  | 3 fém sg (hi) |
| ----------------------------- | ------------------- | ----------- | ------------- |
| rajjaʼ                        | faire revenir       | rajjaʼ**t** | rajjaʼ**at**  |
| daʼʼak                        | frotter             | daʼʼak**t** | daʼʼak**at**  |
| dawwad                        | être rempli de vers | dawwad**t** | dawwad**at**  |
| haddad                        | menacer             | haddad**t** | haddad**at**  |
| ajjan                         | pétrir              | ajjan**t**  | ajjan**at**   |

_Exercice pour l'app :_ affiche un pronom (ex. "hi") et un verbe à l'accompli (ex. "ajjan"), demande à l'apprenant de produire la forme conjuguée (_ajjanat_).

---

## Chapitre 10 — Conjugaison : l'inaccompli (l'action en cours)

**L'inaccompli** indique que l'action n'est pas encore terminée. Il garde les mêmes consonnes que l'accompli, mais ajoute un **préfixe** (et parfois un suffixe), avec des voyelles qui peuvent changer.

### Le mécanisme préfixe + suffixe

| Verbe à l'inaccompli | Préfixe | Suffixe | Forme de base (accompli) | Sens   |
| -------------------- | ------- | ------- | ------------------------ | ------ |
| yaktubu              | ya-     | -u      | katab                    | écrire |
| tamchi               | ta-     | -i      | macha                    | aller  |
| nacharbo             | na-     | -o      | chirib                   | boire  |

### Exemples réels du corpus, classés par type de préfixe

| Verbe (accompli) | Inaccompli | Sens                   |
| ---------------- | ---------- | ---------------------- |
| abad             | yaʼabud    | adorer Dieu            |
| saal             | yisiil     | couler                 |
| anhafad          | yinhafid   | être gardé             |
| rajjaʼ           | yirajjiʼ   | faire revenir          |
| daʼʼak           | yidaʼʼik   | frotter                |
| kajjaʾ           | yukujj     | se coiffer d'un turban |
| dawwad           | yidawwid   | être rempli de vers    |
| haddad           | yihaddid   | menacer                |
| akhad            | yaakhud    | épouser                |
| amar             | yaamur     | ordonner               |

**Méthode pratique face à un mot inconnu qui ressemble à un verbe conjugué :**

1. Identifier un préfixe reconnaissable (ya-, yi-, ta-, na-, yu-…).
2. Identifier un suffixe éventuel (-u, -i, -o…).
3. Retirer les deux mentalement pour reconstituer la forme de base.
4. Chercher cette forme de base dans le dictionnaire.

_Idée de fonctionnalité pour l'app :_ un « conjugueur inversé » — l'utilisateur tape un mot conjugué (ex. _yihaddid_), l'app détecte le préfixe _yi-_ et le suffixe _-id_ et propose _haddad_ comme forme à rechercher.

---

## Chapitre 11 — Conjugaison : l'impératif (donner un ordre)

L'impératif sert à donner un ordre ou une instruction directe. Dans le dictionnaire, il est souvent donné juste après l'inaccompli.

| Verbe (accompli) | Inaccompli | Impératif | Sens       |
| ---------------- | ---------- | --------- | ---------- |
| aba              | yaaba      | aaba      | refuser    |
| abad             | yaʼabud    | aʼabud    | adorer     |
| anbalas          | yinbalis   | anbalis   | s'échapper |
| aawan            | yiʼaawin   | aawin     | aider      |
| allag            | yiʼallig   | allig     | suspendre  |
| anjamma          | yinjamma   | anjamma   | se reposer |
| ajjan            | yiʼajjin   | ajjin     | pétrir     |

**Ce qu'il faut retenir :** l'impératif ressemble souvent à l'inaccompli débarrassé de son préfixe personnel (ya-/yi-), mais garde parfois une voyelle ou une consonne légèrement différente — c'est pourquoi il vaut mieux le mémoriser directement depuis la fiche du mot plutôt que de le déduire systématiquement.

_Exercice :_ transformer une phrase affirmative simple en ordre (ex. _"tu aides"_ → _"aawin !"_).

---

## Chapitre 12 — Un mot, plusieurs sens : homographes et polysémie

### Les homographes

Deux mots différents peuvent s'écrire pareil sans avoir le même sens. On les distingue par un petit numéro après le mot.

**Exemple réel du corpus :**

- **abad₁** _(v.tr.)_ = adorer Dieu
- **abad₂** _(n.m.)_ = pour toujours

### Les mots à plusieurs sens liés

Un seul mot peut avoir plusieurs sens proches, numérotés dans la même entrée (et non deux mots séparés) :

- **ibre** : 1) aiguille (à coudre) — 2) injection, vaccination
- **ajab** _(selon la catégorie grammaticale)_ : comme nom = miracle ; comme verbe = plaire

**Pour l'app :** afficher clairement le petit numéro d'homographe (abad₁ / abad₂) pour éviter la confusion, et regrouper les sens multiples d'un même mot sous une seule fiche numérotée plutôt que de créer une nouvelle fiche à chaque sens.

---

## Chapitre 13 — Récapitulatif et auto-évaluation

**Fiche mémo finale (à afficher en boucle ou en fin de parcours) :**

1. Deux sons spéciaux : **kh** (guttural) et **ʼ** (coup de glotte).
2. Quatre lettres à prononcer autrement qu'en français : **g** (toujours dur), **j** (= "dj"), **h** (aspiré, jamais muet), **u** (= "ou").
3. Ordre alphabétique propre : `a b ch d e f g h i j k kh l m n o p r s t tch u w y z ʼ`
4. Les noms ont singulier / pluriel (parfois plusieurs) / duel (**-een**) / collectif + singulatif (**-aay**, **-a**).
5. Les adjectifs s'accordent : base (masc.) / **-e,-a** (fém.) / **-iin** (masc. pl.) / **-aat** (fém. pl., rare).
6. Les verbes ont deux aspects : **accompli** (terminé, base + suffixe personnel) et **inaccompli** (en cours, préfixe + base + suffixe parfois), plus un **impératif** pour les ordres.
7. Attention aux homographes (numérotés) et aux mots à sens multiples.

**Quiz final suggéré (10 questions), à répartir ainsi :**

- 2 questions de reconnaissance de son (kh vs ʼ, à l'oral si possible)
- 2 questions d'orthographe (g/j/h/u)
- 2 questions sur pluriel/duel/collectif
- 2 questions sur l'accord des adjectifs
- 2 questions sur la conjugaison (donner l'accompli ou l'inaccompli d'un verbe)

---

---
# 8. Fine-tuning avec Unsloth Studio

`uv run td-arabic finetune {check,prepare,install,studio}`

Objectif : adapter un petit modèle de langage « instruct » pour qu'il **traduise entre le
français et l'arabe tchadien latinisé**. Le projet **prépare les données**. L'entraînement se fait
dans **[Unsloth Studio](https://unsloth.ai/docs/new/studio/install)**, l'application locale
officielle d'Unsloth.

## 8.1 Pourquoi Unsloth Studio

- **Un seul outil sur les trois systèmes** : Unsloth Studio entraîne sur macOS (MLX, puce Apple),
  sur Windows sans WSL et sur Linux (GPU NVIDIA). La bibliothèque Python d'Unsloth, elle,
  n'entraîne toujours pas sur Mac.
- **Séparé du projet** : Unsloth Studio s'installe dans son propre environnement
  (`~/.unsloth/studio`, ou `UNSLOTH_STUDIO_HOME`). L'installer ou le mettre à jour ne touche ni
  au studio du corpus, ni à l'API, ni aux dépendances du projet.
- **Interface complète** : choix du modèle, réglages LoRA, suivi de la perte, test du modèle et
  export (GGUF, Hugging Face) sont dans Unsloth Studio. Le studio du corpus n'a donc plus
  d'onglet Entraînement.

## 8.2 Installation automatique selon le système

```bash
uv run td-arabic finetune check              # système, GPU, Unsloth Studio installé ou non
uv run td-arabic finetune install --dry-run  # affiche la commande sans l'exécuter
uv run td-arabic finetune install            # installe (ou met à jour) Unsloth Studio
```

`install` lance l'installeur officiel du système détecté :

| Système | Commande exécutée | Pour entraîner |
| --- | --- | --- |
| macOS | `curl -fsSL https://unsloth.ai/install.sh \| sh` | Mac à puce Apple (M1–M5), macOS 12+, `git` et `cmake` (Homebrew) |
| Linux | `curl -fsSL https://unsloth.ai/install.sh \| sh` | GPU NVIDIA et son pilote, `cmake` et `build-essential` |
| Windows | `irm https://unsloth.ai/install.ps1 \| iex` (PowerShell) | GPU NVIDIA et son pilote, Visual Studio Build Tools 2022 |

Avant d'installer, la commande signale ce qui manque : outil absent, aucun GPU NVIDIA détecté
(`nvidia-smi`), ou Mac Intel (pas d'entraînement MLX). La même commande met à jour une
installation existante.

## 8.3 Préparer les données et entraîner

```bash
uv run td-arabic finetune prepare   # écrit data/finetune/train.jsonl et valid.jsonl
uv run td-arabic finetune studio    # lance Unsloth Studio sur http://127.0.0.1:8888
```

Dans Unsloth Studio, onglet **Local** :

1. chargez `data/finetune/train.jsonl` (format **chatml** ou **auto**) ;
2. choisissez le modèle de base et les réglages (ci-dessous) ;
3. lancez l'entraînement, puis testez et exportez le modèle depuis Unsloth Studio.

`valid.jsonl` contient des paires jamais vues à l'entraînement : il sert à l'évaluation. `--port`
change le port. Le jeton `HF_TOKEN` du fichier `.env` est transmis à Unsloth Studio, ce qui
accélère le téléchargement des modèles.

### Réglages conseillés (dans Unsloth Studio)

Ces réglages viennent des premiers essais faits avec ce corpus :

| Réglage | Valeur | Pourquoi |
| --- | --- | --- |
| Modèle | petit modèle « instruct » quantifié en 4 bits (Llama 3.2 1B sur Mac 16 Go, 3B avec un GPU) | tient en mémoire |
| Méthode | QLoRA, rang 16, alpha 16 | seuls les adaptateurs sont entraînés |
| Apprendre seulement les réponses (*train on completions / responses only*), si l'option est proposée | activé | les réponses font 1 à 3 mots : sans ce réglage, la perte baisse sans que le modèle apprenne à traduire |
| Passages (époques) | 2 ou plus | un vocabulaire se mémorise : un passage partiel ne voit qu'une partie des mots |
| Taux d'apprentissage | 2e-4 | |

## 8.4 Configuration : `configs/finetune.yaml`

Le fichier ne décrit que **les données**. Les réglages d'entraînement se font dans Unsloth Studio.

| Clé | Rôle | Défaut |
| --- | --- | --- |
| `seed` | graine du mélange des exemples d'entraînement | 3407 |
| `data.source` | `corpus` (paires de traduction) ou `dataset` (toutes les tâches, voir 8.5) | `corpus` |
| `data.include_lexicon`, `include_expressions`, `include_validated_sentences` | sources de la source `corpus` | phrases validées seulement |
| `data.tasks` | source `dataset` : tâches à garder (vide = toutes) | toutes |
| `data.directions` | `fr-ar`, `ar-fr` | les deux |
| `data.valid_ratio` | source `corpus` : part des paires gardées pour l'évaluation | 0,05 |
| `data.max_pairs` | nombre de paires d'entraînement (0 = toutes) | 0 |
| `data.system_prompt` | consigne système de chaque exemple | traduction, orthographe SIL |

## 8.5 Données d'entraînement

Chaque ligne de `train.jsonl` et `valid.jsonl` est une conversation au format **ChatML**, reconnu
directement par Unsloth :

```json
{"messages": [{"role": "system", "content": "Traduis entre le français et l'arabe tchadien…"},
              {"role": "user", "content": "Traduis en arabe tchadien : avoir honte"},
              {"role": "assistant", "content": "aab"}]}
```

Deux sources (`data.source`) :

- `corpus` (défaut) : les paires du corpus (`corpus_arabe_tchadien_francais.csv`, avec les ajouts
  **validés**) et les phrases **validées** de la banque. Les brouillons et les propositions non
  relues ne sont jamais utilisés. Par défaut, seules les phrases validées sont prises.
- `dataset` : toutes les tâches de `td-arabic dataset` (traduction, définition, flexion, forme de
  base, orthographe), sans les entrées signalées comme erreurs, avec le découpage par lemme et par
  gabarit du jeu de données. Voir [9.7](09-architecture-donnees.md#97-tâches-dentraînement-exportssft).
  Avec cette source, prendre une consigne système générale.

Et pour les deux sources :

- **Deux sens** : français → arabe tchadien et arabe tchadien → français.
- **Nombre de paires** (`data.max_pairs`) : les paires sont choisies au hasard mais toujours les
  mêmes, et les sous-ensembles sont **emboîtés** (les 100 font partie des 1 000). On peut donc
  comparer des modèles entraînés sur des quantités croissantes. L'évaluation ne change pas.
- **Séparation par paire** : les deux sens d'une même paire sont toujours du même côté. La
  séparation est un hachage de l'identifiant : elle reste **stable** quand on ajoute des paires.
- Si `prepare` ne trouve aucun exemple (banque vide, lexique désactivé), il le dit.

## 8.6 Limites et précautions

- **Données surtout lexicales** : le lexique apprend des mots, pas des phrases. Les phrases
  validées de la banque sont indispensables pour un vrai traducteur de phrases.
- **Unsloth Studio est un outil externe** : il est installé par son installeur officiel. Le
  projet ne le teste pas, il vérifie seulement sa présence et le lance.
- **Licences** : les modèles Llama 3.2 sont sous licence *Llama 3.2 Community License*. Les
  données dérivent du lexique SIL Tchad (voir [éthique et licences](05-ethique-licences.md)) : ne
  pas publier de modèle entraîné sans l'accord requis.

---

# 9. Architecture des données pour l'entraînement

`uv run td-arabic dataset` → `data/dataset/`

## 9.1 Le problème

Le corpus actuel est **une ligne = un mot + une définition** (`lexique_final.csv`,
`corpus_arabe_tchadien_francais.csv`). Ce format suffit pour chercher un mot. Il ne suffit pas pour
entraîner un modèle :

| Constat dans les données | Conséquence pour l'entraînement |
| --- | --- |
| Les formes (`pl. buyud`, `inacc. yaktib`) sont une chaîne de texte | le modèle ne voit jamais que *buyud* est le pluriel de *abyad* |
| Plusieurs mots ont la même glose (`témoigner` → *chahad*, *chihid*) | deux exemples `fr→td` qui se contredisent |
| Erreurs d'extraction (`reine malika al-umm n.f. reine mère`, `chauve- souris`, entrées rangées sous la mauvaise lettre) | le modèle apprend les erreurs |
| Les corrections sont faites dans des CSV à part, sans trace commune | on ne sait pas ce qui a été vérifié |
| Les 5 099 phrases viennent de ~100 gabarits et le découpage est fait au hasard | des phrases presque identiques en entraînement et en évaluation : un score trop optimiste |
| Une seule tâche (traduire) | le modèle ne connaît ni la morphologie ni l'orthographe |

## 9.2 Les modèles dont on s'inspire

| Source | Ce qu'on en reprend |
| --- | --- |
| **LIFT** (format lexical de SIL, FieldWorks) et **OntoLex-Lemon** (W3C) | arbre entrée → formes → sens → exemples ; homographes = entrées distinctes |
| **Wiktionnaire / kaikki.org** (JSONL) | une entrée par ligne ; formes étiquetées par `tags` normalisés (`plural`, `feminine`, `imperfective`…) |
| **Universal Dependencies** | catégorie universelle `upos` (NOUN, VERB, ADJ…) à côté de l'abréviation du lexique |
| **FLORES-200 / NLLB** | codes de langue `shu_Latn`, `shu_Arab`, `fra_Latn` (ISO 639-3 *shu* = arabe tchadien) ; découpage `dev` / `devtest` figé |
| **MADAR** (arabe dialectal, 25 villes) et **MAFAND-MT** (langues africaines) | phrases parallèles avec domaine, provenance ; format Hugging Face `translation` |
| **FLAN / Aya** | plusieurs tâches et plusieurs formulations de consigne à partir des mêmes données |
| **Datasheets for Datasets** (Gebru et al.) | la provenance et la qualité de chaque enregistrement sont dans les données, pas à côté |

## 9.3 Organisation

```
data/
  raw/          PDF SIL (ne jamais modifier)
  interim/      extraction brute (td-arabic extract)
  processed/    lexique et corpus plats (td-arabic build-corpus)
  resources/    saisies humaines : corrections, expressions, ajouts, gabarits
  sentences/    banque de phrases (brouillon / validée / rejetée)
  dataset/      ← GÉNÉRÉ par td-arabic dataset, jamais édité à la main
    lexicon/entries.jsonl        une entrée lexicale par ligne
    corpus/sentences.jsonl       une paire de phrases par ligne
    annotations/issues.jsonl     les erreurs : détectées, corrigées, ouvertes
    exports/sft/{train,dev,test,probe}.jsonl   exemples « messages », toutes tâches
    exports/mt/{train,dev,test}.jsonl          paires au format Hugging Face « translation »
    stats.json
```

Règle : **on corrige la source, jamais le généré.** Une erreur se corrige dans `data/resources`
(ou la banque de phrases), puis on relance la commande.

## 9.4 Entrée lexicale (`lexicon/entries.jsonl`)

```json
{
  "id": "td:abyad",
  "lemma": {"shu_Latn": "abyad", "shu_Arab": null},
  "homograph": null,
  "pos": "adj.", "upos": "ADJ", "features": {},
  "forms": [
    {"form": "beeda", "tags": ["feminine"], "label": "f."},
    {"form": "buyud", "tags": ["plural"], "label": "pl."}
  ],
  "senses": [
    {"id": "td:abyad/s1", "definition_fr": "blanc", "glosses_fr": ["blanc"],
     "origin": "pdf", "examples": [], "trainable": true}
  ],
  "expressions": [
    {"id": "td:abyad/x1", "text": "abyad karr", "gloss_fr": "très blanc", "glosses_fr": ["très blanc"]}
  ],
  "provenance": {"source": "sil-tchad-2021", "origin": "pdf", "page": 16, "column": "left", "section": "A a"},
  "quality": {"status": "extracted", "ligature_reconstructed": false, "flags": [], "trainable": true}
}
```

- **Homographes** (`abad1` verbe, `abad2` nom) : deux entrées, `td:abad#1` et `td:abad#2`.
- **Sens** : un ajout validé (`ajouts_corpus.csv`) sur un mot déjà connu, avec la même catégorie,
  devient un **sens de plus** de l'entrée (`origin: "ajout"`) au lieu d'une ligne isolée.
- **Gloses** : les virgules du lexique séparent des quasi-synonymes d'un même sens
  (`"grue, ibis"`) ; `glosses_fr` les découpe (sauf entre parenthèses).
- **`shu_Arab`** : le PDF donne aussi chaque mot en écriture arabe, mais la police (Scheherazade) est
  encodée sans table Unicode : le texte n'est pas récupérable sans OCR. Le champ est prévu, vide.
- **`examples`** : prévu pour relier les phrases validées à chaque sens.

## 9.5 Phrase (`corpus/sentences.jsonl`)

```json
{
  "id": "phr:mar-1a2b3c4d",
  "text": {"shu_Latn": "Ana nachri sukkar.", "shu_Arab": null, "fra_Latn": "J'achète du sucre."},
  "domain": "marche",
  "lemmas": [{"lemma": "chara", "entries": ["td:chara"]}],
  "out_of_lexicon": [],
  "provenance": {"origin": "template", "template_id": "mar-achat", "created": "…", "modified": "…"},
  "quality": {"status": "validated", "flags": ["ambiguous_source"], "trainable": true},
  "group": "tpl:mar-achat"
}
```

`group` décide du découpage : toutes les phrases d'un même gabarit vont du même côté (train, dev
ou test). Les phrases de test ont donc une **structure** jamais vue à l'entraînement.

## 9.6 Les erreurs comme données (`annotations/issues.jsonl`)

```json
{"id": "iss:…", "target": "td:malika/s1", "field": "definition_fr", "type": "merged_entries",
 "severity": "error", "evidence": "reine malika al-umm n.f. reine mère", "suggestion": null,
 "status": "open", "detector": "auto:pos_in_definition", "note": "…"}
```

| `type` | Détection | Gravité | Traitement |
| --- | --- | --- | --- |
| `merged_entries` | une abréviation (`n.f.`, `conj.`…) dans une définition | error | exclu de l'entraînement tant qu'il est ouvert |
| `line_break_hyphen` | `chauve- souris` (coupure de ligne du PDF) | warning | corrigé automatiquement (`fixed`) |
| `wrong_section` | l'initiale du mot ne correspond pas à la lettre de la section (pages où deux lettres se suivent : E/F, O/P/R, Tch/U) | info | corrigé automatiquement |
| `ligature_reconstructed` | fi/ff/fl reconstruits à l'extraction | info | à vérifier sur le PDF |
| `unlabelled_form`, `unknown_pos` | forme sans étiquette, catégorie vide | warning | à compléter |
| `spelling` | `dj`, `ou`, `gu` devant e/i, `'` dans un ajout ou une phrase (règles du préambule du lexique) | warning | correction proposée |
| `duplicate` | même paire de phrases deux fois | error | la copie est exclue |
| `ambiguous_source` | une phrase française, plusieurs traductions (genre, nombre) | info | gardé : les deux sont justes |
| `unknown_lemma` | un lemme de la phrase absent du lexique | warning | à relier |

Les corrections faites à la main (`corrections_entrees.csv`) y figurent avec `status: "fixed"` et
`detector: "manuel:corrections_entrees"`. Le même problème garde le même `id` d'une construction à
l'autre, ce qui permet de suivre ce qui a été traité.

Un enregistrement est **entraînable** (`quality.trainable`) s'il n'a aucune erreur `error` ouverte
et si ce n'est ni un brouillon ni une phrase rejetée.

## 9.7 Tâches d'entraînement (`exports/sft`)

Chaque ligne : `{"id", "task", "split", "messages": [system, user, assistant], "source_ids", …}`,
`td-arabic finetune prepare` en garde les `messages` (format ChatML) pour Unsloth Studio.

| Tâche | Exemple | Découpage |
| --- | --- | --- |
| `traduction_mot` | « Comment dit-on « témoigner » ? » → `chahad / chihid` | `probe` |
| `definition` | `abyad` → `adj. blanc (f. beeda, pl. buyud)` | `probe` |
| `flexion` | « Donne le pluriel de « abyad ». » → `buyud` | par lemme |
| `lemmatisation` | `buyud` → `abyad (pluriel de abyad)` | par lemme |
| `orthographe` | `djambah` → `jambah` | par lemme |
| `traduction_phrase` | phrase fr ↔ td | par gabarit |

- **Un mot jamais vu ne peut pas être traduit** : les tâches de vocabulaire sont toutes entraînées,
  et `probe` (5 % fixes des exemples d'entraînement) mesure la **mémorisation**.
- Morphologie et orthographe sont découpées **par lemme** : `dev` et `test` mesurent si le modèle
  **généralise** à des mots qu'il n'a pas vus fléchis.
- Les phrases sont découpées **par gabarit** (10 % dev, 10 % test : une centaine de gabarits de
  tailles très inégales).
- Le découpage est un hachage de l'identifiant du groupe : ajouter des données ne déplace jamais
  les anciennes.
- Les fautes d'orthographe sont l'inverse des règles du préambule du lexique (« écrivez *jambah* et
  non *djambah* », *guffa* et non *gouffa*, *gelbi* et non *guelbi*, voyelles longues doublées,
  coupure de gorge `ʼ`).

**Entraîner sur ces tâches** : `data.source: dataset` dans `configs/finetune.yaml`.
`td-arabic finetune prepare` reconstruit alors
`data/dataset`, puis prend `train` pour l'entraînement et `dev` + `probe` pour l'évaluation ;
`test` n'est jamais utilisé. `data.tasks` choisit les tâches, `data.directions` filtre les tâches
de traduction, `data.max_pairs` limite le nombre de mots et de phrases. La consigne système de
chaque exemple est remplacée par `data.system_prompt`, à réutiliser pour interroger le modèle : la choisir
générale (pas seulement « Traduis… »).

`exports/mt` donne les mêmes paires au format Hugging Face (`{"translation": {"fra_Latn": …,
"shu_Latn": …}}`) pour les modèles de traduction (NLLB, mT5).

## 9.8 Suite

1. **Sens fusionnés sans marque** : `ibre` « aiguille injection, vaccination », `darar` « jalousie
   entre co-épouses perte, impact négatif ». Le préambule du lexique dit que ces sens sont numérotés
   1 et 2 (c'est son exemple pour `ibre`), mais l'extraction n'a pas gardé les numéros. Ce n'est pas
   détectable automatiquement : à relever lors de la validation page
   par page (type `merged_senses`).
2. **Phrases naturelles** : toutes les phrases viennent de gabarits. Il faut des phrases dites ou
   écrites par des locuteurs (contes, proverbes, conversations enregistrées), avec la région du
   locuteur, comme MADAR. Sinon le modèle n'apprendra que les gabarits.
3. **Écriture arabe** : OCR des mots en écriture arabe du PDF pour remplir `shu_Arab`
   (translittération latin ↔ arabe).

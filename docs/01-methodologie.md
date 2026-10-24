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

*Lexique arabe tchadien – français*, SIL Tchad, 11e édition, 2021 (PDF de 171 pages) :

| Pages | Contenu | Traitement |
| --- | --- | --- |
| 1–14 | Préambule, notes de prononciation et de grammaire | texte conservé (`lexique_texte_complet.txt`) |
| 15–171 | Dictionnaire sur deux colonnes, 25 sections alphabétiques (A, B, Ch, …, Tch, …, Z) | entrées structurées |

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

| Indice typographique | Interprétation |
| --- | --- |
| CharisSIL,Bold ~11 pt **sur la marge** de la colonne | début d'une nouvelle entrée |
| même police, **indentée** | sous-entrée / expression (rattachée à l'entrée) |
| chiffre < 9 pt collé au mot-vedette | numéro d'homographe (`abad¹`, `abad²`) |
| CharisSIL,Bold ~10 pt après `pl.`, `f.`, `inacc.`… | valeur d'une forme fléchie |
| police ≥ 13 pt | titre de section (« A a », « Tch tch ») |
| `top` < 45 pt | en-tête de page (ignoré) |

Difficultés résolues :

- **Colonnes à marges miroir** : les pages paires sont décalées de 13,9 pt. La frontière
  est recalculée par page à partir des deux positions `x0` les plus fréquentes des
  mots-vedettes.
- **Texte arabe inexploitable** : la police ScheherazadeNew a un mappage CID → Unicode
  cassé ; le texte arabe est écarté (seule la translittération latine est utilisée).
- **Ligatures latines** sans Unicode : `(cid:19)` → *fi*, `(cid:30)` → *ff*,
  `(cid:31)` → *ffi*, `)` au milieu d'un mot gras → *fl* (`kha)a` → *khafla*).
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
  les seules différences sont les 5 corrections de ligature *fl*. Le corpus final contient
  les mêmes 4 909 paires que celui produit par l'ancien notebook, une fois retirés les
  marqueurs artificiels d'homographes (voir ci-dessous).

## 1.6 Changements par rapport à la v0.1 (notebook)

| v0.1 | v0.2 | Raison |
| --- | --- | --- |
| homographe 2 noté par un `ʾ` final (`abadʾ`), le 3 gardait son chiffre (`tchakka3`) | `src = abad`, `sense_number = 2` | les sens 2 et 3 étaient introuvables par l'API (ex. `hatta` sens 2) |
| découpage des expressions dans le notebook (code automatique jamais utilisé) | fichier CSV de découpages validés + liste à vérifier | traçabilité, pas de code mort |
| `)` → `fl` corrigé seulement si le mot-vedette en contenait | correction à l'extraction, partout | `fiilim` pl. `a)aam` → `aflaam` |
| `n.f` et `n.f.` coexistaient | catégorie normalisée `n.f.` | cohérence |
| expressions ajoutées en fin de fichier | expressions placées après leur entrée mère | lisibilité |

## 1.7 Limites connues

- Quelques définitions contiennent encore une sous-entrée non séparée
  (ex. `ambaakir` : « demain ambaakirtah adv. le lendemain », `beet` : « maison comp. … »).
- Les pages 15–171 n'ont pas toutes été relues avec l'application de validation.
- Le lexique ne donne que la 3e pers. masc. sg. de l'inaccompli ; les autres personnes sont
  dérivées par règle (préfixes `n-`, `t-`) et restent à confirmer par un locuteur pour les
  verbes irréguliers.

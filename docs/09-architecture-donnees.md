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

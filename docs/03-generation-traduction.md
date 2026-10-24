# 3. Génération et traduction de phrases

## 3.1 Traduction de mots

`td-arabic translate <mot>` · API `GET /translate?q=…&direction=auto|ar-fr|fr-ar`

Recherche en cascade (`src/td_arabic/translation/lexicon.py`) :

| Étape | Statut renvoyé | Exemple |
| --- | --- | --- |
| 1. exacte (avec ou sans article `al-`/`l-`) | `exact_match` | `al-suug` → marché |
| 2. forme fléchie du lexique | `form_match` | `aswaag` → marché (*pluriel de suug*) |
| 2b. inaccompli conjugué (`n-`, `t-` à la place de `y-`) | `form_match` | `nachri` → acheter (*1re pers. sg.*) |
| 3. floue (RapidFuzz, ratio ≥ 50, 5 suggestions) | `no_exact_match` | `oogid` → `oogiid` allumette |
| — | `no_match` | |

Côté français, chaque glose est indexée entière et par parties (`cher, coûteux` → `cher`,
`coûteux`), sans les parenthèses (`toi (masc)` → `toi`).

## 3.2 Traduction de phrases (glose assistée)

`td-arabic translate "phrase"` · API `GET /translate/sentence` · onglet *Traduire* du studio

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

`td-arabic generate -t <thème> -n <nombre> --seed <graine> [--save]` · onglet *Générer*

### Principe

Des **gabarits** bilingues (`data/resources/themes.yaml`) sont remplis avec des mots du
lexique. Règle de conception : **aucun mot arabe tchadien n'est inventé**.

- Chaque mot td d'un gabarit ou d'une liste de vocabulaire est un mot-vedette du lexique
  (vérifié par les tests).
- L'**inaccompli** conjugué vient de la forme `inacc.` du lexique (3e pers. masc. sg.), à
  laquelle on applique la règle des préfixes personnels (cours, chap. 10) :
  `yachri` → *ana* **n**achri, *inta* / *hi* **t**achri, *hu* **y**achri.
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
et **mots hors lexique** (ex. `aleekum` dans *Salaam aleekum*). Statut initial : `brouillon`.

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

| Thème | Exemples | Phrases possibles |
| --- | --- | --- |
| `salutations` | *Inta aafe?* — Tu vas bien ? · *Kikkeef al-ahal?* — Comment va la famille ? | 17 |
| `marche` | *Hi tachri sukkar.* — Elle achète du sucre. · *Al-rizz be kam?* — Combien coûte le riz ? | 1198 |
| `journee` | *Ana nakhdim fajur.* — Je travaille tôt le matin. · *Hu yachrab almi.* — Il boit de l'eau. | 382 |
| `temps` | *Al-wata haamiye.* — Il fait chaud. · *Ambaakir al-matar yaji.* — Demain, il va pleuvoir. | 11 |
| `deplacements` | *Inta tamchi al-hille.* — Tu vas au village. · *Al-suug ween?* — Où est le marché ? | 48 |
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
    - {td: tamur, fr: {part: "des dattes", def: "les dattes"}}

themes:
  cuisine:
    titre: À la cuisine
    gabarits:
      - id: cui-manger
        td: "{P} {V} {N}."          # pronom, verbe conjugué, nom
        fr: "{V} {N.part}."         # le verbe français inclut son sujet
        verbes: [manger]
        slots: {N: fruits}
    phrases:                        # phrases figées validées
      - {td: "…", fr: "…"}
```

Puis `uv run pytest tests/test_generation.py` : les tests vérifient que chaque mot existe
dans le lexique et que chaque gabarit se génère sans erreur.

## 3.4 Cycle de validation

```
gabarit / traduction / saisie ──► brouillon ──(relecture par un locuteur)──► validee ──► enregistrement
                                       └──────────────────────────────────► rejetee
```

L'onglet *Phrases* du studio permet de corriger le texte td ou fr et de changer le statut.
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

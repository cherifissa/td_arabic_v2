# Échantillon public

Petit extrait des données, publié pour montrer leur **format**. Le corpus complet se
reconstruit avec `uv run td-arabic pipeline` à partir du PDF du lexique (voir le
[README](../../README.md)).

| Fichier | Lignes | Extrait de |
| --- | --- | --- |
| `phrases_echantillon.csv` | 24 | `data/sentences/phrases.csv` (banque de phrases) |

## `phrases_echantillon.csv`

Phrases produites par les gabarits de `data/resources/themes.yaml`, deux par thème
(12 des 14 thèmes), au statut `validee`, tirées de la banque de 4 858 phrases.

| Colonne | Contenu |
| --- | --- |
| `id` | identifiant stable (préfixe du thème + empreinte) |
| `theme` | thème du gabarit |
| `template_id` | gabarit d'origine |
| `fr` / `td` | phrase en français / en arabe tchadien latinisé |
| `lemmes` | mots-vedettes du lexique utilisés, séparés par `;` |
| `hors_lexique` | mots absents du lexique (formules figées, etc.) |
| `statut` | `brouillon`, `validee` ou `rejetee` |
| `source` | `gabarit` (généré) ou saisie manuelle |

## Source et droits

Les phrases sont écrites par l'auteur à partir de gabarits ; leurs mots viennent du
*Lexique arabe tchadien – français* (SIL Tchad, 11e édition, 2021). Aucune paire du lexique
n'est publiée ici tant que SIL Tchad n'a pas donné son accord ; le format des paires est
décrit dans la [fiche de données](../../docs/02-corpus-datasheet.md).

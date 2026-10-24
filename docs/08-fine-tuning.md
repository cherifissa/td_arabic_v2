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

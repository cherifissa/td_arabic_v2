# 7. Feuille de route de recherche

## Questions de recherche envisagées

1. Dans quelle mesure un lexique bilingue d'apprentissage (~4 700 entrées) permet-il
   d'amorcer un corpus parallèle de phrases pour une langue peu dotée ?
2. Quel gain apporte l'adaptation de modèles multilingues de reconnaissance vocale
   (ex. MMS, Whisper) avec quelques heures de parole en arabe tchadien multi-locuteurs ?
3. Quelle est l'influence de la variation régionale et du profil des locuteurs sur ces
   performances ?

## Étapes

| Étape | Livrable | État |
| --- | --- | --- |
| Extraction et structuration du lexique SIL | `data/processed/` | fait (v0.2) |
| Outils : traduction de mots / phrases, API | `td-arabic translate`, API | fait (v0.2) |
| Génération de phrases thématiques | `themes.yaml`, studio | fait — 14 thèmes, 4 858 phrases |
| Studio d'enregistrement multi-locuteurs | `td-arabic studio` | fait (v0.2) |
| Données de fine-tuning (ChatML) | `td-arabic finetune prepare` | fait |
| Dépôt public : README, échantillon, fiche de données | `data/samples/`, docs | fait |
| Relecture complète de l'extraction (pages 15–171) | `data/validation/` | en cours |
| Autorisation de diffusion SIL Tchad | accord écrit | à faire |
| Protocole éthique et formulaire de consentement | `docs/ethique/` | rédigé — validation par un comité d'éthique à faire |
| Collecte audio pilote (5 à 10 locuteurs) | `data/audio/` | à faire |
| Validation des phrases par plusieurs locuteurs (accord inter-annotateurs) | statistiques | à faire |
| Expériences ASR (MMS / Whisper, ajustement fin) | WER / CER | à faire |
| Expériences de traduction (NLLB, mT5 + lexique) | BLEU / chrF | à faire |

## Dépendances pour les expériences

`uv sync --extra ml` installe transformers, datasets, evaluate, sacrebleu, sentencepiece,
accelerate et scikit-learn.

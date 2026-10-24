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

   | Réglage | Défaut | Conseil |
   | --- | --- | --- |
   | Fréquence d'échantillonnage | 16 000 Hz | 16 kHz pour l'ASR ; 22 050 ou 44 100 Hz pour la synthèse vocale |
   | Couper les silences début/fin | oui | |
   | Seuil de silence | −40 dB | monter vers −30 dB dans un lieu bruyant, descendre pour une voix faible |
   | Marge conservée | 150 ms | silence laissé avant et après la parole |
   | Normaliser le volume | oui | crête ramenée à −1 dBFS |

3. **Phrases** — valider les phrases à lire.
4. **Enregistrer** — choisir le locuteur (et éventuellement des thèmes). La phrase s'affiche
   en grand en arabe tchadien, la traduction en dessous. Cliquer sur le micro, lire, arrêter :
   la prise est traitée et sauvegardée, puis réécoutable. *Phrase suivante* pour continuer.
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

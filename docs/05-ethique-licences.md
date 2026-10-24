# 5. Éthique, consentement et licences

## 5.1 Données lexicales : droits de SIL Tchad

Le corpus textuel est **dérivé** du *Lexique arabe tchadien – français* (SIL Tchad, 2021).
Ce document est protégé par le droit d'auteur. Avant toute diffusion publique du PDF ou des
fichiers de `data/interim/` et `data/processed/` il est envisager de :

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
dehors des formules de politesse courantes (*in cha Allah*, *hamdulillah*). Les phrases
générées sont relues avant d'être enregistrées.

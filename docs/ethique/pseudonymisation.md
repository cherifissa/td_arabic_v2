# Méthode de pseudonymisation des locuteurs

La voix est une donnée personnelle. Ce document décrit comment le projet sépare
l'identité des locuteurs de leurs enregistrements, et ce qui est vérifié avant toute
publication. Il complète le [formulaire de consentement](formulaire-consentement.md) et
la section 5.2 de [éthique et licences](../05-ethique-licences.md).

**Pseudonymisation n'est pas anonymisation** : une voix reste reconnaissable. Le but est
qu'aucun fichier du corpus ne permette, à lui seul, de retrouver le nom d'une personne.

## 1. Deux espaces séparés

| Espace | Contenu | Où | Accès |
| --- | --- | --- | --- |
| **Identité** | formulaires signés, nom réel, contact, table de correspondance `nom ↔ spkNNN` | hors du dépôt, sur un support chiffré (ou papier sous clé) | responsable du projet uniquement |
| **Corpus** | `data/audio/locuteurs.json`, `metadata.csv`, fichiers WAV | `data/audio/` (exclu de Git par `.gitignore`) | équipe de recherche |

Le code ne stocke **jamais** de nom réel : le studio d'enregistrement ne propose pas de champ
pour cela.

## 2. Identifiant et pseudonyme

- Chaque locuteur reçoit un identifiant séquentiel `spk001`, `spk002`, … attribué
  automatiquement (`SpeakerRegistry.next_id` dans `src/td_arabic/recording/speakers.py`).
  L'identifiant ne contient que des minuscules, des chiffres, `-` ou `_` (contrôle à
  l'enregistrement).
- L'ordre des identifiants ne suit aucune information personnelle (ni âge, ni lieu).
- Le **pseudonyme** sert seulement à reconnaître la personne dans le studio pendant les
  séances. Il ne doit pas être dérivé du vrai nom (pas d'initiales, pas de surnom connu) et
  il **n'apparaît pas** dans `metadata.csv`.

## 3. Métadonnées minimales

| Information | Stockée sous la forme | Jamais stockée |
| --- | --- | --- |
| Âge | tranche : `18-25`, `26-35`, `36-50`, `51-65`, `65+` | date de naissance, âge exact |
| Origine | ville ou région (`N'Djamena`, `Abéché`…) | adresse, quartier |
| Genre | `femme`, `homme` ou `autre / non précisé` (facultatif) | — |
| Langues | langue première, autres langues | — |
| Consentement | case cochée + date (automatique) | signature, nom |

Les mineurs ne sont pas enregistrés (pas de tranche d'âge en dessous de 18 ans).

## 4. Garde-fous dans le code

- **Pas de consentement, pas d'enregistrement** : `AudioDataset.save_take` lève
  `ConsentError` si le profil n'a pas le consentement coché
  (`src/td_arabic/recording/dataset.py`).
- **Noms de fichiers neutres** : `wavs/<spkNNN>/<id_phrase>.wav`, sans nom ni date.
- **Contenu neutre** : les phrases lues sont générées par gabarits ; elles ne contiennent ni
  nom réel, ni information personnelle, ni sujet sensible (religion, politique, santé d'une
  personne réelle) en dehors des formules de politesse courantes.
- **Exclusion de Git** : `data/audio/` est dans `.gitignore`.

## 5. Avant toute publication du corpus audio

1. Vérifier que chaque locuteur publié a coché la case « corpus ouvert » du formulaire ;
   retirer les autres.
2. Retirer la colonne `pseudo` et `locuteurs.json` ; ne publier que `metadata.csv` et les WAV.
3. Réécouter un échantillon de prises : aucune parole hors phrase (nom prononcé, échange
   avec l'enquêteur, bruit identifiant un lieu).
4. Vérifier qu'aucune combinaison de métadonnées ne désigne une seule personne (par
   exemple une seule femme de 65+ ans d'une petite ville) ; si oui, élargir la région ou la
   tranche d'âge pour cette personne.
5. Faire relire la liste par une seconde personne.

## 6. Droit de retrait

À la demande d'un locuteur (identifié par son `spkNNN`, retrouvé dans la table de
correspondance) :

1. supprimer `data/audio/wavs/<spkNNN>/` ;
2. supprimer ses lignes de `metadata.csv` et son profil dans `locuteurs.json` ;
3. noter la date du retrait dans la table de correspondance (sans conserver la voix) ;
4. exclure ses données des versions suivantes de tout corpus publié et de tout modèle
   réentraîné.

# Notebooks

`explore_lexique_entries.ipynb` est le notebook d'exploration historique (v0.1), réécrit et
commenté étape par étape. Son traitement est désormais reproduit, et corrigé, par
`src/td_arabic/lexicon/corpus.py` (`td-arabic build-corpus`) ; voir
docs/01-methodologie.md, section 1.6. Il est conservé pour la traçabilité et n'est plus
nécessaire au pipeline.

Le notebook :

- se lance depuis la racine du projet ou depuis `notebooks/` ;
- lit `data/interim/lexique_entries.csv` et écrit **uniquement** dans
  `data/interim/notebook_v01/` (jamais dans `data/processed/`) ;
- vérifie ses résultats contre le pipeline (dernière étape) : ils concordent, à l'harmonisation
  `n.f` → `n.f.` près ;
- documente en tête les différences avec la première version.

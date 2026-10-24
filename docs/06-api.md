# 6. Référence de l'API REST

```bash
cp .env.example .env     # définir API_KEY
uv run td-arabic serve   # http://127.0.0.1:8000 — Swagger : /docs, ReDoc : /redoc
```

Toutes les routes sauf `/health`, `/docs`, `/redoc` et `/openapi.json` exigent l'en-tête
`X-API-Key`. Sans `API_KEY` configurée, l'API refuse les requêtes (pas de clé par défaut).

| Méthode | Route | Paramètres | Rôle |
| --- | --- | --- | --- |
| GET | `/health` | — | état et nombre d'entrées |
| GET | `/translate` | `q`, `direction` = `auto` \| `ar-fr` \| `fr-ar` | traduction d'un mot ou d'une expression |
| GET | `/translate/sentence` | `text`, `direction` = `fr-ar` \| `ar-fr` | glose d'une phrase |
| GET | `/generation/themes` | — | thèmes disponibles |
| GET | `/generation` | `theme` (répétable), `n` (1-200), `seed` | phrases générées |

## `/translate`

Format compatible avec la v0.1 ; ajouts : statut `form_match`, champs `direction` et `note`.

```bash
curl -H "X-API-Key: $API_KEY" "http://127.0.0.1:8000/translate?q=nachri"
```

```json
{
  "query": "nachri",
  "status": "form_match",
  "word": "chara",
  "translations": [
    {"output": "acheter", "pos": "v.tr.", "sense_number": null, "forms": "inacc. yachri",
     "direction": "ar-fr", "note": "inaccompli (1re pers. sg.) de chara"}
  ]
}
```

`status` : `exact_match`, `form_match`, `no_exact_match` (avec `suggestions` : `word`,
`translations`, `similarity`) ou `no_match`.

## `/translate/sentence`

```json
{
  "source": "Ana nachri laham",
  "direction": "ar-fr",
  "gloss": "Je acheter viande",
  "coverage": 1.0,
  "segments": [
    {"source": "ana", "match": "exact", "candidates": [{"text": "je", "pos": "pron.", "...": "..."}]},
    {"source": "nachri", "match": "forme", "candidates": ["..."]}
  ]
}
```

## `/generation`

```bash
curl -H "X-API-Key: $API_KEY" "http://127.0.0.1:8000/generation?theme=marche&n=2&seed=42"
```

```json
[
  {"id": "mar-…", "theme": "marche", "template_id": "mar-achat",
   "fr": "Elle achète du sucre.", "td": "Hi tachri sukkar.",
   "lemmes": ["chara", "sukkar"], "hors_lexique": [], "statut": "brouillon", "source": "gabarit"}
]
```

## Codes d'erreur

| Code | Cas |
| --- | --- |
| 403 | clé absente ou invalide |
| 404 | thème inconnu |
| 422 | paramètre invalide |
| 500 | `API_KEY` non configurée |

## Migration depuis l'ancienne API (`chad_arabic_translation`)

- `GET /translate?q=` : inchangé pour les clients existants (mêmes champs).
- Plus de clé par défaut `default_api_key` ; route de test `/test-error` supprimée.
- Lancement : `uv run td-arabic serve` au lieu de `uvicorn main:app`.

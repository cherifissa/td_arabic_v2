"""REST API (FastAPI): word and sentence translation, sentence generation.

Run with ``td-arabic serve`` (or ``uvicorn td_arabic.api.app:app``). Every
route except ``/health`` and the documentation requires the ``X-API-Key``
header to match the ``API_KEY`` environment variable (``.env`` file).
"""

from __future__ import annotations

import os
import secrets
import time

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from td_arabic import __version__
from td_arabic.config import API_KEY_ENV, API_KEY_HEADER, PATHS
from td_arabic.generation.generator import SentenceGenerator
from td_arabic.translation.lexicon import get_lexicon
from td_arabic.translation.sentence import translate_sentence
from td_arabic.utils.log import get_logger

load_dotenv(PATHS.root / ".env")
log = get_logger("api", log_to_file=True)
_api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


def require_api_key(key: str | None = Security(_api_key_header)) -> None:
    """FastAPI dependency checking the ``X-API-Key`` header.

    Args:
        key: Value of the header, injected by FastAPI.

    Raises:
        HTTPException: 500 if ``API_KEY`` is not configured on the server,
            403 if the key is missing or wrong (constant-time comparison).
    """
    expected = os.getenv(API_KEY_ENV)
    if not expected:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            f"{API_KEY_ENV} non configurée côté serveur (.env).")
    if not key or not secrets.compare_digest(key, expected):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Clé API invalide ou manquante.")


app = FastAPI(
    title="Arabe tchadien – français",
    description="Lexique bilingue (SIL Tchad 2021) : recherche de mots, glose de phrases, "
                "génération de phrases thématiques pour la constitution d'un corpus.",
    version=__version__,
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["GET"],
    allow_headers=[API_KEY_HEADER, "Content-Type", "Accept"],
)


@app.middleware("http")
async def access_log(request: Request, call_next):
    """Log one line per request: method, path, client, status and duration.

    Args:
        request: Incoming request.
        call_next: Next handler in the middleware chain.

    Returns:
        The response, unchanged.
    """
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    client = request.client.host if request.client else "?"
    level = log.warning if response.status_code >= 400 else log.info
    level("%s %s (%s) -> %d en %.0f ms", request.method, request.url.path, client,
          response.status_code, ms)
    return response


@app.get("/health", tags=["système"])
def health() -> dict:
    """Health check (no API key required).

    Returns:
        Status, API version and number of lexicon entries.
    """
    return {"status": "ok", "version": __version__, "entrees": len(get_lexicon())}


api = APIRouter(dependencies=[Depends(require_api_key)])


@api.get("/translate", tags=["traduction"])
def translate_word(
    q: str = Query(..., min_length=1, description="Mot ou expression à traduire"),
    direction: str = Query("auto", pattern="^(auto|ar-fr|fr-ar)$"),
) -> dict:
    """Translate a word or expression.

    Exact match first, then inflected form, then fuzzy (5 suggestions max).

    Args:
        q: Word or expression to translate.
        direction: ``auto``, ``ar-fr`` or ``fr-ar``.

    Returns:
        The lookup result in the v1-compatible format.
    """
    return get_lexicon().lookup(q, direction).as_dict()


@api.get("/translate/sentence", tags=["traduction"])
def translate_text(
    text: str = Query(..., min_length=1, max_length=500),
    direction: str = Query("fr-ar", pattern="^(ar-fr|fr-ar)$"),
) -> dict:
    """Gloss a sentence word by word (a draft for a speaker to validate).

    Args:
        text: Sentence, up to 500 characters.
        direction: ``fr-ar`` or ``ar-fr``.

    Returns:
        Source, direction, gloss, coverage and segments.
    """
    return translate_sentence(text, direction).as_dict()


@api.get("/generation/themes", tags=["génération"])
def list_themes() -> dict:
    """List the generation themes.

    Returns:
        ``{theme_key: title}``.
    """
    return SentenceGenerator().themes()


@api.get("/generation", tags=["génération"])
def generate(
    theme: list[str] | None = Query(None, description="Thèmes (tous par défaut)"),
    n: int = Query(10, ge=1, le=200, description="Nombre de phrases par thème"),
    seed: int | None = Query(None, description="Graine aléatoire (reproductibilité)"),
) -> list[dict]:
    """Generate sentences for one or several themes.

    Args:
        theme: Theme keys (repeatable); every theme when omitted.
        n: Sentences per theme (1-200).
        seed: Random seed for reproducible output.

    Returns:
        The generated sentences as dicts.

    Raises:
        HTTPException: 404 if a theme does not exist.
    """
    generator = SentenceGenerator()
    unknown = set(theme or []) - set(generator.themes())
    if unknown:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Thème(s) inconnu(s) : {sorted(unknown)}")
    return [s.as_dict() for s in generator.generate(theme, n, seed)]


app.include_router(api)

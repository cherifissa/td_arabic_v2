"""Streamlit app for the human validation of the extracted lexicon text.

Shows the original PDF page next to the extracted, editable text;
corrections are saved page by page, together with the resume position.

Run with ``td-arabic validate``.
"""

from __future__ import annotations

import streamlit as st

from td_arabic.config import DICTIONARY_FIRST_PAGE, DICTIONARY_LAST_PAGE, PATHS
from td_arabic.utils.io import read_json, write_json

FIRST, LAST = DICTIONARY_FIRST_PAGE, DICTIONARY_LAST_PAGE
TOTAL = LAST - FIRST + 1
RENDER_DPI = 180


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------

def clamp_page(value) -> int:
    """Clamp a page number to the dictionary range.

    Args:
        value: Any value convertible to int.

    Returns:
        The page number within ``[FIRST, LAST]``; ``FIRST`` if ``value`` is
        not a number.
    """
    try:
        return max(FIRST, min(int(value), LAST))
    except (TypeError, ValueError):
        return FIRST


def load_pages(path) -> dict[int, dict]:
    """Load a page list and index it by page number.

    Args:
        path: JSON file holding ``[{"page": n, "texte": ...}, ...]``.

    Returns:
        ``{n: {"page": n, "texte": ...}}``; empty if the file does not exist.
    """
    data = read_json(path, default=[]) or []
    return {int(p["page"]): p for p in data if isinstance(p, dict) and "page" in p}


def save_correction(page: int, text: str) -> None:
    """Save the corrected text of one page (replacing any previous correction).

    Args:
        page: Page number.
        text: Corrected text.
    """
    pages = load_pages(PATHS.validation_pages_json)
    pages[page] = {"page": page, "texte": text}
    write_json(PATHS.validation_pages_json, [pages[k] for k in sorted(pages)])


def load_last_page() -> int:
    """Return the page to resume from (``FIRST`` if no progress is saved)."""
    return clamp_page((read_json(PATHS.validation_progress_json, default={}) or {})
                      .get("last_saved_page", FIRST))


def go_to(page) -> None:
    """Make ``page`` the current page and save it as the resume position.

    Args:
        page: Target page number (clamped to the dictionary range).
    """
    page = clamp_page(page)
    st.session_state.page_num = page
    write_json(PATHS.validation_progress_json, {"last_saved_page": page})


@st.cache_data(show_spinner=False)
def render_pdf_page(page: int):
    """Render one PDF page as an image (cached by Streamlit).

    Args:
        page: 1-based page number.

    Returns:
        A PIL image at ``RENDER_DPI``, or None if the PDF is missing or the
        page is out of range.
    """
    import pdfplumber
    if not PATHS.lexicon_pdf.exists():
        return None
    with pdfplumber.open(PATHS.lexicon_pdf) as pdf:
        if not 1 <= page <= len(pdf.pages):
            return None
        return pdf.pages[page - 1].to_image(resolution=RENDER_DPI).original


# --------------------------------------------------------------------------
# User interface
# --------------------------------------------------------------------------

def header(page: int, done: int) -> None:
    """Draw the title, the three counters and the progress bar.

    Args:
        page: Current page.
        done: Number of corrected pages.
    """
    st.title("Validation du lexique arabe tchadien")
    st.caption(f"Correction manuelle du texte extrait (pages {FIRST}-{LAST})")
    c1, c2, c3 = st.columns(3)
    c1.metric("Page actuelle", page, delta=f"{page - FIRST + 1}/{TOTAL}")
    c2.metric("Pages corrigées", done)
    c3.metric("Pages restantes", TOTAL - done)
    st.progress(done / TOTAL, text=f"Progression : {done}/{TOTAL} pages — {100 * done / TOTAL:.1f} %")


def navigation(corrected: dict) -> None:
    """Draw the page selector and the "first uncorrected page" button.

    Args:
        corrected: Corrected pages, indexed by page number.
    """
    st.session_state.page_selector = st.session_state.page_num
    left, right = st.columns([3, 1])
    left.number_input("Numéro de page", FIRST, LAST, step=1, key="page_selector",
                      on_change=lambda: go_to(st.session_state.page_selector))
    right.markdown("<br>", unsafe_allow_html=True)
    if right.button("Première page non corrigée", width="stretch"):
        todo = next((p for p in range(FIRST, LAST + 1) if p not in corrected), None)
        if todo:
            go_to(todo)
            st.rerun()


def page_grid(page: int, corrected: dict) -> None:
    """Draw the quick-access grid of all pages (corrected ones are ticked).

    Args:
        page: Current page (its button is disabled).
        corrected: Corrected pages, indexed by page number.
    """
    with st.expander("Accès rapide aux pages"):
        st.caption("✓ = page corrigée · page actuelle désactivée")
        for start in range(FIRST, LAST + 1, 20):
            st.markdown(f"**Pages {start}-{min(start + 19, LAST)}**")
            cols = st.columns(10)
            for i in range(start, min(start + 19, LAST) + 1):
                label = f"✓ {i}" if i in corrected else str(i)
                if cols[(i - start) % 10].button(label, key=f"goto_{i}", width="stretch",
                                                  disabled=i == page):
                    go_to(i)
                    st.rerun()


def main() -> None:
    """Render the whole validation page."""
    st.set_page_config(page_title="Validation du lexique", layout="wide")
    if "page_num" not in st.session_state:
        st.session_state.page_num = load_last_page()
    page = clamp_page(st.session_state.page_num)

    raw = load_pages(PATHS.raw_pages_json)
    corrected = load_pages(PATHS.validation_pages_json)
    header(page, len(corrected))
    navigation(corrected)

    if page in corrected:
        text = corrected[page].get("texte", "")
        st.success("Page corrigée")
    elif page in raw:
        text = raw[page].get("texte", "")
        st.info("Texte extrait (non corrigé)")
    else:
        text = ""
        st.warning(f"Aucun texte extrait : lancez `td-arabic extract` ({PATHS.raw_pages_json.name}).")

    col_pdf, col_text = st.columns(2, gap="large")
    with col_pdf:
        st.subheader(f"Document original — page {page}")
        image = render_pdf_page(page)
        if image is None:
            st.error(f"PDF introuvable ou page invalide : {PATHS.lexicon_pdf}")
        else:
            st.image(image, width="stretch")
    with col_text:
        st.subheader(f"Texte à corriger — page {page}")
        edited = st.text_area("Éditeur", value=text, height=650, key=f"text_{page}",
                              label_visibility="collapsed")
        st.caption(f"{len(edited.splitlines())} lignes · {len(edited.split())} mots · "
                   f"{len(edited)} caractères")

    prev_col, save_col, next_col = st.columns([1, 2, 1])
    if prev_col.button("Page précédente", width="stretch", disabled=page <= FIRST):
        go_to(page - 1)
        st.rerun()
    if save_col.button("Sauvegarder et passer à la suivante", type="primary", width="stretch"):
        save_correction(page, edited)
        st.toast(f"Page {page} sauvegardée")
        go_to(page + 1)
        st.rerun()
    if next_col.button("Page suivante", width="stretch", disabled=page >= LAST):
        go_to(page + 1)
        st.rerun()

    page_grid(page, corrected)


if __name__ == "__main__":
    main()

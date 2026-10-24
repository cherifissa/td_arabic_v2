"""Step 1 — Extraction of the Chadian Arabic – French Lexicon (SIL Chad, 2021).

The PDF has a real text layer: words are read directly with their font, size
and position (pdfplumber), without OCR.

Document layout:
  - pages 1-14   : front matter / grammar notes (one column);
  - pages 15-171 : dictionary on TWO columns, entries shaped like
                   ``headword[n] (forms) POS definition``.

Quirks handled:
  - the Arabic script (ScheherazadeNew font) has a broken CID -> Unicode
    mapping: it is dropped (the corpus only uses the Latin transliteration);
  - some Latin ligatures (fi, ff, ffi, fl) come out as ``(cid:N)`` or ``)``:
    they are rebuilt and flagged with ``ligature_reconstructed``;
  - a new entry = a bold headword (CharisSIL,Bold ~11 pt) aligned on its
    column margin; homographs carry a superscript digit;
  - margins are mirrored recto/verso: the column boundary is recomputed for
    every page.

Outputs (``data/interim``): structured entries (JSON + CSV), a readable full
text and the raw text per page (used by the validation app).
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from td_arabic.config import DICTIONARY_FIRST_PAGE, FRONT_MATTER_LAST_PAGE, PATHS
from td_arabic.utils.io import write_json, write_text
from td_arabic.utils.log import get_logger

log = get_logger(__name__)

# --------------------------------------------------------------------------
# Typographic parameters (measured on the PDF)
# --------------------------------------------------------------------------

HEADER_TOP_LIMIT = 45.0        # above this: page header (number + guide words)
HEADWORD_FONT = "CharisSIL,Bold"
HEADWORD_SIZE = (10.4, 11.6)   # size range of a headword
SUPERSCRIPT_MAX_SIZE = 9.0     # superscript homograph digit
SECTION_TITLE_SIZE_MIN = 13.0  # section titles "A a", "Tch tch"... (14 pt)
MARGIN_TOLERANCE = 6.0         # on the margin (entry) vs indented (sub-entry)
LINE_CLUSTER_TOL = 6.0         # vertical tolerance to group words into a line
FRONT_MATTER_LINE_TOL = 4.0
COLUMN_GUTTER = 10.0           # blank space observed before the right column
ARABIC_FONT = "ScheherazadeNew"

FORM_LABELS = {
    "inacc.", "impr.", "pl.", "f.", "f.pl.", "sg.", "dl.", "var.", "comp.",
    "m.", "m.pl.", "part.prs.",
}
POS_TAGS = {
    "n.m.", "n.f.", "n.f", "adj.", "v.tr.", "v.i.", "n.coll.", "n.coll.f.",
    "expr.", "adv.", "num.", "prép.", "pron.", "interj.", "conj.", "n.pl.",
    "interg.", "coll.", "part.interg.", "art.déf.", "n.", "neg.",
}
ARABIC_RANGES = [(0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)]

# Latin-font ligatures with no Unicode mapping, identified from the glyph width
# cross-checked against known words (e.g. "abdal(cid:19)teen" -> abdalfiteen).
LATIN_LIGATURE_CID_MAP = {"19": "fi", "30": "ff", "31": "ffi"}
# The "fl" ligature of CharisSIL,Bold comes out as ")" inside a word
# (e.g. "kha)a" -> "khafla").
_FL_LIGATURE = re.compile(r"(?<=[A-Za-z])\)(?=[A-Za-z])")
_CID = re.compile(r"\(cid:(\d+)\)")


# --------------------------------------------------------------------------
# Words: low-level cleaning
# --------------------------------------------------------------------------

def font_of(word: dict) -> str:
    """Return the font name without its subset prefix.

    Args:
        word: A pdfplumber word with a ``fontname`` key.

    Returns:
        The font name, e.g. ``"GXQVTB+CharisSIL,Bold"`` -> ``"CharisSIL,Bold"``.
    """
    return word["fontname"].split("+")[-1]


def is_headword_font(word: dict) -> bool:
    """Tell whether a word uses the headword font (any size).

    Args:
        word: A pdfplumber word.

    Returns:
        True if the font is CharisSIL,Bold.
    """
    return font_of(word) == HEADWORD_FONT


def is_headword_sized(word: dict) -> bool:
    """Tell whether a word looks like a headword (bold font, ~11 pt).

    Args:
        word: A pdfplumber word with ``fontname`` and ``size``.

    Returns:
        True if both font and size match a headword.
    """
    return is_headword_font(word) and HEADWORD_SIZE[0] <= word["size"] <= HEADWORD_SIZE[1]


def is_superscript_digit(word: dict) -> bool:
    """Tell whether a word is a superscript homograph number.

    Args:
        word: A pdfplumber word.

    Returns:
        True for a small (< 9 pt) all-digit token.
    """
    return word["text"].isdigit() and word["size"] < SUPERSCRIPT_MAX_SIZE


def _is_bad_char(ch: str) -> bool:
    """Return True for control characters and Arabic-script code points."""
    code = ord(ch)
    return code < 0x20 or any(lo <= code <= hi for lo, hi in ARABIC_RANGES)


def repair_ligatures(text: str, fontname: str = "") -> tuple[str, bool]:
    """Replace badly encoded Latin ligatures.

    Args:
        text: Raw word text from the PDF.
        fontname: Font of the word; the ``)`` -> ``fl`` fix only applies to
            CharisSIL fonts (a French parenthesis must stay untouched).

    Returns:
        A tuple ``(fixed_text, changed)`` where ``changed`` tells whether a
        ligature was rebuilt.
    """
    fixed = text
    for code, repl in LATIN_LIGATURE_CID_MAP.items():
        fixed = fixed.replace(f"(cid:{code})", repl)
    if "CharisSIL" in fontname:
        fixed = _FL_LIGATURE.sub("fl", fixed)
    return fixed, fixed != text


def clean_word(word: dict) -> dict | None:
    """Clean one word, or drop it.

    - Arabic font: dropped, except the delimiters ``( ) /`` (they bound the
      groups of forms and are removed later).
    - Latin font: ligatures repaired; any remaining Arabic or control
      character, or an unknown ``(cid:N)``, means the word is dropped.

    Args:
        word: A pdfplumber word (``text``, ``fontname``, ``size``, ``x0``, ``top``).

    Returns:
        A copy of the word with its text repaired (and
        ``ligature_reconstructed=True`` if a ligature was rebuilt), or None if
        the word must be discarded.
    """
    text = word["text"]
    if not text or not text.strip():
        return None
    if ARABIC_FONT in word["fontname"]:
        return word if text in {"(", ")", "/"} else None

    text, reconstructed = repair_ligatures(text, word["fontname"])
    if "cid:" in text or any(_is_bad_char(c) for c in text):
        return None
    cleaned = dict(word, text=text)
    if reconstructed:
        cleaned["ligature_reconstructed"] = True
    return cleaned


def is_noise_token(word: dict) -> bool:
    """Tell whether a token is a delimiter coming from the Arabic font.

    Args:
        word: A cleaned word.

    Returns:
        True for ``( ) /`` in the Arabic font; French parentheses are kept.
    """
    return word["text"] in {"(", ")", "/"} and ARABIC_FONT in word["fontname"]


def page_words(page, skip_header: bool = True) -> list[dict]:
    """Extract and clean all useful words of a page.

    Args:
        page: A ``pdfplumber`` page.
        skip_header: Drop words above ``HEADER_TOP_LIMIT`` (page number and
            guide words).

    Returns:
        The cleaned words, in pdfplumber order.
    """
    words = page.extract_words(extra_attrs=["fontname", "size"])
    out = []
    for w in words:
        if skip_header and w["top"] < HEADER_TOP_LIMIT:
            continue
        cleaned = clean_word(w)
        if cleaned is not None:
            out.append(cleaned)
    return out


# --------------------------------------------------------------------------
# Lines, columns and section titles
# --------------------------------------------------------------------------

def cluster_lines(words: list[dict], tol: float = LINE_CLUSTER_TOL) -> list[list[dict]]:
    """Group words into visual lines.

    The tolerance is "chained": each word is compared with the previous one,
    not with the first word of the line, which absorbs small baseline shifts
    between Latin, Arabic and superscript fonts.

    Args:
        words: Words with ``top`` and ``x0`` coordinates.
        tol: Maximum vertical gap (pt) between two words of the same line.

    Returns:
        Lines sorted top to bottom, each line sorted left to right.
    """
    lines: list[list[dict]] = []
    current: list[dict] = []
    last_top: float | None = None
    for w in sorted(words, key=lambda w: w["top"]):
        if current and (w["top"] - last_top) > tol:
            lines.append(current)
            current = []
        current.append(w)
        last_top = w["top"]
    if current:
        lines.append(current)
    for line in lines:
        line.sort(key=lambda w: w["x0"])
    lines.sort(key=lambda line: min(w["top"] for w in line))
    return lines


def line_text(line: list[dict]) -> str:
    """Join the words of a line with single spaces.

    Args:
        line: Words of one visual line.

    Returns:
        The line as text.
    """
    return " ".join(w["text"] for w in line)


def line_top(line: list[dict]) -> float:
    """Return the vertical position of a line.

    Args:
        line: Words of one visual line.

    Returns:
        The smallest ``top`` coordinate of its words.
    """
    return min(w["top"] for w in line)


def find_split_x(words: list[dict], page_width: float) -> float:
    """Compute the boundary between the two columns of THIS page.

    The two most frequent ``x0`` positions of headwords are the margins of
    the two columns (an indented sub-entry appears only once or twice at the
    same ``x0``). The page is split just before the right-hand margin.

    Args:
        words: Body words of the page.
        page_width: Page width in points (fallback: half of it).

    Returns:
        The x coordinate separating the left and right columns.
    """
    counts = Counter(round(w["x0"], 1) for w in words if is_headword_sized(w))
    if len(counts) < 2:
        return page_width / 2
    _, right_margin = sorted(x for x, _ in counts.most_common(2))
    return right_margin - COLUMN_GUTTER


def find_column_margin(lines: list[list[dict]]) -> float:
    """Return the left margin of a column.

    Args:
        lines: Lines of one column.

    Returns:
        The smallest ``x0`` of a headword-sized word (43.0 if none).
    """
    xs = [w["x0"] for line in lines for w in line if is_headword_sized(w)]
    return min(xs) if xs else 43.0


@dataclass
class Column:
    """One column of a dictionary page.

    Attributes:
        name: ``"left"`` or ``"right"``.
        lines: Visual lines of the column, top to bottom.
    """

    name: str
    lines: list[list[dict]]


@dataclass
class PageLayout:
    """A dictionary page split into section titles and columns.

    Attributes:
        number: 1-based page number.
        columns: The (one or two) non-empty columns.
        titles: Section titles as ``(top, text)``, top to bottom.
    """

    number: int
    columns: list[Column]
    titles: list[tuple[float, str]] = field(default_factory=list)


def layout_dictionary_page(page, number: int) -> PageLayout:
    """Split a dictionary page into section titles and two columns.

    Args:
        page: A ``pdfplumber`` page from the dictionary body.
        number: Its 1-based page number.

    Returns:
        The page layout.
    """
    words = page_words(page)
    title_words = [w for w in words if w["size"] >= SECTION_TITLE_SIZE_MIN]
    body_words = [w for w in words if w["size"] < SECTION_TITLE_SIZE_MIN]
    split_x = find_split_x(body_words, page.width)

    titles = sorted((line_top(l), line_text(l)) for l in cluster_lines(title_words))
    columns = []
    for name, x_min, x_max in (("left", 0, split_x), ("right", split_x, page.width)):
        col_words = [w for w in body_words if x_min <= w["x0"] < x_max]
        if col_words:
            columns.append(Column(name, cluster_lines(col_words)))
    return PageLayout(number, columns, titles)


def iter_titled_lines(
    lines: list[list[dict]], titles: list[tuple[float, str]]
) -> Iterator[tuple[str | None, list[dict] | None]]:
    """Merge lines and section titles in vertical order.

    Section titles are centred across the page, so they are detected on the
    full page width and re-inserted into each column at their height.

    Args:
        lines: Lines of one column, top to bottom.
        titles: Section titles as ``(top, text)``, sorted by ``top``.

    Yields:
        ``(title, None)`` when a section starts, then ``(None, line)`` for each
        line; titles below the last line are yielded at the end.
    """
    t_idx = 0
    for line in lines:
        top = line_top(line)
        while t_idx < len(titles) and titles[t_idx][0] <= top:
            yield titles[t_idx][1], None
            t_idx += 1
        yield None, line
    for _, title in titles[t_idx:]:
        yield title, None


# --------------------------------------------------------------------------
# Dictionary entries
# --------------------------------------------------------------------------

def segment_entries(
    column: Column, page_num: int, section: str, titles: list[tuple[float, str]]
) -> tuple[list[dict[str, Any]], str]:
    """Split one column into raw entries.

    A line starting with a headword-sized word on the column margin opens a
    new entry; any other line is appended to the current entry.

    Args:
        column: The column to segment.
        page_num: Page number, stored in each entry.
        section: Section in force at the top of the column.
        titles: Section titles of the page as ``(top, text)``.

    Returns:
        A tuple ``(entries, section)``: the raw entries (``tokens``, ``page``,
        ``column``, ``section``) and the section in force at the bottom of the
        column.
    """
    margin = find_column_margin(column.lines)
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for title, line in iter_titled_lines(column.lines, titles):
        if title is not None:
            section = title
            continue
        first = line[0]
        if is_headword_sized(first) and abs(first["x0"] - margin) <= MARGIN_TOLERANCE:
            if current is not None:
                entries.append(current)
            current = {"tokens": list(line), "page": page_num,
                       "column": column.name, "section": section}
        elif current is not None:
            current["tokens"].extend(line)
        # otherwise: orphan text before the first entry -> ignored

    if current is not None:
        entries.append(current)
    return entries, section


def parse_entry(raw: dict[str, Any]) -> dict[str, Any]:
    """Parse a raw entry into headword, homograph number, forms, POS and definition.

    Args:
        raw: A raw entry from :func:`segment_entries`.

    Returns:
        A dict with ``headword`` (with its homograph digit, e.g. ``abad1``),
        ``headword_base``, ``sense_number``, ``forms`` (list of
        ``{"label", "value"}``), ``pos``, ``definition``, ``section``,
        ``page``, ``column`` and ``ligature_reconstructed``.
    """
    tokens = [t for t in raw["tokens"] if not is_noise_token(t)]
    idx = 1
    headword = tokens[0]["text"]

    # Multi-word headword (e.g. "fi chaan"): same font and size.
    while idx < len(tokens) and is_headword_sized(tokens[idx]):
        headword += " " + tokens[idx]["text"]
        idx += 1

    sense_number = None
    if idx < len(tokens) and is_superscript_digit(tokens[idx]):
        sense_number = int(tokens[idx]["text"])
        idx += 1

    forms: list[tuple[str, str]] = []
    while idx < len(tokens) and tokens[idx]["text"] in FORM_LABELS:
        label = tokens[idx]["text"]
        idx += 1
        # The value is in the headword font (small size, sometimes full size).
        parts = []
        while (idx < len(tokens) and is_headword_font(tokens[idx])
               and tokens[idx]["size"] <= HEADWORD_SIZE[1]):
            parts.append(tokens[idx]["text"])
            idx += 1
        if parts:
            forms.append((label, " ".join(parts)))

    pos = None
    if idx < len(tokens) and tokens[idx]["text"] in POS_TAGS:
        pos = tokens[idx]["text"]
        idx += 1

    definition = " ".join(t["text"] for t in tokens[idx:] if not is_superscript_digit(t))
    definition = re.sub(r"\s+([;:,.!?])", r"\1", definition)
    definition = re.sub(r"\s{2,}", " ", definition).strip()

    return {
        "headword": f"{headword}{sense_number}" if sense_number else headword,
        "headword_base": headword,
        "sense_number": sense_number,
        "forms": [{"label": l, "value": v} for l, v in forms],
        "pos": pos,
        "definition": definition,
        "section": raw["section"],
        "page": raw["page"],
        "column": raw["column"],
        "ligature_reconstructed": any(t.get("ligature_reconstructed") for t in raw["tokens"]),
    }


def forms_to_str(forms: list[dict[str, str]]) -> str:
    """Serialise a list of forms.

    Args:
        forms: Items ``{"label": "inacc.", "value": "yaʼabud"}``.

    Returns:
        The forms joined with ``" / "``, e.g. ``"inacc. yaʼabud / impr. aʼabud"``.
    """
    return " / ".join(f"{f['label']} {f['value']}" for f in forms)


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------

@dataclass
class Extraction:
    """The three views of the lexicon produced by :func:`extract`.

    Attributes:
        front_matter: Full text of the front matter, one item per page.
        raw_pages: Text of every page in reading order (validation app input).
        entries: Structured dictionary entries.
    """

    front_matter: list[dict[str, Any]]
    raw_pages: list[dict[str, Any]]
    entries: list[dict[str, Any]]


def _front_matter_text(page, skip_header: bool) -> str:
    """Return the text of a one-column front-matter page, line by line."""
    lines = cluster_lines(page_words(page, skip_header), tol=FRONT_MATTER_LINE_TOL)
    return "\n".join(line_text(l) for l in lines)


def extract(pdf_path: Path) -> Extraction:
    """Read the PDF once and build the three views of the lexicon.

    Args:
        pdf_path: Path to the SIL lexicon PDF.

    Returns:
        The extraction result (front matter, raw pages, entries).

    Raises:
        ImportError: If the optional ``pdfplumber`` dependency is missing
            (install with ``uv sync --extra extract``).
        FileNotFoundError: If ``pdf_path`` does not exist.
    """
    import pdfplumber  # optional dependency [extract]

    front, raw_pages, entries = [], [], []
    section = ""
    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        for i in range(FRONT_MATTER_LAST_PAGE):
            page = pdf.pages[i]
            front.append({"page": i + 1, "text": _front_matter_text(page, False).strip()})
            raw_pages.append({"page": i + 1, "texte": _front_matter_text(page, True)})

        for page_index in range(DICTIONARY_FIRST_PAGE - 1, total):
            number = page_index + 1
            layout = layout_dictionary_page(pdf.pages[page_index], number)

            column_texts = []
            for column in layout.columns:
                merged = [title or line_text(line)
                          for title, line in iter_titled_lines(column.lines, layout.titles)]
                column_texts.append("\n".join(merged))
                raw_entries, section = segment_entries(column, number, section, layout.titles)
                entries.extend(parse_entry(r) for r in raw_entries)
            raw_pages.append({"page": number, "texte": "\n".join(column_texts)})

            if number % 20 == 0:
                log.info("page %d/%d — %d entrées", number, total, len(entries))
    return Extraction(front, raw_pages, entries)


def render_full_text(front_matter: list[dict[str, Any]], entries: list[dict[str, Any]]) -> str:
    """Render the whole lexicon as readable plain text.

    Args:
        front_matter: Front-matter pages from :func:`extract`.
        entries: Structured entries from :func:`extract`.

    Returns:
        The text: front matter, then entries grouped under their section.
    """
    lines = ["LEXIQUE ARABE TCHADIEN - FRANÇAIS (SIL Tchad, 2021)", "=" * 60, "",
             f"PRÉAMBULE (pages 1-{FRONT_MATTER_LAST_PAGE})", "-" * 60]
    lines += [f"\n[page {p['page']}]\n{p['text']}" for p in front_matter]
    lines += ["\n\n", f"CORPS DU DICTIONNAIRE (pages {DICTIONARY_FIRST_PAGE}+)", "-" * 60]
    last_section = None
    for e in entries:
        if e["section"] != last_section:
            lines.append(f"\n### {e['section']} ###\n")
            last_section = e["section"]
        forms = f" ({forms_to_str(e['forms'])})" if e["forms"] else ""
        pos = f" {e['pos']}" if e["pos"] else ""
        lines.append(f"{e['headword']}{forms}{pos} {e['definition']}")
    return "\n".join(lines)


ENTRY_CSV_COLUMNS = ["headword", "headword_base", "sense_number", "forms", "pos", "definition",
                     "section", "page", "column", "ligature_reconstructed"]


def entries_to_csv(entries: list[dict[str, Any]]) -> str:
    """Serialise entries as CSV text.

    Args:
        entries: Structured entries from :func:`extract`.

    Returns:
        CSV text with the ``ENTRY_CSV_COLUMNS`` header.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(ENTRY_CSV_COLUMNS)
    for e in entries:
        writer.writerow([e["headword"], e["headword_base"], e["sense_number"] or "",
                         forms_to_str(e["forms"]), e["pos"] or "", e["definition"],
                         e["section"], e["page"], e["column"], e["ligature_reconstructed"]])
    return buf.getvalue()


def run(pdf_path: Path | None = None) -> Extraction:
    """Run step 1 and write its outputs to ``data/interim``.

    Writes ``lexique_entries.json``, ``lexique_entries.csv``,
    ``lexique_texte_complet.txt`` and ``pdf_pages_brutes.json``.

    Args:
        pdf_path: PDF to read; defaults to ``PATHS.lexicon_pdf``.

    Returns:
        The extraction result.

    Raises:
        FileNotFoundError: If the PDF does not exist.
    """
    pdf_path = pdf_path or PATHS.lexicon_pdf
    log.info("Extraction de %s", pdf_path.name)
    result = extract(pdf_path)
    log.info("%d entrées extraites", len(result.entries))

    write_json(PATHS.entries_json, {"source": pdf_path.name,
                                    "entries_count": len(result.entries),
                                    "entries": result.entries})
    write_text(PATHS.entries_csv, entries_to_csv(result.entries))
    write_text(PATHS.full_text_txt, render_full_text(result.front_matter, result.entries))
    write_json(PATHS.raw_pages_json, result.raw_pages)
    for p in (PATHS.entries_json, PATHS.entries_csv, PATHS.full_text_txt, PATHS.raw_pages_json):
        log.info("  -> %s", p.relative_to(PATHS.root))
    return result

"""Central configuration: every path and constant of the project.

No other module hard-codes a path: they all import ``PATHS``. The project
root can be overridden with the ``TD_ARABIC_ROOT`` environment variable
(useful to run the pipeline on a copy of the data).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _project_root() -> Path:
    """Resolve the repository root.

    Returns:
        The directory given by ``TD_ARABIC_ROOT`` if set, otherwise the
        repository root (``src/td_arabic/config.py`` -> two levels up).
    """
    env = os.getenv("TD_ARABIC_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Paths:
    """All file-system locations used by the project, derived from one root.

    Attributes:
        root: Repository root; every other path is computed from it.
    """

    root: Path

    # --- data folders ------------------------------------------------------
    @property
    def data(self) -> Path:
        """Top-level ``data/`` folder."""
        return self.root / "data"

    @property
    def raw(self) -> Path:
        """Untouched source files (the SIL lexicon PDF)."""
        return self.data / "raw"

    @property
    def interim(self) -> Path:
        """Raw outputs of the PDF extraction (step 1)."""
        return self.data / "interim"

    @property
    def processed(self) -> Path:
        """Final lexicon and corpus files (step 2)."""
        return self.data / "processed"

    @property
    def resources(self) -> Path:
        """Hand-curated inputs: manual expression splits and templates."""
        return self.data / "resources"

    # --- source --------------------------------------------------------------
    @property
    def lexicon_pdf(self) -> Path:
        """SIL Chad lexicon PDF (11th edition, 2021)."""
        return self.raw / "SHU_Lexique_arabe_francais_11e_2021.pdf"

    # --- step 1: PDF extraction ----------------------------------------------
    @property
    def raw_pages_json(self) -> Path:
        """Extracted text per page, read by the validation app."""
        return self.interim / "pdf_pages_brutes.json"

    @property
    def entries_json(self) -> Path:
        """Structured dictionary entries (JSON)."""
        return self.interim / "lexique_entries.json"

    @property
    def entries_csv(self) -> Path:
        """Structured dictionary entries (flat CSV)."""
        return self.interim / "lexique_entries.csv"

    @property
    def full_text_txt(self) -> Path:
        """Human-readable dump of the whole lexicon."""
        return self.interim / "lexique_texte_complet.txt"

    # --- step 2: lexicon / corpus structuring --------------------------------
    @property
    def manual_expressions_csv(self) -> Path:
        """Hand-validated splits of entries containing ``expr.``."""
        return self.resources / "expressions_manuelles.csv"

    @property
    def expressions_review_csv(self) -> Path:
        """Entries with ``expr.`` that still need a manual split."""
        return self.interim / "expressions_a_verifier.csv"

    @property
    def lexicon_final_csv(self) -> Path:
        """Final lexicon: one row per entry or expression, with provenance."""
        return self.processed / "lexique_final.csv"

    @property
    def corpus_csv(self) -> Path:
        """Chadian Arabic -> French pairs (single source of truth)."""
        return self.processed / "corpus_arabe_tchadien_francais.csv"

    @property
    def corpus_bilingual_csv(self) -> Path:
        """Same pairs in both directions (``ar-fr`` and ``fr-ar``)."""
        return self.processed / "corpus_bilingue.csv"

    # --- sentence generation -------------------------------------------------
    @property
    def themes_yaml(self) -> Path:
        """Sentence templates and vocabulary lists."""
        return self.resources / "themes.yaml"

    @property
    def word_families_csv(self) -> Path:
        """Groups of French words built from the same root (naître, naissance, né…)."""
        return self.resources / "familles_mots.csv"

    @property
    def entry_corrections_csv(self) -> Path:
        """Hand-made corrections of definitions extracted from the PDF (applied by ``build-corpus``)."""
        return self.resources / "corrections_entrees.csv"

    @property
    def corpus_additions_csv(self) -> Path:
        """Words and senses added by hand to the corpus (merged by ``build-corpus``)."""
        return self.resources / "ajouts_corpus.csv"

    @property
    def french_wordlist_csv(self) -> Path:
        """Important French words with synonyms and antonyms (coverage check)."""
        return self.resources / "mots_francais_importants.csv"

    @property
    def sentences_csv(self) -> Path:
        """Sentence bank (draft / validated / rejected)."""
        return self.data / "sentences" / "phrases.csv"

    # --- audio recordings ----------------------------------------------------
    @property
    def audio(self) -> Path:
        """Root of the audio corpus."""
        return self.data / "audio"

    @property
    def speakers_json(self) -> Path:
        """Speaker profiles and their audio settings."""
        return self.audio / "locuteurs.json"

    @property
    def audio_metadata_csv(self) -> Path:
        """Audio manifest (one row per recording)."""
        return self.audio / "metadata.csv"

    @property
    def wavs(self) -> Path:
        """WAV files, one sub-folder per speaker."""
        return self.audio / "wavs"

    # --- manual validation of the extraction ---------------------------------
    @property
    def validation_pages_json(self) -> Path:
        """Pages corrected in the validation app."""
        return self.data / "validation" / "pages_corrigees.json"

    @property
    def validation_progress_json(self) -> Path:
        """Last page saved in the validation app."""
        return self.data / "validation" / "progression.json"

    # --- logs ------------------------------------------------------------------
    # --- fine-tuning ------------------------------------------------------------
    @property
    def finetune_config(self) -> Path:
        """Fine-tuning settings (model, LoRA, training), see docs/08-fine-tuning.md."""
        return self.root / "configs" / "finetune.yaml"

    @property
    def finetune_data(self) -> Path:
        """Training data built from the corpus (train.jsonl / valid.jsonl)."""
        return self.data / "finetune"

    @property
    def dataset(self) -> Path:
        """Training dataset (entries, sentences, issues, exports), see docs/09-architecture-donnees.md."""
        return self.data / "dataset"

    @property
    def models(self) -> Path:
        """Fine-tuned adapters and their training reports (not versioned)."""
        return self.root / "models"

    @property
    def logs(self) -> Path:
        """Log folder (API access log)."""
        return self.root / "logs"


PATHS = Paths(_project_root())

# --- Source lexicon (SIL Chad, 2021) ------------------------------------------
FRONT_MATTER_LAST_PAGE = 14  # pages 1-14: front matter
DICTIONARY_FIRST_PAGE = 15   # pages 15-171: dictionary body
DICTIONARY_LAST_PAGE = 171

# --- Search ---------------------------------------------------------------------
FUZZY_LIMIT = 5
FUZZY_THRESHOLD = 50

# --- API ------------------------------------------------------------------------
API_KEY_ENV = "API_KEY"
API_KEY_HEADER = "X-API-Key"

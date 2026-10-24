"""Sentence bank (``data/sentences/phrases.csv``).

Life cycle of a sentence: ``brouillon`` (draft) -> ``validee`` (validated) or
``rejetee`` (rejected). Only validated sentences are offered for recording by
default. A speaker may correct the text; the identifier stays the same.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from td_arabic.config import PATHS
from td_arabic.generation.generator import GeneratedSentence, sentence_id
from td_arabic.utils.io import read_csv, write_csv

COLUMNS = ["id", "theme", "template_id", "fr", "td", "lemmes", "hors_lexique",
           "statut", "source", "cree_le", "modifie_le"]
STATUSES = ("brouillon", "validee", "rejetee")
LIST_SEP = "; "


def _now() -> str:
    """Return the current UTC time in ISO 8601, to the second."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SentenceStore:
    """CSV-backed bank of sentences to validate and record.

    Attributes:
        path: CSV file holding the bank.
    """

    def __init__(self, path: Path | None = None):
        """Open a sentence bank.

        Args:
            path: CSV file; defaults to ``PATHS.sentences_csv`` (created on
                first save).
        """
        self.path = path or PATHS.sentences_csv

    def load(self) -> pd.DataFrame:
        """Load the whole bank.

        Returns:
            A DataFrame with ``COLUMNS`` (empty if the file does not exist yet).
        """
        if not self.path.exists():
            return pd.DataFrame(columns=COLUMNS)
        df = read_csv(self.path)
        return df.reindex(columns=COLUMNS, fill_value="")

    def save(self, df: pd.DataFrame) -> None:
        """Atomically overwrite the bank.

        Args:
            df: The full bank, with at least ``COLUMNS``.
        """
        write_csv(self.path, df[COLUMNS])

    def add(self, sentences: list[GeneratedSentence]) -> int:
        """Add the sentences that are not in the bank yet.

        Args:
            sentences: Sentences to add; ids already present are skipped.

        Returns:
            The number of sentences actually added.
        """
        df = self.load()
        known = set(df["id"])
        now = _now()
        rows = [{**s.as_dict(), "lemmes": LIST_SEP.join(s.lemmes),
                 "hors_lexique": LIST_SEP.join(s.hors_lexique),
                 "cree_le": now, "modifie_le": now}
                for s in sentences if s.id not in known]
        if rows:
            self.save(pd.concat([df, pd.DataFrame(rows)], ignore_index=True))
        return len(rows)

    def add_manual(self, td: str, fr: str, theme: str = "libre", source: str = "manuel") -> str:
        """Add a sentence typed or translated by hand, as a draft.

        Args:
            td: Chadian Arabic text.
            fr: French text.
            theme: Theme key (``"libre"`` by default).
            source: Origin label, e.g. ``"manuel"`` or ``"traduction"``.

        Returns:
            The sentence identifier (existing one if already in the bank).
        """
        sid = sentence_id(theme, td, fr)
        self.add([GeneratedSentence(sid, theme, "", fr, td, source=source)])
        return sid

    def update(self, sentence_id_: str, **fields) -> None:
        """Update fields of one sentence and stamp ``modifie_le``.

        Args:
            sentence_id_: Identifier of the sentence.
            **fields: Columns to set, e.g. ``statut="validee"``, ``td="..."``.

        Raises:
            ValueError: If ``statut`` is not one of ``STATUSES``.
            KeyError: If the sentence is not in the bank.
        """
        if "statut" in fields and fields["statut"] not in STATUSES:
            raise ValueError(f"statut inconnu : {fields['statut']}")
        df = self.load()
        mask = df["id"] == sentence_id_
        if not mask.any():
            raise KeyError(sentence_id_)
        for key, value in fields.items():
            df.loc[mask, key] = value
        df.loc[mask, "modifie_le"] = _now()
        self.save(df)

    def settled_ids(self, include_rejected: bool = True) -> set[str]:
        """Return the ids of the sentences already reviewed.

        A validated sentence must not be generated again; a rejected one neither,
        since a speaker has already decided about it.

        Args:
            include_rejected: Also return the rejected sentences (default).

        Returns:
            The set of ids with status ``validee`` (and ``rejetee``).
        """
        df = self.load()
        wanted = ("validee", "rejetee") if include_rejected else ("validee",)
        return set(df.loc[df["statut"].isin(wanted), "id"])

    def by_status(self, *statuses: str) -> pd.DataFrame:
        """Filter the bank by status.

        Args:
            *statuses: Statuses to keep; none means every sentence.

        Returns:
            The matching rows.
        """
        df = self.load()
        return df[df["statut"].isin(statuses)] if statuses else df

"""Audio corpus: WAV files plus the ``data/audio/metadata.csv`` manifest.

Layout (compatible with Hugging Face ``datasets.load_dataset("audiofolder",
...)``, the ``file_name`` column being relative to ``data/audio``):

    data/audio/
    ├── locuteurs.json
    ├── metadata.csv
    └── wavs/<speaker>/<sentence_id>.wav

A sentence recorded again by the same speaker replaces the previous take.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from td_arabic.config import PATHS
from td_arabic.recording.audio import AudioClip, encode_wav, process
from td_arabic.recording.speakers import Speaker
from td_arabic.utils.io import read_csv, write_bytes, write_csv

METADATA_COLUMNS = ["file_name", "sentence_id", "speaker_id", "td", "fr", "theme",
                    "duration_s", "sample_rate", "genre", "tranche_age", "region",
                    "recorded_at"]


class ConsentError(PermissionError):
    """Raised when a speaker without recorded consent tries to record."""


@dataclass
class SavedRecording:
    """Result of :meth:`AudioDataset.save_take`.

    Attributes:
        path: Absolute path of the written WAV file.
        clip: The processed audio.
        row: The manifest row added for this take.
    """

    path: Path
    clip: AudioClip
    row: dict


class AudioDataset:
    """The audio corpus on disk (WAV files + manifest).

    Attributes:
        root: Corpus root folder.
        metadata_path: Manifest CSV inside ``root``.
    """

    def __init__(self, root: Path | None = None):
        """Open an audio corpus.

        Args:
            root: Corpus folder; defaults to ``PATHS.audio``.
        """
        self.root = root or PATHS.audio
        self.metadata_path = self.root / "metadata.csv"

    def load(self) -> pd.DataFrame:
        """Load the manifest.

        Returns:
            A DataFrame with ``METADATA_COLUMNS`` (empty if no take yet).
        """
        if not self.metadata_path.exists():
            return pd.DataFrame(columns=METADATA_COLUMNS)
        return read_csv(self.metadata_path).reindex(columns=METADATA_COLUMNS, fill_value="")

    def _save(self, df: pd.DataFrame) -> None:
        """Write the manifest, sorted by speaker then sentence."""
        write_csv(self.metadata_path, df.sort_values(["speaker_id", "sentence_id"])[METADATA_COLUMNS])

    def relative_path(self, speaker_id: str, sentence_id: str) -> str:
        """Return the WAV path of a take, relative to the corpus root.

        Args:
            speaker_id: Speaker identifier.
            sentence_id: Sentence identifier.

        Returns:
            E.g. ``"wavs/spk001/mar-1a2b3c4d.wav"``.
        """
        return f"wavs/{speaker_id}/{sentence_id}.wav"

    def save_take(self, speaker: Speaker, sentence: dict, wav_bytes: bytes) -> SavedRecording:
        """Process one take with the speaker's settings and add it to the corpus.

        Args:
            speaker: The speaker who recorded.
            sentence: Sentence row with at least ``id``, ``td`` and ``fr``
                (``theme`` optional).
            wav_bytes: Raw WAV recorded by the browser.

        Returns:
            The saved recording (path, processed clip, manifest row).

        Raises:
            ConsentError: If the speaker has not given consent.
            AudioError: If the take cannot be decoded or is too short/long.
        """
        if not speaker.consentement:
            raise ConsentError(f"le locuteur {speaker.id} n'a pas donné son consentement")
        clip = process(wav_bytes, speaker.reglages)
        rel = self.relative_path(speaker.id, sentence["id"])
        path = self.root / rel
        write_bytes(path, encode_wav(clip))

        row = {"file_name": rel, "sentence_id": sentence["id"], "speaker_id": speaker.id,
               "td": sentence["td"], "fr": sentence["fr"], "theme": sentence.get("theme", ""),
               "duration_s": f"{clip.duration:.3f}", "sample_rate": str(clip.sample_rate),
               "genre": speaker.genre, "tranche_age": speaker.tranche_age, "region": speaker.region,
               "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        df = self.load()
        df = df[df["file_name"] != rel]
        self._save(pd.concat([df, pd.DataFrame([row])], ignore_index=True))
        return SavedRecording(path, clip, row)

    def delete(self, speaker_id: str, sentence_id: str) -> None:
        """Remove a take (WAV file and manifest row); used for withdrawal requests.

        Args:
            speaker_id: Speaker identifier.
            sentence_id: Sentence identifier.
        """
        rel = self.relative_path(speaker_id, sentence_id)
        (self.root / rel).unlink(missing_ok=True)
        df = self.load()
        self._save(df[df["file_name"] != rel])

    def recorded_ids(self, speaker_id: str) -> set[str]:
        """Return the ids of the sentences a speaker has already recorded.

        Args:
            speaker_id: Speaker identifier.

        Returns:
            The set of sentence identifiers.
        """
        df = self.load()
        return set(df.loc[df["speaker_id"] == speaker_id, "sentence_id"])

    def stats(self) -> dict:
        """Summarise the audio corpus.

        Returns:
            Number of takes, total duration in minutes, number of speakers and
            distinct sentences, and takes/minutes per speaker.
        """
        df = self.load()
        if df.empty:
            return {"enregistrements": 0, "duree_totale_min": 0.0, "locuteurs": 0, "par_locuteur": {}}
        dur = df["duration_s"].astype(float)
        per = df.assign(d=dur).groupby("speaker_id")["d"].agg(["count", "sum"])
        return {
            "enregistrements": len(df),
            "duree_totale_min": round(float(dur.sum()) / 60, 2),
            "locuteurs": df["speaker_id"].nunique(),
            "phrases_distinctes": df["sentence_id"].nunique(),
            "par_locuteur": {k: {"prises": int(r["count"]), "minutes": round(float(r["sum"]) / 60, 2)}
                             for k, r in per.iterrows()},
        }

"""Speaker profiles (``data/audio/locuteurs.json``).

Every person who records has a pseudonymised profile and their own audio
settings. Informed consent is mandatory before any recording
(see docs/05-ethique-licences.md).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, fields
from datetime import date
from pathlib import Path

from td_arabic.config import PATHS
from td_arabic.recording.audio import AudioSettings
from td_arabic.utils.io import read_json, write_json

GENRES = ("femme", "homme", "autre / non précisé")
TRANCHES_AGE = ("18-25", "26-35", "36-50", "51-65", "65+")


@dataclass
class Speaker:
    """A pseudonymised speaker profile.

    Attributes:
        id: Identifier used in file names, e.g. ``spk001``.
        pseudo: Pseudonym (never a real name in the published corpus).
        genre: One of ``GENRES``.
        tranche_age: One of ``TRANCHES_AGE`` (no birth date is stored).
        region: Town or region of origin (dialect variation).
        langue_premiere: First language.
        autres_langues: Other languages spoken.
        consentement: Informed consent given; required to record.
        date_consentement: ISO date of consent, set automatically.
        notes: Free notes (equipment, recording conditions...).
        reglages: The speaker's audio processing settings.
    """

    id: str
    pseudo: str
    genre: str = GENRES[-1]
    tranche_age: str = ""
    region: str = ""
    langue_premiere: str = "arabe tchadien"
    autres_langues: str = ""
    consentement: bool = False
    date_consentement: str = ""
    notes: str = ""
    reglages: AudioSettings = field(default_factory=AudioSettings)

    def as_dict(self) -> dict:
        """Return the profile as a JSON-serialisable dict (settings nested)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Speaker":
        """Build a profile from its stored dict.

        Args:
            data: A dict as written by :meth:`as_dict`; unknown keys are ignored.

        Returns:
            The speaker profile.
        """
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in data.items() if k in known}
        data["reglages"] = AudioSettings(**data.get("reglages", {}))
        return cls(**data)


class SpeakerRegistry:
    """JSON-backed list of speaker profiles.

    Attributes:
        path: JSON file holding the profiles.
    """

    def __init__(self, path: Path | None = None):
        """Open a registry.

        Args:
            path: JSON file; defaults to ``PATHS.speakers_json``.
        """
        self.path = path or PATHS.speakers_json

    def all(self) -> list[Speaker]:
        """Return every profile (empty list if the file does not exist)."""
        return [Speaker.from_dict(d) for d in read_json(self.path, default=[])]

    def get(self, speaker_id: str) -> Speaker:
        """Return one profile.

        Args:
            speaker_id: Identifier, e.g. ``"spk001"``.

        Returns:
            The speaker profile.

        Raises:
            KeyError: If no profile has this identifier.
        """
        for s in self.all():
            if s.id == speaker_id:
                return s
        raise KeyError(speaker_id)

    def next_id(self) -> str:
        """Return the next free ``spkNNN`` identifier (``spk001`` for an empty registry)."""
        numbers = [int(m.group(1)) for s in self.all() if (m := re.fullmatch(r"spk(\d+)", s.id))]
        return f"spk{max(numbers, default=0) + 1:03d}"

    def save(self, speaker: Speaker) -> Speaker:
        """Create or replace a profile.

        The consent date is set to today when consent is given without a date.

        Args:
            speaker: Profile to store.

        Returns:
            The stored profile.

        Raises:
            ValueError: If the identifier contains characters other than
                lower-case letters, digits, ``-`` or ``_``.
        """
        if not re.fullmatch(r"[a-z0-9_-]+", speaker.id):
            raise ValueError("identifiant : minuscules, chiffres, - ou _ uniquement")
        if speaker.consentement and not speaker.date_consentement:
            speaker.date_consentement = date.today().isoformat()
        others = [s for s in self.all() if s.id != speaker.id]
        write_json(self.path, [s.as_dict() for s in [*others, speaker]])
        return speaker

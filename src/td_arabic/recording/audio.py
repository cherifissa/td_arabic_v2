"""Recording processing: WAV decoding, mono mix-down, resampling, leading and
trailing silence removal, peak normalisation, 16-bit PCM encoding.

Standard library + numpy (scipy, when available, for high-quality
resampling). The default output format (16 kHz, mono, 16-bit) is the
standard of speech-recognition corpora (Common Voice, MMS, Whisper).
"""

from __future__ import annotations

import io
import wave
from dataclasses import dataclass
from math import gcd
from pathlib import Path

import numpy as np

SAMPLE_RATES = (16000, 22050, 24000, 44100, 48000)


@dataclass
class AudioSettings:
    """Per-speaker processing settings.

    Attributes:
        sample_rate: Output sample rate in Hz (16 kHz for ASR, 22.05 or
            44.1 kHz for speech synthesis).
        trim_silence: Remove leading and trailing silence.
        silence_threshold_db: RMS level (dBFS) below which a frame counts as
            silence; raise it in a noisy room.
        padding_ms: Silence kept before and after the speech.
        normalize: Scale the take so that its peak reaches ``peak_dbfs``.
        peak_dbfs: Target peak after normalisation.
        min_duration_s: Shorter takes are rejected.
        max_duration_s: Longer takes are rejected.
    """

    sample_rate: int = 16000
    trim_silence: bool = True
    silence_threshold_db: float = -40.0
    padding_ms: int = 150
    normalize: bool = True
    peak_dbfs: float = -1.0
    min_duration_s: float = 0.5
    max_duration_s: float = 30.0


@dataclass
class AudioClip:
    """Mono audio in memory.

    Attributes:
        samples: float32 samples in [-1, 1].
        sample_rate: Sample rate in Hz.
    """

    samples: np.ndarray
    sample_rate: int

    @property
    def duration(self) -> float:
        """Duration in seconds."""
        return len(self.samples) / self.sample_rate

    @property
    def peak_dbfs(self) -> float:
        """Peak level in dBFS (``-inf`` for silence)."""
        peak = float(np.max(np.abs(self.samples))) if len(self.samples) else 0.0
        return 20 * np.log10(peak) if peak > 0 else -np.inf


class AudioError(ValueError):
    """Raised when a take cannot be decoded or is unusable (too short/long)."""


def decode_wav(data: bytes) -> AudioClip:
    """Decode an integer PCM WAV file into a mono clip.

    Args:
        data: WAV bytes, 8/16/24/32-bit integer PCM, any number of channels.

    Returns:
        The clip, channels averaged to mono, as float32 in [-1, 1].

    Raises:
        AudioError: If the data is not a readable WAV or uses an unsupported
            sample width (e.g. 32-bit float).
    """
    try:
        with wave.open(io.BytesIO(data)) as wav:
            channels, width, rate = wav.getnchannels(), wav.getsampwidth(), wav.getframerate()
            frames = wav.readframes(wav.getnframes())
    except (wave.Error, EOFError) as exc:
        raise AudioError(f"WAV illisible : {exc}") from exc

    if width == 1:
        samples = (np.frombuffer(frames, np.uint8).astype(np.float32) - 128) / 128
    elif width == 2:
        samples = np.frombuffer(frames, "<i2").astype(np.float32) / 32768
    elif width == 3:
        raw = np.frombuffer(frames, np.uint8).reshape(-1, 3)
        ints = (raw[:, 0].astype(np.int32) | raw[:, 1].astype(np.int32) << 8
                | raw[:, 2].astype(np.int32) << 16)
        ints = np.where(ints >= 1 << 23, ints - (1 << 24), ints)
        samples = ints.astype(np.float32) / (1 << 23)
    elif width == 4:
        samples = np.frombuffer(frames, "<i4").astype(np.float32) / 2**31
    else:
        raise AudioError(f"profondeur non gérée : {8 * width} bits")
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return AudioClip(samples.astype(np.float32), rate)


def resample(clip: AudioClip, target_rate: int) -> AudioClip:
    """Change the sample rate of a clip.

    Uses polyphase filtering (``scipy.signal.resample_poly``) when scipy is
    installed, otherwise linear interpolation.

    Args:
        clip: Input clip.
        target_rate: Desired sample rate in Hz.

    Returns:
        A new clip at ``target_rate``, clipped to [-1, 1].
    """
    if clip.sample_rate == target_rate or not len(clip.samples):
        return AudioClip(clip.samples, target_rate)
    try:
        from scipy.signal import resample_poly
        g = gcd(clip.sample_rate, target_rate)
        out = resample_poly(clip.samples, target_rate // g, clip.sample_rate // g)
    except ImportError:  # linear interpolation fallback
        n = int(round(len(clip.samples) * target_rate / clip.sample_rate))
        out = np.interp(np.linspace(0, len(clip.samples) - 1, n),
                        np.arange(len(clip.samples)), clip.samples)
    return AudioClip(np.clip(out, -1, 1).astype(np.float32), target_rate)


def trim_silence(clip: AudioClip, threshold_db: float, padding_ms: int, frame_ms: int = 20) -> AudioClip:
    """Cut leading and trailing silence, based on per-frame RMS energy.

    Args:
        clip: Input clip.
        threshold_db: Frames whose RMS level is at or below this (dBFS) are silent.
        padding_ms: Silence kept before the first and after the last voiced frame.
        frame_ms: Analysis frame length.

    Returns:
        The trimmed clip; an empty clip if no frame is above the threshold.
    """
    frame = max(1, clip.sample_rate * frame_ms // 1000)
    n_frames = len(clip.samples) // frame
    if n_frames == 0:
        return clip
    frames = clip.samples[: n_frames * frame].reshape(n_frames, frame)
    rms_db = 20 * np.log10(np.sqrt(np.mean(frames**2, axis=1)) + 1e-10)
    voiced = np.flatnonzero(rms_db > threshold_db)
    if not len(voiced):
        return AudioClip(clip.samples[:0], clip.sample_rate)
    pad = clip.sample_rate * padding_ms // 1000
    start = max(0, voiced[0] * frame - pad)
    end = min(len(clip.samples), (voiced[-1] + 1) * frame + pad)
    return AudioClip(clip.samples[start:end], clip.sample_rate)


def normalize_peak(clip: AudioClip, peak_dbfs: float) -> AudioClip:
    """Scale a clip so that its peak reaches ``peak_dbfs``.

    Args:
        clip: Input clip.
        peak_dbfs: Target peak level, e.g. ``-1.0``.

    Returns:
        The scaled clip (unchanged if it is pure silence).
    """
    peak = float(np.max(np.abs(clip.samples))) if len(clip.samples) else 0.0
    if peak == 0:
        return clip
    gain = 10 ** (peak_dbfs / 20) / peak
    return AudioClip((clip.samples * gain).astype(np.float32), clip.sample_rate)


def process(data: bytes, settings: AudioSettings) -> AudioClip:
    """Apply the full processing chain to one take.

    Decode -> mono -> resample -> trim silence -> check duration -> normalise.

    Args:
        data: WAV bytes as recorded by the browser.
        settings: The speaker's audio settings.

    Returns:
        The processed clip, ready for :func:`encode_wav`.

    Raises:
        AudioError: If the WAV cannot be decoded, or the trimmed take is
            shorter than ``min_duration_s`` or longer than ``max_duration_s``.
    """
    clip = decode_wav(data)
    clip = resample(clip, settings.sample_rate)
    if settings.trim_silence:
        clip = trim_silence(clip, settings.silence_threshold_db, settings.padding_ms)
    if clip.duration < settings.min_duration_s:
        raise AudioError(f"prise trop courte ({clip.duration:.2f} s) : parlez plus près du micro "
                         "ou baissez le seuil de silence")
    if clip.duration > settings.max_duration_s:
        raise AudioError(f"prise trop longue ({clip.duration:.1f} s)")
    if settings.normalize:
        clip = normalize_peak(clip, settings.peak_dbfs)
    return clip


def encode_wav(clip: AudioClip) -> bytes:
    """Encode a clip as a mono 16-bit PCM WAV file.

    Args:
        clip: Clip to encode (samples outside [-1, 1] are clipped).

    Returns:
        The WAV file bytes.
    """
    pcm = (np.clip(clip.samples, -1, 1) * 32767).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(clip.sample_rate)
        wav.writeframes(pcm)
    return buf.getvalue()


def read_wav_file(path: Path) -> AudioClip:
    """Read a WAV file from disk.

    Args:
        path: WAV file.

    Returns:
        The decoded mono clip.

    Raises:
        FileNotFoundError: If the file does not exist.
        AudioError: If it is not a supported WAV file.
    """
    return decode_wav(Path(path).read_bytes())

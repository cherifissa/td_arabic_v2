"""Tests of audio processing, speaker profiles and the audio corpus."""

import io
import wave

import numpy as np
import pytest

from td_arabic.recording.audio import (
    AudioError, AudioSettings, decode_wav, encode_wav, process, AudioClip,
)
from td_arabic.recording.dataset import AudioDataset, ConsentError
from td_arabic.recording.speakers import Speaker, SpeakerRegistry


def make_wav(rate=48000, channels=2, speech_s=1.0, silence_s=0.5) -> bytes:
    t = np.arange(int(rate * speech_s)) / rate
    tone = 0.3 * np.sin(2 * np.pi * 220 * t)
    signal = np.concatenate([np.zeros(int(rate * silence_s)), tone, np.zeros(int(rate * silence_s))])
    pcm = (np.repeat(signal[:, None], channels, axis=1) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def test_process_resamples_trims_and_normalizes():
    clip = process(make_wav(), AudioSettings(sample_rate=16000, padding_ms=100))
    assert clip.sample_rate == 16000
    assert 1.1 < clip.duration < 1.3          # 1 s de parole + 2 x 100 ms de marge
    assert abs(clip.peak_dbfs - (-1.0)) < 0.1


def test_wav_roundtrip():
    clip = AudioClip(np.linspace(-0.5, 0.5, 1600, dtype=np.float32), 16000)
    back = decode_wav(encode_wav(clip))
    assert back.sample_rate == 16000 and np.allclose(back.samples, clip.samples, atol=1e-4)


def test_too_short_take_is_rejected():
    with pytest.raises(AudioError):
        process(make_wav(speech_s=0.1, silence_s=0.2), AudioSettings())


def test_speakers_and_dataset(tmp_path):
    registry = SpeakerRegistry(tmp_path / "locuteurs.json")
    assert registry.next_id() == "spk001"
    speaker = registry.save(Speaker(id="spk001", pseudo="A", consentement=True))
    assert speaker.date_consentement
    assert registry.next_id() == "spk002"
    assert registry.get("spk001").reglages.sample_rate == 16000

    dataset = AudioDataset(tmp_path)
    sentence = {"id": "mar-1234", "td": "Ana nachri laham.", "fr": "J'achète de la viande.", "theme": "marche"}
    saved = dataset.save_take(speaker, sentence, make_wav())
    assert saved.path.exists() and saved.row["file_name"] == "wavs/spk001/mar-1234.wav"
    dataset.save_take(speaker, sentence, make_wav())  # nouvelle prise : remplace
    assert len(dataset.load()) == 1 and dataset.recorded_ids("spk001") == {"mar-1234"}
    assert dataset.stats()["locuteurs"] == 1

    with pytest.raises(ConsentError):
        dataset.save_take(Speaker(id="spk002", pseudo="B"), sentence, make_wav())
    dataset.delete("spk001", "mar-1234")
    assert dataset.load().empty and not saved.path.exists()

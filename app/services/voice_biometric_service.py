"""
Voice Biometric Service

Lightweight speaker verification engine using MFCC-based speaker embeddings.
Creates 240-dimensional voice embeddings from Mel-Frequency Cepstral
Coefficients and their deltas, then compares them via cosine similarity to
determine if the person speaking matches the enrolled student.

This approach uses only numpy + scipy (no torch/resemblyzer), making the
Docker image small and the build fast.

Enrollment flow:
    1. Student submits 3–5 audio samples (WAV, base64-encoded).
    2. Each sample is preprocessed and encoded into a 240-dim embedding.
    3. Embeddings are averaged into a single voiceprint and stored in the DB.

Verification flow:
    1. During an assessment, audio is captured alongside each spoken response.
    2. The audio is encoded into an embedding.
    3. Cosine similarity is computed against the stored voiceprint.
    4. If similarity < threshold → verification fails → session flagged.

All audio processing runs in a thread pool to avoid blocking the event loop.
"""

import base64
import io
import logging
import wave

import numpy as np
from scipy.fftpack import dct

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────

VERIFICATION_THRESHOLD = 0.70

# Minimum audio duration (seconds) for a reliable embedding
MIN_AUDIO_DURATION = 1.5

# Minimum samples required to finalize enrollment
MIN_ENROLLMENT_SAMPLES = 3

# Maximum consecutive verification failures before session is flagged
MAX_CONSECUTIVE_FAILURES = 3

# ── MFCC parameters ──────────────────────────────────────────────────

_SAMPLE_RATE = 16000
_N_MFCC = 20
_N_MELS = 40
_N_FFT = 512
_HOP_LENGTH = 160       # 10 ms
_WIN_LENGTH = 400       # 25 ms
_PRE_EMPHASIS = 0.97

# Cached mel filterbank (computed once)
_mel_fb: np.ndarray | None = None


def _mel_filterbank() -> np.ndarray:
    """Create a mel-spaced triangular filterbank (cached)."""
    global _mel_fb
    if _mel_fb is not None:
        return _mel_fb

    n_bins = _N_FFT // 2 + 1
    low_mel = 0.0
    high_mel = 2595.0 * np.log10(1.0 + (_SAMPLE_RATE / 2.0) / 700.0)
    mel_points = np.linspace(low_mel, high_mel, _N_MELS + 2)
    hz_points = 700.0 * (10.0 ** (mel_points / 2595.0) - 1.0)
    bin_points = np.floor((_N_FFT + 1) * hz_points / _SAMPLE_RATE).astype(int)

    fb = np.zeros((_N_MELS, n_bins))
    for i in range(_N_MELS):
        left, center, right = bin_points[i], bin_points[i + 1], bin_points[i + 2]
        for j in range(left, center):
            if center != left:
                fb[i, j] = (j - left) / (center - left)
        for j in range(center, right):
            if right != center:
                fb[i, j] = (right - j) / (right - center)

    _mel_fb = fb
    return fb


def _compute_mfcc(audio: np.ndarray) -> np.ndarray:
    """Compute MFCCs from 16 kHz float32 mono audio. Returns (n_frames, n_mfcc)."""
    # Pre-emphasis
    emphasized = np.append(audio[0], audio[1:] - _PRE_EMPHASIS * audio[:-1])

    # Framing
    n_frames = 1 + (len(emphasized) - _WIN_LENGTH) // _HOP_LENGTH
    if n_frames < 1:
        raise ValueError("Audio too short for MFCC extraction")

    indices = (
        np.arange(_WIN_LENGTH)[None, :]
        + np.arange(n_frames)[:, None] * _HOP_LENGTH
    )
    frames = emphasized[indices]

    # Hamming window
    frames *= np.hamming(_WIN_LENGTH)

    # Power spectrum
    mag = np.abs(np.fft.rfft(frames, _N_FFT))
    power = (mag ** 2) / _N_FFT

    # Mel filterbank -> log mel energies
    mel_spec = power @ _mel_filterbank().T
    mel_spec = np.maximum(mel_spec, np.finfo(float).eps)
    log_mel = np.log(mel_spec)

    # DCT -> MFCCs
    mfccs = dct(log_mel, type=2, axis=1, norm="ortho")[:, :_N_MFCC]
    return mfccs


def _compute_delta(features: np.ndarray) -> np.ndarray:
    """Compute first-order delta features."""
    padded = np.pad(features, ((1, 1), (0, 0)), mode="edge")
    return (padded[2:] - padded[:-2]) / 2.0


def _resample(samples: np.ndarray, orig_rate: int, target_rate: int) -> np.ndarray:
    """Simple linear-interpolation resampler."""
    if orig_rate == target_rate:
        return samples
    duration = len(samples) / orig_rate
    target_len = int(duration * target_rate)
    indices = np.linspace(0, len(samples) - 1, target_len)
    return np.interp(indices, np.arange(len(samples)), samples).astype(np.float32)


# ── Audio helpers ─────────────────────────────────────────────────────


def _decode_audio_b64(audio_b64: str) -> np.ndarray:
    """Decode base64-encoded WAV audio into a float32 numpy array at 16 kHz.

    Supports:
      - Standard WAV (RIFF header present)
      - Raw PCM 16-bit signed LE mono at 16 kHz (no header)
    """
    raw = base64.b64decode(audio_b64)

    if raw[:4] == b"RIFF":
        buf = io.BytesIO(raw)
        with wave.open(buf, "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())

        if sampwidth == 2:
            samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        elif sampwidth == 4:
            samples = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            raise ValueError(f"Unsupported sample width: {sampwidth}")

        # Mono mixdown
        if n_channels > 1:
            samples = samples.reshape(-1, n_channels).mean(axis=1)

        # Resample to 16 kHz if needed
        if framerate != _SAMPLE_RATE:
            samples = _resample(samples, framerate, _SAMPLE_RATE)

        return samples

    # Fallback: raw PCM 16-bit signed LE mono 16 kHz
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return samples


def _compute_embedding(audio: np.ndarray) -> np.ndarray:
    """Compute a 240-dimensional speaker embedding from audio samples.

    The embedding is built from statistical summaries of MFCCs,
    delta-MFCCs, and delta-delta-MFCCs (20 coefficients each ×
    4 statistics × 3 feature sets = 240 dimensions).
    """
    mfccs = _compute_mfcc(audio)
    deltas = _compute_delta(mfccs)
    delta_deltas = _compute_delta(deltas)

    parts: list[np.ndarray] = []
    for feat in (mfccs, deltas, delta_deltas):
        parts.append(feat.mean(axis=0))
        parts.append(feat.std(axis=0))
        parts.append(np.percentile(feat, 25, axis=0))
        parts.append(np.percentile(feat, 75, axis=0))

    embedding = np.concatenate(parts).astype(np.float32)

    # L2-normalize
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm

    return embedding


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


# ── Public API (all synchronous — call via run_in_executor) ───────────


def compute_embedding_from_audio(audio_b64: str) -> list[float]:
    """Convert base64 audio to a 240-dim embedding vector (as list of floats).

    Raises ValueError if audio is too short for a reliable embedding.
    """
    audio = _decode_audio_b64(audio_b64)
    duration = len(audio) / _SAMPLE_RATE
    if duration < MIN_AUDIO_DURATION:
        raise ValueError(
            f"Audio too short ({duration:.1f}s). "
            f"Need at least {MIN_AUDIO_DURATION}s for a reliable voiceprint."
        )
    embedding = _compute_embedding(audio)
    return embedding.tolist()


def average_embeddings(embeddings: list[list[float]]) -> list[float]:
    """Average multiple embeddings into a single voiceprint."""
    arr = np.array(embeddings, dtype=np.float32)
    avg = arr.mean(axis=0)
    # L2-normalize the averaged embedding
    norm = np.linalg.norm(avg)
    if norm > 0:
        avg = avg / norm
    return avg.tolist()


def verify_speaker(
    live_embedding: list[float],
    stored_embedding: list[float],
    threshold: float = VERIFICATION_THRESHOLD,
) -> tuple[bool, float]:
    """Compare a live audio embedding against a stored voiceprint.

    Returns (passed, similarity_score).
    """
    live = np.array(live_embedding, dtype=np.float32)
    stored = np.array(stored_embedding, dtype=np.float32)
    score = _cosine_similarity(live, stored)
    passed = score >= threshold
    logger.debug(
        "Speaker verification: similarity=%.4f threshold=%.2f passed=%s",
        score, threshold, passed,
    )
    return passed, score

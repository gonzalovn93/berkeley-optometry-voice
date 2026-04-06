import sounddevice as sd
import numpy as np

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024
SILENCE_THRESHOLD = 0.02      # RMS volume below this = silence
SILENCE_DURATION = 1.5        # seconds of silence before stopping recording
MIN_SPEECH_DURATION = 0.5     # seconds of audio before silence detection kicks in


def list_audio_devices():
    """List all available audio devices at startup."""
    print("\n--- Audio Devices ---")
    print(sd.query_devices())
    print(f"\nDefault input:  {sd.default.device[0]}")
    print(f"Default output: {sd.default.device[1]}")
    print("---------------------\n")


def record_until_silence() -> np.ndarray | None:
    """
    Records from microphone until 1.5 seconds of silence detected.
    Returns float32 numpy array or None if nothing captured.
    """
    print("🎤  Listening... (speak now, pause when done)")

    audio_chunks = []
    silent_chunks = 0
    speech_started = False

    chunks_per_second = SAMPLE_RATE // CHUNK_SIZE
    max_silent_chunks = int(SILENCE_DURATION * chunks_per_second)
    min_speech_chunks = int(MIN_SPEECH_DURATION * chunks_per_second)

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
        blocksize=CHUNK_SIZE,
    ) as stream:
        while True:
            chunk, _ = stream.read(CHUNK_SIZE)
            rms = float(np.sqrt(np.mean(chunk ** 2)))

            if rms > SILENCE_THRESHOLD:
                speech_started = True
                silent_chunks = 0
                audio_chunks.append(chunk.copy())
            elif speech_started:
                audio_chunks.append(chunk.copy())
                silent_chunks += 1
                if silent_chunks >= max_silent_chunks:
                    break
            else:
                # Not yet speaking — collect a small buffer anyway
                audio_chunks.append(chunk.copy())
                if len(audio_chunks) > chunks_per_second * 5:
                    # 5 seconds with no speech — return None
                    return None

    if len(audio_chunks) < min_speech_chunks:
        return None

    return np.concatenate(audio_chunks, axis=0)


def play_audio_bytes(audio_bytes: bytes) -> None:
    """
    Plays raw PCM int16 bytes through the speaker.
    OpenAI TTS returns PCM at 24kHz by default.
    """
    audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    sd.play(audio_array, samplerate=24000)
    sd.wait()

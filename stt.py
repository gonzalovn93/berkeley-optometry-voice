import io
import os
import numpy as np
import scipy.io.wavfile as wav
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
SAMPLE_RATE = 16000

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def transcribe(audio_array: np.ndarray) -> str:
    """
    Sends recorded audio to OpenAI Whisper for transcription.
    Returns transcript string or empty string if nothing heard.
    """

    # Convert float32 -> int16 WAV bytes
    audio_int16 = (audio_array * 32767).astype(np.int16)
    buffer = io.BytesIO()
    wav.write(buffer, SAMPLE_RATE, audio_int16)
    buffer.seek(0)
    buffer.name = "recording.wav"

    response = _client.audio.transcriptions.create(
        model="whisper-1",
        file=buffer,
        language="en",
    )

    return response.text.strip()

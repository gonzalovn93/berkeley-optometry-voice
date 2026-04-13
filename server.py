"""
FastAPI server for the Berkeley Optometry Voice Agent.
Serves a browser UI where users can talk to Maya via push-to-talk.
"""

import io
import os
import uuid
from urllib.parse import quote
import numpy as np
import scipy.io.wavfile as wav
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from stt import transcribe
from tts import synthesize, synthesize_parallel, get_filler_audio
from conversation import ConversationManager
from transcript import TranscriptRecorder

app = FastAPI(title="Berkeley Optometry Voice Agent")

# ── Session storage (in-memory for demo) ────────────────────────────────────

sessions: dict[str, dict] = {}

OPENING_LINE = (
    "Thank you for calling Berkeley Optometry Clinic. "
    "This is Maya, your scheduling assistant. How can I help you today?"
)


def get_or_create_session(session_id: str) -> dict:
    if session_id not in sessions:
        convo = ConversationManager()
        recorder = TranscriptRecorder()
        # Prime the conversation
        convo.add_user_turn("(call started)")
        convo.get_response()
        sessions[session_id] = {
            "convo": convo,
            "recorder": recorder,
            "started": True,
        }
    return sessions[session_id]


# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    with open(os.path.join(os.path.dirname(__file__), "templates", "index.html")) as f:
        return f.read()


@app.post("/api/start")
async def start_call():
    """Start a new call — returns session ID and Maya's greeting audio."""
    session_id = str(uuid.uuid4())[:8]
    session = get_or_create_session(session_id)
    session["recorder"].add_turn("Maya", OPENING_LINE)

    audio_bytes = synthesize(OPENING_LINE)

    return Response(
        content=audio_bytes,
        media_type="audio/pcm",
        headers={
            "X-Session-Id": session_id,
            "X-Maya-Text": quote(OPENING_LINE),
        },
    )


@app.post("/api/talk")
async def talk(
    audio: UploadFile = File(...),
    session_id: str = Form(...),
):
    """
    Receive caller audio, transcribe, get Maya's response, return TTS audio.
    """
    session = get_or_create_session(session_id)
    convo = session["convo"]
    recorder = session["recorder"]

    # Read uploaded audio
    audio_data = await audio.read()

    # Convert WAV bytes to numpy array
    buffer = io.BytesIO(audio_data)
    try:
        sample_rate, audio_array = wav.read(buffer)
        if audio_array.dtype == np.int16:
            audio_array = audio_array.astype(np.float32) / 32768.0
    except Exception:
        return JSONResponse({"error": "Could not read audio file"}, status_code=400)

    # STT
    user_text = transcribe(audio_array)
    if not user_text:
        fallback = "I'm sorry, I didn't catch that. Could you say that once more?"
        recorder.add_turn("Maya", fallback)
        audio_bytes = synthesize(fallback)
        return Response(
            content=audio_bytes,
            media_type="audio/pcm",
            headers={
                "X-Maya-Text": quote(fallback),
                "X-Caller-Text": "",
                "X-Call-Ended": "false",
                "X-Escalated": "false",
            },
        )

    recorder.add_turn("Caller", user_text)

    # Claude response
    convo.add_user_turn(user_text)
    maya_response = convo.get_response()

    if not maya_response:
        maya_response = "I'm sorry, something went wrong. Let me connect you with our team."

    recorder.add_turn("Maya", maya_response)

    # TTS — parallel sentence synthesis (2-3x faster for multi-sentence responses)
    audio_bytes = synthesize_parallel(maya_response)

    # Prepend filler audio when tool calls caused extra latency.
    # The caller hears "Mm-hmm, let me check on that" immediately,
    # masking the 1-2 seconds of tool execution + second LLM call.
    if convo.last_used_tools:
        audio_bytes = get_filler_audio() + audio_bytes

    call_ended = convo.call_ended
    escalated = convo.escalated

    # Save transcript if call ended
    if call_ended or escalated:
        outcome = "escalated to human" if escalated else "completed successfully"
        recorder.save(token_usage=convo.token_usage, outcome=outcome)
        # Clean up session
        if session_id in sessions:
            del sessions[session_id]

    return Response(
        content=audio_bytes,
        media_type="audio/pcm",
        headers={
            "X-Maya-Text": quote(maya_response.replace("\n", " ")),
            "X-Caller-Text": quote(user_text),
            "X-Call-Ended": str(call_ended).lower(),
            "X-Escalated": str(escalated).lower(),
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

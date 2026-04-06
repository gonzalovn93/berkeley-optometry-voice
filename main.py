import os
import sys
from dotenv import load_dotenv

from audio import record_until_silence, play_audio_bytes, list_audio_devices
from stt import transcribe
from tts import synthesize
from conversation import ConversationManager
from transcript import TranscriptRecorder

load_dotenv()

OPENING_LINE = (
    "Thank you for calling Berkeley Optometry Clinic. "
    "This is Maya, your scheduling assistant. How can I help you today?"
)


def speak_and_record(text: str, tts_fn, playback_fn,
                     recorder: TranscriptRecorder) -> None:
    """Synthesize, play, and record Maya's turn."""
    print(f"\n🔊  Maya: {text}\n")
    recorder.add_turn("Maya", text)
    audio_bytes = tts_fn(text)
    playback_fn(audio_bytes)


def main():
    print("\n" + "=" * 60)
    print("  Berkeley Optometry Clinic — Voice Scheduling Agent")
    print("=" * 60)

    # List audio devices so user can verify mic/speaker
    list_audio_devices()

    print("Starting call... Press Ctrl+C to end at any time.\n")

    convo = ConversationManager()
    recorder = TranscriptRecorder()

    # Opening greeting — no user input needed
    speak_and_record(OPENING_LINE, synthesize, play_audio_bytes, recorder)
    convo.add_user_turn("(call started)")
    convo.get_response()  # Prime the conversation state

    try:
        while not convo.call_ended and not convo.escalated:
            # Step 1: Record caller
            audio = record_until_silence()

            if audio is None:
                speak_and_record(
                    "Are you still there? Take your time.",
                    synthesize, play_audio_bytes, recorder,
                )
                continue

            # Step 2: Transcribe
            print("   ⏳  Transcribing...")
            user_text = transcribe(audio)

            if not user_text:
                speak_and_record(
                    "I'm sorry, I didn't catch that. Could you say that once more?",
                    synthesize, play_audio_bytes, recorder,
                )
                continue

            print(f"\n👤  Caller: {user_text}")
            recorder.add_turn("Caller", user_text)

            # Step 3: Get Claude's response (tool use handled inside)
            print("   ⏳  Thinking...")
            convo.add_user_turn(user_text)
            agent_response = convo.get_response()

            # Step 4: Speak response
            if agent_response:
                speak_and_record(
                    agent_response, synthesize, play_audio_bytes, recorder,
                )

    except KeyboardInterrupt:
        print("\n\nCall interrupted by user.")

    # Determine outcome
    if convo.escalated:
        outcome = "escalated to human"
    elif convo.call_ended:
        outcome = "completed successfully"
    else:
        outcome = "interrupted"

    # Save transcript
    recorder.save(
        token_usage=convo.token_usage,
        outcome=outcome,
    )

    print(f"\n✅  Call ended. Outcome: {outcome}")
    print(f"   Tokens used: {sum(convo.token_usage.values()):,}")


if __name__ == "__main__":
    main()

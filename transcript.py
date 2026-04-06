import os
from datetime import datetime


class TranscriptRecorder:
    def __init__(self):
        self.turns = []
        self.start_time = datetime.now()

    def add_turn(self, speaker: str, text: str):
        """speaker is 'Caller' or 'Maya'"""
        self.turns.append({
            "speaker": speaker,
            "text": text,
            "time": datetime.now().strftime("%H:%M:%S"),
        })

    def save(self, token_usage: dict, outcome: str = "completed") -> str:
        os.makedirs("output", exist_ok=True)
        filename = f"output/transcript_{self.start_time.strftime('%Y%m%d_%H%M%S')}.md"

        lines = [
            "# Berkeley Optometry Clinic — Call Transcript",
            f"**Date:** {self.start_time.strftime('%B %d, %Y')}",
            f"**Time:** {self.start_time.strftime('%I:%M %p')}",
            f"**Outcome:** {outcome}",
            f"**Tokens used:** {token_usage['input'] + token_usage['output']:,} "
            f"(input: {token_usage['input']:,} / output: {token_usage['output']:,})",
            "",
            "---",
            "",
        ]

        for turn in self.turns:
            prefix = "**Maya:**" if turn["speaker"] == "Maya" else "**Caller:**"
            lines.append(f"{prefix} {turn['text']}")
            lines.append("")

        content = "\n".join(lines)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"\n📄  Transcript saved to {filename}")
        return filename

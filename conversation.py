import anthropic
import json
import os
from dotenv import load_dotenv
from prompt import SYSTEM_PROMPT, TOOLS
from tools import execute_tool

load_dotenv()


class ConversationManager:
    MODEL = "claude-haiku-4-5-20251001"
    MAX_TOKENS = 256  # Maya speaks 2-3 sentences max

    def __init__(self):
        self.client = anthropic.Anthropic()
        self.messages = []
        self.call_ended = False
        self.escalated = False
        self.token_usage = {"input": 0, "output": 0}

    def add_user_turn(self, text: str):
        self.messages.append({"role": "user", "content": text})

    def get_response(self) -> str:
        """
        Sends current messages to Claude. Handles tool use loop.
        Returns the final text response to speak aloud.
        """
        while True:
            response = self.client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=self.messages,
            )

            self.token_usage["input"] += response.usage.input_tokens
            self.token_usage["output"] += response.usage.output_tokens

            # Tool use — execute tools, feed results back
            if response.stop_reason == "tool_use":
                self.messages.append({
                    "role": "assistant",
                    "content": response.content,
                })

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        print(f"   🔧 Tool call: {block.name}({json.dumps(block.input, indent=None)})")
                        result = execute_tool(block.name, block.input)
                        print(f"   ✓  Result: {json.dumps(result)}")

                        # Check for call end or escalation signals
                        if block.name == "end_call":
                            self.call_ended = True
                        if block.name == "escalate_to_human":
                            self.escalated = True

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        })

                self.messages.append({
                    "role": "user",
                    "content": tool_results,
                })
                continue  # Loop back to get Claude's next response

            # End turn — extract text response
            elif response.stop_reason == "end_turn":
                self.messages.append({
                    "role": "assistant",
                    "content": response.content,
                })
                text_response = " ".join(
                    block.text for block in response.content
                    if hasattr(block, "text")
                ).strip()
                return text_response

            else:
                return "I'm sorry, something went wrong. Let me connect you with our team."

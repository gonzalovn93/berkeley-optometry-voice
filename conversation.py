import anthropic
import json
import os
from dotenv import load_dotenv
from prompt import SYSTEM_PROMPT, TOOLS
from tools import execute_tool

load_dotenv()

# ── Prompt caching ─────────────────────────────────────────────────────────
# The system prompt (~650 tokens) and 7 tool schemas are identical on every
# turn.  Anthropic prompt caching keeps them in a server-side cache so only
# the first request in a 5-minute window pays the full processing cost.
# Subsequent turns see a cache read — ~100-200 ms faster and 90% cheaper
# on the cached prefix.

CACHED_SYSTEM = [
    {
        "type": "text",
        "text": SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"},
    }
]

CACHED_TOOLS = TOOLS[:-1] + [
    {**TOOLS[-1], "cache_control": {"type": "ephemeral"}}
]


class ConversationManager:
    MODEL = "claude-haiku-4-5-20251001"
    MAX_TOKENS = 512  # Enough for tool calls + spoken response

    def __init__(self):
        self.client = anthropic.Anthropic()
        self.messages = []
        self.call_ended = False
        self.escalated = False
        self.last_used_tools = False
        self.token_usage = {"input": 0, "output": 0}
        self.cache_metrics = {"read": 0, "created": 0}

    def add_user_turn(self, text: str):
        self.messages.append({"role": "user", "content": text})

    def _track_cache(self, usage):
        """Track prompt-cache hits for observability."""
        if hasattr(usage, "cache_read_input_tokens") and usage.cache_read_input_tokens:
            self.cache_metrics["read"] += usage.cache_read_input_tokens
        if hasattr(usage, "cache_creation_input_tokens") and usage.cache_creation_input_tokens:
            self.cache_metrics["created"] += usage.cache_creation_input_tokens

    def get_response(self) -> str:
        """
        Sends current messages to Claude. Handles tool use loop.
        Returns the final text response to speak aloud.
        Sets self.last_used_tools = True when tool calls occurred (signals
        the server to prepend filler audio).
        """
        self.last_used_tools = False

        while True:
            response = self.client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                system=CACHED_SYSTEM,
                tools=CACHED_TOOLS,
                messages=self.messages,
            )

            self.token_usage["input"] += response.usage.input_tokens
            self.token_usage["output"] += response.usage.output_tokens
            self._track_cache(response.usage)

            # Tool use — execute tools, feed results back
            if response.stop_reason == "tool_use":
                self.last_used_tools = True
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

            elif response.stop_reason == "max_tokens":
                # Response got truncated — extract any text we got
                self.messages.append({
                    "role": "assistant",
                    "content": response.content,
                })
                text_response = " ".join(
                    block.text for block in response.content
                    if hasattr(block, "text")
                ).strip()
                return text_response if text_response else "I'm sorry, could you repeat that?"

            else:
                return "I'm sorry, something went wrong. Let me connect you with our team."

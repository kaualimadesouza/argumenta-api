import anthropic

from argumenta.adapters.llm.prompts.reaction_v1 import (
    CONVINCED_INSTRUCTION,
    PROMPT_VERSION,
    REBUTTAL_INSTRUCTION,
    SYSTEM_PROMPT,
    USER_TEMPLATE,
)
from argumenta.application.reactions.ports import ReactionRequest, ReactionText
from argumenta.domain.enums import Verdict
from argumenta.domain.errors import EvaluationFailedError


class ClaudeReactionEngine:
    """Free-text generation, mild temperature: the reaction is performance,
    not judgement (the verdict was already decided by the evaluation engine)."""

    def __init__(self, api_key: str, model: str, max_tokens: int = 400) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def generate(self, request: ReactionRequest) -> ReactionText:
        instruction = (
            CONVINCED_INSTRUCTION if request.verdict == Verdict.APPROVED else REBUTTAL_INSTRUCTION
        )
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=0.7,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": USER_TEMPLATE.format(
                            character_name=request.character_name,
                            persona_brief=request.persona_brief,
                            chapter_objective=request.chapter_objective,
                            verdict_instruction=instruction,
                            student_text=request.student_text,
                        ),
                    }
                ],
            )
        except anthropic.AnthropicError as error:
            raise EvaluationFailedError(str(error)) from error

        body = "".join(block.text for block in response.content if block.type == "text").strip()
        if not body:
            raise EvaluationFailedError("reaction engine returned no text")
        return ReactionText(
            body=body,
            model=self._model,
            prompt_version=PROMPT_VERSION,
            output_tokens=response.usage.output_tokens,
        )

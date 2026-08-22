import anthropic

from argumenta.adapters.llm.contract import Effort, ensure_usable
from argumenta.adapters.llm.prompts.reaction_v1 import (
    CONVINCED_INSTRUCTION,
    PROMPT_VERSION,
    REBUTTAL_INSTRUCTION,
    SYSTEM_PROMPT,
    USER_TEMPLATE,
)
from argumenta.adapters.llm.prompts.student_text import defuse_fence
from argumenta.adapters.llm.usage import billed_input_tokens
from argumenta.application.reactions.ports import ReactionRequest, ReactionText
from argumenta.domain.enums import Verdict
from argumenta.domain.errors import EvaluationFailedError


class ClaudeReactionEngine:
    """Free text: the reaction is performance, not judgement (the verdict was
    already decided by the evaluation engine). Low effort and a budget with
    room to spare, because thinking comes out of max_tokens and a truncated
    reaction is an empty one."""

    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int = 1500,
        effort: Effort = "low",
        timeout: float = 30.0,
        max_retries: int = 1,
    ) -> None:
        # the call happens inside an open transaction, so the SDK default of ten
        # minutes would hold a pool connection idle in transaction that long
        self._client = anthropic.Anthropic(
            api_key=api_key, timeout=timeout, max_retries=max_retries
        )
        self._model = model
        self._max_tokens = max_tokens
        self._effort = effort

    def generate(self, request: ReactionRequest) -> ReactionText:
        instruction = (
            CONVINCED_INSTRUCTION if request.verdict == Verdict.APPROVED else REBUTTAL_INSTRUCTION
        )
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                output_config={"effort": self._effort},
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": USER_TEMPLATE.format(
                            character_name=request.character_name,
                            persona_brief=request.persona_brief,
                            chapter_objective=request.chapter_objective,
                            verdict_instruction=instruction,
                            student_text=defuse_fence(request.student_text),
                        ),
                    }
                ],
            )
        except anthropic.AnthropicError as error:
            raise EvaluationFailedError(str(error)) from error

        ensure_usable(response.stop_reason, self._max_tokens)
        body = "".join(block.text for block in response.content if block.type == "text").strip()
        if not body:
            raise EvaluationFailedError("reaction engine returned no text")
        return ReactionText(
            body=body,
            model=self._model,
            prompt_version=PROMPT_VERSION,
            input_tokens=billed_input_tokens(response.usage),
            output_tokens=response.usage.output_tokens,
        )

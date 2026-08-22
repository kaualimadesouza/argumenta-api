from argumenta.adapters.llm.effort import Effort
from argumenta.adapters.llm.prompts.reaction_v1 import (
    CONVINCED_INSTRUCTION,
    PROMPT_VERSION,
    REBUTTAL_INSTRUCTION,
    SYSTEM_PROMPT,
    USER_TEMPLATE,
)
from argumenta.adapters.llm.prompts.student_text import defuse_fence
from argumenta.adapters.llm.provider import LlmCall, LlmProvider
from argumenta.application.reactions.ports import ReactionRequest, ReactionText
from argumenta.domain.enums import Verdict


class LlmReactionEngine:
    """Free text: the reaction is performance, not judgement. Low effort and a
    budget with room to spare, because thinking comes out of the token budget and
    a truncated reaction is an empty one."""

    def __init__(
        self,
        provider: LlmProvider,
        max_tokens: int = 1500,
        effort: Effort | None = "low",
    ) -> None:
        self._provider = provider
        self._max_tokens = max_tokens
        self._effort = effort

    def generate(self, request: ReactionRequest) -> ReactionText:
        instruction = (
            CONVINCED_INSTRUCTION if request.verdict == Verdict.APPROVED else REBUTTAL_INSTRUCTION
        )
        reply = self._provider.text(
            LlmCall(
                system=SYSTEM_PROMPT,
                user=USER_TEMPLATE.format(
                    character_name=request.character_name,
                    persona_brief=request.persona_brief,
                    chapter_objective=request.chapter_objective,
                    verdict_instruction=instruction,
                    student_text=defuse_fence(request.student_text),
                ),
                max_tokens=self._max_tokens,
                effort=self._effort,
            )
        )
        return ReactionText(
            body=reply.body,
            model=reply.model,
            prompt_version=PROMPT_VERSION,
            input_tokens=reply.usage.input_tokens,
            output_tokens=reply.usage.output_tokens,
        )

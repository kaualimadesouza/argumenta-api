"""Issue #43: the vendor is configuration. Each provider is held to the same
contract with a fake client, and the schema translation is checked against the
real evaluation contract, because that is what breaks on a strict endpoint."""

import json
from types import SimpleNamespace
from typing import Any

import pytest

from argumenta.adapters.llm.anthropic_provider import AnthropicProvider
from argumenta.adapters.llm.evaluation_engine import EvaluationOutput
from argumenta.adapters.llm.factory import build_provider
from argumenta.adapters.llm.google_provider import GoogleProvider
from argumenta.adapters.llm.openai_provider import OpenAiProvider
from argumenta.adapters.llm.provider import LlmCall, StructuredCall
from argumenta.adapters.llm.schema import inlined_schema, strict_schema
from argumenta.domain.errors import EvaluationFailedError
from argumenta.settings import Settings

_SCHEMA = EvaluationOutput.model_json_schema()
_PAYLOAD = {
    "scores": [{"dimension": "coesao", "score": 70, "evidence": "trecho"}],
    "annotations": [],
}


def _structured(effort: Any = "high") -> StructuredCall:
    return StructuredCall(
        system="sistema",
        user="texto do aluno",
        max_tokens=8000,
        effort=effort,
        name="report_evaluation",
        description="Report it.",
        schema=_SCHEMA,
    )


def _text(effort: Any = "low") -> LlmCall:
    return LlmCall(system="sistema", user="texto", max_tokens=1500, effort=effort)


class FakeCreate:
    def __init__(self, response: Any) -> None:
        self._response = response
        self.kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return self._response


class FakeOpenAi:
    def __init__(self, response: Any, **init: Any) -> None:
        self.completions = FakeCreate(response)
        self.chat = SimpleNamespace(completions=self.completions)
        self.init_kwargs = init


class FakeGoogle:
    def __init__(self, response: Any, **init: Any) -> None:
        self.models = FakeGenerate(response)
        self.init_kwargs = init


class FakeGenerate:
    def __init__(self, response: Any) -> None:
        self._response = response
        self.kwargs: dict[str, Any] = {}

    def generate_content(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return self._response


def _openai_response(
    content: str | None = None,
    finish_reason: str = "stop",
    refusal: str | None = None,
) -> Any:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason,
                message=SimpleNamespace(content=content, refusal=refusal),
            )
        ],
        usage=SimpleNamespace(prompt_tokens=1200, completion_tokens=400),
    )


def _google_response(text: str | None = None, finish_reason: str = "STOP") -> Any:
    return SimpleNamespace(
        text=text,
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name=finish_reason))],
        usage_metadata=SimpleNamespace(prompt_token_count=1200, candidates_token_count=400),
    )


@pytest.fixture
def openai_client(monkeypatch: pytest.MonkeyPatch) -> Any:
    import openai

    def install(response: Any) -> FakeOpenAi:
        holder: dict[str, FakeOpenAi] = {}

        def factory(**kwargs: Any) -> FakeOpenAi:
            holder["client"] = FakeOpenAi(response, **kwargs)
            return holder["client"]

        monkeypatch.setattr(openai, "OpenAI", factory)
        return holder  # type: ignore[return-value]

    return install


@pytest.fixture
def google_client(monkeypatch: pytest.MonkeyPatch) -> Any:
    from google import genai

    def install(response: Any) -> Any:
        holder: dict[str, FakeGoogle] = {}

        def factory(**kwargs: Any) -> FakeGoogle:
            holder["client"] = FakeGoogle(response, **kwargs)
            return holder["client"]

        monkeypatch.setattr(genai, "Client", factory)
        return holder

    return install


class TestStrictSchema:
    """OpenAI rejects a schema that allows unknown keys or optional fields, and
    the rejection is a 400 on every correction, not a bad grade."""

    def test_every_object_forbids_unknown_keys(self) -> None:
        strict = strict_schema(_SCHEMA)

        assert strict["additionalProperties"] is False
        assert strict["$defs"]["AnnotationOutput"]["additionalProperties"] is False

    def test_every_property_is_required_even_the_optional_ones(self) -> None:
        annotation = strict_schema(_SCHEMA)["$defs"]["AnnotationOutput"]

        assert "suggestion" in annotation["required"]
        assert set(annotation["required"]) == set(annotation["properties"])

    def test_the_original_schema_is_left_alone(self) -> None:
        strict_schema(_SCHEMA)

        assert "additionalProperties" not in _SCHEMA


class TestInlinedSchema:
    """Gemini's response schema has no `$ref`, so a nested contract sent as is
    comes back as an empty answer."""

    def test_no_reference_survives(self) -> None:
        inlined = json.dumps(inlined_schema(_SCHEMA))

        assert "$ref" not in inlined
        assert "$defs" not in inlined

    def test_the_nested_contract_is_still_there(self) -> None:
        inlined = inlined_schema(_SCHEMA)
        annotation = inlined["properties"]["annotations"]["items"]

        assert annotation["properties"]["span_start"]["type"] == "integer"
        assert "spelling" in annotation["properties"]["type"]["enum"]


class TestOpenAiProvider:
    def test_the_schema_goes_out_strict(self, openai_client: Any) -> None:
        holder = openai_client(_openai_response(content=json.dumps(_PAYLOAD)))

        OpenAiProvider(api_key="k", model="gpt-5").structured(_structured())

        sent = holder["client"].completions.kwargs["response_format"]
        assert sent["type"] == "json_schema"
        assert sent["json_schema"]["strict"] is True
        assert sent["json_schema"]["schema"]["additionalProperties"] is False

    def test_the_five_efforts_collapse_into_the_three_it_has(self, openai_client: Any) -> None:
        holder = openai_client(_openai_response(content=json.dumps(_PAYLOAD)))

        OpenAiProvider(api_key="k", model="gpt-5").structured(_structured(effort="xhigh"))

        assert holder["client"].completions.kwargs["reasoning_effort"] == "high"

    def test_no_thinking_knob_when_the_model_has_none(self, openai_client: Any) -> None:
        """A non-reasoning model answers 400 to `reasoning_effort`, so None means
        the knob is not sent at all."""
        holder = openai_client(_openai_response(content=json.dumps(_PAYLOAD)))

        OpenAiProvider(api_key="k", model="gpt-4.1").structured(_structured(effort=None))

        assert "reasoning_effort" not in holder["client"].completions.kwargs

    def test_the_payload_and_the_cost_come_back(self, openai_client: Any) -> None:
        openai_client(_openai_response(content=json.dumps(_PAYLOAD)))

        reply = OpenAiProvider(api_key="k", model="gpt-5").structured(_structured())

        assert reply.payload == _PAYLOAD
        assert (reply.usage.input_tokens, reply.usage.output_tokens) == (1200, 400)
        assert reply.model == "gpt-5"

    def test_a_truncated_answer_says_so_instead_of_failing_to_parse(
        self, openai_client: Any
    ) -> None:
        openai_client(_openai_response(content='{"scores"', finish_reason="length"))

        with pytest.raises(EvaluationFailedError, match="max_completion_tokens"):
            OpenAiProvider(api_key="k", model="gpt-5").structured(_structured())

    def test_a_refusal_is_not_an_empty_reaction(self, openai_client: Any) -> None:
        openai_client(_openai_response(content=None, refusal="I cannot help with that"))

        with pytest.raises(EvaluationFailedError, match="refused"):
            OpenAiProvider(api_key="k", model="gpt-5").text(_text())

    def test_free_text_comes_back_stripped(self, openai_client: Any) -> None:
        openai_client(_openai_response(content="  Esta bem, voce me convenceu.  "))

        reply = OpenAiProvider(api_key="k", model="gpt-5").text(_text())

        assert reply.body == "Esta bem, voce me convenceu."


class TestGoogleProvider:
    def test_the_schema_goes_out_inlined_as_json(self, google_client: Any) -> None:
        holder = google_client(_google_response(text=json.dumps(_PAYLOAD)))

        GoogleProvider(api_key="k", model="gemini-3-pro").structured(_structured())

        config = holder["client"].models.kwargs["config"]
        assert config["response_mime_type"] == "application/json"
        assert "$ref" not in json.dumps(config["response_schema"])

    def test_effort_becomes_a_thinking_budget(self, google_client: Any) -> None:
        holder = google_client(_google_response(text=json.dumps(_PAYLOAD)))

        GoogleProvider(api_key="k", model="gemini-3-pro").structured(_structured(effort="low"))

        assert holder["client"].models.kwargs["config"]["thinking_config"] == {
            "thinking_budget": 1024
        }

    def test_the_payload_and_the_cost_come_back(self, google_client: Any) -> None:
        google_client(_google_response(text=json.dumps(_PAYLOAD)))

        reply = GoogleProvider(api_key="k", model="gemini-3-pro").structured(_structured())

        assert reply.payload == _PAYLOAD
        assert (reply.usage.input_tokens, reply.usage.output_tokens) == (1200, 400)

    def test_running_out_of_room_says_so(self, google_client: Any) -> None:
        google_client(_google_response(text='{"scores"', finish_reason="MAX_TOKENS"))

        with pytest.raises(EvaluationFailedError, match="max_output_tokens"):
            GoogleProvider(api_key="k", model="gemini-3-pro").structured(_structured())

    def test_an_empty_reaction_is_a_failure(self, google_client: Any) -> None:
        google_client(_google_response(text="   "))

        with pytest.raises(EvaluationFailedError, match="no text"):
            GoogleProvider(api_key="k", model="gemini-3-pro").text(_text())


class TestVendorSelection:
    def test_each_vendor_gets_its_own_provider_and_its_own_key(
        self, openai_client: Any, google_client: Any
    ) -> None:
        openai_client(_openai_response(content="ok"))
        google_client(_google_response(text="ok"))
        settings = Settings(
            anthropic_api_key="anthropic-key",  # pragma: allowlist secret
            openai_api_key="openai-key",  # pragma: allowlist secret
            google_api_key="google-key",  # pragma: allowlist secret
        )

        built = {
            vendor: build_provider(settings, vendor=vendor, model="m", timeout=10.0)
            for vendor in ("anthropic", "openai", "google")
        }

        assert isinstance(built["anthropic"], AnthropicProvider)
        assert isinstance(built["openai"], OpenAiProvider)
        assert isinstance(built["google"], GoogleProvider)

    def test_the_reaction_can_answer_from_another_vendor(self) -> None:
        """The flavour beat is not the graded correction, so it can run on a
        cheaper model without moving a single score."""
        settings = Settings(llm_vendor="anthropic", reaction_llm_vendor="google")

        assert (settings.reaction_llm_vendor or settings.llm_vendor) == "google"

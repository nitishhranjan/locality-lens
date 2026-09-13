"""Error attribution in intent extraction.

The distinction these pin down is user-visible: `unreadable_profile` stops
the run and asks the person to reword, while `provider_error` degrades to a
default metric set and carries on. Getting it backwards means telling someone
their perfectly good description was unreadable because a rate limit was hit.
"""
import pytest

from lib import llm


class FakeCompletions:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0) if self.outcomes else self.outcomes
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeClient:
    def __init__(self, outcomes):
        self.chat = type("chat", (), {"completions": FakeCompletions(outcomes)})()


def response(payload: str):
    message = type("m", (), {"content": payload})()
    return type("r", (), {"choices": [type("c", (), {"message": message})()]})()


RATE_LIMIT = RuntimeError(
    "Error code: 429 - {'error': {'message': 'Rate limit reached for model "
    "`openai/gpt-oss-20b` in organization `org_01`'}}"
)
JSON_FAILURE = RuntimeError(
    "Error code: 400 - {'error': {'message': \"Failed to generate JSON. "
    "Please adjust your prompt. See 'failed_generation'\"}}"
)

GOOD = '{"usable": true, "profile_type": "family", "priorities": ["schools"], ' \
       '"concerns": [], "lifestyle": "", "selected_metrics": ["school_count"], ' \
       '"reasoning": "ok"}'
VAGUE = '{"usable": false, "profile_type": "unknown", "priorities": [], ' \
        '"concerns": [], "lifestyle": "", "selected_metrics": [], "reasoning": ""}'


@pytest.fixture
def stub(monkeypatch):
    def install(outcomes):
        client = FakeClient(outcomes)
        monkeypatch.setattr(llm, "_client", lambda cfg: client)
        return client

    return install


class TestJsonFailureDetection:
    def test_recognises_a_structured_output_rejection(self):
        assert llm._is_json_failure(str(JSON_FAILURE))

    @pytest.mark.parametrize(
        "message",
        [str(RATE_LIMIT), "Connection timeout", "500 internal server error", ""],
    )
    def test_other_faults_are_not_json_failures(self, message):
        assert not llm._is_json_failure(message)


class TestAttribution:
    async def test_rate_limit_is_a_provider_error(self, stub):
        stub([RATE_LIMIT, RATE_LIMIT])
        out = await llm.extract_intent("Retired, no car", "Indiranagar")
        assert out["reason"] == "provider_error"
        assert out["degraded"] is True

    async def test_repeated_json_failure_blames_the_text(self, stub):
        stub([JSON_FAILURE, JSON_FAILURE])
        out = await llm.extract_intent("???", "Indiranagar")
        assert out["reason"] == "unreadable_profile"
        assert out["hint"] == llm.UNREADABLE_HINT

    async def test_json_failure_then_rate_limit_blames_the_provider(self, stub):
        """The regression.

        A run that hit a JSON failure and then a rate limit never reached a
        verdict on the text. Reporting it as unreadable would stop the run and
        ask the user to reword something that may have been fine - the
        expensive error of the two.
        """
        stub([JSON_FAILURE, RATE_LIMIT])
        out = await llm.extract_intent("I cycle everywhere", "Indiranagar")
        assert out["reason"] == "provider_error"

    async def test_retry_after_a_json_failure_can_still_succeed(self, stub):
        client = stub([JSON_FAILURE, response(GOOD)])
        out = await llm.extract_intent("Family with kids", "Indiranagar")
        assert out["degraded"] is False
        assert out["selected_metrics"] == ["school_count"]
        assert client.chat.completions.calls == 2

    async def test_model_saying_unusable_stops_the_run(self, stub):
        stub([response(VAGUE)])
        out = await llm.extract_intent("okay", "Indiranagar")
        assert out["reason"] == "unreadable_profile"

    async def test_usable_response_is_not_degraded(self, stub):
        stub([response(GOOD)])
        out = await llm.extract_intent("Family with kids", "Indiranagar")
        assert out["degraded"] is False
        assert "reason" not in out

    async def test_empty_profile_short_circuits_without_calling_the_model(self, stub):
        client = stub([response(GOOD)])
        out = await llm.extract_intent("", "Indiranagar")
        assert out["degraded"] is True
        assert client.chat.completions.calls == 0

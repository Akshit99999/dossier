from pathlib import Path

import pytest

from dossier_agent.agent import DossierAgent, DossierError, ResearchResult, load_system_prompt


class FakeResponse:
    id = "resp_test"
    output_text = "1. SUMMARY — Test result."


class FakeResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse()


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


def test_builtin_policy_is_available_without_private_prompt_file():
    prompt = load_system_prompt()
    assert "Evidence over assumption" in prompt
    assert "Never fabricate" in prompt


def test_live_research_uses_web_search_and_prompt():
    client = FakeClient()
    agent = DossierAgent(client=client, model="test-model", provider="openai")

    result = agent.research("Is this claim supported?", output_format="human")

    call = client.responses.calls[0]
    assert result.response_id == "resp_test"
    assert call["model"] == "test-model"
    assert call["tools"] == [{"type": "web_search"}]
    assert "Research request: Is this claim supported?" in call["input"]
    assert "Evidence over assumption" in call["instructions"]
    assert call["store"] is False


def test_offline_mode_omits_web_tool():
    client = FakeClient()
    DossierAgent(client=client, provider="openai", live_web=False).research("Question")
    assert "tools" not in client.responses.calls[0]
    assert "Live web search is unavailable" in client.responses.calls[0]["input"]


def test_json_result_parses_fenced_json():
    result = ResearchResult('```json\n{"verdict":"confirmed"}\n```')
    assert result.as_json() == {"verdict": "confirmed"}


def test_json_result_rejects_invalid_json():
    with pytest.raises(DossierError):
        ResearchResult("not json").as_json()


def test_prompt_loader_accepts_private_plaintext_prompt(tmp_path: Path):
    path = tmp_path / "prompt.md"
    path.write_text("private local policy", encoding="utf-8")
    assert load_system_prompt(path) == "private local policy"

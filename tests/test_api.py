import json
import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_create_conversation(client):
    url = "/api/conversations/"
    resp = client.post(url, data=json.dumps({"title": "My Chat"}), content_type="application/json")
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "My Chat"


@pytest.mark.django_db
def test_message_flow_with_mocked_gemini(client, monkeypatch):
    # Create conversation
    resp = client.post("/api/conversations/", data=json.dumps({}), content_type="application/json")
    conv = resp.json()

    # Mock gemini
    from chat.services import gemini

    def fake_generate_reply(history, prompt, timeout_s=10):
        assert prompt == "Hello"
        return "Hi there!"

    monkeypatch.setattr(gemini, "generate_reply", fake_generate_reply)

    # Send message
    url = f"/api/conversations/{conv['id']}/messages/"
    send = client.post(url, data=json.dumps({"text": "Hello"}), content_type="application/json")
    assert send.status_code == 201
    payload = send.json()
    assert payload["user_message"]["role"] == "user"
    assert payload["ai_message"]["role"] == "ai"

    # List messages with since
    list_url = f"/api/conversations/{conv['id']}/messages/?since=0"
    messages = client.get(list_url)
    assert messages.status_code == 200
    data = messages.json()
    assert len(data["results"]) == 2

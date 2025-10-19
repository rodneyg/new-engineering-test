import json
import pytest
from django.core.cache import cache
from chat.models import Conversation, Message, MessageFeedback


@pytest.mark.django_db
def test_create_conversation(client):
    url = "/api/conversations/"
    resp = client.post(url, data=json.dumps({"title": "My Chat"}), content_type="application/json")
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "My Chat"


@pytest.mark.django_db
def test_delete_conversation_removes_messages(client):
    conv = Conversation.objects.create(title="Old chat")
    Message.objects.create(conversation=conv, role=Message.ROLE_USER, text="Hello")

    url = f"/api/conversations/{conv.id}/"
    resp = client.delete(url)
    assert resp.status_code == 204
    assert Conversation.objects.filter(id=conv.id).count() == 0
    assert Message.objects.filter(conversation_id=conv.id).count() == 0


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


@pytest.mark.django_db
def test_message_flow_fallback_when_gemini_unavailable(client, monkeypatch, settings):
    settings.DEBUG = True

    resp = client.post("/api/conversations/", data=json.dumps({}), content_type="application/json")
    conv = resp.json()

    from chat.services import gemini

    def failing_reply(history, prompt, timeout_s=10):
        raise gemini.GeminiServiceError("service down")

    monkeypatch.setattr(gemini, "generate_reply", failing_reply)

    url = f"/api/conversations/{conv['id']}/messages/"
    send = client.post(url, data=json.dumps({"text": "Hello"}), content_type="application/json")
    assert send.status_code == 201
    payload = send.json()
    assert payload["ai_message"]["role"] == "ai"
    assert payload["ai_message"]["text"].startswith("(Gemini unavailable)")


@pytest.mark.django_db
def test_message_rate_limiting(client, monkeypatch, settings):
    cache.clear()
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["message"] = "2/minute"

    resp = client.post("/api/conversations/", data=json.dumps({}), content_type="application/json")
    conv = resp.json()

    from chat.services import gemini

    monkeypatch.setattr(gemini, "generate_reply", lambda history, prompt, timeout_s=10: "ok")

    url = f"/api/conversations/{conv['id']}/messages/"
    body = json.dumps({"text": "Hello"})
    headers = {"content_type": "application/json"}

    first = client.post(url, data=body, **headers)
    second = client.post(url, data=body, **headers)
    assert first.status_code == 201
    assert second.status_code == 201

    third = client.post(url, data=body, **headers)
    assert third.status_code == 429
    detail = third.json().get("detail", "").lower()
    assert "throttle" in detail or "rate" in detail


@pytest.mark.django_db
def test_actionable_insights_success(client, monkeypatch):
    cache.clear()
    conv = Conversation.objects.create(title="Data")
    msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="Answer")
    MessageFeedback.objects.create(message=msg, is_helpful=False, comment="Too short")

    from chat.services import gemini

    monkeypatch.setattr(
        gemini,
        "generate_actionable_insights",
        lambda summary, timeout_s=15: "- Improve onboarding\n- Update docs",
    )

    resp = client.post("/api/insights/actionable/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["insights"].startswith("- ")


@pytest.mark.django_db
def test_actionable_insights_raises_502_when_disabled(client, monkeypatch, settings):
    cache.clear()
    settings.DEBUG = False
    from chat.services import gemini

    def boom(summary, timeout_s=15):
        raise gemini.GeminiServiceError("nope")

    monkeypatch.setattr(gemini, "generate_actionable_insights", boom)

    resp = client.post("/api/insights/actionable/")
    assert resp.status_code == 502
    assert "detail" in resp.json()


@pytest.mark.django_db
def test_actionable_insights_returns_placeholder_when_debug(client, monkeypatch, settings):
    cache.clear()
    settings.DEBUG = True
    from chat.services import gemini

    def boom(summary, timeout_s=15):
        raise gemini.GeminiServiceError("down")

    monkeypatch.setattr(gemini, "generate_actionable_insights", boom)

    resp = client.post("/api/insights/actionable/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["insights"].startswith("(Gemini unavailable)")


@pytest.mark.django_db
def test_submit_feedback_and_update(client):
    conv = Conversation.objects.create(title="Feedback Test")
    ai_msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="Assistant reply")
    url = f"/api/conversations/{conv.id}/messages/{ai_msg.id}/feedback/"

    first = client.post(url, data=json.dumps({"is_helpful": True}), content_type="application/json")
    assert first.status_code == 201
    payload = first.json()
    assert payload["is_helpful"] is True
    assert payload["comment"] == ""

    second = client.post(
        url,
        data=json.dumps({"is_helpful": False, "comment": "Needs work"}),
        content_type="application/json",
    )
    assert second.status_code == 200
    feedback = MessageFeedback.objects.get(message=ai_msg)
    assert feedback.is_helpful is False
    assert feedback.comment == "Needs work"


@pytest.mark.django_db
def test_feedback_rejected_for_user_message(client):
    conv = Conversation.objects.create(title="Feedback Test")
    user_msg = Message.objects.create(conversation=conv, role=Message.ROLE_USER, text="Hello")
    url = f"/api/conversations/{conv.id}/messages/{user_msg.id}/feedback/"

    resp = client.post(url, data=json.dumps({"is_helpful": True}), content_type="application/json")
    assert resp.status_code == 400
    assert resp.json()["detail"].lower().startswith("feedback is only")


@pytest.mark.django_db
def test_insights_endpoint(client):
    conv1 = Conversation.objects.create(title="First")
    conv2 = Conversation.objects.create(title="Second")
    msg1 = Message.objects.create(conversation=conv1, role=Message.ROLE_AI, text="Answer one")
    msg2 = Message.objects.create(conversation=conv1, role=Message.ROLE_AI, text="Answer two")
    msg3 = Message.objects.create(conversation=conv2, role=Message.ROLE_AI, text="Answer three")

    MessageFeedback.objects.create(message=msg1, is_helpful=True, comment="")
    MessageFeedback.objects.create(message=msg2, is_helpful=False, comment="Not great")
    MessageFeedback.objects.create(message=msg3, is_helpful=True, comment="Nice")

    resp = client.get("/api/insights/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_feedback"] == 3
    assert data["helpful_count"] == 2
    assert data["not_helpful_count"] == 1
    assert isinstance(data["per_conversation"], list)
    assert any(item["conversation_id"] == conv1.id for item in data["per_conversation"])
    assert len(data["recent_feedback"]) <= 10

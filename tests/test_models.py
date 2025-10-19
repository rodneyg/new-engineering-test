import pytest
from chat.models import Conversation, Message, MessageFeedback


def test_message_sequence_increments_and_updates_conversation(db):
    conv = Conversation.objects.create(title=None)
    t0 = conv.updated_at
    msg1 = Message.objects.create(conversation=conv, role=Message.ROLE_USER, text="hi")
    msg2 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="hello")

    assert msg1.sequence == 1
    assert msg2.sequence == 2
    conv.refresh_from_db()
    assert conv.updated_at >= t0


def test_feedback_attaches_to_ai_message_and_sets_conversation(db):
    conv = Conversation.objects.create(title=None)
    ai_msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="assistant")
    feedback = MessageFeedback.objects.create(message=ai_msg, is_helpful=True, comment="Nice")

    assert feedback.conversation_id == conv.id
    assert feedback.message_id == ai_msg.id
    assert feedback.is_helpful is True
    assert ai_msg.feedback == feedback


def test_feedback_rejects_user_message(db):
    conv = Conversation.objects.create(title=None)
    user_msg = Message.objects.create(conversation=conv, role=Message.ROLE_USER, text="hello?")

    with pytest.raises(ValueError):
        MessageFeedback.objects.create(message=user_msg, is_helpful=False)

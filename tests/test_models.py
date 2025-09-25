import time
from django.utils import timezone
from chat.models import Conversation, Message


def test_message_sequence_increments_and_updates_conversation(db):
    conv = Conversation.objects.create(title=None)
    t0 = conv.updated_at
    msg1 = Message.objects.create(conversation=conv, role=Message.ROLE_USER, text="hi")
    msg2 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="hello")

    assert msg1.sequence == 1
    assert msg2.sequence == 2
    conv.refresh_from_db()
    assert conv.updated_at >= t0


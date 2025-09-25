from rest_framework import serializers

from .models import Conversation, Message


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "title", "created_at", "updated_at"]


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "conversation", "role", "text", "created_at", "sequence"]
        read_only_fields = ["id", "created_at", "sequence", "conversation", "role"]


class CreateMessageSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=1000, allow_blank=False, trim_whitespace=True)

    def validate_text(self, value: str) -> str:
        text = value.strip()
        if not text:
            raise serializers.ValidationError("Message text cannot be empty.")
        return text


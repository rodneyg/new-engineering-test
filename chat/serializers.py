from rest_framework import serializers

from .models import Conversation, Message, MessageFeedback


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "title", "created_at", "updated_at"]


class MessageFeedbackSerializer(serializers.ModelSerializer):
    conversation = serializers.PrimaryKeyRelatedField(read_only=True)
    message = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = MessageFeedback
        fields = ["id", "conversation", "message", "is_helpful", "comment", "created_at"]
        read_only_fields = fields


class MessageSerializer(serializers.ModelSerializer):
    feedback = MessageFeedbackSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ["id", "conversation", "role", "text", "created_at", "sequence", "feedback"]
        read_only_fields = ["id", "created_at", "sequence", "conversation", "role", "feedback"]


class CreateMessageSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=1000, allow_blank=False, trim_whitespace=True)

    def validate_text(self, value: str) -> str:
        text = value.strip()
        if not text:
            raise serializers.ValidationError("Message text cannot be empty.")
        return text


class CreateFeedbackSerializer(serializers.Serializer):
    is_helpful = serializers.BooleanField()
    comment = serializers.CharField(
        max_length=500,
        allow_blank=True,
        required=False,
        trim_whitespace=True,
    )

    def validate_comment(self, value: str) -> str:
        return value.strip()

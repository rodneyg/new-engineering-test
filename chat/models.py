from __future__ import annotations

from django.db import models, transaction
from django.utils import timezone


class Conversation(models.Model):
    title = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "id"]

    def __str__(self) -> str:  # pragma: no cover
        return self.title or f"Conversation {self.pk}"


class Message(models.Model):
    ROLE_USER = "user"
    ROLE_AI = "ai"
    ROLE_CHOICES = (
        (ROLE_USER, "User"),
        (ROLE_AI, "AI"),
    )

    conversation = models.ForeignKey(Conversation, related_name="messages", on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    sequence = models.PositiveIntegerField()

    class Meta:
        ordering = ["sequence", "id"]
        unique_together = ("conversation", "sequence")
        indexes = [
            models.Index(fields=["conversation", "sequence"]),
        ]

    def save(self, *args, **kwargs):
        if self.sequence is None:
            # Ensure sequence increments per conversation
            with transaction.atomic():
                last = (
                    Message.objects.select_for_update()
                    .filter(conversation=self.conversation)
                    .order_by("-sequence")
                    .first()
                )
                self.sequence = 1 if last is None else last.sequence + 1
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)
        # Bump conversation updated_at
        Conversation.objects.filter(pk=self.conversation_id).update(updated_at=timezone.now())

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.conversation_id}#{self.sequence}:{self.role}"


class MessageFeedback(models.Model):
    message = models.OneToOneField(Message, related_name="feedback", on_delete=models.CASCADE)
    conversation = models.ForeignKey(
        Conversation,
        related_name="feedbacks",
        on_delete=models.CASCADE,
        editable=False,
    )
    is_helpful = models.BooleanField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["conversation", "is_helpful"]),
        ]

    def save(self, *args, **kwargs):
        if self.message.role != Message.ROLE_AI:
            raise ValueError("Feedback can only be attached to AI messages.")
        self.conversation = self.message.conversation
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover
        status = "helpful" if self.is_helpful else "not helpful"
        return f"Feedback on message {self.message_id} ({status})"

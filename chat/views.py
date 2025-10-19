from __future__ import annotations

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.db.models import QuerySet, Count, Q, Max
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Conversation, Message, MessageFeedback
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    CreateMessageSerializer,
    MessageFeedbackSerializer,
    CreateFeedbackSerializer,
)
from .services import gemini


class ConversationListCreateView(APIView):
    def get(self, request: Request) -> Response:
        qs: QuerySet[Conversation] = Conversation.objects.all().order_by("-updated_at")
        # Manual pagination using limit/offset to align with plan
        try:
            limit = min(int(request.query_params.get("limit", 20)), 100)
        except ValueError:
            limit = 20
        try:
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            offset = 0
        items = qs[offset : offset + limit]
        data = ConversationSerializer(items, many=True).data
        return Response({"results": data, "count": qs.count(), "offset": offset, "limit": limit})

    def post(self, request: Request) -> Response:
        title = (request.data or {}).get("title")
        conv = Conversation.objects.create(title=title or None)
        return Response(ConversationSerializer(conv).data, status=status.HTTP_201_CREATED)


class ConversationDetailView(APIView):
    def get(self, request: Request, pk: int) -> Response:
        conv = get_object_or_404(Conversation, pk=pk)
        return Response(ConversationSerializer(conv).data)


class MessageListCreateView(APIView):
    def get(self, request: Request, pk: int) -> Response:
        conv = get_object_or_404(Conversation, pk=pk)
        try:
            since = int(request.query_params.get("since", 0))
        except ValueError:
            since = 0
        try:
            limit = min(int(request.query_params.get("limit", 50)), 200)
        except ValueError:
            limit = 50
        qs = conv.messages.all()
        if since:
            qs = qs.filter(sequence__gt=since)
        qs = qs.order_by("sequence")[:limit]
        results = list(qs)
        return Response({
            "results": MessageSerializer(results, many=True).data,
            "lastSeq": (results[-1].sequence if results else since),
        })

    def post(self, request: Request, pk: int) -> Response:
        conv = get_object_or_404(Conversation, pk=pk)
        serializer = CreateMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        text: str = serializer.validated_data["text"].strip()

        # Persist user message
        user_msg = Message.objects.create(conversation=conv, role=Message.ROLE_USER, text=text)

        # Build short history context (last 10 messages)
        history = list(
            conv.messages.order_by("-sequence").values("role", "text")[:10]
        )[::-1]

        try:
            reply = gemini.generate_reply(history=history, prompt=text, timeout_s=10)
        except gemini.GeminiServiceError as e:
            if settings.DEBUG or getattr(settings, "GEMINI_ALLOW_FALLBACK", False):
                reply = f"(Gemini unavailable) {e}"
            else:
                return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        ai_msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text=reply)
        return Response({
            "user_message": MessageSerializer(user_msg).data,
            "ai_message": MessageSerializer(ai_msg).data,
        }, status=status.HTTP_201_CREATED)


class MessageFeedbackView(APIView):
    def post(self, request: Request, pk: int, message_id: int) -> Response:
        conv = get_object_or_404(Conversation, pk=pk)
        message = get_object_or_404(Message, pk=message_id, conversation=conv)
        if message.role != Message.ROLE_AI:
            return Response({"detail": "Feedback is only allowed on AI messages."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = CreateFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        comment = payload.get("comment", "")

        feedback, created = MessageFeedback.objects.update_or_create(
            message=message,
            defaults={
                "is_helpful": payload["is_helpful"],
                "comment": comment,
            },
        )
        response_serializer = MessageFeedbackSerializer(feedback)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class InsightsView(APIView):
    def get(self, request: Request) -> Response:
        feedback_qs = MessageFeedback.objects.select_related("conversation", "message")
        total = feedback_qs.count()
        helpful = feedback_qs.filter(is_helpful=True).count()
        not_helpful = total - helpful
        helpful_rate = helpful / total if total else 0.0

        per_conversation_raw = (
            feedback_qs.values("conversation_id", "conversation__title")
            .annotate(
                feedback_count=Count("id"),
                helpful_count=Count("id", filter=Q(is_helpful=True)),
                not_helpful_count=Count("id", filter=Q(is_helpful=False)),
                last_feedback_at=Max("created_at"),
            )
            .order_by("-feedback_count", "-last_feedback_at")[:20]
        )

        per_conversation = [
            {
                "conversation_id": row["conversation_id"],
                "title": row["conversation__title"],
                "feedback_count": row["feedback_count"],
                "helpful_count": row["helpful_count"],
                "not_helpful_count": row["not_helpful_count"],
                "helpful_rate": (
                    row["helpful_count"] / row["feedback_count"] if row["feedback_count"] else 0.0
                ),
                "last_feedback_at": row["last_feedback_at"],
            }
            for row in per_conversation_raw
        ]

        recent_feedback = [
            {
                "id": fb.id,
                "conversation_id": fb.conversation_id,
                "message_id": fb.message_id,
                "title": fb.conversation.title,
                "is_helpful": fb.is_helpful,
                "comment": fb.comment,
                "created_at": fb.created_at,
                "message_preview": fb.message.text[:200],
            }
            for fb in feedback_qs.order_by("-created_at")[:10]
        ]

        data = {
            "total_feedback": total,
            "helpful_count": helpful,
            "not_helpful_count": not_helpful,
            "helpful_rate": helpful_rate,
            "per_conversation": per_conversation,
            "recent_feedback": recent_feedback,
        }
        return Response(data)

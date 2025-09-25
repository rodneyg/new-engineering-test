from __future__ import annotations

from typing import Any

from django.shortcuts import get_object_or_404
from django.db.models import QuerySet
from django.conf import settings
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Conversation, Message
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    CreateMessageSerializer,
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
            # Remove user message to keep integrity if AI fails? We keep it and surface 502.
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        ai_msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text=reply)
        return Response({
            "user_message": MessageSerializer(user_msg).data,
            "ai_message": MessageSerializer(ai_msg).data,
        }, status=status.HTTP_201_CREATED)

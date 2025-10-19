from __future__ import annotations

from rest_framework.throttling import SimpleRateThrottle


class MessageRateThrottle(SimpleRateThrottle):
    scope = "message"

    def get_cache_key(self, request, view):
        if request.method.upper() != "POST":
            return None
        ident = self.get_ident(request)
        if ident is None:
            return None
        return self.cache_key_for_ident(ident)

    def cache_key_for_ident(self, ident: str) -> str:
        return f"throttle:{self.scope}:{ident}"

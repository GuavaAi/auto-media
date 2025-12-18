from __future__ import annotations

from typing import Dict

from app.services.publish.provider_base import PublishProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: Dict[str, PublishProvider] = {}

    def register(self, provider: PublishProvider) -> None:
        self._providers[provider.provider] = provider

    def get(self, provider_name: str) -> PublishProvider:
        p = self._providers.get(provider_name)
        if not p:
            raise KeyError(f"unknown provider: {provider_name}")
        return p


registry = ProviderRegistry()

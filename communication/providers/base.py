"""
Plug-and-play messaging providers (SMS / WhatsApp).

Register new providers with ``register_provider`` and they appear in admin choices.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Type


class BaseMessagingProvider:
    """Interface for outbound SMS / WhatsApp providers."""

    key: str = ''
    label: str = ''
    supports_sms: bool = False
    supports_whatsapp: bool = False

    def send_sms(
        self,
        to_number: str,
        text: str,
        *,
        config: Optional[Dict[str, Any]] = None,
        timeout: int = 15,
    ) -> Dict[str, Any]:
        raise NotImplementedError(f'{self.key} does not support SMS')

    def send_whatsapp_template(
        self,
        to_number: str,
        *,
        template_name: str,
        language: str = 'en',
        body_params: Optional[List[str]] = None,
        auth_copy_code: bool = False,
        config: Optional[Dict[str, Any]] = None,
        timeout: int = 15,
    ) -> Dict[str, Any]:
        raise NotImplementedError(f'{self.key} does not support WhatsApp')

    def send_whatsapp_text(
        self,
        to_number: str,
        text: str,
        *,
        config: Optional[Dict[str, Any]] = None,
        timeout: int = 15,
    ) -> Dict[str, Any]:
        raise NotImplementedError(f'{self.key} does not support WhatsApp free-form text')


_REGISTRY: Dict[str, BaseMessagingProvider] = {}


def register_provider(provider: BaseMessagingProvider) -> BaseMessagingProvider:
    if not provider.key:
        raise ValueError('Provider.key is required')
    _REGISTRY[provider.key] = provider
    return provider


def get_provider(key: str) -> Optional[BaseMessagingProvider]:
    ensure_providers_loaded()
    return _REGISTRY.get((key or '').strip().lower())


def list_providers(*, sms: bool = False, whatsapp: bool = False) -> List[BaseMessagingProvider]:
    ensure_providers_loaded()
    items = list(_REGISTRY.values())
    if sms:
        items = [p for p in items if p.supports_sms]
    if whatsapp:
        items = [p for p in items if p.supports_whatsapp]
    return sorted(items, key=lambda p: p.label.lower())


def sms_provider_choices():
    return [(p.key, p.label) for p in list_providers(sms=True)]


def whatsapp_provider_choices():
    return [(p.key, p.label) for p in list_providers(whatsapp=True)]


_loaded = False


def ensure_providers_loaded():
    global _loaded
    if _loaded:
        return
    # Import side-effect registrations
    from communication.providers import plivo as _plivo  # noqa: F401
    from communication.providers import smartping as _smartping  # noqa: F401
    _loaded = True

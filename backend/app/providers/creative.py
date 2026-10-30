"""Creative assistant provider boundary (AGENTS §3 providers, §18 WOW assistant).

Structured proposal boundary: providers never execute decisions or persist
anything — they return a ready template ad draft; humans/campaigns decide what
happens with it.

Selection is configuration-driven (`CREATIVE_PROVIDER` in settings):
- `offline-template` (default): deterministic bilingual template pack, no
  network, no keys.
- `llm-openai-compatible`: optional OpenAI-compatible chat-completions
  endpoint; requires `LLM_API_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`.
- `live-*`: clearly reports an unconfigured integration (stub), never a fake
  payload.

Offline translation note: the secondary language is produced by a phrase-map
template pack (deterministic); arbitrary product words are kept verbatim. A
real translation/AI provider can be plugged in without touching callers.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Literal, Protocol

from pydantic import BaseModel, Field


class CreativeBrief(BaseModel):
    product: str = Field(min_length=1, max_length=60)
    discount_pct: float | None = Field(default=None, ge=1, le=90)
    audience: Literal["any", "holiday", "family", "children", "business", "coffee", "duty_free"] = "any"
    zone_hint: str | None = None
    note: str | None = None


class CreativeAssistantProvider(Protocol):
    async def assist(self, brief: CreativeBrief, lang_alt: str) -> dict: ...


class ProviderUnconfigured(Exception):
    pass


class ProviderInvalidResponse(Exception):
    """The provider answered, but its output was not a valid creative draft."""


class CreativeDraft(BaseModel):
    """The only shape an external creative provider may return to the app."""

    headline_en: str = Field(min_length=1, max_length=120)
    headline_alt: str = Field(min_length=1, max_length=120)
    body_en: str = Field(min_length=1, max_length=300)
    body_alt: str = Field(min_length=1, max_length=300)
    cta: str = Field(min_length=1, max_length=40)
    bg: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    fg: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    image: str = Field(min_length=1, max_length=80)
    show_code: bool = True


class OfflineTemplateAssistant:
    """Deterministic offline template pack: brief → creative payload shaped
    exactly like stored creatives (headline_en/…, motif, cta) so callers can
    preview it with the same player component (English + configured 2nd)."""

    _PACKS: dict[str, dict] = {
        "holiday": {
            "en": "{product}{disc} — sample before boarding",
            "alt": "{product}{disc}: prueba antes de tu vuelo",
            "body_en": "Travellers in transit: the exclusive counter is minutes away from your gate.",
            "body_alt": "Viajeros en transito: el mostrador exclusivo esta a minutos de tu puerta.",
            "motif": "motif-arc", "bg": "#9d174d",
        },
        "duty_free": {
            "en": "{product}{disc} — duty-free exclusive",
            "alt": "{product}{disc}: exclusivo libre de impuestos",
            "body_en": "International travellers: claim the set before customs doors close.",
            "body_alt": "Viajeros internacionales: reclame el set antes de cerrar la aduana.",
            "motif": "motif-arc", "bg": "#9d174d",
        },
        "family": {
            "en": "{product}{disc} — the kids await your return",
            "alt": "{product}{disc}: los pequenos esperan contigo",
            "body_en": "Family favourite by the gates — bundle for the little ones during the wait.",
            "body_alt": "Favorito de la familia junto a las puertas — paquete para los pequenos.",
            "motif": "motif-toys", "bg": "#5b21b6",
        },
        "children": {
            "en": "{product}{disc} — buy 2, get 1 free",
            "alt": "{product}{disc}: lleva 2 y paga 1",
            "body_en": "Keep little travellers busy during the delay claim window.",
            "body_alt": "Mantega ocupados a los pequenos durante la espera.",
            "motif": "motif-toys", "bg": "#5b21b6",
        },
        "business": {
            "en": "{product} — day pass, showers and suites",
            "alt": "{product}: pase de dia, duchas y suites",
            "body_en": "Premium travellers: upgrade the wait into a working lounge session.",
            "body_alt": "Pasajeros premium: convierta la espera en sesion de trabajo.",
            "motif": "motif-lounge", "bg": "#155e75",
        },
        "coffee": {
            "en": "{product} to your gate — skip the queue",
            "alt": "{product} hasta la puerta: evita la fila",
            "body_en": "Fresh brew releases through the corridor every few minutes.",
            "body_alt": "Cafe recien hecho por el pasillo cada pocos minutos.",
            "motif": "motif-coffee", "bg": "#b45309",
        },
        "any": {
            "en": "{product} at the gate — {disc_plain}",
            "alt": "{product} en tu puerta: {disc_plain}",
            "body_en": "Recently refreshed drops for travellers in terminals near you.",
            "body_alt": "Novedades recientes para viajeros en terminales proximas.",
            "motif": "motif-house", "bg": "#0f766e",
        },
    }

    async def assist(self, brief: CreativeBrief, lang_alt: str) -> dict:
        pack = self._PACKS.get(brief.audience, self._PACKS["any"])
        disc_en = f" — {int(brief.discount_pct)}% off" if brief.discount_pct else ""
        disc_alt = f"{int(brief.discount_pct)}% dto" if brief.discount_pct else ""
        disc_plain = f"{int(brief.discount_pct)}% off" if brief.discount_pct else "companion offer"
        v = dict(
            id=f"draft-{hash((brief.product, brief.audience, brief.discount_pct)) & 0xffff:04x}",
            headline_en=pack["en"].format(product=brief.product, disc=disc_en, disc_plain=disc_plain),
            headline_alt=pack["alt"].format(product=brief.product, disc=disc_alt, disc_plain=disc_plain),
            body_en=pack["body_en"], body_alt=pack["body_alt"],
            cta="Scan to claim", bg=pack["bg"], fg="#ffffff",
            image=pack["motif"], show_code=True,
        )
        return {
            "provider": "offline-template",
            "creative": v,
            "lang": [lang_alt, "en"],
            "notes": "offline template pack v1: deterministic, bilingual phrase-map; product text kept verbatim in both languages",
        }


class LiveStubAssistant:
    """Pluggable boundary for a real provider. Always reports unconfigured -
    never fabricates a payload (AGENTS §3)."""

    def __init__(self, name: str) -> None:
        self.name = name

    async def assist(self, brief: CreativeBrief, lang_alt: str) -> dict:
        raise ProviderUnconfigured(
            f"creative provider '{self.name}' is not configured for this deployment"
        )


class OpenAICompatibleAssistant:
    """Optional LLM creative provider using the common chat-completions shape.

    The network call runs off the asyncio event loop. The response is parsed and
    validated before it crosses the provider boundary; it never persists data,
    schedules an ad, or becomes an unchecked decision.
    """

    def __init__(self, base_url: str, api_key: str, model: str, timeout_s: float) -> None:
        if not base_url or not api_key or not model:
            raise ProviderUnconfigured(
                "llm-openai-compatible requires LLM_API_BASE_URL, LLM_API_KEY, and LLM_MODEL"
            )
        self.endpoint = base_url.rstrip("/")
        if not self.endpoint.endswith("/chat/completions"):
            self.endpoint += "/chat/completions"
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s

    async def assist(self, brief: CreativeBrief, lang_alt: str) -> dict:
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You create concise airport retail ad drafts. Return JSON only with exactly these "
                        "fields: headline_en, headline_alt, body_en, body_alt, cta, bg, fg, image, show_code. "
                        "Use six-digit hex colors, a short motif name for image, and no personal data."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({
                        "product": brief.product,
                        "discount_pct": brief.discount_pct,
                        "audience": brief.audience,
                        "zone_hint": brief.zone_hint,
                        "note": brief.note,
                        "secondary_language": lang_alt,
                    }),
                },
            ],
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            raw = await asyncio.to_thread(self._request, request)
            outer = json.loads(raw)
            content = outer["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
            draft = CreativeDraft.model_validate(json.loads(content))
        except (urllib.error.URLError, TimeoutError, OSError, KeyError, IndexError,
                TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderInvalidResponse(f"LLM creative response was invalid: {exc}") from exc
        return {
            "provider": "llm-openai-compatible",
            "creative": {"id": f"llm-{abs(hash((brief.product, brief.audience))) & 0xffff:04x}", **draft.model_dump()},
            "lang": [lang_alt, "en"],
            "notes": "validated LLM draft; review before publishing",
        }

    def _request(self, request: urllib.request.Request) -> str:
        with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
            return response.read().decode("utf-8")


def assistant_for(name: str | None, *, settings=None) -> CreativeAssistantProvider:
    name = (name or "offline-template").strip()
    if name in ("", "offline-template"):
        return OfflineTemplateAssistant()
    if name == "llm-openai-compatible":
        if settings is None:
            raise ProviderUnconfigured("LLM settings are unavailable")
        return OpenAICompatibleAssistant(
            settings.llm_api_base_url,
            settings.llm_api_key,
            settings.llm_model,
            settings.provider_call_timeout_s,
        )
    return LiveStubAssistant(name)

# Optional LLM creative assistant

The platform supports an optional OpenAI-compatible chat-completions provider
for the Retailer creative assistant. It is deliberately limited to drafting
bilingual ad copy. The LLM cannot select campaigns, change eligibility, schedule
screens, or write to the database.

## Configuration

Set these variables before starting the backend:

```bash
CREATIVE_PROVIDER=llm-openai-compatible
LLM_API_BASE_URL=https://your-provider.example/v1
LLM_API_KEY=replace-me
LLM_MODEL=your-model
```

The provider appends `/chat/completions` unless the base URL already ends with
that path. `PROVIDER_CALL_TIMEOUT_S` controls the request timeout and defaults to
one second. Keep the offline default (`CREATIVE_PROVIDER=offline-template`) when
no endpoint or credential is available.

## Contract and safety boundary

The request is sent as a short creative brief containing product, discount,
audience, zone hint, note, and configured secondary language. The response must
be JSON containing `headline_en`, `headline_alt`, `body_en`, `body_alt`, `cta`,
six-digit-hex `bg` and `fg` colours, `image`, and `show_code`.

Pydantic validation rejects missing, oversized, or malformed fields. A malformed
provider response returns HTTP 502 and does not create a campaign. An absent
configuration returns HTTP 501. The provider call runs outside the asyncio event
loop and is bounded by the configured timeout.

The normal campaign decision pipeline remains deterministic and evidence-first.
This provider is a human-review drafting aid, not an autonomous publishing or
targeting system. Do not send passenger-level data or personal information.

## Local verification

The integration boundary is tested without network access:

```bash
.venv/bin/pytest -q backend/tests/test_creative_assist.py
```

The test uses a fake OpenAI-compatible response and verifies authorization,
timeout propagation, structured validation, and missing-configuration handling.

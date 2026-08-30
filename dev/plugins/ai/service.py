from __future__ import annotations

import random
import re
from logging import Logger

import aiohttp
import asyncio
from yandex_ai_studio_sdk import AIStudio

from varibles.dialogue_loader import TEXT


def get_fallback_message() -> str:
    return TEXT("SYSTEM_PROMPT", "fallback_variants")


def clean_ai_tag(text: str) -> str:
    return re.sub(r"#ai\b", "", text or "", flags=re.IGNORECASE).strip()


def build_system_prompt(name: str) -> str:
    additional_text = TEXT("SYSTEM_PROMPT", "ADDITIONAL_TEMPLATE", name=name)
    basement_key = "podval_1" if random.random() < 0.3 else "podval_2"
    basement_prompt = TEXT("SYSTEM_PROMPT", basement_key)
    return (
        f"{TEXT('SYSTEM_PROMPT', '1')}\n\n"
        f"{basement_prompt}\n\n"
        f"{TEXT('SYSTEM_PROMPT', '2')}\n\n"
        f"{additional_text}"
    )


class AIService:
    def __init__(
        self,
        catalog_id: str,
        secret_key: str,
        *,
        logger: Logger | None = None,
        model_name: str = "yandexgpt-lite",
    ) -> None:
        self.catalog_id = catalog_id
        self.secret_key = secret_key
        self.logger = logger
        self.model_name = model_name
        self.sdk = AIStudio(folder_id=catalog_id, auth=secret_key)

    def ask_ai(self, user_text: str, name: str) -> str | None:
        if not (user_text or "").strip():
            return None

        messages = [
            {"role": "system", "text": build_system_prompt(name)},
            {"role": "user", "text": clean_ai_tag(user_text)},
        ]

        try:
            model = self.sdk.models.completions(self.model_name)
            model = model.configure(temperature=0.7, max_tokens=1800)
            result = model.run(messages)

            if hasattr(result, "choices") and result.choices:
                return result.choices[0].text
            if hasattr(result, "alternatives") and result.alternatives:
                return result.alternatives[0].text
            if isinstance(result, str):
                return result
            return get_fallback_message()
        except Exception as error:
            if self.logger is not None:
                self.logger.error(f"Ошибка в AIService.ask_ai: {error}")
            return get_fallback_message()

    async def count_tokens(self, text: str, model: str | None = None) -> int:
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/tokenize"
        headers = {
            "Authorization": f"Api-Key {self.secret_key}",
            "Content-Type": "application/json",
        }
        data = {
            "modelUri": f"gpt://{self.catalog_id}/{model or self.model_name}",
            "text": text,
        }
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=data) as response:
                response.raise_for_status()
                payload = await response.json()
        return len(payload.get("tokens", []))


async def stream_ai(user_text: str, name: str, service: AIService):
    response = await asyncio.to_thread(service.ask_ai, user_text, name)
    if response is not None:
        yield response


async def count_tokens(text: str, service: AIService, model: str | None = None) -> int:
    return await service.count_tokens(text, model=model)

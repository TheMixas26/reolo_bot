from __future__ import annotations

import random
import re
from logging import Logger

import requests
from yandex_ai_studio_sdk import AIStudio

from varibles.dialogue_loader import TEXT

SYSTEM_PROMPT_1 = TEXT("SYSTEM_PROMPT", "1")
SYSTEM_PROMPT_2 = TEXT("SYSTEM_PROMPT", "2")
SYSTEM_PROMPT_podval1 = TEXT("SYSTEM_PROMPT", "podval_1")
SYSTEM_PROMPT_podval2 = TEXT("SYSTEM_PROMPT", "podval_2")
ADDITIONAL_TEMPLATE = TEXT("SYSTEM_PROMPT", "ADDITIONAL_TEMPLATE")


def get_fallback_message() -> str:
    return TEXT("SYSTEM_PROMPT", "fallback_variants")


def clean_ai_tag(text: str) -> str:
    return re.sub(r"#ai\b", "", text or "", flags=re.IGNORECASE).strip()


def build_system_prompt(name: str) -> str:
    additional_text = ADDITIONAL_TEMPLATE.format(name=name)
    basement_prompt = SYSTEM_PROMPT_podval1 if random.random() < 0.3 else SYSTEM_PROMPT_podval2
    return f"{SYSTEM_PROMPT_1}\n\n{basement_prompt}\n\n{SYSTEM_PROMPT_2}\n\n{additional_text}"


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

    def count_tokens(self, text: str, model: str | None = None) -> int:
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/tokenize"
        headers = {
            "Authorization": f"Api-Key {self.secret_key}",
            "Content-Type": "application/json",
        }
        data = {
            "modelUri": f"gpt://{self.catalog_id}/{model or self.model_name}",
            "text": text,
        }
        response = requests.post(url, headers=headers, json=data, timeout=15)
        response.raise_for_status()
        return len(response.json().get("tokens", []))


async def stream_ai(user_text: str, name: str, service: AIService):
    response = service.ask_ai(user_text, name)
    if response is not None:
        yield response


def count_tokens(text: str, service: AIService, model: str | None = None) -> int:
    return service.count_tokens(text, model=model)

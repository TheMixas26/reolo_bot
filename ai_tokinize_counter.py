import requests
import json
from config import CATALOG_ID, SECRET_KEY
from ai_module import SYSTEM_PROMPT_1, SYSTEM_PROMPT_2, ADDITIONAL_TEMPLATE, SYSTEM_PROMPT_podval1

def count_tokens(text, model="yandexgpt-lite"):
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/tokenize"
    headers = {
        "Authorization": f"Api-Key {SECRET_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "modelUri": f"gpt://{CATALOG_ID}/{model}",
        "text": text
    }
    response = requests.post(url, headers=headers, json=data)
    tokens = response.json().get("tokens", [])
    return len(tokens)

cleaned_text = "Ну как там в подвалах живётся? #ai"
system_content = f"{SYSTEM_PROMPT_1}\n\n{SYSTEM_PROMPT_podval1}\n\n{SYSTEM_PROMPT_2}\n\n{ADDITIONAL_TEMPLATE}"

# Использование
system_tokens = count_tokens(system_content)
user_tokens = count_tokens(cleaned_text)
print(f"Системник: {system_tokens}, Юзер: {user_tokens}, ВСЕГО: {system_tokens + user_tokens}")
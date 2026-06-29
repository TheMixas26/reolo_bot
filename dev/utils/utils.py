import random
from datetime import datetime
from varibles.dialogue_loader import TEXT

from config import predlojka_bot, admin, backup_chat
import logging

logger = logging.getLogger(__name__)

def thx_for_message(user_name: str, mes_type: str) -> str:
    FUN = random.random()

    time = "day" if 6 <= datetime.now().hour < 23 else "night"

    if mes_type == '!':
        if FUN < 0.9:
            return TEXT("thx", time, "variants_v", name=user_name)
        elif FUN >= 0.98:
            return TEXT("thx", time, "podval_variants_v", name=user_name)
        else:
            return TEXT("thx", time, "secret_variants_v", name=user_name)

    elif mes_type == '?':
        return TEXT("thx", time, "variants_q", name=user_name)

    elif mes_type == 'event':
        return TEXT("thx", time, "events_variants")

    elif mes_type == 'report':
        return TEXT("thx", time, "report_variants")

    elif mes_type == 'message':
        return TEXT("thx", time, "message_variants")

    else:
        return TEXT("thx", time, "variants_v", name=user_name)


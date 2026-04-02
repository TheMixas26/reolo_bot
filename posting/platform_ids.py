from __future__ import annotations

from posting.models import Platform

VK_USER_ID_OFFSET = 10**12


def to_storage_user_id(platform: Platform, user_id: int | str) -> int:
    numeric_user_id = int(user_id)
    if platform == Platform.VK:
        return VK_USER_ID_OFFSET + numeric_user_id
    return numeric_user_id

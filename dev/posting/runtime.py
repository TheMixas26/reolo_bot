from __future__ import annotations

import config as app_config

from posting.adapters.telegram import TelegramAdapter
from posting.adapters.vk import VKAdapter
from posting.models import Platform, PostTarget
from posting.services import PostPublisher

telegram_adapter = TelegramAdapter(app_config.predlojka_bot)
vk_adapter = None

post_adapters = {Platform.TELEGRAM: telegram_adapter}
post_targets = [PostTarget(platform=Platform.TELEGRAM, destination_id=app_config.channel, name="telegram_channel")]

vk_token = getattr(app_config, "VK_TOKEN", "")
vk_owner_id = getattr(app_config, "VK_OWNER_ID", None)
vk_group_id = getattr(app_config, "VK_GROUP_ID", None)
vk_api_version = getattr(app_config, "VK_API_VERSION", "5.199")

if vk_token and (vk_owner_id or vk_group_id):
    resolved_owner_id = vk_owner_id or (-int(vk_group_id))
    vk_adapter = VKAdapter(
        vk_token,
        api_version=vk_api_version,
        group_id=vk_group_id,
        telegram_adapter=telegram_adapter,
    )
    post_adapters[Platform.VK] = vk_adapter
    post_targets.append(PostTarget(platform=Platform.VK, destination_id=resolved_owner_id, name="vk_wall"))

post_publisher = PostPublisher(post_adapters, post_targets)
telegram_admin_target = PostTarget(platform=Platform.TELEGRAM, destination_id=app_config.admin, name="telegram_admin")

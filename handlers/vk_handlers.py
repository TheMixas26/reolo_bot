from __future__ import annotations

import logging
import time

from analytics.stats import log_event
from handlers.predlojka_handlers import submit_external_post
from posting.runtime import vk_adapter
from utils.utils import thx_for_message

logger = logging.getLogger(__name__)


def _acknowledge_vk_submission(peer_id: int, author_name: str, *, is_question: bool) -> None:
    if vk_adapter is None:
        return
    vk_adapter.send_message(peer_id, thx_for_message(author_name, mes_type="?" if is_question else "!"))


def run_vk_listener() -> None:
    if vk_adapter is None:
        logger.info("VK listener skipped: adapter is not configured.")
        return

    logger.info("VK listener started.")

    while True:
        try:
            for event in vk_adapter.listen():
                if event.get("type") != "message_new":
                    continue

                message = event.get("object", {}).get("message", {})
                if not message:
                    continue
                if message.get("out"):
                    continue

                from_id = int(message.get("from_id", 0))
                peer_id = int(message.get("peer_id", 0))
                if from_id <= 0 or peer_id <= 0:
                    continue

                post = vk_adapter.create_post_from_event(event)
                if not post.text and not post.attachments:
                    vk_adapter.send_message(peer_id, "Пока что я умею принимать из VK только текст, фото и документы.")
                    continue

                submit_external_post(
                    post,
                    acknowledge_callback=lambda prepared_post, peer_id=peer_id: _acknowledge_vk_submission(
                        peer_id,
                        prepared_post.author.display_name,
                        is_question=prepared_post.is_question,
                    ),
                )
                log_event(
                    "vk_submission_received",
                    bot="predlojka",
                    user_id=from_id,
                    chat_id=peer_id,
                    metadata={
                        "content_type": post.content_type_label,
                        "anonymous": post.is_anonymous,
                    },
                )
        except Exception as error:
            logger.error(f"VK listener crashed: {error}", exc_info=True)
            time.sleep(5)

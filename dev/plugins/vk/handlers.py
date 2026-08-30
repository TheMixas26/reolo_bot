from __future__ import annotations
from varibles.dialogue_loader import TEXT
from core.core_plugin.stats import log_event
from plugins.predlojka.handlers import submit_external_post
from plugins.predlojka.classes import PostParser
from plugins.predlojka import thx_for_message

def _acknowledge_vk_submission(vk_adapter, peer_id: int, author_name: str, *, is_question: bool) -> None:
    if vk_adapter is None:
        return
    vk_adapter.send_message(peer_id, thx_for_message(author_name, mes_type="?" if is_question else "!"))


def _send_vk_message(vk_adapter, peer_id: int, text: str, *, ignore_reaction: bool) -> None:
    if vk_adapter is None or ignore_reaction:
        return
    vk_adapter.send_message(peer_id, text)


def _handle_vk_ai_request(context, peer_id: int, from_id: int, author_name: str, prompt_text: str, *, ignore_reaction: bool) -> None:
    log_event("ai_requested", bot="predlojka", user_id=from_id, chat_id=peer_id, metadata={"source_platform": "vk"})

    try:
        full_text = context.ai_service.ask_ai(prompt_text, author_name)
        _send_vk_message(context.vk_adapter, peer_id, full_text, ignore_reaction=ignore_reaction)
        log_event("ai_completed", bot="predlojka", user_id=from_id, chat_id=peer_id, metadata={"source_platform": "vk"})
    except Exception as error:
        context.logger.error(f"VK AI request failed: {error}", exc_info=True)
        log_event(
            "ai_failed",
            bot="predlojka",
            user_id=from_id,
            chat_id=peer_id,
            metadata={"source_platform": "vk", "error": str(error)[:300]},
        )
        _send_vk_message(context.vk_adapter, peer_id, "Извините, что-то пошло не так... Попробуй ещё раз позже (^_^;)", ignore_reaction=ignore_reaction)


def run_vk_listener(context=None) -> None:
    logger = context.logger
    vk_adapter = getattr(context, "vk_adapter", None)

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

                parsed = PostParser.parse_submission_text(message.get("text") or "")
                author_name = vk_adapter.build_display_name(from_id)
                if context.hybernation_status:
                    vk_adapter.send_message(peer_id, TEXT("hibernation_message"))
                    continue
                if parsed.ignore_reaction:
                    continue
                if parsed.route != "post":
                    if parsed.route == "message":
                        _send_vk_message(vk_adapter, peer_id, "Тег #message из VK пока не поддерживается. Напиши напрямую админу в Telegram.", ignore_reaction=parsed.ignore_reaction)
                    elif parsed.route == "report":
                        _send_vk_message(vk_adapter, peer_id, "Тег #report из VK пока не поддерживается отдельным маршрутом. Лучше продублировать это в Telegram.", ignore_reaction=parsed.ignore_reaction)
                    elif parsed.route == "event":
                        _send_vk_message(vk_adapter, peer_id, "Тег #event из VK пока не поддерживается отдельным маршрутом. Лучше прислать идею в Telegram.", ignore_reaction=parsed.ignore_reaction)
                    continue

                if parsed.wants_ai:
                    _handle_vk_ai_request(
                        context,
                        peer_id,
                        from_id,
                        author_name,
                        parsed.clean_text or (message.get("text") or ""),
                        ignore_reaction=parsed.ignore_reaction,
                    )
                    continue

                post = vk_adapter.create_post_from_event(event)
                if not post.text and not post.attachments:
                    _send_vk_message(vk_adapter, peer_id, "Пока что я умею принимать из VK только текст, фото и документы.", ignore_reaction=parsed.ignore_reaction)
                    continue

                submit_external_post(
                    post,
                    acknowledge_callback=(
                        None
                        if parsed.ignore_reaction
                        else lambda prepared_post, peer_id=peer_id: _acknowledge_vk_submission(
                            vk_adapter,
                            peer_id,
                            prepared_post.author.display_name,
                            is_question=prepared_post.is_question,
                        )
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

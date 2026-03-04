from config import predlojka_bot, db, admin, channel, channel_red, bot_version, chat_mishas_den
from telebot import types
from utils import thx_for_message
from ai_module import ask_ai, stream_ai
import time
import threading
import logging
from datetime import datetime
from tinydb import Query

# Настройка логирования для отладки
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

q = types.ReplyKeyboardRemove()
media_groups_buffer = {}
media_groups_timer = {}
MEDIA_GROUP_TIMEOUT = 2.0
album_moderation_messages = {}  # media_group_id -> [message_ids]
album_media_cache = {}          # media_group_id -> media list
moderation_payload_cache = {}   # admin_message_id -> payload for draft/schedule
schedule_context = {}           # admin_id -> pending scheduling context
scheduled_posts_table = db.table("scheduled_posts")


def build_moderation_markup(approve_data):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Одобрить", callback_data=approve_data))
    markup.add(types.InlineKeyboardButton("Запретить", callback_data="-"))
    markup.add(types.InlineKeyboardButton("В черновик", callback_data="draft"))
    markup.add(types.InlineKeyboardButton("Запланировать", callback_data="schedule"))
    return markup


def save_moderation_payload(admin_message_id, original_message, content_type, payload):
    text_content = original_message.text if original_message.content_type == 'text' else original_message.caption or ""
    text_lower = text_content.lower()
    moderation_payload_cache[admin_message_id] = {
        "content_type": content_type,
        "payload": payload,
        "source_user_id": original_message.from_user.id,
        "is_question": '#вопрос' in text_lower,
        "is_anon": '#анон' in text_lower,
    }


def serialize_album_media(media_list):
    payload = []
    for media in media_list:
        media_type = 'photo' if isinstance(media, types.InputMediaPhoto) else 'video'
        payload.append({
            "type": media_type,
            "file_id": media.media,
            "caption": media.caption
        })
    return payload


def publish_payload(content_type, payload):
    if content_type == 'text':
        predlojka_bot.send_message(channel, payload['text'], parse_mode=payload.get('parse_mode'))
    elif content_type == 'sticker':
        predlojka_bot.send_sticker(channel, payload['file_id'])
        if payload.get('user_name_text'):
            predlojka_bot.send_message(channel, payload['user_name_text'], disable_notification=True)
    elif content_type == 'video':
        predlojka_bot.send_video(channel, payload['file_id'], caption=payload.get('caption'))
    elif content_type == 'photo':
        predlojka_bot.send_photo(channel, payload['file_id'], caption=payload.get('caption'))
    elif content_type == 'document':
        predlojka_bot.send_document(channel, payload['file_id'], caption=payload.get('caption'))
    elif content_type == 'audio':
        predlojka_bot.send_audio(channel, payload['file_id'], caption=payload.get('caption'))
    elif content_type == 'voice':
        predlojka_bot.send_voice(channel, payload['file_id'], caption=payload.get('caption'))
    elif content_type == 'album':
        media = []
        for item in payload:
            if item['type'] == 'photo':
                media.append(types.InputMediaPhoto(item['file_id'], caption=item.get('caption')))
            else:
                media.append(types.InputMediaVideo(item['file_id'], caption=item.get('caption')))
        safe_send_media_group(channel, media)
    else:
        raise ValueError(f"Неподдерживаемый тип контента: {content_type}")


def publish_due_scheduled_posts():
    now = datetime.now()
    status_query = Query()
    records = scheduled_posts_table.search(status_query.status == 'scheduled')
    for record in records:
        publish_at = record.get('publish_at')
        if not publish_at:
            continue
        try:
            scheduled_time = datetime.fromisoformat(publish_at)
        except Exception:
            logger.error(f"Некорректный publish_at в scheduled_posts: {publish_at}")
            continue
        if scheduled_time <= now:
            try:
                publish_payload(record['content_type'], record['payload'])
                scheduled_posts_table.remove(doc_ids=[record.doc_id])
                logger.info(f"Опубликован запланированный пост doc_id={record.doc_id}")
            except Exception as e:
                logger.error(f"Ошибка публикации запланированного поста doc_id={record.doc_id}: {e}")


def save_post_to_scheduled(content_type, payload, source_user_id, is_question, is_anon, publish_at=None, status='draft'):
    scheduled_posts_table.insert({
        "payload": payload,
        "content_type": content_type,
        "publish_at": publish_at,
        "is_question": is_question,
        "is_anon": is_anon,
        "source_user_id": source_user_id,
        "status": status,
        "created_at": datetime.now().isoformat(timespec='seconds')
    })

def none_type(obj):
    return "" if obj is None else f'{obj}'

def safe_delete_message(chat_id, message_id, max_retries=3):
    """Безопасное удаление сообщения с повторными попытками"""
    for attempt in range(max_retries):
        try:
            predlojka_bot.delete_message(chat_id, message_id)
            return True
        except Exception as e:
            logger.error(f"Ошибка при удалении сообщения {message_id} (попытка {attempt + 1}): {e}")
            time.sleep(0.5)
    return False

def safe_send_media_group(chat_id, media, max_retries=3):
    """Безопасная отправка медиагруппы с повторными попытками"""
    for attempt in range(max_retries):
        try:
            sent_msgs = predlojka_bot.send_media_group(chat_id, media)
            return sent_msgs
        except Exception as e:
            logger.error(f"Ошибка при отправке медиагруппы (попытка {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
    return None

# --- Приём сообщений ---
@predlojka_bot.message_handler(content_types=['sticker', 'text', 'document', 'audio', 'voice'])
def accepter(message):
    if message.content_type == 'text' and message.text.startswith('/'):
        predlojka_bot.reply_to(message, "Боюсь, такой команды я не знаю...")
    else:
        if message.content_type == 'text' and '#ai' in message.text.lower():
            if message.chat.id == chat_mishas_den or message.chat.id not in (channel, channel_red, chat_mishas_den):
                name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
                
                msg = predlojka_bot.reply_to(message, "Думаю... (*￣3￣)╭")
                
                # ИСПРАВЛЕНИЕ ТУТ:
                import asyncio
                
                # Создаём новый event loop для этого потока
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    async def get_ai_response():
                        full_response = ""
                        async for chunk in stream_ai(message.text, name):
                            full_response = chunk
                        return full_response
                    
                    # Запускаем асинхронную функцию синхронно
                    full_text = loop.run_until_complete(get_ai_response())
                    
                    # Редактируем сообщение с готовым ответом
                    try:
                        predlojka_bot.edit_message_text(
                            full_text,
                            chat_id=message.chat.id,
                            message_id=msg.message_id
                        )
                    except Exception as e:
                        logger.error(f"Ошибка при редактировании сообщения: {e}")
                        # Если не получилось отредактировать, отправляем новое
                        predlojka_bot.send_message(message.chat.id, full_text)
                        
                except Exception as e:
                    logger.error(f"Ошибка в AI-запросе: {e}")
                    try:
                        predlojka_bot.edit_message_text(
                            "Извини, что-то пошло не так... Попробуй ещё раз позже (^_^;)",
                            chat_id=message.chat.id,
                            message_id=msg.message_id
                        )
                    except:
                        predlojka_bot.send_message(message.chat.id, "Извини, ошибка обработки...")
                finally:
                    loop.close()

        elif message.chat.id not in (channel, channel_red, -1002228334833):
            adafa_think_text_content = message.text if message.content_type == 'text' else message.caption or ""
            # Определяем имя пользователя
            if '#анон' in adafa_think_text_content.lower():
                user_name = '\n\n🤫 Аноним'
            else:
                last_name = message.from_user.last_name if message.from_user.last_name is not None else ""
                user_name = f'\n\n👤 {message.from_user.first_name} {last_name}'
            # Вопрос или обычное сообщение
            if '#вопрос' in adafa_think_text_content:
                predlojka_bot.send_message(
                    message.chat.id,
                    thx_for_message(user_name[4:], mes_type="?"),
                    reply_markup=q
                )
                markup = build_moderation_markup("+" + user_name + 'question' + '|')
                logger.info(f"Predlojka get new question! It is {message.content_type}")
                if message.content_type == 'text':
                    sent = predlojka_bot.send_message(
                        admin,
                        f'Вам поступил новый вопрос от {user_name[4:]}\n\n<blockquote>{message.text}</blockquote>',
                        reply_markup=markup,
                        parse_mode='HTML'
                    )
                    save_moderation_payload(sent.message_id, message, 'text', {
                        "text": f'Вам поступил новый вопрос от {user_name[4:]}\n\n<blockquote>{message.text}</blockquote>',
                        "parse_mode": 'HTML'
                    })
                elif message.content_type == 'sticker':
                    sent = predlojka_bot.send_sticker(admin, message.sticker.file_id, reply_markup=build_moderation_markup("&" + user_name + 'question' + '|'))
                    save_moderation_payload(sent.message_id, message, 'sticker', {
                        "file_id": message.sticker.file_id,
                        "user_name_text": user_name
                    })
                elif message.content_type == 'video':
                    sent = predlojka_bot.send_video(admin, message.video.file_id, reply_markup=markup, caption=none_type(message.caption) + user_name)
                    save_moderation_payload(sent.message_id, message, 'video', {"file_id": message.video.file_id, "caption": none_type(message.caption) + user_name})
                elif message.content_type == 'photo':
                    sent = predlojka_bot.send_photo(admin, message.photo[0].file_id, reply_markup=markup, caption=none_type(message.caption) + user_name)
                    save_moderation_payload(sent.message_id, message, 'photo', {"file_id": message.photo[0].file_id, "caption": none_type(message.caption) + user_name})
                elif message.content_type == 'document':
                    sent = predlojka_bot.send_document(admin, message.document.file_id, reply_markup=markup, caption=none_type(message.caption) + user_name)
                    save_moderation_payload(sent.message_id, message, 'document', {"file_id": message.document.file_id, "caption": none_type(message.caption) + user_name})
                elif message.content_type == 'audio':
                    sent = predlojka_bot.send_audio(admin, message.audio.file_id, reply_markup=markup, caption=none_type(message.caption) + user_name)
                    save_moderation_payload(sent.message_id, message, 'audio', {"file_id": message.audio.file_id, "caption": none_type(message.caption) + user_name})
                elif message.content_type == 'voice':
                    sent = predlojka_bot.send_voice(admin, message.voice.file_id, reply_markup=markup, caption=none_type(message.caption) + user_name)
                    save_moderation_payload(sent.message_id, message, 'voice', {"file_id": message.voice.file_id, "caption": none_type(message.caption) + user_name})
            else:
                predlojka_bot.send_message(
                    message.chat.id,
                    thx_for_message(user_name[4:], mes_type="!"),
                    reply_markup=q
                )
                markup = build_moderation_markup("+" + user_name)
                logger.info(f"Predlojka get new message! It is {message.content_type}")
                if message.content_type == 'text':
                    sent = predlojka_bot.send_message(admin, message.text + user_name, reply_markup=markup)
                    save_moderation_payload(sent.message_id, message, 'text', {"text": message.text + user_name})
                elif message.content_type == 'sticker':
                    sent = predlojka_bot.send_sticker(admin, message.sticker.file_id, reply_markup=build_moderation_markup("&" + user_name))
                    save_moderation_payload(sent.message_id, message, 'sticker', {
                        "file_id": message.sticker.file_id,
                        "user_name_text": user_name
                    })
                elif message.content_type == 'video':
                    sent = predlojka_bot.send_video(admin, message.video.file_id, reply_markup=markup, caption=none_type(message.caption) + user_name)
                    save_moderation_payload(sent.message_id, message, 'video', {"file_id": message.video.file_id, "caption": none_type(message.caption) + user_name})
                elif message.content_type == 'photo':
                    sent = predlojka_bot.send_photo(admin, message.photo[0].file_id, reply_markup=markup, caption=none_type(message.caption) + user_name)
                    save_moderation_payload(sent.message_id, message, 'photo', {"file_id": message.photo[0].file_id, "caption": none_type(message.caption) + user_name})
                elif message.content_type == 'document':
                    sent = predlojka_bot.send_document(admin, message.document.file_id, reply_markup=markup, caption=none_type(message.caption) + user_name)
                    save_moderation_payload(sent.message_id, message, 'document', {"file_id": message.document.file_id, "caption": none_type(message.caption) + user_name})
                elif message.content_type == 'audio':
                    sent = predlojka_bot.send_audio(admin, message.audio.file_id, reply_markup=markup, caption=none_type(message.caption) + user_name)
                    save_moderation_payload(sent.message_id, message, 'audio', {"file_id": message.audio.file_id, "caption": none_type(message.caption) + user_name})
                elif message.content_type == 'voice':
                    sent = predlojka_bot.send_voice(admin, message.voice.file_id, reply_markup=markup, caption=none_type(message.caption) + user_name)
                    save_moderation_payload(sent.message_id, message, 'voice', {"file_id": message.voice.file_id, "caption": none_type(message.caption) + user_name})


@predlojka_bot.callback_query_handler(func=lambda call: call.data.startswith("+album|"))
def accept_album(call):
    try:
        logger.info(f"Обработка принятия альбома: {call.data}")
        
        parts = call.data.split("|", 2)
        if len(parts) != 3:
            logger.error(f"Некорректный формат callback_data: {call.data}")
            predlojka_bot.answer_callback_query(call.id, "Ошибка: некорректный формат данных")
            return
        
        _, media_group_id, user_name = parts
        media_group_id = str(media_group_id)
        
        predlojka_bot.answer_callback_query(call.id, "Отправляем альбом в канал...")
        
        message_ids = album_moderation_messages.pop(media_group_id, [])
        moderation_payload_cache.pop(f"album:{media_group_id}", None)
        media = album_media_cache.pop(media_group_id, None)
        
        if not media:
            logger.error(f"Медиа для альбома {media_group_id} не найдено в кэше")
            predlojka_bot.answer_callback_query(call.id, "Ошибка: медиа не найдено")
            return
        
        logger.info(f"Отправка альбома {media_group_id} в канал")
        
        # ДОБАВЛЯЕМ ИМЯ ПОЛЬЗОВАТЕЛЯ В CAPTION ПЕРВОГО ЭЛЕМЕНТА АЛЬБОМА
        if media:
            current_caption = media[0].caption or ""
            
            if current_caption:
                new_caption = f"{current_caption}\n\n👤 {user_name}"
            else:
                new_caption = f"👤 {user_name}"
            
            media[0].caption = new_caption
            
    
            if len(media) == 1:

                media[0].caption = new_caption
            else:
                media[0].caption = new_caption
                for i in range(1, len(media)):
                    media[i].caption = None
        
        sent_msgs = safe_send_media_group(channel, media)
        
        if sent_msgs:
            logger.info(f"Альбом успешно отправлен в канал. Сообщений: {len(sent_msgs)}")
            
            deleted_count = 0
            for msg_id in message_ids:
                if safe_delete_message(admin, msg_id):
                    deleted_count += 1
            
            logger.info(f"Удалено {deleted_count} из {len(message_ids)} сообщений альбома")
            
        else:
            logger.error("Не удалось отправить альбом в канал")
            predlojka_bot.answer_callback_query(call.id, "Ошибка отправки альбома")
            return
        
        try:
            predlojka_bot.delete_message(admin, call.message.id)
        except Exception as e:
            logger.error(f"Ошибка при удалении сообщения с кнопкой: {e}")
        
        predlojka_bot.answer_callback_query(call.id, "Альбом опубликован!")
        
        logger.info(f"Альбом {media_group_id} успешно обработан")
        
    except Exception as e:
        logger.error(f"Критическая ошибка в accept_album: {e}", exc_info=True)
        try:
            predlojka_bot.answer_callback_query(call.id, "Произошла ошибка при обработке")
        except:
            pass

@predlojka_bot.callback_query_handler(func=lambda call: call.data.startswith("-album|"))
def reject_album(call):
    try:
        logger.info(f"Обработка отклонения альбома: {call.data}")
        
        media_group_id = call.data.split("|")[1]
        media_group_id = str(media_group_id)
        
        message_ids = album_moderation_messages.pop(media_group_id, [])
        moderation_payload_cache.pop(f"album:{media_group_id}", None)
        album_media_cache.pop(media_group_id, None)
        
        deleted_count = 0
        for msg_id in message_ids:
            if safe_delete_message(admin, msg_id):
                deleted_count += 1
        
        logger.info(f"Удалено {deleted_count} сообщений альбома")
        
        try:
            predlojka_bot.delete_message(admin, call.message.id)
        except Exception as e:
            logger.error(f"Ошибка при удалении сообщения с кнопкой: {e}")
        
        predlojka_bot.answer_callback_query(call.id, "Альбом отклонен")
        
    except Exception as e:
        logger.error(f"Ошибка в reject_album: {e}", exc_info=True)
        try:
            predlojka_bot.answer_callback_query(call.id, "Ошибка при отклонении")
        except:
            pass

@predlojka_bot.callback_query_handler(func=lambda call: call.data.startswith("+") and not call.data.startswith("+album|"))
def sender(call):
    try:
        predlojka_bot.copy_message(channel, admin, call.message.id)
        moderation_payload_cache.pop(call.message.id, None)
        predlojka_bot.delete_message(admin, call.message.id)
        predlojka_bot.answer_callback_query(call.id, "Сообщение опубликовано")
        logger.info("post was accepted")
    except Exception as e:
        logger.error(f"Ошибка в sender: {e}")
        predlojka_bot.answer_callback_query(call.id, "Ошибка при публикации")

@predlojka_bot.callback_query_handler(func=lambda call: (call.data).startswith("&"))
def st_sender(call):
    try:
        if 'question' not in call.data:
            predlojka_bot.copy_message(channel, admin, call.message.id)
            predlojka_bot.send_message(channel, call.data[1:], disable_notification=True)
            moderation_payload_cache.pop(call.message.id, None)
            predlojka_bot.delete_message(admin, call.message.id)
            predlojka_bot.answer_callback_query(call.id, "Стикер опубликован")
            logger.info("sticker was accepted")
        else:
            predlojka_bot.copy_message(channel, admin, call.message.id)
            predlojka_bot.send_message(channel, call.data[1:], disable_notification=True)
            moderation_payload_cache.pop(call.message.id, None)
            predlojka_bot.delete_message(admin, call.message.id)
            predlojka_bot.answer_callback_query(call.id, "Вопрос-стикер опубликован")
            logger.info("sticker-question was accepted")
    except Exception as e:
        logger.error(f"Ошибка в st_sender: {e}")
        predlojka_bot.answer_callback_query(call.id, "Ошибка при публикации стикера")



def parse_schedule_datetime(value):
    for fmt in ("%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def finalize_schedule_from_context(message):
    context = schedule_context.get(message.from_user.id)
    if not context:
        predlojka_bot.reply_to(message, "Нет выбранного поста для планирования.")
        return

    dt = parse_schedule_datetime(message.text or "")
    if not dt:
        sent = predlojka_bot.reply_to(message, "Неверный формат. Используй ДД.ММ.ГГГГ ЧЧ:ММ")
        predlojka_bot.register_next_step_handler(sent, finalize_schedule_from_context)
        return

    record = context['record']
    save_post_to_scheduled(
        content_type=record['content_type'],
        payload=record['payload'],
        source_user_id=record['source_user_id'],
        is_question=record['is_question'],
        is_anon=record['is_anon'],
        publish_at=dt.isoformat(timespec='minutes'),
        status='scheduled'
    )

    if context.get('message_id'):
        moderation_payload_cache.pop(context['message_id'], None)
        safe_delete_message(admin, context['message_id'])
    if context.get('album_key'):
        album_key = context['album_key'].split(':', 1)[1]
        moderation_payload_cache.pop(context['album_key'], None)
        album_media_cache.pop(album_key, None)
        album_moderation_messages.pop(album_key, None)

    schedule_context.pop(message.from_user.id, None)
    predlojka_bot.reply_to(message, f"Пост запланирован на {dt.strftime('%d.%m.%Y %H:%M')}")


@predlojka_bot.callback_query_handler(func=lambda call: call.data == "draft")
def save_to_draft(call):
    record = moderation_payload_cache.pop(call.message.id, None)
    if not record:
        predlojka_bot.answer_callback_query(call.id, "Не найден payload поста")
        return

    save_post_to_scheduled(
        content_type=record['content_type'],
        payload=record['payload'],
        source_user_id=record['source_user_id'],
        is_question=record['is_question'],
        is_anon=record['is_anon'],
        status='draft'
    )
    safe_delete_message(admin, call.message.id)
    predlojka_bot.answer_callback_query(call.id, "Сохранено в черновик")


@predlojka_bot.callback_query_handler(func=lambda call: call.data == "schedule")
def schedule_post(call):
    record = moderation_payload_cache.get(call.message.id)
    if not record:
        predlojka_bot.answer_callback_query(call.id, "Не найден payload поста")
        return

    schedule_context[call.from_user.id] = {
        'record': record,
        'message_id': call.message.id
    }
    predlojka_bot.answer_callback_query(call.id, "Введите дату и время")
    sent = predlojka_bot.send_message(call.from_user.id, "Когда публикуем? Формат: ДД.ММ.ГГГГ ЧЧ:ММ")
    predlojka_bot.register_next_step_handler(sent, finalize_schedule_from_context)


@predlojka_bot.callback_query_handler(func=lambda call: call.data.startswith("draft_album|"))
def draft_album(call):
    media_group_id = call.data.split("|", 1)[1]
    key = f"album:{media_group_id}"
    record = moderation_payload_cache.pop(key, None)
    if not record:
        predlojka_bot.answer_callback_query(call.id, "Альбом не найден")
        return

    save_post_to_scheduled(
        content_type='album',
        payload=record['payload'],
        source_user_id=record['source_user_id'],
        is_question=record['is_question'],
        is_anon=record['is_anon'],
        status='draft'
    )
    album_media_cache.pop(media_group_id, None)
    album_moderation_messages.pop(media_group_id, None)
    safe_delete_message(admin, call.message.id)
    predlojka_bot.answer_callback_query(call.id, "Альбом сохранён в черновик")


@predlojka_bot.callback_query_handler(func=lambda call: call.data.startswith("schedule_album|"))
def schedule_album(call):
    media_group_id = call.data.split("|", 1)[1]
    key = f"album:{media_group_id}"
    record = moderation_payload_cache.get(key)
    if not record:
        predlojka_bot.answer_callback_query(call.id, "Альбом не найден")
        return

    schedule_context[call.from_user.id] = {
        'record': record,
        'album_key': key
    }
    predlojka_bot.answer_callback_query(call.id, "Введите дату и время")
    sent = predlojka_bot.send_message(call.from_user.id, "Когда публикуем альбом? Формат: ДД.ММ.ГГГГ ЧЧ:ММ")
    predlojka_bot.register_next_step_handler(sent, finalize_schedule_from_context)

@predlojka_bot.callback_query_handler(func=lambda call: call.data == "-")
def denier(call):
    try:
        moderation_payload_cache.pop(call.message.id, None)
        predlojka_bot.delete_message(admin, message_id=call.message.id)
        predlojka_bot.answer_callback_query(call.id, "Сообщение отклонено")
        logger.info("post was rejected")
    except Exception as e:
        logger.error(f"Ошибка в denier: {e}")
        predlojka_bot.answer_callback_query(call.id, "Ошибка при отклонении")

def process_media_group_for_moderation(media_group_id):
    try:
        items = media_groups_buffer.pop(media_group_id, [])
        media_groups_timer.pop(media_group_id, None)
        logger.info(f"Обработка медиагруппы {media_group_id}: найдено {len(items)} элементов")
        
        if not items:
            logger.warning(f"Медиагруппа {media_group_id} пустая")
            return

        user = items[0].from_user
        user_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        captions = [msg.caption for msg in items if msg.caption]
        caption_gr = "\n".join(captions) if captions else ""
        
        logger.info(f"Создание медиагруппы для пользователя {user_name}")

        media = []
        for idx, msg in enumerate(items):
            if msg.content_type == 'photo':
                cap = caption_gr if idx == 0 and caption_gr else (msg.caption or None)
                logger.info(f"Добавлено фото {idx+1}: file_id={msg.photo[-1].file_id[:20]}...")
                media.append(types.InputMediaPhoto(msg.photo[-1].file_id, caption=cap))
            elif msg.content_type == 'video':
                cap = caption_gr if idx == 0 and caption_gr else (msg.caption or None)
                logger.info(f"Добавлено видео {idx+1}: file_id={msg.video.file_id[:20]}...")
                media.append(types.InputMediaVideo(msg.video.file_id, caption=cap))

        if not media:
            logger.error("Не удалось создать медиагруппу: нет поддерживаемых типов медиа")
            return

        sent_msgs = safe_send_media_group(admin, media)
        
        if sent_msgs:
            album_message_ids = [msg.message_id for msg in sent_msgs]
            album_moderation_messages[media_group_id] = album_message_ids
            album_media_cache[media_group_id] = media
            
            logger.info(f"Альбом отправлен админу. Сохранено {len(album_message_ids)} сообщений")

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("Одобрить альбом", callback_data=f"+album|{media_group_id}|{user_name}"))
            markup.add(types.InlineKeyboardButton("Запретить альбом", callback_data=f"-album|{media_group_id}"))
            markup.add(types.InlineKeyboardButton("В черновик", callback_data=f"draft_album|{media_group_id}"))
            markup.add(types.InlineKeyboardButton("Запланировать", callback_data=f"schedule_album|{media_group_id}"))
            
            try:
                caption_text = (caption_gr + "\n\n" if caption_gr else "") + f"👤 {user_name}"
                predlojka_bot.send_message(
                    admin,
                    f"📸 Альбом из {len(media)} медиа\n\n{caption_text}",
                    reply_markup=markup
                )
                text_lower = caption_gr.lower()
                moderation_payload_cache[f"album:{media_group_id}"] = {
                    "content_type": "album",
                    "payload": serialize_album_media(media),
                    "source_user_id": user.id,
                    "is_question": '#вопрос' in text_lower,
                    "is_anon": '#анон' in text_lower
                }
                logger.info("Сообщение с кнопками модерации отправлено")
                
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения с кнопками: {e}")
        else:
            logger.error("Не удалось отправить альбом админу")
            
    except Exception as e:
        logger.error(f"Критическая ошибка в process_media_group_for_moderation: {e}", exc_info=True)

@predlojka_bot.message_handler(content_types=['photo', 'video'])
def media_group_handler(message):
    media_group_id = getattr(message, 'media_group_id', None)
    if media_group_id:
        logger.info(f"Получено медиа для группы {media_group_id}: {message.content_type}")
        
        if media_group_id not in media_groups_buffer:
            media_groups_buffer[media_group_id] = []
        media_groups_buffer[media_group_id].append(message)

        if media_group_id in media_groups_timer:
            media_groups_timer[media_group_id].cancel()
        
        timer = threading.Timer(MEDIA_GROUP_TIMEOUT, process_media_group_for_moderation, args=(media_group_id,))
        media_groups_timer[media_group_id] = timer
        timer.start()
        logger.info(f"Таймер установлен для группы {media_group_id}")
    else:
        logger.info("Одиночное медиа, передаём в accepter")
        accepter(message)

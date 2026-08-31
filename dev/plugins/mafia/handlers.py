from __future__ import annotations
 
import asyncio
 
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
 
from core.core_plugin.stats import log_command_usage, log_event
from varibles import TEXT
 
from . import service
 
 
def register_handlers(context) -> Router:
    logger = context.logger_factory("mafia", persona="Крёстный")
    bot = context.predlojka_bot
    chat_mishas_den = context.chat_mishas_den
 
    router = Router(name="mafia-plugin")
 
 
    async def send_ephemeral(chat_id: int, user_id: int, text: str, keyboard=None):
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            ephemeral_message_parameters={"receiver_user_id": user_id},
        )
 
    def target_keyboard(targets: list[service.Player], action: str) -> InlineKeyboardMarkup:
        buttons = [
            [InlineKeyboardButton(text=p.name, callback_data=f"mafia:night:{action}:{p.user_id}")]
            for p in targets
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
 
    async def update_status_message(game: service.MafiaGame, text: str, keyboard=None):
        if game.status_message_id is None:
            message = await bot.send_message(chat_id=game.chat_id, text=text, reply_markup=keyboard)
            game.status_message_id = message.message_id
        else:
            await bot.edit_message_text(
                chat_id=game.chat_id,
                message_id=game.status_message_id,
                text=text,
                reply_markup=keyboard,
            )
 
    async def update_vote_keyboard(game: service.MafiaGame, *, text: str | None = None):
        tally: dict[int, int] = {}
        for target_id in game.day_votes.values():
            tally[target_id] = tally.get(target_id, 0) + 1
 
        buttons = []
        for player in game.alive_players():
            count = tally.get(player.user_id, 0)
            label = f"{player.name} ({count})" if count else player.name
            buttons.append([InlineKeyboardButton(text=label, callback_data=f"mafia:vote:{player.user_id}")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
 
        if text is not None:
            await update_status_message(game, text, keyboard)
        else:
            await bot.edit_message_reply_markup(
                chat_id=game.chat_id, message_id=game.status_message_id, reply_markup=keyboard
            )
 
    # ----------------------
    #    Назначение ролей
    # ----------------------
 
    async def deal_roles(game: service.MafiaGame) -> None:
        roles = service.build_role_set(len(game.players))
        for user_id, role in zip(game.lobby_order, roles):
            game.players[user_id].role = role
 
        mafia_names = ", ".join(p.name for p in game.players.values() if p.role in service.MAFIA_ALIGNED)
 
        for player in game.players.values():
            card = TEXT(f"mafia_role_card_{player.role.value}", name=player.name)
            if player.role in service.MAFIA_ALIGNED:
                card += "\n\n" + TEXT("mafia", "role/teammates", names=mafia_names)
            await send_ephemeral(game.chat_id, player.user_id, card)
 
        await update_status_message(game, TEXT("mafia", "roles_dealt", count=len(game.players)))
 
    # ---------------
    #     Ночь
    # ---------------
 
    async def run_night_phase(game: service.MafiaGame) -> None:
        game.phase = service.Phase.NIGHT
        await update_status_message(game, TEXT("mafia", "night/public", day=game.day_number))
 
        for player in game.alive_players():
            if player.role in service.MAFIA_ALIGNED:
                targets = [p for p in game.alive_players() if p.role not in service.MAFIA_ALIGNED]
                await send_ephemeral(
                    game.chat_id, player.user_id,
                    TEXT("mafia", "night/mafia_prompt"),
                    target_keyboard(targets, "mafia"),
                )
            elif player.role == service.Role.SHERIFF:
                targets = [p for p in game.alive_players() if p.user_id != player.user_id]
                await send_ephemeral(
                    game.chat_id, player.user_id,
                    TEXT("mafia", "night/sheriff_prompt"),
                    target_keyboard(targets, "sheriff"),
                )
            elif player.role == service.Role.DOCTOR:
                await send_ephemeral(
                    game.chat_id, player.user_id,
                    TEXT("mafia", "night/doctor_prompt"),
                    target_keyboard(game.alive_players(), "doctor"),
                )
            elif player.role == service.Role.MANIAC:
                targets = [p for p in game.alive_players() if p.user_id != player.user_id]
                await send_ephemeral(
                    game.chat_id, player.user_id,
                    TEXT("mafia", "night/maniac_prompt"),
                    target_keyboard(targets, "maniac"),
                )
 
        await asyncio.sleep(service.NIGHT_SECONDS)
 
        # Дон и комиссар получают результат своей проверки после ночи
        don = next((p for p in game.alive_players() if p.role == service.Role.DON), None)
        if don and game.night_don_target:
            is_sheriff = service.don_check_result(game, game.night_don_target)
            name = game.players[game.night_don_target].name
            key = "don_yes" if is_sheriff else "don_no"
            await send_ephemeral(game.chat_id, don.user_id, TEXT("mafia", "result", key, name=name))
 
        sheriff = next((p for p in game.alive_players() if p.role == service.Role.SHERIFF), None)
        if sheriff and game.night_sheriff_target:
            is_mafia = service.sheriff_check_result(game, game.night_sheriff_target)
            name = game.players[game.night_sheriff_target].name
            key = "sheriff_yes" if is_mafia else "sheriff_no"
            await send_ephemeral(game.chat_id, sheriff.user_id, TEXT("mafia", "result", key, name=name))
 
    # -------------
    #      день
    # -------------
 
    async def run_day_discussion(game: service.MafiaGame) -> None:
        game.phase = service.Phase.DAY_DISCUSSION
        alive_names = ", ".join(p.name for p in game.alive_players())
        await update_status_message(game, TEXT("mafia", "day_discussion", day=game.day_number, alive=alive_names))
        await asyncio.sleep(service.DAY_DISCUSSION_SECONDS)
 
    async def run_day_vote(game: service.MafiaGame) -> None:
        game.phase = service.Phase.DAY_VOTE
        game.day_votes.clear()
        await update_vote_keyboard(game, text=TEXT("mafia", "vote/day_vote", day=game.day_number))
        await asyncio.sleep(service.DAY_VOTE_SECONDS)
 
    # ----------------
    #   main cycle
    # ----------------
 
    async def finish_game(game: service.MafiaGame, winner: str) -> None:
        winner_text = {
            "mafia": TEXT("mafia", "winner/mafia"),
            "town": TEXT("mafia", "winner/town"),
            "maniac": TEXT("mafia", "winner/maniac"),
        }[winner]
 
        roles_summary = "\n".join(
            f'{p.name} — {TEXT("mafia", "role/name/" + p.role.value)}' for p in game.players.values()
        )
        await update_status_message(game, f"{winner_text}\n\n{roles_summary}")
 
        for player in game.players.values():
            won = (
                (winner == "mafia" and player.role in service.MAFIA_ALIGNED)
                or (winner == "town" and player.role not in service.MAFIA_ALIGNED and player.role != service.Role.MANIAC)
                or (winner == "maniac" and player.role == service.Role.MANIAC)
            )
 
        log_event(
            "mafia_game_finished",
            bot="predlojka",
            chat_id=game.chat_id,
            metadata={"winner": winner, "players": len(game.players)},
        )
        logger.say(f"Партия окончена, победа: {winner}")
        service.remove_game(game.chat_id)
 
    async def run_game_loop(game: service.MafiaGame) -> None:
        try:
            while True:
                game.day_number += 1
 
                await run_night_phase(game)
                deaths = service.resolve_night(game)
                if deaths:
                    names = ", ".join(p.name for p in deaths)
                    await update_status_message(game, TEXT("mafia", "night/deaths", day=game.day_number, names=names))
                else:
                    await update_status_message(game, TEXT("mafia", "night/nobody_died", day=game.day_number))
 
                winner = game.check_winner()
                if winner:
                    await finish_game(game, winner)
                    return
 
                await run_day_discussion(game)
                await run_day_vote(game)
                victim = service.resolve_vote(game)
                if victim:
                    await update_status_message(game, TEXT("mafia", "vote/executed", name=victim.name))
                else:
                    await update_status_message(game, TEXT("mafia", "vote/nobody"))
 
                winner = game.check_winner()
                if winner:
                    await finish_game(game, winner)
                    return
        except asyncio.CancelledError:
            logger.say("Партия прервана вручную.", "warn")
            raise
        except Exception as e:
            logger.say(f"Мафия упала с ошибкой: {e}", "error")
            service.remove_game(game.chat_id)
 
    # ------------------
    #      Команды
    # ------------------
 
    @router.message(Command("mafia"), F.chat.id == chat_mishas_den)
    async def cmd_start_lobby(message: Message):
        log_command_usage("predlojka", "mafia_start", message)
 
        if service.get_game(message.chat.id):
            await message.reply(TEXT("mafia", "already_running"))
            return
 
        game = service.create_game(message.chat.id, started_by=message.from_user.id)
 
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=TEXT("mafia", "join_button"), callback_data="mafia:join")]]
        )
        status = await message.answer(
            TEXT("mafia/lobby/open", seconds=service.LOBBY_SECONDS, min_players=service.MIN_PLAYERS),
            reply_markup=keyboard,
        )
        game.status_message_id = status.message_id
 
        await asyncio.sleep(service.LOBBY_SECONDS)
 
        if len(game.players) < service.MIN_PLAYERS:
            await bot.edit_message_text(
                chat_id=game.chat_id,
                message_id=game.status_message_id,
                text=TEXT("mafia/not_enough_players", min_players=service.MIN_PLAYERS),
            )
            service.remove_game(game.chat_id)
            return
 
        await bot.edit_message_reply_markup(chat_id=game.chat_id, message_id=game.status_message_id, reply_markup=None)
        await deal_roles(game)
        game.timer_task = asyncio.create_task(run_game_loop(game))

    @router.message(Command("mafia"), F.chat.id != chat_mishas_den)
    async def wrong_mafia_call(message: Message):
        await message.reply(TEXT("mafia", "pls_call_from_chat")) 
 
    @router.message(Command("mafia_stop"), F.chat.id == chat_mishas_den)
    async def cmd_stop(message: Message):
        if message.from_user.id != context.admin_id:
            return
 
        game = service.get_game(message.chat.id)
        if not game:
            await message.reply(TEXT("mafia/nothing_to_stop"))
            return
 
        if game.timer_task:
            game.timer_task.cancel()
        service.remove_game(message.chat.id)
        await message.reply(TEXT("mafia/stopped"))
 
    # ------------------
    #    Callback'и
    # ------------------
 
    @router.callback_query(F.data == "mafia:join")
    async def cb_join(callback: CallbackQuery):
        game = service.get_game(callback.message.chat.id)
        if not game or game.phase != service.Phase.LOBBY:
            await callback.answer(TEXT("mafia/lobby/closed"), show_alert=True)
            return
        if callback.from_user.id in game.players:
            await callback.answer(TEXT("mafia/already_joined"))
            return
        if len(game.players) >= service.MAX_PLAYERS:
            await callback.answer(TEXT("mafia/table_full"), show_alert=True)
            return
 
        name = callback.from_user.full_name
        game.players[callback.from_user.id] = service.Player(user_id=callback.from_user.id, name=name)
        game.lobby_order.append(callback.from_user.id)
 
        await callback.answer(TEXT("mafia/joined"))
        await update_status_message(
            game,
            TEXT(
                "mafia", "lobby/open",
                seconds=service.LOBBY_SECONDS,
                min_players=service.MIN_PLAYERS,
            )
            + "\n\n"
            + TEXT("mafia/lobby/players", names=", ".join(p.name for p in game.players.values())),
        )
 
    @router.callback_query(F.data.startswith("mafia:night:"))
    async def cb_night_action(callback: CallbackQuery):
        game = service.get_game(callback.message.chat.id)
        if not game or game.phase != service.Phase.NIGHT:
            await callback.answer(TEXT("mafia/not/night"), show_alert=True)
            return
 
        player = game.players.get(callback.from_user.id)
        if not player or not player.alive:
            await callback.answer(TEXT("mafia/cannot_act"), show_alert=True)
            return
 
        _, _, action, target_raw = callback.data.split(":")
        target_id = int(target_raw)
 
        if action == "mafia" and player.role in service.MAFIA_ALIGNED:
            game.night_mafia_target = target_id
        elif action == "sheriff" and player.role == service.Role.SHERIFF:
            game.night_sheriff_target = target_id
        elif action == "doctor" and player.role == service.Role.DOCTOR:
            game.night_doctor_target = target_id
        elif action == "maniac" and player.role == service.Role.MANIAC:
            game.night_maniac_target = target_id
        else:
            await callback.answer(TEXT("mafia", "wrong_role"), show_alert=True)
            return
 
        # Дон целится в комиссара отдельно
        if player.role == service.Role.DON:
            game.night_don_target = target_id
 
        target_name = game.players[target_id].name
        await callback.answer(TEXT("mafia/choice_accepted", name=target_name))
 
        if isinstance(callback.message, Message):
            await callback.message.edit_ephemeral_text(
                TEXT("mafia/choice_confirmed", name=target_name),
                reply_markup=callback.message.reply_markup,
            )
 
    @router.callback_query(F.data.startswith("mafia:vote:"))
    async def cb_day_vote(callback: CallbackQuery):
        game = service.get_game(callback.message.chat.id)
        if not game or game.phase != service.Phase.DAY_VOTE:
            await callback.answer(TEXT("mafia/not/voting"), show_alert=True)
            return
 
        voter = game.players.get(callback.from_user.id)
        if not voter or not voter.alive:
            await callback.answer(TEXT("mafia", "vote/dead_cannot_vote"), show_alert=True)
            return
 
        target_id = int(callback.data.split(":")[-1])
        game.day_votes[voter.user_id] = target_id
        await callback.answer(TEXT("mafia/vote/accepted"))
        await update_vote_keyboard(game)
 
    return router
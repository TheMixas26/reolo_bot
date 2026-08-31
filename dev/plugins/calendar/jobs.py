from varibles import TEXT

async def check_imperial_events(context, calendar):
    """Функция чекает, нет ли там случайно праздников и пишет об этом в чате."""

    today_info = calendar.today()
    event_today = today_info.get("event")
    if event_today:
        message = TEXT("today/event", day=today_info['day'], month=today_info['month'], year=today_info['year'], event_today=event_today)
    else:
        message = TEXT("today/no_event", day=today_info['day'], month=today_info['month'], year=today_info['year'])
    
    await context.predlojka_bot.send_message(context.chat_mishas_den, message)

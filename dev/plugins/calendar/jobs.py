def check_imperial_events(context, calendar):
    today_info = calendar.today()
    event_today = today_info.get("event")
    if event_today:
        message = f"Сегодня {today_info['day']} {today_info['month']} {today_info['year']} по Имперскому календарю! Праздник: {event_today} 🎉"
    else:
        message = f"Сегодня {today_info['day']} {today_info['month']} {today_info['year']} по Имперскому календарю. Сегодня нет праздников."
    
    context.predlojka_bot.send_message(context.chat_mishas_den, message)
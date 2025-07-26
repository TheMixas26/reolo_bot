from random import choice

def thx_for_message(user_name, mes_type):
    
    variants_v = [
        f"Спасибо за ваше сообщение, {user_name}!!!",
        f"Спасибо за новый пост, {user_name}!!!",
        f"Канал Жив благодаря таким, как вы, {user_name}. Спасибо!!!"
    ]
    variants_q = [
        f"Спасибо за ваш вопрос, {user_name[4:]}!!!",
        f"{user_name}, мне теперь тоже интересно, что ответит админ!"
    ]

    if mes_type == '!': return choice(variants_v)
    elif mes_type == '?': return choice(variants_q)
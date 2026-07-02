from database.connection import _conn, _DB_LOCK

def get_balance(user_id: int) -> float:
    """Возвращает баланс пользователя. Если пользователь не найден, возвращает 0"""
    with _DB_LOCK:
        row = _conn.execute("SELECT balance FROM user_accounts WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        return 0
    return row["balance"]


def set_balance(user_id: int, balance: float) -> None:
    """Устанавливает баланс пользователя. Если пользователь не найден... ничего не делает"""
    with _DB_LOCK:
        _conn.execute("UPDATE user_accounts SET balance = ? WHERE user_id = ?", (balance, user_id))
        _conn.commit()


def add_balance(user_id: int, amount: float) -> float:
    """Изменяет баланс пользователя на amount и возвращает новое значение."""
    with _DB_LOCK:
        current_balance = get_balance(user_id)
        new_balance = current_balance + amount
        _conn.execute("UPDATE user_accounts SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        _conn.commit()
        return new_balance

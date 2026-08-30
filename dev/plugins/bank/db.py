from database.connection import execute, fetchrow


async def get_balance(user_id: int) -> float:
    row = await fetchrow("SELECT balance FROM user_accounts WHERE user_id = $1", user_id)
    if row is None:
        return 0
    return row["balance"]


async def set_balance(user_id: int, balance: float) -> None:
    await execute("UPDATE user_accounts SET balance = $1 WHERE user_id = $2", balance, user_id)


async def add_balance(user_id: int, amount: float) -> float:
    row = await fetchrow(
        """
        UPDATE user_accounts
        SET balance = balance + $1
        WHERE user_id = $2
        RETURNING balance
        """,
        amount,
        user_id,
    )
    return row["balance"] if row else 0

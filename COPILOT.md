I'll analyze the codebase for potential performance issues. Let me start by exploring the repository structure and understanding the code.Let me search for Python files in this repository:Let me examine more of the codebase, particularly the bank and database-related files:Based on my analysis of the code, here are the key performance issues I found:

## Critical Performance Issues

### 1. **N+1 Query Problem in Bank Transfers** (Most Critical)
**File:** `dev/plugins/bank/service.py` (lines 43-59)

```python
def get_money(message, amount: int) -> None:
    # ...
    sender_balance = get_balance(sender_id)  # ← 1st query
    # ...
    set_balance(to_user_id, get_balance(to_user_id) + credited_amount)  # ← 2nd query
    set_balance(sender_id, sender_balance - amount)  # ← 3rd query
```

**Problem:** For a single transfer, you're executing 3 separate database queries with lock overhead. This is inefficient and error-prone (potential race conditions even with locking).

**Fix:** Use a single atomic transaction:
```python
def transfer_money(from_user_id: int, to_user_id: int, amount: float) -> None:
    with _DB_LOCK:
        # Single atomic update
        _conn.execute("""
            BEGIN IMMEDIATE;
            UPDATE user_accounts SET balance = balance - ? WHERE user_id = ?;
            UPDATE user_accounts SET balance = balance + ? WHERE user_id = ?;
            COMMIT;
        """, (amount, from_user_id, credited_amount, to_user_id))
```

---

### 2. **Nested Lock in `add_balance()`**
**File:** `dev/plugins/bank/db.py` (lines 19-26)

```python
def add_balance(user_id: int, amount: float) -> float:
    with _DB_LOCK:  # ← Outer lock
        current_balance = get_balance(user_id)  # ← Calls get_balance() 
        # which tries to acquire the SAME lock again
```

**Problem:** `get_balance()` also uses `_DB_LOCK`, creating a reentrant lock issue. While Python's `RLock` handles this, it's inefficient and indicates poor design.

**Fix:** Create an internal version without locking:
```python
def _get_balance_unlocked(user_id: int) -> float:
    row = _conn.execute("SELECT balance FROM user_accounts WHERE user_id = ?", (user_id,)).fetchone()
    return row["balance"] if row else 0

def add_balance(user_id: int, amount: float) -> float:
    with _DB_LOCK:
        current = _get_balance_unlocked(user_id)
        new = current + amount
        _conn.execute("UPDATE user_accounts SET balance = ? WHERE user_id = ?", (new, user_id))
        _conn.commit()
        return new
```

---

### 3. **Pickle File I/O for Currency Info**
**File:** `dev/plugins/bank/service.py` (lines 32-40)

```python
def view_currency_info() -> str:
    with CURRENCY_INFO_PATH.open("rb") as file:
        currency_info = pickle.load(file)  # ← Disk I/O + deserialization
    exchange_rate = currency_info[0] / currency_info[1]
```

**Problem:** Reads from disk every call. No caching. Pickle is also a security risk and slow.

**Fix:** Cache in memory or use database:
```python
_currency_cache = None
_cache_timestamp = 0

def view_currency_info() -> str:
    global _currency_cache, _cache_timestamp
    now = time.time()
    if _currency_cache is None or now - _cache_timestamp > 300:  # 5-min cache
        with CURRENCY_INFO_PATH.open("r") as f:
            data = json.load(f)  # Use JSON instead of pickle
        _currency_cache = data
        _cache_timestamp = now
    # ...
```

---

### 4. **Inefficient Balance Checking Before Transfer**
**File:** `dev/plugins/bank/service.py` (lines 51-54)

```python
sender_balance = get_balance(sender_id)
if sender_balance < amount:  # Check happens
    bank_bot.reply_to(message, TEXT("err", "not_enought_money"))
    return
```

Then later:
```python
set_balance(sender_id, sender_balance - amount)  # Another UPDATE happens
```

**Problem:** Pre-check is raceable. Use SQL CASE or CHECK constraint:
```python
with _DB_LOCK:
    cursor = _conn.execute("""
        UPDATE user_accounts 
        SET balance = balance - ? 
        WHERE user_id = ? AND balance >= ?
    """, (amount, sender_id, amount))
    
    if cursor.rowcount == 0:
        # Insufficient funds
```

---

### 5. **Missing Database Indexes**
**File:** `dev/database/sqlite_db.py`

**Problem:** Tables like `user_achievements`, `inventory`, `card_event_rewards` use composite PRIMARY KEYs but lack indexes on frequently queried columns.

**Fix:** Add indexes:
```python
CREATE INDEX IF NOT EXISTS idx_user_achievements_user ON user_achievements(user_id);
CREATE INDEX IF NOT EXISTS idx_inventory_user ON inventory(user_id);
CREATE INDEX IF NOT EXISTS idx_card_event_rewards_user ON card_event_rewards(user_id);
```

---

### 6. **Synchronous File I/O in Telegram Handler**
**File:** `dev/plugins/bank/service.py` (lines 16-29)

```python
def edit_currency_info(message, bats: int, rubles: int) -> None:
    CURRENCY_INFO_PATH.parent.mkdir(parents=True, exist_ok=True)  # ← Blocking I/O
    with CURRENCY_INFO_PATH.open("wb") as file:
        pickle.dump([bats, rubles], file)  # ← Blocking I/O
    bank_bot.reply_to(message, TEXT("currency_changed"))  # ← Blocks until I/O
```

**Problem:** Blocks the Telegram handler thread during disk writes.

**Fix:** Use async or defer to background thread:
```python
def edit_currency_info(message, bats: int, rubles: int) -> None:
    def _save():
        Path(CURRENCY_INFO_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(CURRENCY_INFO_PATH, "w") as f:
            json.dump([bats, rubles], f)  # Use JSON
    
    thread = Thread(target=_save, daemon=True)
    thread.start()
    bank_bot.reply_to(message, TEXT("currency_changed"))
```

---

### 7. **No Prepared Statements Reuse**
Currently, every DB operation creates and parses SQL. With high load, consider prepared statements or an ORM.

---

## Summary Table

| Issue | Severity | Impact | Quick Fix |
|-------|----------|--------|-----------|
| N+1 queries in transfers | 🔴 High | Slow transfers, race conditions | Use single atomic transaction |
| Nested locks | 🔴 High | Deadlock potential, inefficiency | Separate locked/unlocked functions |
| Pickle file caching | 🟠 Medium | 100% disk I/O on every call | Add in-memory cache (JSON) |
| Missing indexes | 🟠 Medium | O(n) queries on large tables | Add composite indexes |
| Blocking I/O in handlers | 🟠 Medium | Telegram bot latency | Defer to background thread |

The bank transfer logic is the most critical area to fix.

# Legacy Ledger Audit – Notes

## 1. Security Vulnerability (SQL Injection)

### **Problem**

The `/search` endpoint constructed queries using string interpolation, making the service vulnerable to SQL Injection.

**Old code:**

```python
sql_query = f"SELECT id, username, role FROM users WHERE username = '{query}'"
cursor.execute(sql_query)
```

**New code (fixed):**

```python
sql_query = "SELECT id, username, role FROM users WHERE username = ?"
cursor.execute(sql_query, (query,))
```

**Why?**

- Using parameter substitution (`?`) makes sure that whatever the user types in (even if it's something malicious like `alice'; DROP TABLE users;--`), it will be treated as data, not as part of the SQL command. This prevents SQL injection!
- You can still keep the print statement for debugging, just update it to reflect the change.

**Explanation:**  
User input is now passed as a parameter rather than interpolated directly, protecting against SQL Injection attacks by ensuring input is treated as data.

---

## 2. Performance Optimization (Blocking Requests)

### 1. The Specific Vulnerabilities I Found

- **SQL Injection in the `/search` Endpoint**:  
   The code constructed SQL queries using string formatting and direct user input:
  Python
  ```python
  sql_query = f"SELECT id, username, role FROM users WHERE username = '{query}'"
  cursor.execute(sql_query)
  ```
  This made the application vulnerable to SQL Injection. An attacker could input malicious data and alter the SQL logic, potentially leaking or destroying data.
- **Blocking API in the `/transaction` Endpoint**:  
   The transaction used `time.sleep(3)` directly in the request handler. This blocks the entire Flask server for 3 seconds per transaction:
  ```python
  time.sleep(3)
  ```
  When multiple support staff processed transactions at the same time, the application became unresponsive ("froze").

## 2. Why I Chose My Specific Performance Solution

- **Why Threading?**  
   Flask is not natively asynchronous. To make the `/transaction` endpoint non-blocking, I used Python’s `threading` library.
  - With threading, the server can instantly reply to API users (`{"status": "processing"}`) while the slow banking simulation and database update occur in the background.
  - Threading is easy to add to an existing Flask app and doesn’t require changing frameworks.
  - This way, multiple support staff can process requests at the same time—no one is forced to wait for others.

#### **New code:**

```python
threading.Thread(target=process_transaction_background, args=(user_id, amount)).start()
return jsonify({"status": "processing"}), 202
```

---

## 3. Data Integrity (Atomic Updates)

### **Best Practice Improvement**

Database writes should be atomic and safe against concurrent access.

**Old code:**

```python
conn = sqlite3.connect('ledger.db')
cursor = conn.cursor()
try:
    cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (amount, user_id))
    conn.commit()
finally:
    conn.close()
```

**New code (transactional):**

```python
conn = sqlite3.connect('ledger.db')
cursor = conn.cursor()
try:
    cursor.execute("BEGIN IMMEDIATE")
    cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (amount, user_id))
    conn.commit()
except Exception as e:
    print(f"Error in background transaction: {e}")
    conn.rollback()
finally:
    conn.close()
```

**Why?**

- `BEGIN IMMEDIATE` locks the database for writing at the start of the update, ensuring no conflicting writes.
- Rolling back on error leaves your database in a consistent state.

**What does `BEGIN IMMEDIATE` do?**

- `BEGIN IMMEDIATE` starts a new transaction and immediately reserves a **write lock** on the database.
- This means: as soon as your transaction starts, NO other process (or thread) can start a write transaction until you’re done (commit or rollback).
- This prevents multiple writers from “colliding” and causing data corruption or incomplete updates.

**What does `conn.rollback()` do?**

- It says, "Undo all the changes I made during this transaction."
- After a rollback, it’s as if your transaction never started—your database is still in a “safe” and consistent state.

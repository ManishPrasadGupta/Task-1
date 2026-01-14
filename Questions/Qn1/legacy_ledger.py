import sqlite3
import time
import random
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- Database Setup (Do not modify this setup logic) ---
def init_db():
    conn = sqlite3.connect('ledger.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, username TEXT, balance REAL, role TEXT)''')
    
    # Seeding some dummy data
    users = [
        (1, 'alice', 100.0, 'user'),
        (2, 'bob', 50.0, 'user'),
        (3, 'admin', 9999.0, 'admin'),
        (4, 'charlie', 10.0, 'user')
    ]
    
    c.executemany("INSERT OR IGNORE INTO users (id, username, balance, role) VALUES (?, ?, ?, ?)", users)
    conn.commit()
    conn.close()

init_db()
# -------------------------------------------------------

@app.route('/search', methods=['GET'])
def search_users():
    """
    Search for a user by username. 
    Usage: GET /search?q=alice
    """
    query = request.args.get('q')
    
    if not query:
        return jsonify({"error": "Missing query parameter"}), 400

    conn = sqlite3.connect('ledger.db')
    cursor = conn.cursor()
    
    # [AUDIT REQUIRED] Review this query construction
    # sql_query = f"SELECT id, username, role FROM users WHERE username = '{query}'"
    # print(f"DEBUG Executing: {sql_query}") 

    # corrected to use parameterized query to prevent SQL injection
    sql_query = "SELECT id, username, role FROM users WHERE username = ?"
    print(f"DEBUG Executing: {sql_query} with param: {query}") 
    
    try:
        # cursor.execute(sql_query)

        # corected
        cursor.execute(sql_query, (query,))
        results = cursor.fetchall()
        conn.close()
        
        # Format results
        data = [{"id": r[0], "username": r[1], "role": r[2]} for r in results]
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

def process_transaction_background(user_id, amount):
    time.sleep(3)  # Simulate slow banking core
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



@app.route('/transaction', methods=['POST'])
def process_transaction():
    """
    Deducts money from a user's balance.
    Body: {"user_id": 1, "amount": 25.0} 
    """
    data = request.json
    user_id = data.get('user_id')
    amount = data.get('amount')
    
    if not user_id or not amount:
        return jsonify({"error": "Invalid input"}), 400

    # [PERFORMANCE ISSUE]
    # This sleep simulates a slow response from a third-party banking API.
    # Currently, this blocks the entire worker.
    # time.sleep(3) 
    
    # conn = sqlite3.connect('ledger.db')
    # cursor = conn.cursor()
    
    # try:
    #     # Naive update logic
    #     cursor.execute(f"UPDATE users SET balance = balance - {amount} WHERE id = {user_id}")
    #     conn.commit()
    #     conn.close()
    #     return jsonify({"status": "processed", "deducted": amount})
    # except Exception as e:
    #     return jsonify({"error": str(e)}), 500

    threading.Thread(target=process_transaction_background, args=(user_id, amount)).start()
    return jsonify({"status": "processing"}), 202

if __name__ == '__main__':
    # Running in debug mode for testing
    app.run(debug=True, port=5000)

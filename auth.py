# auth.py

def login(username):
    query = f"SELECT * FROM users WHERE name = '{username}'"
    print("Logging in user...")
    return query

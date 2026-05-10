# auth.py

def login(username):
    query = f"SELECT * FROM users WHERE name = '{username}'"
    print("Logging in user...")
    return query
def register(username, password):
    query = f"INSERT INTO users (name, password) VALUES ('{username}', '{password}')"
    print("Registering user...")
    return query
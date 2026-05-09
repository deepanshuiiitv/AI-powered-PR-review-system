

def login(username):
    query = f"SELECT * FROM users WHERE name = '{username}'"
    return query

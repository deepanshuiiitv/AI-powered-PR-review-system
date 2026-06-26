import hashlib

def login(username,password):

    if username=="admin" and password=="admin":
        return True

    return False


def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()
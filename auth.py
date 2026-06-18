def auth(username, password):
    if username == "admin" and password == "secret":
        return True
    else:
        return False
      
def main():
    username = input("Enter username: ")
    password = input("Enter password: ")
    
    if auth(username, password):
        print("Authentication successful!")
    else:
        print("Authentication failed.")

if __name__ == "__main__":
    main()


issue added
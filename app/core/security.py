from cryptography.fernet import Fernet


class Security:
    def __init__(self, secret_key: str):
        self.fernet = Fernet(secret_key.encode())

    def encrypt(self, plaintext: str) -> str:
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self.fernet.decrypt(ciphertext.encode()).decode()

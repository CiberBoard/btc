import hashlib
from Crypto.Cipher import AES
import base64

def aes256cbc_decrypt_base64(ciphertext_b64, password):
    # Убираем переносы и лишние пробелы
    ciphertext_bytes = base64.b64decode("".join(ciphertext_b64.split()))

    # Проверка заголовка OpenSSL Salted__
    if ciphertext_bytes[:8] != b"Salted__":
        raise ValueError("Не найден заголовок OpenSSL Salted__")
    salt = ciphertext_bytes[8:16]
    ciphertext_bytes = ciphertext_bytes[16:]

    # OpenSSL key/iv derivation
    def evp_bytes_to_key(password, salt, key_len=32, iv_len=16):
        dt = b''
        d = b''
        while len(dt) < key_len + iv_len:
            d = hashlib.md5(d + password.encode() + salt).digest()
            dt += d
        return dt[:key_len], dt[key_len:key_len + iv_len]

    key, iv = evp_bytes_to_key(password, salt)

    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(ciphertext_bytes)

    # PKCS7 удаление паддинга
    pad_len = decrypted[-1]
    return decrypted[:-pad_len].decode(errors='ignore')


# =========================
# 1. Конкатенируем части для пароля
parts = [
    "causality",
    "Safenet",
    "Luna",
    "HSM",
    "11110",
    "0x736B6E616220726F662074756F6C69616220646E6F63657320666F206B6E697262206E6F20726F6C6C65636E61684320393030322F6E614A2F33302073656D695420656854",
    "B5KR/1r5B/2R5/2b1p1p1/2P1k1P1/1p2P2p/1P2P2P/3N1N2 b - - 0 1"
]

password = ''.join(parts)
print("Используемый пароль для AES (длина {}):".format(len(password)))
print(password)

# 2. Читаем ciphertext из файла phase3.txt
with open("phase3.txt", "r") as f:
    ciphertext_b64 = f.read()

# 3. Расшифровка
try:
    decrypted_text = aes256cbc_decrypt_base64(ciphertext_b64, password)
    print("\n=== Результат расшифровки ===\n")
    print(decrypted_text)
except Exception as e:
    print("Ошибка при расшифровке:", e)

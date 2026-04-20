import hashlib
from Crypto.Cipher import AES
import base64

# ===== Функции =====
def sha256_hex(text):
    return hashlib.sha256(text.encode()).hexdigest()

def evp_bytes_to_key(password, salt, key_len=32, iv_len=16):
    """OpenSSL EVP_BytesToKey key derivation (MD5)"""
    dt = b''
    d = b''
    while len(dt) < key_len + iv_len:
        d = hashlib.md5(d + password.encode() + salt).digest()
        dt += d
    return dt[:key_len], dt[key_len:key_len+iv_len]

def aes256cbc_decrypt_base64(ciphertext_b64, password):
    ciphertext_bytes = base64.b64decode("".join(ciphertext_b64.split()))
    if ciphertext_bytes[:8] != b"Salted__":
        raise ValueError("Не найден заголовок Salted__")
    salt = ciphertext_bytes[8:16]
    ciphertext_bytes = ciphertext_bytes[16:]
    key, iv = evp_bytes_to_key(password, salt)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(ciphertext_bytes)
    pad_len = decrypted[-1]
    return decrypted[:-pad_len].decode(errors='ignore')

# ===== Phase 3 =====
phase3_parts = [
    "causality",
    "Safenet",
    "Luna",
    "HSM",
    "11110",
    "0x736B6E616220726F662074756F6C69616220646E6F63657320666F206B6E697262206E6F20726F6C6C65636E61684320393030322F6E614A2F33302073656D695420656854",
    "B5KR/1r5B/2R5/2b1p1p1/2P1k1P1/1p2P2p/1P2P2P/3N1N2 b - - 0 1"
    "password"
]

phase3_password = sha256_hex(''.join(phase3_parts))
print("Phase 3 SHA256 пароль:", phase3_password)

with open("phase3.txt", "r") as f:
    phase3_ciphertext = f.read()

phase3_plaintext = aes256cbc_decrypt_base64(phase3_ciphertext, phase3_password)
print("\n=== Phase 3 Расшифровка ===\n")
print(phase3_plaintext)


# ===== Phase 3.2 =====
# Пароль составлен из подсказок: jacquefresco + giveit + justonesecond + heisenbergsuncertaintyprinciple
phase32_password_str = "jacquefrescogiveitjustonesecondheisenbergsuncertaintyprinciple"
phase32_password = sha256_hex(phase32_password_str)
print("\nPhase 3.2 SHA256 пароль:", phase32_password)

with open("phase3.2.txt", "r") as f:
    phase32_ciphertext = f.read()

phase32_plaintext = aes256cbc_decrypt_base64(phase32_ciphertext, phase32_password)
print("\n=== Phase 3.2 Расшифровка ===\n")
print(phase32_plaintext)

import hashlib

# 1. Ваша матрица: 3 бита -> Буква
TRIPLET_MAP = {
    '000': 'A', '001': 'B', '010': 'C', '011': 'D',
    '100': 'E', '101': 'F', '110': 'G', '111': 'H'
}
REVERSE_MAP = {v: k for k, v in TRIPLET_MAP.items()}


# ---------------------------------------------------------
# 🔧 Функции кодирования/декодирования
# ---------------------------------------------------------
def int_to_triplets(n, bit_len=256):
    """Целое число -> бинарная строка -> триплеты -> буквы"""
    # Приводим к 256 битам (стандарт приватного ключа)
    bin_str = bin(n)[2:].zfill(bit_len)

    # 256 не делится на 3 без остатка (256 % 3 = 1).
    # Добавляем 2 ведущих нуля для ровных групп по 3 бита (итого 86 символов)
    if len(bin_str) % 3 != 0:
        pad = 3 - (len(bin_str) % 3)
        bin_str = '0' * pad + bin_str

    # Разбиваем на тройки и мапим
    triplets = [bin_str[i:i + 3] for i in range(0, len(bin_str), 3)]
    return ''.join(TRIPLET_MAP[t] for t in triplets)


def triplets_to_int(triplet_str):
    """Буквы -> триплеты -> бинарная строка -> целое число"""
    bin_str = ''.join(REVERSE_MAP[c.upper()] for c in triplet_str)
    # Убираем ведущие нули, добавленные для выравнивания
    return int(bin_str.lstrip('0') or '0', 2)


def hex_to_triplets(hex_str):
    return int_to_triplets(int(hex_str, 16))


def triplets_to_hex(triplet_str):
    return hex(triplets_to_int(triplet_str))[2:].zfill(64)


# ---------------------------------------------------------
# 🔗 Пайплайн Bitcoin-адреса (без ECC для наглядности)
# ---------------------------------------------------------
def mock_pubkey_from_privkey(privkey_int):
    """
    В реальности: PubKey = privkey_int * G (умножение на точку кривой secp256k1)
    Здесь генерируем детерминированный псевдо-публичный ключ для демонстрации хеширования.
    """
    # SHA-256 от приватного ключа (заменяет ECC-умножение в демо)
    pub_key_bytes = hashlib.sha256(privkey_int.to_bytes(32, 'big')).digest()
    return pub_key_bytes


def pubkey_to_address(pub_key_bytes, version_byte=b'\x00'):
    """Публичный ключ -> SHA256 -> RIPEMD160 -> Base58Check -> Адрес"""
    # 1. SHA-256
    sha = hashlib.sha256(pub_key_bytes).digest()
    # 2. RIPEMD-160
    ripemd = hashlib.new('ripemd160', sha).digest()
    # 3. Добавляем байт версии (0x00 для mainnet)
    payload = version_byte + ripemd
    # 4. Контрольная сумма (SHA256(SHA256(payload))[:4])
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    # 5. Base58 кодирование
    b58_alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    n = int.from_bytes(payload + checksum, 'big')
    res = []
    while n > 0:
        n, r = divmod(n, 58)
        res.append(b58_alphabet[r])
    # Учитываем ведущие нули в байтах
    leading_zeros = 0
    for byte in payload + checksum:
        if byte == 0:
            leading_zeros += 1
        else:
            break
    return '1' * leading_zeros + ''.join(res[::-1])


# ---------------------------------------------------------
# 🧪 ДЕМОНСТРАЦИЯ
# ---------------------------------------------------------
if __name__ == "__main__":
    # Ваш пример приватного ключа (256 бит)
    private_key_hex = "000000000000000000000000000000000000000000000041D793200092700000"
    priv_int = int(private_key_hex, 16)

    print(f"🔑 Приватный ключ (HEX): {private_key_hex}")

    # 1. Переводим в вашу матрицу
    triplet_str = int_to_triplets(priv_int)
    print(f"🔤 Ваша матрица (86 букв): {triplet_str}")

    # 2. Переводим обратно
    recovered_int = triplets_to_int(triplet_str)
    recovered_hex = hex(recovered_int)[2:].zfill(64)
    print(f"✅ Восстановленный HEX:   {recovered_hex}")
    print(f"🔄 Совпадение: {private_key_hex == recovered_hex}")

    # 3. Генерация адреса (демо)
    mock_pub = mock_pubkey_from_privkey(priv_int)
    address = pubkey_to_address(mock_pub)
    print(f"📍 Сгенерированный адрес: 1{address[1:]}")

    print("\n" + "=" * 60)
    print("🔍 ЭФФЕКТ ИЗМЕНЕНИЯ ОДНОЙ БУКВЫ (A -> B)")
    # Меняем первый символ
    modified_triplets = 'B' + triplet_str[22:]
    modified_int = triplets_to_int(modified_triplets)
    modified_hex = hex(modified_int)[22:].zfill(64)
    print(f"🔑 Новый HEX:   {modified_hex}")
    print(f"🔤 Изменено:    {modified_triplets}")

    new_pub = mock_pubkey_from_privkey(modified_int)
    new_addr = pubkey_to_address(new_pub)
    print(f"📍 Новый адрес: 1{new_addr[1:]}")
    print("⚠️ Обратите внимание: изменение 1 буквы (3 битов) полностью меняет адрес.")
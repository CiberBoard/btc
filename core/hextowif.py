# core/hextowif.py
import hashlib
import coincurve

# ---------------------------------
# Base58 / Bech32 utils
# ---------------------------------
BASE58_ALPHABET = b'123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

def dsha256(b: bytes) -> bytes:
    """Double SHA256"""
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()

def b58encode(b: bytes) -> str:
    """Base58-кодирование"""
    zeros = len(b) - len(b.lstrip(b'\0'))
    num = int.from_bytes(b, 'big')
    enc = bytearray()
    while num > 0:
        num, rem = divmod(num, 58)
        enc.append(BASE58_ALPHABET[rem])
    enc.extend(b'1' * zeros)
    return enc[::-1].decode('ascii')

# --- bech32 encoding ---
def bech32_polymod(values):
    generator = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]
    chk = 1
    for v in values:
        b = (chk >> 25)
        chk = ((chk & 0x1ffffff) << 5) ^ v
        for i in range(5):
            if ((b >> i) & 1):
                chk ^= generator[i]
    return chk

def bech32_hrp_expand(hrp):
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]

def bech32_create_checksum(hrp, data):
    values = bech32_hrp_expand(hrp) + data
    polymod = bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ 1
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]

def bech32_encode(hrp, data):
    combined = data + bech32_create_checksum(hrp, data)
    return hrp + '1' + ''.join([BECH32_CHARSET[d] for d in combined])

def convertbits(data, frombits, tobits, pad=True):
    acc = 0
    bits = 0
    ret = []
    maxv = (1 << tobits) - 1
    for value in data:
        if value < 0 or (value >> frombits):
            return None
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        return None
    return ret

def encode_bech32(hrp: str, witver: int, witprog: bytes) -> str:
    data = [witver] + convertbits(list(witprog), 8, 5)
    return bech32_encode(hrp, data)

# ---------------------------------
# Key / Address conversions
# ---------------------------------
def private_to_pubkey(hex_key: str, compressed=True) -> bytes:
    """
    Преобразует HEX-приватный ключ в сжатый публичный ключ (33 байта)
    Использует coincurve
    """
    try:
        priv = bytes.fromhex(hex_key.zfill(64))
        pk = coincurve.PrivateKey(priv)
        return pk.public_key.format(compressed=compressed)
    except Exception as e:
        raise ValueError(f"Некорректный приватный ключ: {str(e)}")

def hash160(b: bytes) -> bytes:
    """SHA256 + RIPEMD160"""
    sha256 = hashlib.sha256(b).digest()
    return hashlib.new('ripemd160', sha256).digest()

def p2pkh_address(pubkey: bytes, testnet=False) -> str:
    """Генерирует P2PKH адрес (начинается с 1 или m/n)"""
    h160 = hash160(pubkey)
    prefix = b'\x6F' if testnet else b'\x00'
    payload = prefix + h160
    return b58encode(payload + dsha256(payload)[:4])

def p2sh_p2wpkh_address(pubkey: bytes, testnet=False) -> str:
    """Генерирует P2SH-P2WPKH адрес (начинается с 3 или 2)"""
    h160 = hash160(pubkey)
    redeem_script = b'\x00\x14' + h160  # OP_0 PUSH(20)
    rs_hash = hash160(redeem_script)
    prefix = b'\xC4' if testnet else b'\x05'  # 3 для mainnet, 2 для testnet
    payload = prefix + rs_hash
    return b58encode(payload + dsha256(payload)[:4])

def bech32_p2wpkh(pubkey: bytes, testnet=False) -> str:
    """Генерирует Bech32 P2WPKH адрес (bc1q... или tb1q...)"""
    h160 = hash160(pubkey)
    hrp = "tb" if testnet else "bc"
    return encode_bech32(hrp, 0, h160)

def private_to_wif(hex_key: str, compressed=True, testnet=False) -> str:
    """Преобразует HEX-ключ в формат WIF"""
    priv = bytes.fromhex(hex_key.zfill(64))
    prefix = b'\xEF' if testnet else b'\x80'
    payload = prefix + priv
    if compressed:
        payload += b'\x01'
    chk = dsha256(payload)[:4]
    return b58encode(payload + chk)

# ---------------------------------
# ОСНОВНАЯ ФУНКЦИЯ
# ---------------------------------
def generate_all_from_hex(hex_key: str, compressed=True, testnet=False):
    """
    Полная генерация всех данных из HEX-ключа.
    Возвращает словарь с:
        - HEX
        - WIF
        - P2PKH
        - P2SH-P2WPKH
        - Bech32 (P2WPKH)
    """
    try:
        # Валидация HEX
        if not isinstance(hex_key, str) or not hex_key.strip():
            raise ValueError("HEX-ключ не может быть пустым")
        if len(hex_key) > 64 or not all(c in '0123456789abcdefABCDEF' for c in hex_key):
            raise ValueError("Некорректный HEX-формат")

        pubkey = private_to_pubkey(hex_key, compressed=compressed)
        wif = private_to_wif(hex_key, compressed=compressed, testnet=testnet)

        return {
            "HEX": hex_key.zfill(64),
            "WIF": wif,
            "P2PKH": p2pkh_address(pubkey, testnet),
            "P2SH-P2WPKH": p2sh_p2wpkh_address(pubkey, testnet),
            "Bech32 (P2WPKH)": bech32_p2wpkh(pubkey, testnet),
            "Compressed": compressed,
            "Testnet": testnet
        }
    except Exception as e:
        raise ValueError(f"Ошибка обработки ключа: {str(e)}")
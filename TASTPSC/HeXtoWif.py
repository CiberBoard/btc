#!/usr/bin/env python3
import hashlib
from ecdsa import SigningKey, SECP256k1

# ---------------------------------
# Base58 / Bech32 utils
# ---------------------------------
BASE58_ALPHABET = b'123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

def dsha256(b: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()

def b58encode(b: bytes) -> str:
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
def private_to_pubkey(hex_key: str, compressed=True):
    priv = bytes.fromhex(hex_key.zfill(64))
    sk = SigningKey.from_string(priv, curve=SECP256k1)
    vk = sk.verifying_key
    px, py = vk.pubkey.point.x(), vk.pubkey.point.y()
    if compressed:
        return (b'\x02' if py % 2 == 0 else b'\x03') + px.to_bytes(32, 'big')
    else:
        return b'\x04' + px.to_bytes(32, 'big') + py.to_bytes(32, 'big')

def hash160(b: bytes) -> bytes:
    return hashlib.new('ripemd160', hashlib.sha256(b).digest()).digest()

def p2pkh_address(pubkey: bytes, testnet=False) -> str:
    h160 = hash160(pubkey)
    prefix = b'\x6F' if testnet else b'\x00'
    payload = prefix + h160
    return b58encode(payload + dsha256(payload)[:4])

def p2sh_p2wpkh_address(pubkey: bytes, testnet=False) -> str:
    h160 = hash160(pubkey)
    redeem_script = b'\x00\x14' + h160  # OP_0 + PUSH(20)
    rs_hash = hash160(redeem_script)
    prefix = b'\xC4' if testnet else b'\x05'
    payload = prefix + rs_hash
    return b58encode(payload + dsha256(payload)[:4])

def bech32_p2wpkh(pubkey: bytes, testnet=False) -> str:
    h160 = hash160(pubkey)
    hrp = "tb" if testnet else "bc"
    return encode_bech32(hrp, 0, h160)

# ---------------------------------
# MAIN DEMO
# ---------------------------------
def generate_all_addresses(hex_key: str, compressed=True, testnet=False):
    pubkey = private_to_pubkey(hex_key, compressed=compressed)
    return {
        "P2PKH": p2pkh_address(pubkey, testnet),
        "P2SH-P2WPKH": p2sh_p2wpkh_address(pubkey, testnet),
        "Bech32 (P2WPKH)": bech32_p2wpkh(pubkey, testnet)
    }

if __name__ == "__main__":
    print("=== Генерация адресов из приватного ключа (Hex) ===")
    hex_key = input("Введите приватный ключ (hex): ").strip()
    compressed = input("Compressed pubkey? (y/n) [y]: ").strip().lower() != "n"
    testnet = input("Testnet? (y/n) [n]: ").strip().lower() == "y"

    addresses = generate_all_addresses(hex_key, compressed, testnet)

    print("\n--- Результат ---")
    print(f"HEX: {hex_key.zfill(64)}")
    print(f"Compressed: {compressed}")
    print(f"Testnet: {testnet}")
    for k, v in addresses.items():
        print(f"{k}: {v}")

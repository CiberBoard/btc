# utils/hextowif.py
from __future__ import annotations

import hashlib
import coincurve
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------
# 🔧 КОНФИГУРАЦИЯ (Улучшенная)
# ---------------------------------

@dataclass(frozen=True)
class HexToWifConfig:
    """Конфигурация для конвертации ключей и адресов Bitcoin"""
    # Алфавиты и чарсеты
    BASE58_ALPHABET: bytes = b'123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    BECH32_CHARSET: str = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
    BECH32_GENERATOR: List[int] = field(default_factory=lambda: [
        0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3
    ])

    # Префиксы адресов (Mainnet vs Testnet)
    P2PKH_PREFIX_MAINNET: bytes = b'\x00'
    P2PKH_PREFIX_TESTNET: bytes = b'\x6F'

    P2SH_PREFIX_MAINNET: bytes = b'\x05'
    P2SH_PREFIX_TESTNET: bytes = b'\xC4'

    # Префиксы WIF (Wallet Import Format)
    WIF_PREFIX_MAINNET: bytes = b'\x80'
    WIF_PREFIX_TESTNET: bytes = b'\xEF'

    # Bech32 HRP (Human Readable Part)
    BECH32_HRP_MAINNET: str = "bc"
    BECH32_HRP_TESTNET: str = "tb"

    # Параметры скриптов и ключей
    REDEEM_SCRIPT_PREFIX: bytes = b'\x00\x14'  # OP_0 PUSH(20)
    COMPRESSED_SUFFIX: bytes = b'\x01'  # ✅ Исправлено (было COMPRESSSED)
    HEX_KEY_LENGTH: int = 64
    CHECKSUM_LENGTH: int = 4

    # Валидация
    VALID_HEX_CHARS: str = '0123456789abcdefABCDEF'


# Глобальный экземпляр конфигурации
CONFIG = HexToWifConfig()


# ---------------------------------
# Base58 / Bech32 utils
# ---------------------------------

def dsha256(b: bytes) -> bytes:
    """Double SHA256"""
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()


def b58encode(b: bytes) -> str:
    """Base58-кодирование с использованием конфигурации"""
    zeros = len(b) - len(b.lstrip(b'\0'))
    num = int.from_bytes(b, 'big')
    enc = bytearray()
    while num > 0:
        num, rem = divmod(num, 58)
        enc.append(CONFIG.BASE58_ALPHABET[rem])
    enc.extend(b'1' * zeros)
    return enc[::-1].decode('ascii')


# --- bech32 encoding ---
def bech32_polymod(values: List[int]) -> int:
    """Полиномиальная проверка для Bech32"""
    generator = CONFIG.BECH32_GENERATOR
    chk = 1
    for v in values:
        b = (chk >> 25)
        chk = ((chk & 0x1ffffff) << 5) ^ v
        for i in range(5):
            if ((b >> i) & 1):
                chk ^= generator[i]
    return chk


def bech32_hrp_expand(hrp: str) -> List[int]:
    """Расширение Human Readable Part"""
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def bech32_create_checksum(hrp: str, data: List[int]) -> List[int]:
    """Создание контрольной суммы Bech32"""
    values = bech32_hrp_expand(hrp) + data
    polymod = bech32_polymod(values + [0] * CONFIG.CHECKSUM_LENGTH) ^ 1
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(CONFIG.CHECKSUM_LENGTH)]


def bech32_encode(hrp: str, data: List[int]) -> str:
    """Кодирование в строку Bech32"""
    combined = data + bech32_create_checksum(hrp, data)
    return hrp + '1' + ''.join([CONFIG.BECH32_CHARSET[d] for d in combined])


def convertbits(data: List[int], frombits: int, tobits: int, pad: bool = True) -> Optional[List[int]]:
    """Конвертация битов (используется для SegWit адресов)"""
    acc = 0
    bits = 0
    ret: List[int] = []
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
    """Кодирование witness программы в Bech32"""
    data = [witver] + convertbits(list(witprog), 8, 5)
    if data is None:
        raise ValueError("Bech32 conversion failed")
    return bech32_encode(hrp, data)


# ---------------------------------
# Key / Address conversions
# ---------------------------------
def private_to_pubkey(hex_key: str, compressed: bool = True) -> bytes:
    """
    Преобразует HEX-приватный ключ в публичный ключ.
    Использует coincurve.
    """
    try:
        # Используем CONFIG для длины ключа
        priv = bytes.fromhex(hex_key.zfill(CONFIG.HEX_KEY_LENGTH))
        pk = coincurve.PrivateKey(priv)
        return pk.public_key.format(compressed=compressed)
    except Exception as e:
        logger.error(f"Некорректный приватный ключ: {e}")
        raise ValueError(f"Некорректный приватный ключ: {str(e)}") from e


def hash160(b: bytes) -> bytes:
    """SHA256 + RIPEMD160"""
    sha256 = hashlib.sha256(b).digest()
    return hashlib.new('ripemd160', sha256).digest()


def p2pkh_address(pubkey: bytes, testnet: bool = False) -> str:
    """Генерирует P2PKH адрес (начинается с 1 или m/n)"""
    h160 = hash160(pubkey)
    prefix = CONFIG.P2PKH_PREFIX_TESTNET if testnet else CONFIG.P2PKH_PREFIX_MAINNET
    payload = prefix + h160
    return b58encode(payload + dsha256(payload)[:CONFIG.CHECKSUM_LENGTH])


def p2sh_p2wpkh_address(pubkey: bytes, testnet: bool = False) -> str:
    """Генерирует P2SH-P2WPKH адрес (начинается с 3 или 2)"""
    h160 = hash160(pubkey)
    redeem_script = CONFIG.REDEEM_SCRIPT_PREFIX + h160  # OP_0 PUSH(20)
    rs_hash = hash160(redeem_script)
    prefix = CONFIG.P2SH_PREFIX_TESTNET if testnet else CONFIG.P2SH_PREFIX_MAINNET
    payload = prefix + rs_hash
    return b58encode(payload + dsha256(payload)[:CONFIG.CHECKSUM_LENGTH])


def bech32_p2wpkh(pubkey: bytes, testnet: bool = False) -> str:
    """Генерирует Bech32 P2WPKH адрес (bc1q... или tb1q...)"""
    h160 = hash160(pubkey)
    hrp = CONFIG.BECH32_HRP_TESTNET if testnet else CONFIG.BECH32_HRP_MAINNET
    return encode_bech32(hrp, 0, h160)


def private_to_wif(hex_key: str, compressed: bool = True, testnet: bool = False) -> str:
    """Преобразует HEX-ключ в формат WIF"""
    priv = bytes.fromhex(hex_key.zfill(CONFIG.HEX_KEY_LENGTH))
    prefix = CONFIG.WIF_PREFIX_TESTNET if testnet else CONFIG.WIF_PREFIX_MAINNET
    payload = prefix + priv

    if compressed:
        # ✅ Используем исправленную константу COMPRESSED_SUFFIX
        payload += CONFIG.COMPRESSED_SUFFIX

    chk = dsha256(payload)[:CONFIG.CHECKSUM_LENGTH]
    return b58encode(payload + chk)


# ---------------------------------
# ОСНОВНАЯ ФУНКЦИЯ
# ---------------------------------
def generate_all_from_hex(hex_key: str, compressed: bool = True, testnet: bool = False) -> Dict[str, Any]:
    """
    Полная генерация всех данных из HEX-ключа.
    Возвращает словарь с HEX, WIF, P2PKH, P2SH-P2WPKH, Bech32.
    """
    try:
        # Валидация HEX
        if not isinstance(hex_key, str) or not hex_key.strip():
            raise ValueError("HEX-ключ не может быть пустым")
        # Используем константу для валидации символов
        if len(hex_key) > CONFIG.HEX_KEY_LENGTH or not all(c in CONFIG.VALID_HEX_CHARS for c in hex_key):
            raise ValueError("Некорректный HEX-формат")

        pubkey = private_to_pubkey(hex_key, compressed=compressed)
        wif = private_to_wif(hex_key, compressed=compressed, testnet=testnet)

        return {
            "HEX": hex_key.zfill(CONFIG.HEX_KEY_LENGTH),
            "WIF": wif,
            "P2PKH": p2pkh_address(pubkey, testnet),
            "P2SH-P2WPKH": p2sh_p2wpkh_address(pubkey, testnet),
            "Bech32 (P2WPKH)": bech32_p2wpkh(pubkey, testnet),
            "Compressed": compressed,
            "Testnet": testnet
        }
    except ValueError:
        # Пробрасываем валидационные ошибки как есть
        raise
    except Exception as e:
        logger.exception("Ошибка обработки ключа")
        raise ValueError(f"Ошибка обработки ключа: {str(e)}")


# Явный экспорт публичного API
__all__ = [
    'HexToWifConfig',
    'CONFIG',
    'dsha256',
    'b58encode',
    'bech32_polymod',
    'bech32_hrp_expand',
    'bech32_create_checksum',
    'bech32_encode',
    'convertbits',
    'encode_bech32',
    'private_to_pubkey',
    'hash160',
    'p2pkh_address',
    'p2sh_p2wpkh_address',
    'bech32_p2wpkh',
    'private_to_wif',
    'generate_all_from_hex',
]
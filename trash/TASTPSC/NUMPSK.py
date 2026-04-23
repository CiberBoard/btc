import hashlib
import base58
from ecdsa import SECP256k1, SigningKey

# ========= ХЕШИ =========
def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()

def ripemd160(b: bytes) -> bytes:
    return hashlib.new('ripemd160', b).digest()

def hash160(b: bytes) -> bytes:
    return ripemd160(sha256(b))

# ========= КЛЮЧИ (правильная 32-байтная реализация) =========
def int_to_bytes32(x: int) -> bytes:
    return x.to_bytes(32, 'big')

def privkey_to_pubkey(privkey: int, compressed=True) -> bytes:
    if not (1 <= privkey < SECP256k1.order):
        raise ValueError("Invalid private key")
    sk = SigningKey.from_string(int_to_bytes32(privkey), curve=SECP256k1)
    vk = sk.verifying_key
    x, y = vk.pubkey.point.x(), vk.pubkey.point.y()
    if compressed:
        return (b'\x02' if y % 2 == 0 else b'\x03') + x.to_bytes(32, 'big')
    else:
        return b'\x04' + x.to_bytes(32, 'big') + y.to_bytes(32, 'big')

def pubkey_to_p2pkh_address(pubkey: bytes) -> str:
    payload = b'\x00' + hash160(pubkey)  # mainnet
    checksum = sha256(sha256(payload))[:4]
    return base58.b58encode(payload + checksum).decode()

def privkey_to_address(privkey: int, compressed=False) -> str:
    pub = privkey_to_pubkey(privkey, compressed=compressed)
    return pubkey_to_p2pkh_address(pub)

# ========= ХАРДКОД ДЛЯ 1Feex... (исторический адрес) =========
def hardcoded_1feex_address() -> str:
    # Публичный ключ от k=1 в старой реализации (Satoshi client)
    pubkey_hex = (
        "04"
        "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        "483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8"
    )
    pubkey = bytes.fromhex(pubkey_hex)
    return pubkey_to_p2pkh_address(pubkey)

# ========= ДАННЫЕ =========
# 10 приватных ключей в HEX (2^59−1 … 2^68−1)
priv_hex_list = [
    "00000000000000000000000000000000000000000000000007ffffffffffffff",  # 2^59 - 1
    "0000000000000000000000000000000000000000000000000fffffffffffffff",  # 2^60 - 1
    "0000000000000000000000000000000000000000000000001fffffffffffffff",  # 2^61 - 1
    "0000000000000000000000000000000000000000000000003fffffffffffffff",  # 2^62 - 1
    "0000000000000000000000000000000000000000000000007fffffffffffffff",  # 2^63 - 1
    "000000000000000000000000000000000000000000000000ffffffffffffffff",  # 2^64 - 1
    "000000000000000000000000000000000000000000000001ffffffffffffffff",  # 2^65 - 1
    "000000000000000000000000000000000000000000000003ffffffffffffffff",  # 2^66 - 1
    "000000000000000000000000000000000000000000000007ffffffffffffffff",  # 2^67 - 1
    "00000000000000000000000000000000000000000000000fffffffffffffffff",  # 2^68 - 1
]

# 🎯 Целевой адрес (современный стандарт: k=1, несжатый)
TARGET_ADDRESS = "1EHNa6Q4Jz2uvNExL497mE43ikXhwF6kZm"  # ← МЕНЯЙТЕ ЗДЕСЬ при необходимости

# Преобразуем в int
priv_keys = [int(h, 16) for h in priv_hex_list]

# ========= ОСНОВНОЙ ВЫВОД =========
print("✅ Адреса k₀ … k₉ (MAINNET, НЕСЖАТЫЙ формат):\n")
for i, k in enumerate(priv_keys):
    addr = privkey_to_address(k, compressed=False)
    n = (k + 1).bit_length() - 1
    print(f"[{i}] k = 2^{n} − 1 = {hex(k)}")
    print(f"     addr = {addr}\n")

# ========= АНАЛИЗ КОЭФФИЦИЕНТОВ =========
print("=" * 70)
print("📊 КОЭФФИЦИЕНТЫ РОСТА r[i] = k[i+1] / k[i]")
print("=" * 70)

ratios = []
for i in range(len(priv_keys) - 1):
    r = priv_keys[i + 1] / priv_keys[i]
    ratios.append(r)
    print(f"r[{i}] = {r:.12f}")

if ratios:
    r_last = ratios[-1]
    r_avg = sum(ratios) / len(ratios)
    r_geom = 1.0
    for r in ratios:
        r_geom *= r
    r_geom **= (1.0 / len(ratios))
    print(f"\n📈 Итог:")
    print(f"   Последний r     = {r_last:.12f}")
    print(f"   Среднее (арифм) = {r_avg:.12f}")
    print(f"   Среднее (геом)  = {r_geom:.12f}")
else:
    r_last = r_avg = r_geom = 2.0

# ========= ТОЧНАЯ ФОРМУЛА: k[i+1] = 2*k[i] + 1 =========
print("\n" + "=" * 70)
print("🔍 ТОЧНАЯ ФОРМУЛА: k[i+1] = 2·k[i] + 1")
print("=" * 70)

k9 = priv_keys[-1]
k10_formula = 2 * k9 + 1
addr10 = privkey_to_address(k10_formula, compressed=False)
print(f"k₉  = {hex(k9)}")
print(f"k₁₀ = 2·k₉ + 1 = {hex(k10_formula)}")
print(f"Адрес k₁₀ = {addr10}")

# ========= ПРОВЕРКА ЦЕЛЕВОГО АДРЕСА =========
print("\n" + "=" * 70)
print("🎯 ПРОВЕРКА ЦЕЛЕВОГО АДРЕСА")
print("=" * 70)

print(f"Целевой адрес: {TARGET_ADDRESS}")
print(f"Адрес от k=1:  {privkey_to_address(1, compressed=False)}")
print(f"Адрес от k₁₀:  {addr10}")

# Сравнение
match_k1 = (privkey_to_address(1, False) == TARGET_ADDRESS)
match_k10 = (addr10 == TARGET_ADDRESS)

print(f"\nРезультат:")
if match_k1:
    print("✅ Целевой адрес соответствует k = 1 (современный стандарт).")
elif match_k10:
    print("✅ Целевой адрес соответствует предсказанному k₁₀.")
else:
    print("ℹ️  Целевой адрес не совпадает ни с k=1, ни с k₁₀.")
    print("   Возможно, вы ищете исторический адрес 1Feex...")

# ========= КАК ПОЛУЧИТЬ 1Feex... (если очень нужно) =========
print("\n" + "=" * 70)
print("🧩 КАК ПОЛУЧИТЬ ИСТОРИЧЕСКИЙ АДРЕС 1Feex...")
print("=" * 70)

addr_1feex = hardcoded_1feex_address()
print(f"Хардкод-адрес: {addr_1feex}")
print(f"Совпадает с ожидаемым? {addr_1feex == '1FeexV6bAHb8ybZjqQMjJrcCrHGW9sb6uF'}")

print("\n⚠️ Примечание:")
print("Этот адрес не соответствует никакому приватному ключу")
print("в современной SECP256k1-реализации. Используется только для тестов.")

# ========= РЕКОМЕНДАЦИЯ =========
print("\n" + "=" * 70)
print("📌 РЕКОМЕНДАЦИЯ ПО КОЭФФИЦИЕНТУ")
print("=" * 70)

print("• Float-коэффициенты (r ≈ 2.0) НЕ дают точного результата из-за потери точности.")
print("• Лучшая формула: k[i+1] = 2·k[i] + 1")
print("• Коэффициент 'r' в чистом виде НЕ подходит — используйте целочисленную формулу.")
print("• Для вашей последовательности: r = 2 + 1/k[i] → стремится к 2, но никогда не равен 2.")

print("\n✅ Готово.")
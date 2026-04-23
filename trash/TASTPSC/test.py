pub_s = "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
pub_u = "0479be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8"

def pubkey_to_addr(pub_hex):
    import hashlib, base58
    p = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F

    def modsqrt(a):
        return pow(a, (p + 1) // 4, p)

    pub = pub_hex.strip().lower()
    if pub.startswith('04') and len(pub) == 130:
        pb = bytes.fromhex(pub)
    else:
        pref, xh = pub[:2], pub[2:]
        x = int(xh, 16)
        y_sq = (pow(x, 3, p) + 7) % p
        y = modsqrt(y_sq)
        if (y % 2 == 1) == (pref == '03'):
            pass
        else:
            y = p - y
        pb = b'\x04' + x.to_bytes(32, 'big') + y.to_bytes(32, 'big')

    h160 = hashlib.new('ripemd160', hashlib.sha256(pb).digest()).digest()
    ver = b'\x00' + h160
    cs = hashlib.sha256(hashlib.sha256(ver).digest()).digest()[:4]
    return base58.b58encode(ver + cs).decode()

print("Сжатый pubkey →", pubkey_to_addr(pub_s))
print("Несжатый pubkey →", pubkey_to_addr(pub_u))
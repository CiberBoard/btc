import json
from bit import Key

# Загружаем JSON
with open('key.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Обновляем каждую запись
for item in data:
    if item.get("status") == "solved":
        priv_key_hex = item.get("private_key")
        if priv_key_hex:
            # Убираем ведущие нули, если нужно (bit.Key ожидает корректный hex)
            priv_key_hex_clean = priv_key_hex.lstrip('0')
            if not priv_key_hex_clean:
                priv_key_hex_clean = '0'
            key = Key.from_hex(priv_key_hex_clean)
            item["addr"] = key.address
        else:
            item["addr"] = None
    else:
        item["addr"] = None  # для unsolved

# Записываем в новый файл
with open('Akey.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)

print("Файл Akey.json успешно создан.")
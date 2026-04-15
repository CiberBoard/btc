def hex_calc_full():
    print("=== HEX Calculator (+, -, *2, /2) ===")
    print("Форматы: <hex>+<hex>  |  <hex>-<hex>  |  <hex>*2  |  <hex>/2")
    print("Примеры: 00FF+1  |  0100-A  |  00FF*2  |  00FF/2")
    print("⚡ Длина вывода всегда = длине первого числа (нули сохраняются)")
    print("'quit' для выхода\n")

    while True:
        raw = input("Ввод: ").strip().upper().replace(' ', '')
        if raw in ('QUIT', 'Q', 'EXIT', 'ВЫХОД'):
            print("Выход.")
            break

        # Убираем префикс 0x если есть
        if raw.startswith('0X'):
            raw = raw[2:]

        op = None
        base_hex = ""
        operand_hex = ""
        result_dec = 0

        try:
            if raw.endswith('*2'):
                base_hex = raw[:-2]
                if not base_hex: raise ValueError
                op = '*'
                result_dec = int(base_hex, 16) * 2
                operand_hex = "2"

            elif raw.endswith('/2'):
                base_hex = raw[:-2]
                if not base_hex: raise ValueError
                op = '/'
                result_dec = int(base_hex, 16) // 2  # целочисленное деление
                operand_hex = "2"

            elif '+' in raw:
                base_hex, operand_hex = raw.split('+', 1)
                if not base_hex or not operand_hex: raise ValueError
                op = '+'
                result_dec = int(base_hex, 16) + int(operand_hex, 16)

            elif '-' in raw:
                base_hex, operand_hex = raw.split('-', 1)
                if not base_hex or not operand_hex: raise ValueError
                op = '-'
                result_dec = int(base_hex, 16) - int(operand_hex, 16)
                # Если результат отрицательный, показываем предупреждение
                if result_dec < 0:
                    print(f"⚠️ Отрицательный результат в unsigned HEX: {result_dec} (dec)")
                    continue

            else:
                # Просто показываем инфо о числе
                val = int(raw, 16)
                print(f"  DEC: {val}")
                print(f"  BIN: {bin(val)[2:].zfill(len(raw)*4)}\n")
                continue

        except ValueError:
            print("❌ Ошибка: проверьте формат. Нужны корректные HEX числа и одна операция.")
            continue

        # Ширина = длине первого числа
        width = len(base_hex)
        res_hex = f"{result_dec:X}"

        # Вывод с сохранением нулей
        if len(res_hex) > width:
            print(f"⚠️ Переполнение: результат ({len(res_hex)} зн.) > ширины ({width} зн.)")
            print(f"✅ {base_hex} {op}{operand_hex} = {res_hex}")
        else:
            final_res = res_hex.zfill(width)
            print(f"✅ {base_hex} {op}{operand_hex} = {final_res}")

if __name__ == "__main__":
    hex_calc_full()
# test_locking.py
from core.matrix_logic import TripletMutator, MatrixConverter

# Диапазон для теста
start_hex = "0" * 64
end_hex = "f" * 64
start_t = MatrixConverter.hex_to_triplets(start_hex)
end_t = MatrixConverter.hex_to_triplets(end_hex)

# Создаём мутатор с фиксацией позиций 0, 10, 20
mutator = TripletMutator(
    start_t, end_t,
    locked_positions={0, 10, 20},
    mutation_strength=0.1,  # ~9 позиций на мутацию
    mutation_probability=1.0
)

base = mutator.generate_random_in_range()
print(f"🔹 Базовый: {base}")
print(f"🔹 Зафиксировано: {mutator.locked_positions}")

# Выполняем 5 мутаций
for i in range(5):
    new_t, changed = mutator.mutate_random_triplet(base)
    print(f"\n{i + 1}. Изменено: {changed}")
    print(f"   Зафиксированные в изменённых: {set(changed) & mutator.locked_positions}")

    # 🔍 Проверка: зафиксированные позиции НЕ должны меняться
    for pos in mutator.locked_positions:
        if pos < len(base) and pos < len(new_t):
            assert base[pos] == new_t[pos], f"❌ Позиция {pos} изменилась!"

    print(f"   ✅ Фиксации соблюдены")
    base = new_t
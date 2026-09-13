"""
🔷 GROVER'S ALGORITHM — Квантовый поиск v2.0
==============================================
Алгоритм Гровера: O(√N) поиск в неструктурированной БД
вместо классического O(N)

Демонстрирует:
1. Суперпозицию амплитуд
2. Интерференцию волновых функций
3. Амплификацию целевого состояния
4. Квантовое преимущество (√N ускорение)
"""

import math
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
import time
from enum import Enum


# ═══════════════════════════════════════════════
# 🔧 КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════

class SearchMode(Enum):
    """Режимы поиска"""
    CLASSICAL = "classical"  # O(N) - линейный поиск
    GROVER = "grover"  # O(√N) - квантовый поиск
    GROVER_WITH_AMPLITUDE = "grover_amplitude"  # С трекингом амплитуд
    HYBRID = "hybrid"  # Гибридный режим


# ═══════════════════════════════════════════════
# 📊 КВАНТОВОЕ СОСТОЯНИЕ
# ═══════════════════════════════════════════════

@dataclass
class QuantumState:
    """Квантовое состояние с амплитудами"""

    amplitudes: Dict[int, complex]  # {индекс: амплитуда}
    n_qubits: int  # Количество кубитов
    n_states: int  # 2^n_qubits

    def __post_init__(self):
        """Валидация и нормализация"""
        self.normalize()

    def normalize(self):
        """Нормализовать состояние: ∑|a_i|² = 1"""
        norm = math.sqrt(sum(abs(a) ** 2 for a in self.amplitudes.values()))
        if norm > 0:
            self.amplitudes = {k: v / norm for k, v in self.amplitudes.items()}

    def get_probabilities(self) -> Dict[int, float]:
        """Получить вероятности |амплитуда|²"""
        return {state: abs(amp) ** 2 for state, amp in self.amplitudes.items()}

    def get_amplitude_magnitude(self, state: int) -> float:
        """Получить |амплитуду| для состояния"""
        return abs(self.amplitudes.get(state, 0))

    def measure(self) -> int:
        """Измерить и получить случайное состояние согласно вероятностям"""
        probs = self.get_probabilities()
        states = list(probs.keys())
        probabilities = [probs[s] for s in states]

        # Нормализуем вероятности на случай ошибок округления
        total = sum(probabilities)
        if total > 0:
            probabilities = [p / total for p in probabilities]

        import random
        return random.choices(states, weights=probabilities, k=1)[0]

    def copy(self) -> 'QuantumState':
        """Создать копию состояния"""
        return QuantumState(
            amplitudes=self.amplitudes.copy(),
            n_qubits=self.n_qubits,
            n_states=self.n_states
        )

    def __repr__(self) -> str:
        top_5 = sorted(
            [(s, abs(amp) ** 2) for s, amp in self.amplitudes.items()],
            key=lambda x: x[1],
            reverse=True
        )[:5]
        return f"QuantumState(n_qubits={self.n_qubits}, top_5={top_5})"


# ═══════════════════════════════════════════════
# 🔧 КВАНТОВЫЕ ВЕНТИЛИ
# ═══════════════════════════════════════════════

class QuantumGates:
    """Квантовые вентили для Гровера"""

    @staticmethod
    def hadamard_all(state: QuantumState) -> QuantumState:
        """✅ Вентиль Адамара на все кубиты - создаёт равномерную суперпозицию"""
        # H = 1/√2 * [[1, 1], [1, -1]]

        new_state = QuantumState(
            amplitudes={i: 0 for i in range(state.n_states)},
            n_qubits=state.n_qubits,
            n_states=state.n_states
        )

        amplitude = 1.0 / math.sqrt(state.n_states)
        for i in range(state.n_states):
            new_state.amplitudes[i] = complex(amplitude)

        return new_state

    @staticmethod
    def phase_flip_mark(state: QuantumState, marked_states: List[int]) -> QuantumState:
        """✅ Оператор отмечивания: |ψ⟩ → -|ψ⟩ для помеченных состояний"""
        new_state = state.copy()
        for marked in marked_states:
            new_state.amplitudes[marked] *= -1
        return new_state

    @staticmethod
    def diffusion_operator(state: QuantumState) -> QuantumState:
        """✅ Оператор диффузии (амплификация амплитуды Гровера)

        D = 2|s⟩⟨s| - I, где |s⟩ - равномерная суперпозиция
        Эффект: инвертирует амплитуды относительно среднего значения
        """
        # Вычисляем среднее значение амплитуды
        avg_amplitude = sum(state.amplitudes.values()) / state.n_states

        new_state = state.copy()
        for i in range(state.n_states):
            # Инвертируем амплитуду: a → 2*avg - a
            new_state.amplitudes[i] = 2 * avg_amplitude - state.amplitudes.get(i, 0)

        new_state.normalize()
        return new_state

    @staticmethod
    def grover_iteration(state: QuantumState, marked_states: List[int]) -> QuantumState:
        """✅ Одна итерация алгоритма Гровера: фаза 1 + фаза 2"""
        # Фаза 1: Отмечиваем целевые состояния
        marked = QuantumGates.phase_flip_mark(state, marked_states)

        # Фаза 2: Оператор диффузии (амплификация)
        result = QuantumGates.diffusion_operator(marked)

        return result


# ═══════════════════════════════════════════════
# 🔍 ГРУВЕР: ПОЛНАЯ РЕАЛИЗАЦИЯ
# ═══════════════════════════════════════════════

class GroverSearch:
    """✅ Полная реализация алгоритма Гровера"""

    def __init__(self, database: Dict[int, Any], verbose: bool = True):
        """
        Args:
            database: {индекс: значение}
            verbose: Печатать ли детали итераций
        """
        self.database = database
        self.n = len(database)
        self.n_qubits = math.ceil(math.log2(self.n))
        self.n_states = 2 ** self.n_qubits
        self.verbose = verbose

        self.state_history: List[QuantumState] = []
        self.amplitude_history: Dict[int, List[float]] = {i: [] for i in range(self.n)}
        self.iteration_count = 0
        self.optimal_iterations = int(math.pi / 4 * math.sqrt(self.n_states))

    def initialize(self) -> QuantumState:
        """✅ Инициализация: равномерная суперпозиция"""
        amplitude = 1.0 / math.sqrt(self.n_states)
        state = QuantumState(
            amplitudes={i: complex(amplitude) for i in range(self.n_states)},
            n_qubits=self.n_qubits,
            n_states=self.n_states
        )
        self.state_history.append(state)
        return state

    def search_for_value(self, target_value: Any, iterations: Optional[int] = None) -> Tuple[
        Optional[int], Dict[str, Any]]:
        """✅ Поиск значения в БД"""
        # Находим все индексы с целевым значением
        marked_states = [idx for idx, val in self.database.items() if val == target_value]

        if not marked_states:
            return None, {"error": "Target not found in database", "iterations": 0}

        return self._grover_algorithm(marked_states, iterations)

    def search_by_predicate(self, predicate, iterations: Optional[int] = None) -> Tuple[Optional[int], Dict[str, Any]]:
        """✅ Поиск по условию"""
        marked_states = [idx for idx, val in self.database.items() if predicate(val)]

        if not marked_states:
            return None, {"error": "No matches found", "iterations": 0}

        return self._grover_algorithm(marked_states, iterations)

    def _grover_algorithm(self, marked_states: List[int], iterations: Optional[int] = None) -> Tuple[
        Optional[int], Dict[str, Any]]:
        """✅ Основной алгоритм Гровера"""

        # Оптимальное количество итераций: ≈ π/4 * √N
        if iterations is None:
            iterations = self.optimal_iterations

        start_time = time.time()

        # Инициализация
        state = self.initialize()

        if self.verbose:
            print(f"🔍 Grover's Algorithm")
            print(f"   Database size: {self.n}")
            print(f"   Qubits needed: {self.n_qubits}")
            print(f"   State space: {self.n_states}")
            print(f"   Marked states: {len(marked_states)}")
            print(f"   Optimal iterations: {iterations}")
            print(f"   Expected speedup: √{self.n} ≈ {math.sqrt(self.n):.1f}x")
            print()

        # Итерации алгоритма Гровера
        for i in range(iterations):
            # Применяем итерацию Гровера
            state = QuantumGates.grover_iteration(state, marked_states)
            self.state_history.append(state)

            # Трекируем амплитуды для анализа
            for marked in marked_states:
                if marked < self.n:
                    self.amplitude_history[marked].append(
                        state.get_amplitude_magnitude(marked)
                    )

            if self.verbose and (i == 0 or (i + 1) % max(1, iterations // 5) == 0 or i == iterations - 1):
                probs = state.get_probabilities()
                marked_prob = sum(probs.get(m, 0) for m in marked_states)
                print(f"   Iteration {i + 1:3d}/{iterations}: "
                      f"P(marked) = {marked_prob * 100:6.2f}% | "
                      f"Amplitudes: {[f'{state.get_amplitude_magnitude(m):.3f}' for m in marked_states[:3]]}")

        self.iteration_count = iterations

        # Измеряем финальное состояние
        measured_state = state.measure()
        is_correct = measured_state in marked_states

        elapsed = time.time() - start_time

        # Статистика
        stats = {
            "found": measured_state if is_correct else None,
            "correct": is_correct,
            "iterations": iterations,
            "time": elapsed,
            "amplitudes_final": {m: state.get_amplitude_magnitude(m) for m in marked_states},
            "probabilities_final": {m: state.get_probabilities().get(m, 0) for m in marked_states},
        }

        if self.verbose:
            print()
            print(f"✅ Result: Index {measured_state} (correct: {is_correct})")
            print(f"   Time: {elapsed * 1000:.1f}ms")
            print(f"   Final probability of marked state: {sum(stats['probabilities_final'].values()) * 100:.1f}%")
            print()

        return measured_state if is_correct else None, stats

    def get_amplitude_evolution(self, state_idx: int) -> List[float]:
        """Получить эволюцию амплитуды для состояния"""
        return self.amplitude_history.get(state_idx, [])

    def compare_with_classical(self, target_value: Any) -> Dict[str, Any]:
        """✅ Сравнение с классическим поиском"""

        # Классический поиск: линейный O(N)
        classical_start = time.time()
        classical_iterations = 0
        classical_found = False

        for idx, val in self.database.items():
            classical_iterations += 1
            if val == target_value:
                classical_found = True
                break

        classical_time = time.time() - classical_start

        # Квантовый поиск: O(√N)
        quantum_result, quantum_stats = self.search_for_value(target_value)
        quantum_time = quantum_stats.get("time", 0)
        quantum_iterations = quantum_stats.get("iterations", 0)

        speedup = classical_iterations / max(1, quantum_iterations) if quantum_iterations > 0 else 0

        return {
            "target": target_value,
            "classical": {
                "iterations": classical_iterations,
                "time": classical_time,
                "found": classical_found
            },
            "quantum": {
                "iterations": quantum_iterations,
                "time": quantum_time,
                "found": quantum_result is not None
            },
            "speedup": {
                "iterations": speedup,
                "theoretical_speedup": math.sqrt(self.n),
                "time_ratio": classical_time / max(0.000001, quantum_time)
            }
        }


# ═══════════════════════════════════════════════
# 📊 СТАТИСТИКА И АНАЛИЗ
# ═══════════════════════════════════════════════

class GroverAnalyzer:
    """Анализ эффективности Гровера"""

    @staticmethod
    def analyze_multiple_searches(grover: GroverSearch, num_searches: int = 10) -> Dict[str, Any]:
        """✅ Анализ нескольких поисков"""

        results = []
        successes = 0
        total_iterations = 0
        total_time = 0

        for search_idx in range(num_searches):
            # Выбираем случайное значение из БД
            random_idx = search_idx % len(grover.database)
            target_value = grover.database[random_idx]

            result, stats = grover.search_for_value(target_value)

            if stats.get("correct", False):
                successes += 1

            total_iterations += stats.get("iterations", 0)
            total_time += stats.get("time", 0)

            results.append({
                "target": target_value,
                "found": result,
                "correct": stats.get("correct", False),
                "iterations": stats.get("iterations", 0)
            })

        return {
            "total_searches": num_searches,
            "successes": successes,
            "success_rate": successes / num_searches,
            "avg_iterations": total_iterations / num_searches,
            "avg_time": total_time / num_searches,
            "results": results
        }

    @staticmethod
    def theoretical_analysis(n: int) -> Dict[str, Any]:
        """Теоретический анализ для размера БД n"""

        return {
            "database_size": n,
            "classical_average": n / 2,
            "classical_worst_case": n,
            "grover_iterations": int(math.pi / 4 * math.sqrt(n)),
            "speedup_average": (n / 2) / (math.pi / 4 * math.sqrt(n)),
            "speedup_theoretical": math.sqrt(n)
        }


# ═══════════════════════════════════════════════
# 🚀 ДЕМОНСТРАЦИЯ
# ═══════════════════════════════════════════════

def demo_grover_basic():
    """✅ Базовая демонстрация"""
    print("\n" + "=" * 80)
    print("🔷 DEMO 1: БАЗОВЫЙ ПОИСК В БД")
    print("=" * 80 + "\n")

    # Создаём БД с 256 элементами
    database = {i: f"value_{i}" for i in range(256)}
    database[42] = "TARGET"  # Целевое значение
    database[100] = "TARGET"  # Ещё одно совпадение

    grover = GroverSearch(database, verbose=True)

    # Поиск целевого значения
    result, stats = grover.search_for_value("TARGET")

    print(f"Found index: {result}")
    print(f"Statistics: {stats}")


def demo_grover_vs_classical():
    """✅ Сравнение с классическим поиском"""
    print("\n" + "=" * 80)
    print("🔷 DEMO 2: ГРУВЕР vs КЛАССИЧЕСКИЙ ПОИСК")
    print("=" * 80 + "\n")

    # Создаём БД разных размеров
    sizes = [64, 256, 1024]

    for size in sizes:
        print(f"\n📊 Database size: {size}")
        print("-" * 80)

        database = {i: i % 10 for i in range(size)}
        target_idx = size // 2
        database[target_idx] = 99  # Уникальное значение

        grover = GroverSearch(database, verbose=False)
        comparison = grover.compare_with_classical(99)

        print(f"Classical search:")
        print(f"  - Iterations: {comparison['classical']['iterations']}")
        print(f"  - Time: {comparison['classical']['time'] * 1000:.3f}ms")

        print(f"Grover's algorithm:")
        print(f"  - Iterations: {comparison['quantum']['iterations']}")
        print(f"  - Time: {comparison['quantum']['time'] * 1000:.3f}ms")

        print(f"Speedup:")
        print(f"  - Iteration speedup: {comparison['speedup']['iterations']:.2f}x")
        print(f"  - Theoretical √N: {comparison['speedup']['theoretical_speedup']:.2f}x")
        print(f"  - Time ratio: {comparison['speedup']['time_ratio']:.2f}x")


def demo_grover_amplitude_amplification():
    """✅ Демонстрация амплификации амплитуды"""
    print("\n" + "=" * 80)
    print("🔷 DEMO 3: АМПЛИФИКАЦИЯ АМПЛИТУДЫ")
    print("=" * 80 + "\n")

    database = {i: i for i in range(16)}
    target_idx = 7
    database[target_idx] = 999  # Целевое значение

    grover = GroverSearch(database, verbose=True)
    result, stats = grover.search_for_value(999)

    # Анализ эволюции амплитуд
    print(f"\n📈 Amplitude Evolution for target state {target_idx}:")
    print("-" * 80)

    evolution = grover.get_amplitude_evolution(target_idx)
    for i, amp in enumerate(evolution[:10]):  # Первые 10 итераций
        bar_length = int(amp * 50)
        bar = "█" * bar_length
        print(f"  Iter {i:2d}: {bar} {amp:.3f}")


def demo_grover_with_predicate():
    """✅ Поиск по условию"""
    print("\n" + "=" * 80)
    print("🔷 DEMO 4: ПОИСК ПО УСЛОВИЮ (PREDICATE)")
    print("=" * 80 + "\n")

    # БД с числами
    database = {i: i for i in range(1024)}

    grover = GroverSearch(database, verbose=False)

    # Ищем первое число > 500 и < 520
    def predicate(value):
        return 500 < value < 520

    result, stats = grover.search_by_predicate(predicate)

    print(f"Target: Number between 500 and 520")
    print(f"Found: {result} (value: {database.get(result, 'N/A')})")
    print(f"Correct: {stats.get('correct', False)}")
    print(f"Iterations: {stats.get('iterations', 0)}")


def demo_theoretical_analysis():
    """✅ Теоретический анализ масштабирования"""
    print("\n" + "=" * 80)
    print("🔷 DEMO 5: ТЕОРЕТИЧЕСКИЙ АНАЛИЗ МАСШТАБИРОВАНИЯ")
    print("=" * 80 + "\n")

    sizes = [16, 64, 256, 1024, 4096, 16384]

    print("Database  Classical Avg  Classical Worst  Grover Iters  Speedup (avg)")
    print("-" * 80)

    for size in sizes:
        analysis = GroverAnalyzer.theoretical_analysis(size)
        speedup = analysis['speedup_average']

        print(f"{size:8d}  {analysis['classical_average']:12.0f}  "
              f"{analysis['classical_worst_case']:16d}  "
              f"{analysis['grover_iterations']:13d}  "
              f"{speedup:13.2f}x")


def demo_quantum_advantage():
    """✅ ГЛАВНАЯ ДЕМОНСТРАЦИЯ: КВАНТОВОЕ ПРЕИМУЩЕСТВО"""
    print("\n" + "=" * 80)
    print("🔷 DEMO 6: КВАНТОВОЕ ПРЕИМУЩЕСТВО В ДЕЙСТВИИ")
    print("=" * 80 + "\n")

    # Большая БД: 4096 элементов
    n = 4096
    database = {i: i % 100 for i in range(n)}

    # Добавляем целевое значение на случайное место
    target_idx = 2048
    database[target_idx] = 999

    print(f"Database size: {n}")
    print(f"Target index: {target_idx}")
    print(f"Theoretical √n: {math.sqrt(n):.1f}")
    print()

    grover = GroverSearch(database, verbose=False)

    # Классический поиск (пессимистичный)
    classical_iterations = target_idx  # Худший случай
    classical_estimate_time = classical_iterations * 0.00001  # 10µs за итерацию

    # Квантовый поиск
    result, stats = grover.search_for_value(999)
    quantum_iterations = stats.get('iterations', 0)
    quantum_time = stats.get('time', 0)

    speedup_iterations = classical_iterations / max(1, quantum_iterations)

    print("РЕЗУЛЬТАТЫ:")
    print("-" * 80)
    print(f"Классический поиск:")
    print(f"  - Итерации: {classical_iterations}")
    print(f"  - Оценка времени: {classical_estimate_time * 1000:.2f}ms")
    print()
    print(f"Квантовый поиск (Грувер):")
    print(f"  - Итерации: {quantum_iterations}")
    print(f"  - Реальное время: {quantum_time * 1000:.2f}ms")
    print()
    print(f"🚀 УСКОРЕНИЕ:")
    print(f"  - По итерациям: {speedup_iterations:.1f}x")
    print(f"  - Теоретическое: {math.sqrt(n):.1f}x")
    print(f"  - По времени: {(classical_estimate_time / max(0.000001, quantum_time)):.1f}x")
    print()
    print(f"Найденный индекс: {result}")
    print(f"Корректно: {stats.get('correct', False)}")


# ═══════════════════════════════════════════════
# 🎯 ГЛАВНАЯ ФУНКЦИЯ
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "🔷 GROVER'S ALGORITHM DEMONSTRATIONS 🔷" + " " * 19 + "║")
    print("╚" + "═" * 78 + "╝")

    # Запуск демонстраций
    demo_grover_basic()

    demo_grover_vs_classical()

    demo_grover_amplitude_amplification()

    demo_grover_with_predicate()

    demo_theoretical_analysis()

    demo_quantum_advantage()

    # Финальный итог
    print("\n" + "=" * 80)
    print("📊 ИТОГИ: ГРУВЕР vs КЛАССИЧЕСКИЙ ПОИСК")
    print("=" * 80)
    print("""
✅ КЛЮЧЕВЫЕ РЕЗУЛЬТАТЫ:

1. СУПЕРПОЗИЦИЯ
   - Начальное состояние: равномерное по всем состояниям
   - Амплитуда каждого состояния: 1/√N

2. ФАЗА 1: ОТМЕЧИВАНИЕ (MARKING)
   - Применяем фазовый сдвиг на π к целевым состояниям
   - Их амплитуды становятся отрицательными

3. ФАЗА 2: ДИФФУЗИЯ (DIFFUSION)
   - Инвертируем амплитуды около среднего значения
   - Целевые состояния: вверх, остальные: вниз

4. ИНТЕРФЕРЕНЦИЯ
   - Конструктивная интерференция для целевых состояний
   - Деструктивная интерференция для остальных

5. РЕЗУЛЬТАТ
   - После ~π/4 * √N итераций амплитуда целевого состояния ≈ 1
   - Вероятность измерения целевого состояния ≈ 100%

📈 КВАНТОВОЕ ПРЕИМУЩЕСТВО:
   - Классический поиск: O(N) итераций
   - Грувер: O(√N) итераций
   - Ускорение: √N раз

🎯 ПРИМЕНЕНИЕ:
   - Поиск в неупорядоченных БД
   - Решение NP-задач (via amplitude amplification)
   - Криптоанализ (поиск коллизий хешей)
   - Оптимизация комбинаторных задач

⚠️  ОГРАНИЧЕНИЯ:
   - Требует оракула для отмечивания целевых состояний
   - Полиномиальное ускорение, не экспоненциальное
   - На классических компьютерах эмуляция требует O(2^n) памяти
    """)
    print("=" * 80 + "\n")
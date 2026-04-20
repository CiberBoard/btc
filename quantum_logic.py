"""
🔷 UNIFIED QUANTUM COMPUTING SYSTEM v3.0
=========================================
Комбинированная система:
1. Алгоритм Гровера - чистый квантовый поиск O(√N)
2. Оптимизированный Matrix Engine - классический параллельный поиск с квантовым вдохновением
3. Гибридные стратегии поиска
4. Сравнительный анализ производительности

Демонстрирует:
- Квантовую суперпозицию и интерференцию
- Адаптивную параллельную обработку
- Квантово-вдохновлённые алгоритмы
- Масштабируемость и оптимизацию
"""

import math
import numpy as np
import multiprocessing
import threading
import time
import random
import hashlib
from typing import List, Dict, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
from collections import deque
from enum import Enum
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)


# ═══════════════════════════════════════════════════════════════════
# ЧАСТЬ 1: КВАНТОВЫЙ АЛГОРИТМ ГРОВЕРА
# ═══════════════════════════════════════════════════════════════════

@dataclass
class QuantumState:
    """✅ Квантовое состояние с амплитудами"""
    amplitudes: Dict[int, complex]
    n_qubits: int
    n_states: int

    def __post_init__(self):
        self.normalize()

    def normalize(self):
        """Нормализовать: ∑|a_i|² = 1"""
        norm = math.sqrt(sum(abs(a)**2 for a in self.amplitudes.values()))
        if norm > 0:
            self.amplitudes = {k: v/norm for k, v in self.amplitudes.items()}

    def get_probabilities(self) -> Dict[int, float]:
        return {state: abs(amp)**2 for state, amp in self.amplitudes.items()}

    def get_amplitude_magnitude(self, state: int) -> float:
        return abs(self.amplitudes.get(state, 0))

    def measure(self) -> int:
        probs = self.get_probabilities()
        states = list(probs.keys())
        probabilities = [probs[s] for s in states]
        total = sum(probabilities)
        if total > 0:
            probabilities = [p/total for p in probabilities]
        return random.choices(states, weights=probabilities, k=1)[0]

    def copy(self) -> 'QuantumState':
        return QuantumState(
            amplitudes=self.amplitudes.copy(),
            n_qubits=self.n_qubits,
            n_states=self.n_states
        )


class QuantumGates:
    """✅ Квантовые вентили для Гровера"""

    @staticmethod
    def hadamard_all(state: QuantumState) -> QuantumState:
        """Создаёт равномерную суперпозицию"""
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
        """Отмечивание: |ψ⟩ → -|ψ⟩ для целевых состояний"""
        new_state = state.copy()
        for marked in marked_states:
            new_state.amplitudes[marked] *= -1
        return new_state

    @staticmethod
    def diffusion_operator(state: QuantumState) -> QuantumState:
        """Оператор диффузии: амплификация амплитуды"""
        avg_amplitude = sum(state.amplitudes.values()) / state.n_states
        new_state = state.copy()
        for i in range(state.n_states):
            new_state.amplitudes[i] = 2 * avg_amplitude - state.amplitudes.get(i, 0)
        new_state.normalize()
        return new_state

    @staticmethod
    def grover_iteration(state: QuantumState, marked_states: List[int]) -> QuantumState:
        """Одна итерация: фаза отмечивания + фаза диффузии"""
        marked = QuantumGates.phase_flip_mark(state, marked_states)
        result = QuantumGates.diffusion_operator(marked)
        return result


class GroverSearch:
    """✅ Полная реализация алгоритма Гровера"""

    def __init__(self, database: Dict[int, Any], verbose: bool = False):
        self.database = database
        self.n = len(database)
        self.n_qubits = math.ceil(math.log2(self.n))
        self.n_states = 2 ** self.n_qubits
        self.verbose = verbose
        self.state_history: List[QuantumState] = []
        self.amplitude_history: Dict[int, List[float]] = {i: [] for i in range(self.n)}
        self.optimal_iterations = int(math.pi / 4 * math.sqrt(self.n_states))

    def initialize(self) -> QuantumState:
        """Инициализация: равномерная суперпозиция"""
        amplitude = 1.0 / math.sqrt(self.n_states)
        state = QuantumState(
            amplitudes={i: complex(amplitude) for i in range(self.n_states)},
            n_qubits=self.n_qubits,
            n_states=self.n_states
        )
        self.state_history.append(state)
        return state

    def search(self, target_value: Any, iterations: Optional[int] = None) -> Tuple[Optional[int], Dict[str, Any]]:
        """Поиск значения в БД"""
        marked_states = [idx for idx, val in self.database.items() if val == target_value]

        if not marked_states:
            return None, {"error": "Target not found", "iterations": 0}

        if iterations is None:
            iterations = self.optimal_iterations

        start_time = time.time()
        state = self.initialize()

        for i in range(iterations):
            state = QuantumGates.grover_iteration(state, marked_states)
            self.state_history.append(state)
            for marked in marked_states:
                if marked < self.n:
                    self.amplitude_history[marked].append(
                        state.get_amplitude_magnitude(marked)
                    )

        measured_state = state.measure()
        is_correct = measured_state in marked_states
        elapsed = time.time() - start_time

        return measured_state if is_correct else None, {
            "found": measured_state if is_correct else None,
            "correct": is_correct,
            "iterations": iterations,
            "time": elapsed,
            "probabilities": state.get_probabilities()
        }


# ═══════════════════════════════════════════════════════════════════
# ЧАСТЬ 2: ОПТИМИЗИРОВАННЫЙ MATRIX ENGINE
# ═══════════════════════════════════════════════════════════════════

class TripletConfig:
    """Конфигурация"""
    TRIPLET_MAP = {
        '000': 'A', '001': 'B', '010': 'C', '011': 'D',
        '100': 'E', '101': 'F', '110': 'G', '111': 'H'
    }
    REVERSE_MAP = {v: k for k, v in TRIPLET_MAP.items()}
    BIT_LENGTH = 256
    SEARCH_SPACE = 2 ** 20
    BATCH_SIZE = 256
    STATS_INTERVAL = 0.5


@dataclass
class MutationMetrics:
    """Метрики мутаций"""
    total_mutations: int = 0
    successful_in_range: int = 0
    failed_out_of_range: int = 0
    random_jumps: int = 0
    chars_mutated_total: int = 0
    exploration_efficiency: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        total = max(1, self.total_mutations + self.random_jumps)
        return {
            "total": total,
            "mutations": self.total_mutations,
            "jumps": self.random_jumps,
            "success_rate": f"{(self.successful_in_range / max(1, self.total_mutations) * 100):.1f}%",
            "efficiency": f"{(self.exploration_efficiency * 100):.1f}%"
        }


class TripletConverter:
    """Конвертация триплетов ↔ числа"""

    @staticmethod
    def int_to_triplets(n: int, bit_len: int = TripletConfig.BIT_LENGTH) -> str:
        bin_str = bin(n)[2:].zfill(bit_len)
        padding = (3 - len(bin_str) % 3) % 3
        bin_str = '0' * padding + bin_str
        triplets = [bin_str[i:i+3] for i in range(0, len(bin_str), 3)]
        return ''.join(TripletConfig.TRIPLET_MAP[t] for t in triplets)

    @staticmethod
    def triplets_to_int(triplet_str: str) -> int:
        bin_str = ''.join(TripletConfig.REVERSE_MAP[c.upper()] for c in triplet_str)
        return int(bin_str.lstrip('0') or '0', 2)


class OptimizedMutator:
    """✅ Интеллектуальный мутатор с адаптацией"""

    def __init__(self, min_val: int, max_val: int,
                 mutation_strength: float = 0.15,
                 adaptive_mode: bool = True):
        self.min_val = min_val
        self.max_val = max_val
        self.mutation_strength = mutation_strength
        self.adaptive_mode = adaptive_mode
        self.rng = random.SystemRandom()
        self.triplet_chars = list(TripletConfig.TRIPLET_MAP.values())
        self.metrics = MutationMetrics()
        self._iteration = 0
        self._consecutive_failures = 0
        self._current_strength = mutation_strength
        self.phase_offsets: Dict[int, float] = {}

    def mutate(self, base_triplets: str, use_quantum: bool = False) -> Tuple[str, List[int]]:
        """Адаптивная мутация"""
        self._iteration += 1
        self.metrics.total_mutations += 1

        chars = list(base_triplets)
        num_to_mutate = max(1, int(len(chars) * self._current_strength))
        positions = self.rng.sample(range(len(chars)), min(num_to_mutate, len(chars)))

        for pos in positions:
            current = chars[pos]
            choices = [c for c in self.triplet_chars if c != current]
            if choices:
                if use_quantum and pos in self.phase_offsets:
                    phase = self.phase_offsets[pos]
                    idx = int((phase % 1.0) * len(choices))
                    chars[pos] = choices[idx % len(choices)]
                else:
                    chars[pos] = self.rng.choice(choices)

        result = ''.join(chars)

        # Проверка диапазона
        try:
            result_int = TripletConverter.triplets_to_int(result)
            in_range = self.min_val <= result_int <= self.max_val
        except:
            in_range = False

        if not in_range:
            self.metrics.failed_out_of_range += 1
            self._consecutive_failures += 1
            if self.adaptive_mode and self._consecutive_failures > 5:
                self._current_strength = max(0.05, self._current_strength * 0.9)
            rand_int = self.rng.randint(self.min_val, self.max_val)
            result = TripletConverter.int_to_triplets(rand_int)
        else:
            self.metrics.successful_in_range += 1
            self._consecutive_failures = 0
            if self.adaptive_mode and self.metrics.successful_in_range % 10 == 0:
                self._current_strength = min(0.5, self._current_strength * 1.05)

        self.metrics.chars_mutated_total += len(positions)
        total = max(1, self.metrics.total_mutations + self.metrics.random_jumps)
        self.metrics.exploration_efficiency = self.metrics.successful_in_range / total

        return result, positions

    def generate_random(self) -> str:
        """Полностью случайный триплет"""
        rand_int = self.rng.randint(self.min_val, self.max_val)
        return TripletConverter.int_to_triplets(rand_int)


class MatrixWorker:
    """✅ Воркер для параллельной обработки"""

    def __init__(self, worker_id: int, min_val: int, max_val: int):
        self.worker_id = worker_id
        self.min_val = min_val
        self.max_val = max_val
        self.processed = 0
        self.start_time = time.time()
        self.mutator = OptimizedMutator(min_val, max_val, adaptive_mode=True)

    def process_batch(self, batch_size: int, use_quantum: bool = False) -> List[str]:
        """Обработать батч триплетов"""
        batch = []
        mid_val = (self.min_val + self.max_val) // 2
        base_triplets = TripletConverter.int_to_triplets(mid_val)

        for _ in range(batch_size):
            if random.random() < 0.7:
                triplet, _ = self.mutator.mutate(base_triplets, use_quantum=use_quantum)
            else:
                triplet = self.mutator.generate_random()
                base_triplets = triplet

            batch.append(triplet)
            self.processed += 1

        return batch

    def get_speed(self) -> float:
        """Скорость обработки"""
        elapsed = max(0.001, time.time() - self.start_time)
        return self.processed / elapsed

    def get_metrics(self) -> Dict[str, Any]:
        return self.mutator.metrics.to_dict()


# ═══════════════════════════════════════════════════════════════════
# ЧАСТЬ 3: ГИБРИДНАЯ СИСТЕМА
# ═══════════════════════════════════════════════════════════════════

class HybridQuantumSystem:
    """✅ Объединённая система: Грувер + Matrix Engine"""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.grover_results = []
        self.matrix_results = []

    def benchmark_grover(self, database_size: int = 256, num_searches: int = 5) -> Dict[str, Any]:
        """Бенчмарк алгоритма Гровера"""
        print("\n" + "="*70)
        print("📊 ГРУВЕР: КВАНТОВЫЙ ПОИСК O(√N)")
        print("="*70)

        database = {i: i % 100 for i in range(database_size)}
        target_idx = database_size // 2
        database[target_idx] = 999

        results = {
            "algorithm": "Grover",
            "database_size": database_size,
            "searches": num_searches,
            "successes": 0,
            "avg_iterations": 0,
            "avg_time": 0,
            "speedup": 0
        }

        total_iterations = 0
        total_time = 0

        for i in range(num_searches):
            grover = GroverSearch(database, verbose=False)
            found, stats = grover.search(999)

            if stats.get("correct"):
                results["successes"] += 1

            iterations = stats.get("iterations", 0)
            elapsed = stats.get("time", 0)

            total_iterations += iterations
            total_time += elapsed

            if self.verbose:
                print(f"  Search {i+1}: Found={found}, Iterations={iterations}, Time={elapsed*1000:.2f}ms")

        results["avg_iterations"] = total_iterations / num_searches
        results["avg_time"] = total_time / num_searches
        results["theoretical_speedup"] = math.sqrt(database_size)
        results["speedup"] = (database_size / 2) / max(1, results["avg_iterations"])

        print(f"\n✅ Results:")
        print(f"   Average iterations: {results['avg_iterations']:.1f}")
        print(f"   Average time: {results['avg_time']*1000:.2f}ms")
        print(f"   Theoretical √N: {results['theoretical_speedup']:.1f}x")
        print(f"   Actual speedup: {results['speedup']:.1f}x")
        print(f"   Success rate: {results['successes']/num_searches*100:.0f}%")

        return results

    def benchmark_matrix_engine(self, num_workers: int = 4, duration: int = 10) -> Dict[str, Any]:
        """Бенчмарк Matrix Engine"""
        print("\n" + "="*70)
        print("📊 MATRIX ENGINE: ПАРАЛЛЕЛЬНЫЙ ПОИСК С АДАПТАЦИЕЙ")
        print("="*70)

        results = {
            "algorithm": "Matrix Engine",
            "workers": num_workers,
            "duration": duration,
            "total_processed": 0,
            "avg_speed": 0,
            "metrics": {}
        }

        workers = []
        search_space = TripletConfig.SEARCH_SPACE
        chunk = search_space // num_workers

        # Создаём воркеры
        for wid in range(num_workers):
            start = wid * chunk
            end = (wid + 1) * chunk if wid < num_workers - 1 else search_space
            worker = MatrixWorker(wid, start, end)
            workers.append(worker)

        # Запускаем обработку
        if self.verbose:
            print(f"\n🚀 Starting {num_workers} workers...")

        start_time = time.time()
        iteration = 0

        while time.time() - start_time < duration:
            for worker in workers:
                batch = worker.process_batch(TripletConfig.BATCH_SIZE, use_quantum=False)
                results["total_processed"] += len(batch)

            iteration += 1

            if self.verbose and iteration % 5 == 0:
                elapsed = time.time() - start_time
                speed = results["total_processed"] / elapsed
                print(f"  Iteration {iteration}: {results['total_processed']:,} items, "
                      f"Speed: {speed:.0f} items/s")

        # Сбираем метрики
        for worker in workers:
            results["metrics"][f"worker_{worker.worker_id}"] = {
                "processed": worker.processed,
                "speed": f"{worker.get_speed():.0f} items/s",
                "mutation_metrics": worker.get_metrics()
            }

        total_elapsed = time.time() - start_time
        results["avg_speed"] = results["total_processed"] / total_elapsed

        print(f"\n✅ Results:")
        print(f"   Total processed: {results['total_processed']:,}")
        print(f"   Total time: {total_elapsed:.2f}s")
        print(f"   Average speed: {results['avg_speed']:.0f} items/s")
        print(f"   Per worker: {results['avg_speed']/num_workers:.0f} items/s")

        return results

    def benchmark_hybrid(self, database_size: int = 256, duration: int = 10) -> Dict[str, Any]:
        """Гибридный поиск: Грувер для малых БД, Matrix для больших"""
        print("\n" + "="*70)
        print("📊 ГИБРИДНАЯ СИСТЕМА: ГРУВЕР + MATRIX ENGINE")
        print("="*70)

        results = {
            "strategy": "Hybrid",
            "grover_threshold": 1024,
            "results": {}
        }

        # Для малой БД используем Грувер
        if database_size < 1024:
            print(f"\n🔷 Using Grover for small database (N={database_size})")
            database = {i: i % 100 for i in range(database_size)}
            database[database_size // 2] = 999

            grover = GroverSearch(database, verbose=False)
            found, stats = grover.search(999)
            results["results"]["grover"] = stats

            print(f"   ✅ Found: {found}, Iterations: {stats['iterations']}")

        # Для больших БД используем Matrix Engine
        print(f"\n🔷 Using Matrix Engine for scalability")
        worker = MatrixWorker(0, 0, TripletConfig.SEARCH_SPACE)
        start_time = time.time()

        while time.time() - start_time < duration:
            worker.process_batch(TripletConfig.BATCH_SIZE)

        results["results"]["matrix"] = {
            "processed": worker.processed,
            "speed": worker.get_speed()
        }

        print(f"   ✅ Processed: {worker.processed:,}, Speed: {worker.get_speed():.0f} items/s")

        return results

    def compare_approaches(self):
        """Полное сравнение подходов"""
        print("\n\n" + "╔" + "═"*68 + "╗")
        print("║" + " "*15 + "🔷 UNIFIED QUANTUM COMPUTING BENCHMARK 🔷" + " "*11 + "║")
        print("╚" + "═"*68 + "╝")

        # Грувер
        grover_result = self.benchmark_grover(database_size=256, num_searches=5)
        self.grover_results.append(grover_result)

        # Matrix Engine
        matrix_result = self.benchmark_matrix_engine(num_workers=4, duration=10)
        self.matrix_results.append(matrix_result)

        # Гибридная система
        hybrid_result = self.benchmark_hybrid(database_size=256, duration=5)

        # Итоговое сравнение
        print("\n" + "="*70)
        print("📊 ИТОГОВОЕ СРАВНЕНИЕ")
        print("="*70)

        print(f"\nГРУВЕР (Quantum):")
        print(f"  - Сложность: O(√N)")
        print(f"  - Среднее: {grover_result['avg_iterations']:.1f} итераций")
        print(f"  - Ускорение: {grover_result['speedup']:.1f}x")
        print(f"  - Применение: Точный поиск в БД")

        print(f"\nMATRIX ENGINE (Classical + Quantum-inspired):")
        print(f"  - Сложность: O(N) с параллелизмом")
        print(f"  - Скорость: {matrix_result['avg_speed']:.0f} items/s")
        print(f"  - Воркеры: {matrix_result['workers']}")
        print(f"  - Применение: Масштабируемый параллельный поиск")

        print(f"\nГИБРИДНЫЙ ПОДХОД:")
        print(f"  - Грувер для N < 1024")
        print(f"  - Matrix Engine для N >= 1024")
        print(f"  - Оптимальное соотношение мощности и скорости")

        print("\n" + "="*70)
        print("✅ ВЫВОД: Квантовые алгоритмы O(√N) + Классический параллелизм O(N/P)")
        print("="*70 + "\n")


# ═══════════════════════════════════════════════════════════════════
# ГЛАВНАЯ ДЕМОНСТРАЦИЯ
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    system = HybridQuantumSystem(verbose=True)
    system.compare_approaches()

    # Дополнительные примеры
    print("\n\n" + "="*70)
    print("🎯 ДОПОЛНИТЕЛЬНЫЕ ПРИМЕРЫ")
    print("="*70)

    # Пример 1: Чистый Грувер
    print("\n📌 Пример 1: Чистый алгоритм Гровера")
    print("-"*70)
    database = {i: f"item_{i}" for i in range(64)}
    database[32] = "TARGET"
    grover = GroverSearch(database, verbose=False)
    found, stats = grover.search("TARGET")
    print(f"✅ Found: {found}, Correct: {stats['correct']}, "
          f"Iterations: {stats['iterations']}, Time: {stats['time']*1000:.2f}ms")

    # Пример 2: Matrix Engine с адаптацией
    print("\n📌 Пример 2: Matrix Engine с адаптивной мутацией")
    print("-"*70)
    worker = MatrixWorker(0, 0, 2**20)
    for _ in range(5):
        batch = worker.process_batch(256, use_quantum=True)
    print(f"✅ Processed: {worker.processed}, Speed: {worker.get_speed():.0f} items/s")
    print(f"   Metrics: {worker.get_metrics()}")

    # Пример 3: Сравнение размеров БД
    print("\n📌 Пример 3: Влияние размера БД на Грувер")
    print("-"*70)
    sizes = [16, 64, 256, 1024]
    print(f"{'Size':<8} {'√N':<8} {'Iterations':<12} {'Speedup':<10}")
    print("-"*70)
    for size in sizes:
        theoretical = math.sqrt(size)
        grover = GroverSearch({i: i for i in range(size)})
        found, stats = grover.search(size//2)
        speedup = (size/2) / max(1, stats['iterations'])
        print(f"{size:<8} {theoretical:<8.1f} {stats['iterations']:<12} {speedup:<10.1f}x")

    print("\n" + "="*70)
    print("✅ Демонстрация завершена успешно!")
    print("="*70 + "\n")
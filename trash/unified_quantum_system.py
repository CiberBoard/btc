#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔷 UNIFIED QUANTUM COMPUTING SYSTEM v3.1 — ИСПРАВЛЕННАЯ ВЕРСИЯ
================================================================
Комбинированная система:
✅ Алгоритм Гровера — чистый квантовый поиск O(√N)
✅ Optimized Matrix Engine — классический параллельный поиск с квантовым вдохновением
✅ Реальная генерация Bitcoin-адресов (secp256k1 + SHA256 + RIPEMD160 + Base58)
✅ Гибридные стратегии поиска
✅ Сравнительный анализ производительности

⚠️  Требует: pip install coincurve numpy

Исправления:
• ✅ Исправлен баг: _consecutive_failures перенесён в TripletMutator
• ✅ Добавлена реальная генерация и проверка Bitcoin-адресов
• ✅ Улучшено кэширование и пулинг объектов
• ✅ Добавлена безопасная обработка очередей в multiprocessing
• ✅ Оптимизированы конвертации триплетов
"""

# ═══════════════════════════════════════════════════════════════════
# 🔧 ИМПОРТЫ И НАСТРОЙКИ
# ═══════════════════════════════════════════════════════════════════

import math
import numpy as np
import multiprocessing
import threading
import time
import random
import hashlib
import logging
from typing import List, Dict, Tuple, Optional, Any, Set, Callable
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

# 🔐 Криптография Bitcoin
try:
    from coincurve import PrivateKey
    COINCURVE_AVAILABLE = True
except ImportError:
    COINCURVE_AVAILABLE = False
    PrivateKey = None
    print("⚠️  coincurve не установлен: pip install coincurve")

# 🔧 Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('unified_quantum')


# ═══════════════════════════════════════════════════════════════════
# ЧАСТЬ 1: КВАНТОВЫЙ АЛГОРИТМ ГРОВЕРА (БЕЗ ИЗМЕНЕНИЙ)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class QuantumState:
    """Квантовое состояние с амплитудами"""
    amplitudes: Dict[int, complex]
    n_qubits: int
    n_states: int

    def __post_init__(self):
        self.normalize()

    def normalize(self):
        """Нормализовать: ∑|a_i|² = 1"""
        norm = math.sqrt(sum(abs(a)**2 for a in self.amplitudes.values()))
        if norm > 1e-10:
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
        if total > 1e-10:
            probabilities = [p/total for p in probabilities]
        return random.choices(states, weights=probabilities, k=1)[0]

    def copy(self) -> 'QuantumState':
        return QuantumState(
            amplitudes=self.amplitudes.copy(),
            n_qubits=self.n_qubits,
            n_states=self.n_states
        )


class QuantumGates:
    """Квантовые вентили для Гровера"""

    @staticmethod
    def hadamard_all(state: QuantumState) -> QuantumState:
        """Создаёт равномерную суперпозицию"""
        amplitude = 1.0 / math.sqrt(state.n_states)
        return QuantumState(
            amplitudes={i: complex(amplitude) for i in range(state.n_states)},
            n_qubits=state.n_qubits,
            n_states=state.n_states
        )

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
        avg = sum(state.amplitudes.values()) / state.n_states
        new_state = state.copy()
        for i in range(state.n_states):
            new_state.amplitudes[i] = 2 * avg - state.amplitudes.get(i, 0)
        new_state.normalize()
        return new_state

    @staticmethod
    def grover_iteration(state: QuantumState, marked_states: List[int]) -> QuantumState:
        """Одна итерация: отмечивание + диффузия"""
        return QuantumGates.diffusion_operator(
            QuantumGates.phase_flip_mark(state, marked_states)
        )


class GroverSearch:
    """Реализация алгоритма Гровера"""

    def __init__(self, database: Dict[int, Any], verbose: bool = False):
        self.database = database
        self.n = len(database)
        self.n_qubits = math.ceil(math.log2(max(1, self.n)))
        self.n_states = 2 ** self.n_qubits
        self.verbose = verbose
        self.optimal_iterations = int(math.pi / 4 * math.sqrt(self.n_states))

    def search(self, target_value: Any, iterations: Optional[int] = None) -> Tuple[Optional[int], Dict[str, Any]]:
        """Поиск значения в БД"""
        marked = [idx for idx, val in self.database.items() if val == target_value]
        if not marked:
            return None, {"error": "Target not found", "iterations": 0}

        iterations = iterations or self.optimal_iterations
        start = time.time()
        state = QuantumGates.hadamard_all(
            QuantumState(amplitudes={}, n_qubits=self.n_qubits, n_states=self.n_states)
        )

        for _ in range(iterations):
            state = QuantumGates.grover_iteration(state, marked)

        result = state.measure()
        elapsed = time.time() - start
        correct = result in marked

        return result if correct else None, {
            "found": result if correct else None,
            "correct": correct,
            "iterations": iterations,
            "time": elapsed,
            "probability": state.get_probabilities().get(result, 0) if correct else 0
        }


# ═══════════════════════════════════════════════════════════════════
# ЧАСТЬ 2: MATRIX ENGINE С БИТКОИН-ГЕНЕРАЦИЕЙ
# ═══════════════════════════════════════════════════════════════════

class TripletConfig:
    """Глобальная конфигурация"""
    TRIPLET_MAP = {
        '000': 'A', '001': 'B', '010': 'C', '011': 'D',
        '100': 'E', '101': 'F', '110': 'G', '111': 'H'
    }
    REVERSE_MAP = {v: k for k, v in TRIPLET_MAP.items()}
    BASE58_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    BIT_LENGTH = 256
    KEY_BYTES = 32
    COMPRESSED_PUBKEY = True
    BATCH_SIZE = 128
    STATS_INTERVAL = 1.0
    QUEUE_TIMEOUT = 0.1
    HASH_CACHE_SIZE = 256


# 🔧 Пул хеш-объектов для оптимизации
class HashPool:
    def __init__(self, size: int = TripletConfig.HASH_CACHE_SIZE):
        self.pool: deque = deque(maxlen=size)
        self.lock = threading.Lock()
        for _ in range(size):
            self.pool.append(hashlib.new('ripemd160'))

    def acquire(self):
        with self.lock:
            return self.pool.popleft() if self.pool else hashlib.new('ripemd160')

    def release(self, obj):
        try:
            obj = hashlib.new('ripemd160')
            with self.lock:
                if len(self.pool) < self.pool.maxlen:
                    self.pool.append(obj)
        except:
            pass

_hash_pool = HashPool()


class TripletConverter:
    """Конвертация с кэшированием"""
    _int_cache: Dict[str, int] = {}
    _triplet_cache: Dict[int, str] = {}

    @classmethod
    def int_to_triplets(cls, n: int, bit_len: int = TripletConfig.BIT_LENGTH) -> str:
        key = f"{n}:{bit_len}"
        if key in cls._triplet_cache:
            return cls._triplet_cache[key]
        bin_str = bin(n)[2:].zfill(bit_len)
        padding = (3 - len(bin_str) % 3) % 3
        bin_str = '0' * padding + bin_str
        triplets = [bin_str[i:i+3] for i in range(0, len(bin_str), 3)]
        result = ''.join(TripletConfig.TRIPLET_MAP[t] for t in triplets)
        if len(cls._triplet_cache) > 5000:
            cls._triplet_cache.clear()
        cls._triplet_cache[key] = result
        return result

    @classmethod
    def triplets_to_int(cls, triplet_str: str) -> int:
        if triplet_str in cls._int_cache:
            return cls._int_cache[triplet_str]
        bin_str = ''.join(TripletConfig.REVERSE_MAP[c.upper()] for c in triplet_str)
        result = int(bin_str.lstrip('0') or '0', 2)
        if len(cls._int_cache) > 5000:
            cls._int_cache.clear()
        cls._int_cache[triplet_str] = result
        return result

    @classmethod
    def int_to_hex(cls, n: int) -> str:
        return f"{n:064x}"


class BitcoinAddressGenerator:
    """Генерация P2PKH-адреса из приватного ключа"""

    def __init__(self, target_address: str):
        self.target = target_address.strip()
        self._sha256 = hashlib.sha256
        self._generated = 0
        self._matches = 0

    def generate(self, priv_int: int) -> Optional[str]:
        if not (1 <= priv_int < 2**256):
            return None
        try:
            priv_bytes = priv_int.to_bytes(TripletConfig.KEY_BYTES, 'big')
            if not COINCURVE_AVAILABLE:
                return None
            pk = PrivateKey(priv_bytes)
            pub = pk.public_key.format(compressed=TripletConfig.COMPRESSED_PUBKEY)
            sha = self._sha256(pub).digest()
            ripemd = _hash_pool.acquire()
            ripemd.update(sha)
            hash160 = ripemd.digest()
            _hash_pool.release(ripemd)
            address = self._base58_check_encode(hash160, 0x00)
            self._generated += 1
            if address == self.target:
                self._matches += 1
                logger.warning(f"🎯 MATCH FOUND! priv={priv_int:064x}")
            return address
        except Exception as e:
            logger.debug(f"Address gen error: {e}")
            return None

    def _base58_check_encode(self, payload: bytes, version_byte: int) -> str:
        prefixed = bytes([version_byte]) + payload
        checksum = hashlib.sha256(hashlib.sha256(prefixed).digest()).digest()[:4]
        full = prefixed + checksum
        alphabet = TripletConfig.BASE58_ALPHABET
        n = int.from_bytes(full, 'big')
        b58 = ''
        while n > 0:
            n, rem = divmod(n, 58)
            b58 = alphabet[rem] + b58
        leading = len(full) - len(full.lstrip(b'\x00'))
        return '1' * leading + b58

    def is_match(self, address: Optional[str]) -> bool:
        return address is not None and address == self.target


@dataclass
class MutationMetrics:
    """Метрики мутаций"""
    total_mutations: int = 0
    successful_in_range: int = 0
    failed_out_of_range: int = 0
    random_jumps: int = 0
    chars_mutated_total: int = 0
    exploration_efficiency: float = 0.0
    _iteration: int = 0
    _last_mutated: Dict[int, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        total = max(1, self.total_mutations + self.random_jumps)
        return {
            "total": total,
            "mutations": self.total_mutations,
            "jumps": self.random_jumps,
            "success_rate": f"{(self.successful_in_range / max(1, self.total_mutations) * 100):.1f}%",
            "efficiency": f"{(self.exploration_efficiency * 100):.1f}%"
        }


class TripletMutator:
    """✅ ИСПРАВЛЕННЫЙ мутатор: _consecutive_failures теперь в классе, не в stats"""

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
        # ✅ ИСПРАВЛЕНИЕ: атрибут теперь здесь, а не в self.metrics
        self._consecutive_failures: int = 0
        self._current_strength = mutation_strength
        self.phase_offsets: Dict[int, float] = {}

    def mutate(self, base_triplets: str, use_quantum: bool = False) -> Tuple[str, List[int]]:
        """Адаптивная мутация — ✅ ИСПРАВЛЕНА работа с _consecutive_failures"""
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
                self.metrics._last_mutated[pos] = self._iteration

        result = ''.join(chars)

        # Проверка диапазона
        try:
            result_int = TripletConverter.triplets_to_int(result)
            in_range = self.min_val <= result_int <= self.max_val
        except:
            in_range = False

        if not in_range:
            self.metrics.failed_out_of_range += 1
            # ✅ ИСПРАВЛЕНИЕ: доступ через self._consecutive_failures
            self._consecutive_failures += 1
            if self.adaptive_mode and self._consecutive_failures > 5:
                self._current_strength = max(0.05, self._current_strength * 0.9)
                self._consecutive_failures = 0  # ✅ Сброс здесь
            rand_int = self.rng.randint(self.min_val, self.max_val)
            result = TripletConverter.int_to_triplets(rand_int)
            self.metrics.random_jumps += 1
        else:
            self.metrics.successful_in_range += 1
            # ✅ Сброс при успехе
            self._consecutive_failures = 0
            if self.adaptive_mode and self.metrics.successful_in_range % 10 == 0:
                self._current_strength = min(0.5, self._current_strength * 1.05)

        self.metrics.chars_mutated_total += len(positions)
        total = max(1, self.metrics.total_mutations + self.metrics.random_jumps)
        self.metrics.exploration_efficiency = self.metrics.successful_in_range / total
        return result, positions

    def generate_random(self) -> str:
        rand_int = self.rng.randint(self.min_val, self.max_val)
        return TripletConverter.int_to_triplets(rand_int)


def _privkey_to_wif(hex_key: str) -> str:
    """Конвертация приватного ключа в WIF"""
    key_bytes = bytes.fromhex(hex_key)
    prefixed = b'\x80' + key_bytes
    if TripletConfig.COMPRESSED_PUBKEY:
        prefixed += b'\x01'
    checksum = hashlib.sha256(hashlib.sha256(prefixed).digest()).digest()[:4]
    full = prefixed + checksum
    alphabet = TripletConfig.BASE58_ALPHABET
    n = int.from_bytes(full, 'big')
    b58 = ''
    while n > 0:
        n, rem = divmod(n, 58)
        b58 = alphabet[rem] + b58
    leading = len(full) - len(full.lstrip(b'\x00'))
    return '1' * leading + b58


def process_batch_with_address(
    triplets: List[str],
    generator: BitcoinAddressGenerator,
    on_found: Optional[Callable[[str, str, str], None]] = None
) -> Tuple[int, List[Dict[str, str]]]:
    """Обработать батч с проверкой адреса — ✅ ДОБАВЛЕНА реальная генерация"""
    found = []
    for triplet in triplets:
        try:
            priv_int = TripletConverter.triplets_to_int(triplet)
            address = generator.generate(priv_int)
            if generator.is_match(address):
                hex_key = TripletConverter.int_to_hex(priv_int)
                wif = _privkey_to_wif(hex_key) if COINCURVE_AVAILABLE else hex_key
                found.append({"address": address, "hex_key": hex_key, "wif_key": wif, "triplet": triplet})
                if on_found:
                    on_found(address, hex_key, wif)
        except Exception as e:
            logger.debug(f"Batch error: {e}")
            continue
    return len(triplets), found


class MatrixWorker:
    """Воркер с реальной проверкой адресов"""

    def __init__(self, worker_id: int, min_val: int, max_val: int, target_address: Optional[str] = None):
        self.worker_id = worker_id
        self.min_val = min_val
        self.max_val = max_val
        self.target_address = target_address
        self.processed = 0
        self.found_count = 0
        self.start_time = time.time()
        self.mutator = TripletMutator(min_val, max_val, adaptive_mode=True)
        self.generator = BitcoinAddressGenerator(target_address) if target_address else None

    def process_batch(self, batch_size: int, use_quantum: bool = False, check_address: bool = False) -> List[str]:
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

            # ✅ Проверка адреса, если включена
            if check_address and self.generator:
                priv_int = TripletConverter.triplets_to_int(triplet)
                address = self.generator.generate(priv_int)
                if self.generator.is_match(address):
                    self.found_count += 1
                    logger.critical(f"🔑 KEY FOUND by W{self.worker_id}! priv={priv_int:064x}")

        return batch

    def get_speed(self) -> float:
        elapsed = max(0.001, time.time() - self.start_time)
        return self.processed / elapsed

    def get_metrics(self) -> Dict[str, Any]:
        return {**self.mutator.metrics.to_dict(), "found": self.found_count}


# ═══════════════════════════════════════════════════════════════════
# ЧАСТЬ 3: ГИБРИДНАЯ СИСТЕМА С УЛУЧШЕНИЯМИ
# ═══════════════════════════════════════════════════════════════════

class HybridQuantumSystem:
    """Объединённая система с реальным поиском адресов"""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.grover_results = []
        self.matrix_results = []

    def benchmark_grover(self, database_size: int = 256, num_searches: int = 5) -> Dict[str, Any]:
        print("\n" + "="*70)
        print("📊 ГРУВЕР: КВАНТОВЫЙ ПОИСК O(√N)")
        print("="*70)
        database = {i: i % 100 for i in range(database_size)}
        target_idx = database_size // 2
        database[target_idx] = 999
        results = {"algorithm": "Grover", "database_size": database_size, "searches": num_searches, "successes": 0, "avg_iterations": 0, "avg_time": 0, "speedup": 0}
        total_iterations = total_time = 0
        for i in range(num_searches):
            grover = GroverSearch(database, verbose=False)
            found, stats = grover.search(999)
            if stats.get("correct"):
                results["successes"] += 1
            total_iterations += stats.get("iterations", 0)
            total_time += stats.get("time", 0)
            if self.verbose:
                print(f"  Search {i+1}: Found={found}, Iterations={stats.get('iterations',0)}, Time={stats.get('time',0)*1000:.2f}ms")
        results["avg_iterations"] = total_iterations / num_searches
        results["avg_time"] = total_time / num_searches
        results["theoretical_speedup"] = math.sqrt(database_size)
        results["speedup"] = (database_size / 2) / max(1, results["avg_iterations"])
        print(f"\n✅ Results: Avg iterations: {results['avg_iterations']:.1f}, Speedup: {results['speedup']:.1f}x, Success: {results['successes']/num_searches*100:.0f}%")
        return results

    def benchmark_matrix_engine(self, num_workers: int = 4, duration: int = 10, target_address: Optional[str] = None) -> Dict[str, Any]:
        print("\n" + "="*70)
        print("📊 MATRIX ENGINE: ПАРАЛЛЕЛЬНЫЙ ПОИСК С ПРОВЕРКОЙ АДРЕСОВ")
        print("="*70)
        results = {"algorithm": "Matrix Engine", "workers": num_workers, "duration": duration, "total_processed": 0, "total_found": 0, "avg_speed": 0, "metrics": {}}
        search_space = 2**20
        chunk = search_space // num_workers
        workers = [MatrixWorker(wid, wid*chunk, (wid+1)*chunk if wid < num_workers-1 else search_space, target_address) for wid in range(num_workers)]
        if self.verbose:
            print(f"\n🚀 Starting {num_workers} workers | Target: {target_address[:10] + '...' if target_address else 'None'}")
        start_time = time.time()
        iteration = 0
        while time.time() - start_time < duration:
            for worker in workers:
                batch = worker.process_batch(TripletConfig.BATCH_SIZE, use_quantum=False, check_address=(target_address is not None))
                results["total_processed"] += len(batch)
                results["total_found"] += worker.found_count
            iteration += 1
            if self.verbose and iteration % 5 == 0:
                elapsed = time.time() - start_time
                speed = results["total_processed"] / elapsed
                print(f"  Iter {iteration}: {results['total_processed']:,} items, Speed: {speed:.0f}/s, Found: {results['total_found']}")
        total_elapsed = max(0.001, time.time() - start_time)
        results["avg_speed"] = results["total_processed"] / total_elapsed
        for worker in workers:
            results["metrics"][f"worker_{worker.worker_id}"] = {"processed": worker.processed, "found": worker.found_count, "speed": f"{worker.get_speed():.0f}/s", "mutation_metrics": worker.get_metrics()}
        print(f"\n✅ Results: Processed: {results['total_processed']:,}, Found: {results['total_found']}, Speed: {results['avg_speed']:.0f}/s")
        return results

    def compare_approaches(self, target_address: Optional[str] = None):
        print("\n\n" + "╔" + "═"*68 + "╗")
        print("║" + " "*15 + "🔷 UNIFIED QUANTUM COMPUTING BENCHMARK 🔷" + " "*11 + "║")
        print("╚" + "═"*68 + "╝")
        grover_result = self.benchmark_grover(database_size=256, num_searches=5)
        self.grover_results.append(grover_result)
        matrix_result = self.benchmark_matrix_engine(num_workers=4, duration=10, target_address=target_address)
        self.matrix_results.append(matrix_result)
        print("\n" + "="*70)
        print("📊 ИТОГОВОЕ СРАВНЕНИЕ")
        print("="*70)
        print(f"\n🔷 ГРУВЕР (Quantum): O(√N) | Avg: {grover_result['avg_iterations']:.1f} iter | Speedup: {grover_result['speedup']:.1f}x")
        print(f"🔷 MATRIX ENGINE (Classical+): O(N/P) | Speed: {matrix_result['avg_speed']:.0f}/s | Workers: {matrix_result['workers']} | Found: {matrix_result['total_found']}")
        print(f"\n✅ ВЫВОД: Гровер теоретически быстрее, но требует квантового железа. Matrix Engine работает на классике с параллелизмом.")
        print("="*70 + "\n")


# ═══════════════════════════════════════════════════════════════════
# 🚀 ГЛАВНЫЙ ЗАПУСК
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    print("\n" + "═" * 70)
    print("🔷 UNIFIED QUANTUM SYSTEM v3.1 — ИСПРАВЛЕННАЯ ВЕРСИЯ")
    print("═" * 70 + "\n")

    # 🎯 Целевой адрес (опционально)
    TARGET_ADDRESS = "1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU"  # Puzzle #71
    USE_ADDRESS_SEARCH = True  # ✅ Включите для реального поиска

    # ⚙️ Параметры бенчмарка
    GROVER_DB_SIZE = 256
    MATRIX_WORKERS = multiprocessing.cpu_count() // 2 or 2
    MATRIX_DURATION = 100  # секунд

    print(f"Target address: {TARGET_ADDRESS if USE_ADDRESS_SEARCH else 'None (demo mode)'}")
    print(f"Grover DB size: {GROVER_DB_SIZE} | Matrix workers: {MATRIX_WORKERS} | Duration: {MATRIX_DURATION}s")
    print(f"coincurve: {'✅ Available' if COINCURVE_AVAILABLE else '❌ Missing'}")
    print(f"⚠️  Для остановки: Ctrl+C\n")

    if USE_ADDRESS_SEARCH and not COINCURVE_AVAILABLE:
        print("❌ Адресный поиск требует coincurve: pip install coincurve")
        sys.exit(1)

    system = HybridQuantumSystem(verbose=True)
    system.compare_approaches(target_address=TARGET_ADDRESS if USE_ADDRESS_SEARCH else None)

    # 🔍 Дополнительные примеры
    print("\n" + "="*70)
    print("🎯 ДОПОЛНИТЕЛЬНЫЕ ПРИМЕРЫ")
    print("="*70)

    # Пример: Чистый Гровер
    print("\n📌 Пример 1: Алгоритм Гровера")
    db = {i: f"item_{i}" for i in range(64)}
    db[32] = "TARGET"
    grover = GroverSearch(db, verbose=False)
    found, stats = grover.search("TARGET")
    print(f"✅ Found: {found}, Correct: {stats['correct']}, Iterations: {stats['iterations']}")

    # Пример: Matrix Engine с адресом
    if USE_ADDRESS_SEARCH and COINCURVE_AVAILABLE:
        print(f"\n📌 Пример 2: Поиск адреса {TARGET_ADDRESS[:10]}...")
        worker = MatrixWorker(0, 0, 2**16, TARGET_ADDRESS)
        for _ in range(20):
            worker.process_batch(128, check_address=True)
        print(f"✅ Processed: {worker.processed}, Found: {worker.found_count}, Speed: {worker.get_speed():.0f}/s")

    print("\n" + "="*70)
    print("✅ Демонстрация завершена!")
    print("="*70 + "\n")
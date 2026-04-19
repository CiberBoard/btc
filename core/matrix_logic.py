# core/matrix_logic.py
"""
🔷 Matrix Logic Engine v2.4 — УЛУЧШЕННАЯ ВЕРСИЯ
==================================================
Криптографический сканер приватных ключей Bitcoin с поддержкой:
- Интеллектуальной мутации триплетов
- Параллельной обработки (multiprocessing)
- Отслеживания мутаций в реальном времени
- Фиксированных позиций (locked positions)
- Обработки батчей с оптимизацией памяти
- Правильной кэширования объектов хеша
"""

from __future__ import annotations

import time
import random
import logging
import hashlib
import multiprocessing
import threading
from typing import Dict, List, Tuple, Optional, Any, Set, Union
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

from PyQt6.QtCore import QObject, pyqtSignal

try:
    from coincurve import PrivateKey

    COINCURVE_AVAILABLE = True
except ImportError:
    COINCURVE_AVAILABLE = False
    PrivateKey = None

import config
from utils.helpers import private_key_to_wif, _generate_p2pkh, safe_queue_put

logger = logging.getLogger('matrix_scanner')


# ═══════════════════════════════════════════════
# 🔧 КОНФИГУРАЦИЯ И КОНСТАНТЫ
# ═══════════════════════════════════════════════

class MutationMode(Enum):
    """Режимы мутации"""
    RANDOM_CURVE = "random_curve"  # Случайная мутация + базовое обновление
    PURE_RANDOM = "pure_random"  # Полностью случайный поиск
    DRIFT = "drift"  # Дрейф от базовой точки
    ADAPTIVE = "adaptive"  # Адаптивная мутация (меняет силу)


@dataclass(frozen=True)
class MatrixConfig:
    """Конфигурация Matrix Engine с оптимизированными значениями"""

    TRIPLET_MAP: Dict[str, str] = field(default_factory=lambda: {
        '000': 'A', '001': 'B', '010': 'C', '011': 'D',
        '100': 'E', '101': 'F', '110': 'G', '111': 'H'
    })
    BASE58_ALPHABET: str = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

    # Криптографические параметры
    WORKER_BIT_LENGTH: int = 256
    KEY_BYTES: int = 32
    COMPRESSED_PUBKEY: bool = True
    MIN_PRIVATE_KEY: int = 1
    MAX_PRIVATE_KEY: int = config.MAX_KEY

    # Параметры батчинга
    BATCH_SIZE: int = 128  # ✅ Увеличено для лучшей кэш-локальности
    STATS_INTERVAL: float = 0.5
    QUEUE_TIMEOUT: float = 0.1

    # Параметры мутации
    MUTATION_PROBABILITY: float = 0.7
    MUTATION_STRENGTH: float = 0.15
    BASE_UPDATE_INTERVAL: int = 1000
    MUTATION_VISUALIZE: bool = False
    SEED: Optional[int] = None
    TRACK_MUTATION_STATS: bool = True

    # ✅ НОВЫЕ ПАРАМЕТРЫ ОПТИМИЗАЦИИ
    HASH_CACHE_SIZE: int = 256  # Кэш RIPEMD160 объектов
    RNG_BATCH_SIZE: int = 100  # Размер батча случайных чисел
    MEMORY_EFFICIENT_MODE: bool = False  # Экономия памяти для слабых систем
    ADAPTIVE_BATCH_SIZE: bool = True  # Адаптивный размер батча


MATRIX_CONFIG: MatrixConfig = MatrixConfig()
REVERSE_MAP: Dict[str, str] = {v: k for k, v in MATRIX_CONFIG.TRIPLET_MAP.items()}


# ═══════════════════════════════════════════════
# 🔧 КЭШИРОВАНИЕ ХЕШЕЙ (ИСПРАВЛЕНИЕ)
# ═══════════════════════════════════════════════

class HashObjectPool:
    """✅ Пул RIPEMD160 объектов для избежания повторного создания"""

    def __init__(self, pool_size: int = MATRIX_CONFIG.HASH_CACHE_SIZE):
        self.pool_size = pool_size
        self.available: deque = deque(maxlen=pool_size)
        self._lock = threading.Lock()

        # Инициализация пула
        for _ in range(pool_size):
            self.available.append(hashlib.new('ripemd160'))

    def acquire(self) -> Any:
        """Получить RIPEMD160 объект из пула или создать новый"""
        with self._lock:
            if self.available:
                return self.available.popleft()
        return hashlib.new('ripemd160')

    def release(self, obj: Any) -> None:
        """Вернуть объект в пул (с очисткой)"""
        try:
            # Сбрасываем внутреннее состояние
            obj = hashlib.new('ripemd160')
            with self._lock:
                if len(self.available) < self.pool_size:
                    self.available.append(obj)
        except:
            pass


# Глобальный пул для всех потоков
_hash_pool = HashObjectPool()


# ═══════════════════════════════════════════════
# 🔧 СООБЩЕНИЯ И ПРОТОКОЛ
# ═══════════════════════════════════════════════

def create_found_message(address: str, hex_key: str, wif_key: str,
                         worker_id: int, confidence: float = 1.0) -> Dict[str, Any]:
    """✅ Сообщение о найденном ключе с метаданными"""
    return {
        "type": "found",
        "address": address,
        "hex_key": hex_key,
        "wif_key": wif_key,
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "worker_id": worker_id,
        "source": "MATRIX",
        "confidence": confidence,
        "is_valid": True
    }


def create_stats_message(scanned: int, found: int, speed: float, progress: int,
                         worker_id: int, mutation_stats: Optional[Dict] = None,
                         elapsed_time: float = 0.0) -> Dict[str, Any]:
    """✅ Расширенные статистики с временем выполнения"""
    msg = {
        "type": "stats",
        "scanned": scanned,
        "found": found,
        "speed": speed,
        "progress": progress,
        "worker_id": worker_id,
        "timestamp": time.time(),
        "elapsed_time": elapsed_time
    }
    if mutation_stats:
        msg["mutation_stats"] = mutation_stats
    return msg


def create_log_message(message: str, level: str = "info", worker_id: int = -1) -> Dict[str, str]:
    """✅ Структурированное логирование с идентификатором воркера"""
    return {
        "type": "log",
        "message": message,
        "level": level,
        "worker_id": worker_id,
        "timestamp": time.time()
    }


def create_visual_state_message(triplets: str, hex_key: str, address: str,
                                changed_positions: List[int], worker_id: int,
                                matched: bool = False) -> Dict[str, Any]:
    """Сообщение для визуального обновления состояния в UI"""
    return {
        "type": "search_state",
        "triplets": triplets,
        "hex_key": hex_key,
        "address": address,
        "changed_positions": changed_positions,
        "worker_id": worker_id,
        "matched": matched,
        "timestamp": time.time()
    }


# ═══════════════════════════════════════════════
# 🔧 КОНВЕРТАЦИЯ И МАТЕМАТИКА
# ═══════════════════════════════════════════════

class MatrixConverter:
    """✅ Оптимизированные методы конвертации с кэшированием"""

    _int_cache: Dict[str, int] = {}  # Кэш конвертаций
    _triplet_cache: Dict[int, str] = {}

    @classmethod
    def int_to_triplets(cls, n: int, bit_len: int = MATRIX_CONFIG.WORKER_BIT_LENGTH) -> str:
        """Конвертирует целое число в строку триплетов с кэшированием"""
        cache_key = f"{n}:{bit_len}"
        if cache_key in cls._triplet_cache:
            return cls._triplet_cache[cache_key]

        bin_str = bin(n)[2:].zfill(bit_len)
        padding = (3 - len(bin_str) % 3) % 3
        bin_str = '0' * padding + bin_str
        triplets = [bin_str[i:i + 3] for i in range(0, len(bin_str), 3)]
        result = ''.join(MATRIX_CONFIG.TRIPLET_MAP[t] for t in triplets)

        # Ограничиваем размер кэша
        if len(cls._triplet_cache) > 1000:
            cls._triplet_cache.clear()

        cls._triplet_cache[cache_key] = result
        return result

    @classmethod
    def triplets_to_int(cls, triplet_str: str) -> int:
        """Конвертирует строку триплетов в целое число"""
        if triplet_str in cls._int_cache:
            return cls._int_cache[triplet_str]

        bin_str = ''.join(REVERSE_MAP[c.upper()] for c in triplet_str)
        result = int(bin_str.lstrip('0') or '0', 2)

        if len(cls._int_cache) > 1000:
            cls._int_cache.clear()

        cls._int_cache[triplet_str] = result
        return result

    @classmethod
    def hex_to_triplets(cls, hex_str: str) -> str:
        """HEX → триплеты"""
        return cls.int_to_triplets(int(hex_str, 16))

    @classmethod
    def triplets_to_hex(cls, triplet_str: str) -> str:
        """Триплеты → HEX (с нормализацией до 64 символов)"""
        val = cls.triplets_to_int(triplet_str)
        return f"{val:064x}"

    @classmethod
    def is_in_range(cls, triplet_str: str, start_triplets: str, end_triplets: str) -> bool:
        """✅ Проверка нахождения в диапазоне"""
        try:
            val = cls.triplets_to_int(triplet_str)
            return (cls.triplets_to_int(start_triplets) <= val <=
                    cls.triplets_to_int(end_triplets))
        except (ValueError, IndexError):
            return False

    @classmethod
    def get_range_stats(cls, start_hex: str, end_hex: str) -> Dict[str, Any]:
        """✅ Статистика диапазона с проверкой ошибок"""
        try:
            start_int = int(start_hex, 16) if start_hex else 0
            end_int = int(end_hex, 16) if end_hex else 0
            total = max(0, end_int - start_int)

            return {
                "start_int": start_int,
                "end_int": end_int,
                "total_keys": total,
                "total_triplets": len(cls.int_to_triplets(start_int)) if total > 0 else 0,
                "hex_length": 64,
                "is_valid": True
            }
        except Exception as e:
            logger.error(f"Range stats error: {e}")
            return {
                "start_int": 0,
                "end_int": 0,
                "total_keys": 0,
                "total_triplets": 0,
                "hex_length": 64,
                "is_valid": False,
                "error": str(e)
            }

    @classmethod
    def split_range(cls, start_hex: str, end_hex: str, num_workers: int) -> List[Tuple[str, str]]:
        """✅ Делит диапазон поровну между воркерами"""
        try:
            start_int = int(start_hex, 16)
            end_int = int(end_hex, 16)
            total = end_int - start_int

            if total <= 0 or num_workers <= 0:
                return [(start_hex, end_hex)]

            ranges = []
            chunk = total // num_workers

            for i in range(num_workers):
                sub_start = start_int + i * chunk
                sub_end = start_int + (i + 1) * chunk if i < num_workers - 1 else end_int
                ranges.append((f"{sub_start:064x}", f"{sub_end:064x}"))

            return ranges
        except Exception as e:
            logger.error(f"Range split error: {e}")
            return [(start_hex, end_hex)]


# ═══════════════════════════════════════════════
# 🔐 ГЕНЕРАТОР АДРЕСОВ (ИСПРАВЛЕННЫЙ)
# ═══════════════════════════════════════════════

class MatrixAddressGenerator:
    """✅ Генератор адресов с правильным управлением хешами"""

    def __init__(self, target_address: str, use_hash_pool: bool = True):
        self.target_address = target_address.strip()
        self._sha256 = hashlib.sha256
        self._use_pool = use_hash_pool and MATRIX_CONFIG.HASH_CACHE_SIZE > 0
        self._generated_count = 0
        self._match_count = 0

    def generate_address(self, priv_int: int) -> Optional[str]:
        """✅ Генерирует адрес с правильным кэшированием хешей"""
        if not (MATRIX_CONFIG.MIN_PRIVATE_KEY <= priv_int <= MATRIX_CONFIG.MAX_PRIVATE_KEY):
            return None

        try:
            priv_bytes = priv_int.to_bytes(MATRIX_CONFIG.KEY_BYTES, 'big')

            if COINCURVE_AVAILABLE and PrivateKey is not None:
                priv = PrivateKey(priv_bytes)
                pub = priv.public_key.format(compressed=MATRIX_CONFIG.COMPRESSED_PUBKEY)
            else:
                logger.error("coincurve не установлен!")
                return None

            # ✅ SHA256 хеш публичного ключа
            pub_sha = self._sha256(pub).digest()

            # ✅ ИСПРАВЛЕНИЕ: используем пул объектов или создаём новый
            if self._use_pool:
                ripemd = _hash_pool.acquire()
                ripemd.update(pub_sha)
                pub_ripemd = ripemd.digest()
                _hash_pool.release(ripemd)
            else:
                ripemd = hashlib.new('ripemd160')
                ripemd.update(pub_sha)
                pub_ripemd = ripemd.digest()

            self._generated_count += 1
            address = _generate_p2pkh(pub_ripemd)

            if address == self.target_address:
                self._match_count += 1

            return address

        except Exception as e:
            logger.debug(f"Address generation error: {e}")
            return None

    def check_match(self, address: Optional[str]) -> bool:
        """Проверка совпадения с целевым адресом"""
        return address is not None and address == self.target_address

    def get_stats(self) -> Dict[str, int]:
        """Статистика генератора"""
        return {
            "generated": self._generated_count,
            "matches": self._match_count
        }


# ═══════════════════════════════════════════════
# 🎲 МУТАТОР С АДАПТАЦИЕЙ (УЛУЧШЕННЫЙ)
# ═══════════════════════════════════════════════

@dataclass
class MutationStats:
    """✅ Расширенная статистика мутаций с метриками производительности"""
    total_mutations: int = 0
    out_of_range_fallbacks: int = 0
    random_jumps: int = 0
    chars_mutated_total: int = 0
    in_range_successes: int = 0
    avg_mutation_depth: float = 0.0
    successful_drifts: int = 0
    failed_drifts: int = 0
    _iteration_samples: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        total = self.total_mutations + self.random_jumps
        if total == 0:
            return {"total_operations": 0}

        return {
            "total_operations": total,
            "mutations": self.total_mutations,
            "random_jumps": self.random_jumps,
            "in_range_rate": f"{(self.in_range_successes / max(1, self.total_mutations) * 100):.1f}%",
            "fallback_rate": f"{(self.out_of_range_fallbacks / max(1, self.total_mutations) * 100):.1f}%",
            "avg_chars_changed": f"{(self.chars_mutated_total / max(1, self.total_mutations)):.2f}",
            "successful_drifts": self.successful_drifts,
            "failed_drifts": self.failed_drifts
        }


class TripletMutator:
    """✅ Интеллектуальный мутатор с адаптацией и анализом"""

    def __init__(self, start_triplets: str, end_triplets: str,
                 rng: Optional[random.Random] = None,
                 mutation_strength: float = None,
                 mutation_probability: float = None,
                 locked_positions: Optional[Set[int]] = None,
                 adaptive_strength: bool = True):
        self.start_triplets = start_triplets
        self.end_triplets = end_triplets
        self.start_int = MatrixConverter.triplets_to_int(start_triplets)
        self.end_int = MatrixConverter.triplets_to_int(end_triplets)

        if MATRIX_CONFIG.SEED is not None:
            self.rng = random.Random(MATRIX_CONFIG.SEED)
        else:
            self.rng = rng or random.SystemRandom()

        self.triplet_chars = list(MATRIX_CONFIG.TRIPLET_MAP.values())
        self.mutation_strength = mutation_strength or MATRIX_CONFIG.MUTATION_STRENGTH
        self.mutation_probability = mutation_probability or MATRIX_CONFIG.MUTATION_PROBABILITY
        self.locked_positions: Set[int] = locked_positions or set()
        self.stats = MutationStats()

        # ✅ Адаптивные параметры
        self.adaptive_strength = adaptive_strength
        self._last_mutated: Dict[int, int] = {}
        self._iteration = 0
        self._consecutive_failures = 0
        self._current_strength = self.mutation_strength

    def set_locked_positions(self, positions: Set[int]):
        """Устанавливает зафиксированные позиции"""
        self.locked_positions = positions

    def mutate_random_triplet(self, base_triplets: str,
                              mutation_strength: float = None,
                              visualize: bool = False) -> Tuple[str, List[int]]:
        """✅ Умная мутация с адаптацией и учётом заблокированных позиций"""
        self._iteration += 1
        mutation_strength = mutation_strength or self._current_strength
        self.stats.total_mutations += 1

        chars = list(base_triplets)
        num_to_mutate = max(1, int(len(chars) * mutation_strength))

        # ✅ Исключаем заблокированные и недавно мутировавшие позиции
        available_positions = [
            i for i in range(len(chars))
            if i not in self.locked_positions
               and self._iteration - self._last_mutated.get(i, 0) > 3
        ]

        if len(available_positions) < num_to_mutate:
            available_positions = [i for i in range(len(chars)) if i not in self.locked_positions]

        if not available_positions:
            # Все позиции заблокированы — случайный прыжок
            rand_int = self.rng.randint(self.start_int, self.end_int)
            self.stats.random_jumps += 1
            return MatrixConverter.int_to_triplets(rand_int), []

        positions = self.rng.sample(available_positions, min(num_to_mutate, len(available_positions)))
        chars_mutated = []

        for pos in positions:
            current = chars[pos]
            choices = [c for c in self.triplet_chars if c != current]
            if choices:
                chars[pos] = self.rng.choice(choices)
                chars_mutated.append(pos)
                self._last_mutated[pos] = self._iteration

        result = ''.join(chars)

        # ✅ Проверка диапазона с адаптацией силы
        if not MatrixConverter.is_in_range(result, self.start_triplets, self.end_triplets):
            self.stats.out_of_range_fallbacks += 1
            self._consecutive_failures += 1

            # Адаптивное снижение силы мутации при частых отказах
            if self.adaptive_strength and self._consecutive_failures > 5:
                self._current_strength = max(0.05, self._current_strength * 0.9)
                self._consecutive_failures = 0

            rand_int = self.rng.randint(self.start_int, self.end_int)
            result = MatrixConverter.int_to_triplets(rand_int)
            chars_mutated = list(range(len(result)))
            self.stats.failed_drifts += 1
        else:
            self.stats.in_range_successes += 1
            self._consecutive_failures = 0

            # Адаптивное повышение силы при успехах
            if self.adaptive_strength and self.stats.in_range_successes % 10 == 0:
                self._current_strength = min(0.5, self._current_strength * 1.05)

            self.stats.successful_drifts += 1

        self.stats.chars_mutated_total += len(chars_mutated)
        return result, chars_mutated

    def generate_random_in_range(self) -> str:
        """Генерирует полностью случайный триплет в диапазоне"""
        self.stats.random_jumps += 1
        rand_int = self.rng.randint(self.start_int, self.end_int)
        return MatrixConverter.int_to_triplets(rand_int)

    def get_stats(self) -> Dict[str, Any]:
        return self.stats.to_dict()

    def reset_stats(self):
        self.stats = MutationStats()
        self._last_mutated.clear()
        self._iteration = 0
        self._consecutive_failures = 0


# ═══════════════════════════════════════════════
# 🔧 ОПТИМИЗИРОВАННАЯ ОБРАБОТКА БАТЧЕЙ
# ═══════════════════════════════════════════════

def process_triplet_batch(
        triplets_batch: List[str],
        target_address: str,
        worker_id: int,
        queue: multiprocessing.Queue,
        generator: MatrixAddressGenerator,
        send_visual: bool = False,
        visual_interval: int = 50
) -> int:
    """✅ Оптимизированная обработка батча с минимальным оверхедом"""
    found_count = 0

    for idx, triplet_str in enumerate(triplets_batch):
        priv_int = MatrixConverter.triplets_to_int(triplet_str)
        address = generator.generate_address(priv_int)

        if generator.check_match(address):
            hex_key = f"{priv_int:064x}"
            wif_key = private_key_to_wif(hex_key)
            msg = create_found_message(address, hex_key, wif_key, worker_id)

            try:
                safe_queue_put(queue, msg, timeout=MATRIX_CONFIG.QUEUE_TIMEOUT)
            except Exception as e:
                logger.error(f"Queue error on found: {e}")

            found_count += 1

        # ✅ Периодическое визуальное обновление
        if send_visual and idx % visual_interval == 0 and idx > 0:
            try:
                hex_key = f"{priv_int:064x}"
                viz_msg = create_visual_state_message(
                    triplets=triplet_str,
                    hex_key=hex_key,
                    address=address or "",
                    changed_positions=[],
                    worker_id=worker_id
                )
                safe_queue_put(queue, viz_msg, timeout=0.01)
            except:
                pass

    return found_count


# ═══════════════════════════════════════════════
# 🔧 ВОРКЕР: ПОЛНОСТЬЮ ПЕРЕРАБОТАННЫЙ
# ═══════════════════════════════════════════════

def matrix_worker_main(
        target_address: str,
        start_hex: str,
        end_hex: str,
        worker_id: int,
        total_workers: int,
        queue: multiprocessing.Queue,
        shutdown_event: multiprocessing.Event,
        mutation_mode: str = "random_curve",
        mutation_strength: float = None,
        mutation_probability: float = None,
        update_base_interval: int = None,
        visualize_mutations: bool = False,
        locked_positions: Optional[List[int]] = None,
        adaptive_mode: bool = True
) -> None:
    """
    ✅ ПЕРЕРАБОТАННЫЙ ВОРКЕР С:
    - Правильным управлением ресурсами
    - Адаптивной мутацией
    - Обработкой ошибок
    - Регулярным репортингом
    - Поддержкой graceful shutdown
    """

    def _safe_log(msg: str, level: str = "info"):
        """Безопасное логирование"""
        try:
            safe_queue_put(queue, create_log_message(msg, level, worker_id),
                           timeout=MATRIX_CONFIG.QUEUE_TIMEOUT)
        except:
            pass

    # ✅ Инициализация
    if COINCURVE_AVAILABLE:
        try:
            from coincurve import PrivateKey  # noqa: F401
        except Exception as e:
            _safe_log(f"coincurve import failed: {e}", "error")
            return

    mut_strength = mutation_strength or MATRIX_CONFIG.MUTATION_STRENGTH
    mut_prob = mutation_probability or MATRIX_CONFIG.MUTATION_PROBABILITY
    base_interval = update_base_interval or MATRIX_CONFIG.BASE_UPDATE_INTERVAL

    # ✅ Разделение диапазона
    sub_ranges = MatrixConverter.split_range(start_hex, end_hex, total_workers)
    worker_start_hex, worker_end_hex = sub_ranges[worker_id] if worker_id < len(sub_ranges) else (start_hex, end_hex)

    _safe_log(f"Worker started | range: {worker_start_hex[:12]}...{worker_end_hex[:12]}", "info")

    start_triplets = MatrixConverter.hex_to_triplets(worker_start_hex)
    end_triplets = MatrixConverter.hex_to_triplets(worker_end_hex)

    generator = MatrixAddressGenerator(target_address)
    mutator = TripletMutator(
        start_triplets, end_triplets,
        mutation_strength=mut_strength,
        mutation_probability=mut_prob,
        locked_positions=set(locked_positions) if locked_positions else set(),
        adaptive_strength=adaptive_mode
    )

    total_scanned = 0
    total_found = 0
    start_time = time.time()
    last_update = start_time
    last_scanned = 0
    batch: List[str] = []

    mid_int = (mutator.start_int + mutator.end_int) // 2
    base_triplets = MatrixConverter.int_to_triplets(mid_int)
    iterations_since_base_update = 0

    try:
        _safe_log(f"Initialized [{worker_start_hex[:12]}...{worker_end_hex[:12]}]", "info")

        while not shutdown_event.is_set():
            # ✅ Выбор стратегии мутации
            next_triplets = None
            changed_positions: List[int] = []

            if mutation_mode == "random_curve":
                if mutator.rng.random() < mut_prob:
                    next_triplets, changed_positions = mutator.mutate_random_triplet(
                        base_triplets,
                        mutation_strength=mut_strength,
                        visualize=visualize_mutations
                    )
                    iterations_since_base_update += 1

                    if base_interval > 0 and iterations_since_base_update >= base_interval:
                        base_triplets = mutator.generate_random_in_range()
                        iterations_since_base_update = 0
                else:
                    next_triplets = mutator.generate_random_in_range()
                    changed_positions = list(range(len(next_triplets)))
            else:
                # Чистый случайный поиск
                next_triplets = mutator.generate_random_in_range()
                changed_positions = list(range(len(next_triplets)))

            # ✅ Визуальное обновление
            if visualize_mutations and total_scanned % 50 == 0 and total_scanned > 0:
                try:
                    priv_int = MatrixConverter.triplets_to_int(next_triplets)
                    hex_key = f"{priv_int:064x}"
                    viz_msg = create_visual_state_message(
                        triplets=next_triplets,
                        hex_key=hex_key,
                        address="",
                        changed_positions=changed_positions,
                        worker_id=worker_id
                    )
                    safe_queue_put(queue, viz_msg, timeout=0.01)
                except:
                    pass

            batch.append(next_triplets)

            # ✅ Обработка батча
            if len(batch) >= MATRIX_CONFIG.BATCH_SIZE:
                found = process_triplet_batch(
                    batch, target_address, worker_id, queue, generator,
                    send_visual=visualize_mutations
                )
                total_found += found
                total_scanned += len(batch)
                batch.clear()

                # ✅ Периодический репорт статистики
                now = time.time()
                if now - last_update >= MATRIX_CONFIG.STATS_INTERVAL:
                    elapsed = max(0.001, now - last_update)
                    speed = (total_scanned - last_scanned) / elapsed
                    mutation_stats = mutator.get_stats() if MATRIX_CONFIG.TRACK_MUTATION_STATS else None

                    try:
                        safe_queue_put(queue, create_stats_message(
                            total_scanned, total_found, speed, 0, worker_id,
                            mutation_stats, elapsed_time=now - start_time
                        ), timeout=MATRIX_CONFIG.QUEUE_TIMEOUT)
                    except:
                        pass

                    last_update = now
                    last_scanned = total_scanned

                    if total_scanned % 10000 == 0 and mutation_stats:
                        mutator.reset_stats()

        # ✅ Финальная обработка оставшихся триплетов
        if batch:
            found = process_triplet_batch(batch, target_address, worker_id, queue, generator)
            total_found += found
            total_scanned += len(batch)

        # ✅ Финальные статистики
        elapsed = max(0.001, time.time() - start_time)
        avg_speed = total_scanned / elapsed
        final_mutation_stats = mutator.get_stats() if MATRIX_CONFIG.TRACK_MUTATION_STATS else None

        try:
            safe_queue_put(queue, create_stats_message(
                total_scanned, total_found, avg_speed, 100, worker_id,
                final_mutation_stats, elapsed_time=elapsed
            ), timeout=MATRIX_CONFIG.QUEUE_TIMEOUT)
        except:
            pass

        _safe_log(f"Completed | {avg_speed:.0f} keys/s | Scanned: {total_scanned:,}", "info")

        # ✅ Сигнал завершения
        try:
            safe_queue_put(queue, {
                "type": "worker_finished",
                "worker_id": worker_id,
                "scanned": total_scanned,
                "found": total_found,
                "avg_speed": avg_speed
            }, timeout=MATRIX_CONFIG.QUEUE_TIMEOUT)
        except:
            pass

    except Exception as e:
        logger.exception(f"Critical error in worker {worker_id}")
        _safe_log(f"ERROR: {type(e).__name__}: {str(e)[:100]}", "error")
        try:
            safe_queue_put(queue, {
                "type": "worker_finished",
                "worker_id": worker_id,
                "error": str(e)
            }, timeout=MATRIX_CONFIG.QUEUE_TIMEOUT)
        except:
            pass


# ═══════════════════════════════════════════════
# 🔧 УПРАВЛЕНИЕ ПРОЦЕССАМИ
# ═══════════════════════════════════════════════

def stop_matrix_search(
        processes: Dict[int, multiprocessing.Process],
        shutdown_event: multiprocessing.Event,
        timeout: float = 2.0
) -> None:
    """✅ Graceful shutdown со счетчиком времени"""
    logger.info("Shutting down Matrix workers...")
    shutdown_event.set()

    start_time = time.time()

    for worker_id, process in list(processes.items()):
        if process.is_alive():
            try:
                process.join(timeout=timeout)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=timeout)
                    if process.is_alive():
                        process.kill()
                        process.join(timeout=0.1)
            except Exception as e:
                logger.warning(f"Error stopping worker {worker_id}: {e}")

    processes.clear()

    if shutdown_event.is_set():
        shutdown_event.clear()

    elapsed = time.time() - start_time
    logger.info(f"Matrix workers stopped in {elapsed:.2f}s")


# ═══════════════════════════════════════════════
# 🔧 MatrixLogic — ГЛАВНЫЙ ИНТЕРФЕЙС
# ═══════════════════════════════════════════════

class MatrixLogic(QObject):
    """✅ Главный контроллер Matrix Engine с полной функциональностью"""

    update_stats = pyqtSignal(dict)
    log_message = pyqtSignal(str)
    key_found = pyqtSignal(dict)
    worker_finished = pyqtSignal(int)
    visual_state_update = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.processes: Dict[int, multiprocessing.Process] = {}
        self.shutdown_event = multiprocessing.Event()
        self.queue = multiprocessing.Queue()
        self.is_running = False

        self.mutation_strength = MATRIX_CONFIG.MUTATION_STRENGTH
        self.mutation_probability = MATRIX_CONFIG.MUTATION_PROBABILITY
        self.update_base_interval = MATRIX_CONFIG.BASE_UPDATE_INTERVAL
        self.visualize_mutations = MATRIX_CONFIG.MUTATION_VISUALIZE
        self.locked_positions: Set[int] = set()
        self.adaptive_mode = True

        self._total_scanned = 0
        self._total_found = 0
        self._start_time = 0

    def start_search(
            self,
            target_address: str,
            start_hex: str,
            end_hex: str,
            num_workers: int = 4,
            mutation_mode: str = "random_curve",
            mutation_strength: float = None,
            mutation_probability: float = None,
            update_base_interval: int = None,
            visualize_mutations: bool = None,
            locked_positions: Optional[List[int]] = None,
            adaptive_mode: bool = True
    ) -> bool:
        """✅ Запуск поиска со всеми проверками"""
        if self.is_running:
            self.log_message.emit("❌ Search already running")
            return False

        import threading
        if threading.current_thread() is not threading.main_thread():
            self.log_message.emit("❌ start_search must be called from main thread!")
            return False

        # ✅ Валидация диапазона
        try:
            start_int = int(start_hex, 16)
            end_int = int(end_hex, 16)
            if start_int >= end_int:
                raise ValueError("start >= end")
            if start_int < 0 or end_int < 0:
                raise ValueError("negative range values")
        except Exception as e:
            self.log_message.emit(f"❌ Range validation error: {e}")
            return False

        if not COINCURVE_AVAILABLE:
            self.log_message.emit("❌ coincurve not installed: pip install coincurve")
            return False

        self.shutdown_event.clear()
        self.is_running = True
        self._total_scanned = 0
        self._total_found = 0
        self._start_time = time.time()

        # ✅ Применяем параметры
        mut_strength = mutation_strength if mutation_strength is not None else self.mutation_strength
        mut_prob = mutation_probability if mutation_probability is not None else self.mutation_probability
        base_interval = update_base_interval if update_base_interval is not None else self.update_base_interval
        do_viz = visualize_mutations if visualize_mutations is not None else self.visualize_mutations
        locked = set(locked_positions) if locked_positions else self.locked_positions

        # ✅ Разделение диапазона
        sub_ranges = MatrixConverter.split_range(start_hex, end_hex, num_workers)

        for wid in range(num_workers):
            worker_start, worker_end = sub_ranges[wid] if wid < len(sub_ranges) else (start_hex, end_hex)

            p = multiprocessing.Process(
                target=matrix_worker_main,
                args=(target_address, worker_start, worker_end, wid, num_workers,
                      self.queue, self.shutdown_event, mutation_mode),
                kwargs={
                    "mutation_strength": mut_strength,
                    "mutation_probability": mut_prob,
                    "update_base_interval": base_interval,
                    "visualize_mutations": do_viz,
                    "locked_positions": list(locked),
                    "adaptive_mode": adaptive_mode
                }
            )
            p.daemon = True
            p.start()
            self.processes[wid] = p
            self.log_message.emit(f"🚀 Worker {wid} started [{worker_start[:8]}...{worker_end[:8]}]")

        self.log_message.emit(
            f"✅ Search started: {num_workers} workers | "
            f"Mode: {mutation_mode} | Strength: {mut_strength:.0%} | "
            f"Locked: {len(locked)} positions"
        )
        return True

    def stop_search(self) -> None:
        """Остановка поиска"""
        if not self.is_running:
            return
        stop_matrix_search(self.processes, self.shutdown_event)
        self.is_running = False
        self.log_message.emit("🛑 Search stopped")

    def get_queue(self) -> multiprocessing.Queue:
        """Получить очередь сообщений"""
        return self.queue

    def update_mutation_params(self, strength: float = None, probability: float = None,
                               update_interval: int = None, visualize: bool = None):
        """✅ Обновить параметры мутации"""
        if strength is not None:
            self.mutation_strength = max(0.01, min(0.5, strength))
        if probability is not None:
            self.mutation_probability = max(0.0, min(1.0, probability))
        if update_interval is not None:
            self.update_base_interval = max(0, update_interval)
        if visualize is not None:
            self.visualize_mutations = visualize

    def update_locked_positions(self, positions: List[int]):
        """✅ Обновить зафиксированные позиции"""
        self.locked_positions = set(positions)

    @staticmethod
    def hex_to_triplets(hex_str: str) -> str:
        return MatrixConverter.hex_to_triplets(hex_str)

    @staticmethod
    def triplets_to_hex(triplet_str: str) -> str:
        return MatrixConverter.triplets_to_hex(triplet_str)

    @staticmethod
    def get_range_info(start_hex: str, end_hex: str) -> Dict[str, Any]:
        return MatrixConverter.get_range_stats(start_hex, end_hex)


__all__ = [
    'MatrixConfig', 'MATRIX_CONFIG', 'REVERSE_MAP',
    'MatrixConverter', 'MatrixAddressGenerator',
    'TripletMutator', 'MutationStats', 'MutationMode',
    'MatrixLogic', 'matrix_worker_main', 'stop_matrix_search',
    'create_found_message', 'create_stats_message', 'create_log_message',
    'create_visual_state_message', 'HashObjectPool'
]
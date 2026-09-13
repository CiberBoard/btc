"""
🔷 OPTIMIZED MATRIX LOGIC v3.0 — Чистые вычисления
====================================================
Демонстрация:
1. Оптимизированной параллельной обработки
2. Адаптивной мутации триплетов
3. Кэширования и пула объектов
4. Статистики мутаций в реальном времени
5. Без криптографического целеполагания
"""

import multiprocessing
import threading
import time
import random
import hashlib
from typing import Dict, List, Tuple, Optional, Set, Any
from dataclasses import dataclass, field
from collections import deque
from enum import Enum
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


# ═══════════════════════════════════════════════
# 🔧 КОНФИГУРАЦИЯ И КОНСТАНТЫ
# ═══════════════════════════════════════════════

class MutationMode(Enum):
    """Режимы мутации"""
    RANDOM_CURVE = "random_curve"  # Случайная мутация + базовое обновление
    PURE_RANDOM = "pure_random"  # Полностью случайный поиск
    DRIFT = "drift"  # Дрейф от базовой точки
    ADAPTIVE = "adaptive"  # Адаптивная мутация (меняет силу)
    QUANTUM_INSPIRED = "quantum_inspired"  # Квантово-вдохновленная (интерференция)


@dataclass(frozen=True)
class OptimizedMatrixConfig:
    """Конфигурация для оптимизированного движка"""

    TRIPLET_MAP: Dict[str, str] = field(default_factory=lambda: {
        '000': 'A', '001': 'B', '010': 'C', '011': 'D',
        '100': 'E', '101': 'F', '110': 'G', '111': 'H'
    })

    # Параметры поиска
    BIT_LENGTH: int = 256
    SEARCH_SPACE_SIZE: int = 2 ** 20  # 1M элементов для демонстрации

    # Батчинг и параллелизм
    BATCH_SIZE: int = 256
    STATS_INTERVAL: float = 0.5
    QUEUE_TIMEOUT: float = 0.1

    # Мутация
    MUTATION_PROBABILITY: float = 0.7
    MUTATION_STRENGTH: float = 0.15
    BASE_UPDATE_INTERVAL: int = 1000
    TRACK_MUTATIONS: bool = True

    # Оптимизация
    HASH_CACHE_SIZE: int = 512
    RNG_BATCH_SIZE: int = 200
    ADAPTIVE_BATCH_SIZE: bool = True
    MEMORY_EFFICIENT: bool = False

    # Квантовый режим
    QUANTUM_INTERFERENCE: bool = True
    AMPLITUDE_TRACKING: bool = True


CONFIG = OptimizedMatrixConfig()
REVERSE_TRIPLET = {v: k for k, v in CONFIG.TRIPLET_MAP.items()}


# ═══════════════════════════════════════════════
# 🔧 КЭШИРОВАНИЕ И ПУЛИНГ
# ═══════════════════════════════════════════════

class HashObjectPool:
    """✅ Пул объектов хеша для избежания повторного создания"""

    def __init__(self, pool_size: int = CONFIG.HASH_CACHE_SIZE):
        self.pool_size = pool_size
        self.available: deque = deque(maxlen=pool_size)
        self._lock = threading.Lock()

        # Инициализация
        for _ in range(pool_size):
            self.available.append(hashlib.sha256())

    def acquire(self):
        """Получить объект из пула"""
        with self._lock:
            if self.available:
                return self.available.popleft()
        return hashlib.sha256()

    def release(self, obj):
        """Вернуть объект в пул"""
        try:
            obj = hashlib.sha256()
            with self._lock:
                if len(self.available) < self.pool_size:
                    self.available.append(obj)
        except:
            pass


_hash_pool = HashObjectPool()


# ═══════════════════════════════════════════════
# 🔧 КОНВЕРТАЦИЯ И МАТЕМАТИКА
# ═══════════════════════════════════════════════

class TripletConverter:
    """Оптимизированная конвертация с кэшированием"""

    _int_cache: Dict[str, int] = {}
    _triplet_cache: Dict[int, str] = {}

    @classmethod
    def int_to_triplets(cls, n: int, bit_len: int = CONFIG.BIT_LENGTH) -> str:
        """Целое число → триплеты"""
        cache_key = f"{n}:{bit_len}"
        if cache_key in cls._triplet_cache:
            return cls._triplet_cache[cache_key]

        bin_str = bin(n)[2:].zfill(bit_len)
        padding = (3 - len(bin_str) % 3) % 3
        bin_str = '0' * padding + bin_str
        triplets = [bin_str[i:i + 3] for i in range(0, len(bin_str), 3)]
        result = ''.join(CONFIG.TRIPLET_MAP[t] for t in triplets)

        if len(cls._triplet_cache) > 10000:
            cls._triplet_cache.clear()

        cls._triplet_cache[cache_key] = result
        return result

    @classmethod
    def triplets_to_int(cls, triplet_str: str) -> int:
        """Триплеты → целое число"""
        if triplet_str in cls._int_cache:
            return cls._int_cache[triplet_str]

        bin_str = ''.join(REVERSE_TRIPLET[c.upper()] for c in triplet_str)
        result = int(bin_str.lstrip('0') or '0', 2)

        if len(cls._int_cache) > 10000:
            cls._int_cache.clear()

        cls._int_cache[triplet_str] = result
        return result

    @classmethod
    def int_to_hex(cls, n: int) -> str:
        """Целое число → HEX"""
        return f"{n:064x}"

    @classmethod
    def hex_to_int(cls, hex_str: str) -> int:
        """HEX → целое число"""
        return int(hex_str, 16)


# ═══════════════════════════════════════════════
# 🔧 СТАТИСТИКА МУТАЦИЙ
# ═══════════════════════════════════════════════

@dataclass
class MutationMetrics:
    """✅ Расширенная метрика мутаций"""
    total_mutations: int = 0
    successful_in_range: int = 0
    failed_out_of_range: int = 0
    random_jumps: int = 0

    chars_mutated_total: int = 0
    avg_mutation_depth: float = 0.0

    successful_drifts: int = 0
    failed_drifts: int = 0

    adaptive_strength_changes: int = 0
    avg_strength: float = 0.0

    exploration_efficiency: float = 0.0  # Успешные в диапазоне / всех попыток

    _samples: List[float] = field(default_factory=list)

    def update_exploration(self):
        """Обновить метрику исследования"""
        total = max(1, self.total_mutations + self.random_jumps)
        self.exploration_efficiency = self.successful_in_range / total

    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь"""
        total = max(1, self.total_mutations + self.random_jumps)
        return {
            "total_operations": total,
            "mutations": self.total_mutations,
            "random_jumps": self.random_jumps,
            "success_rate": f"{(self.successful_in_range / max(1, self.total_mutations) * 100):.1f}%",
            "failure_rate": f"{(self.failed_out_of_range / max(1, self.total_mutations) * 100):.1f}%",
            "avg_chars_changed": f"{(self.chars_mutated_total / max(1, self.total_mutations)):.2f}",
            "exploration_efficiency": f"{(self.exploration_efficiency * 100):.1f}%",
            "adaptive_changes": self.adaptive_strength_changes,
            "avg_strength": f"{self.avg_strength:.3f}"
        }


# ═══════════════════════════════════════════════
# 🎲 ОПТИМИЗИРОВАННЫЙ МУТАТОР
# ═══════════════════════════════════════════════

class OptimizedTripletMutator:
    """✅ Интеллектуальный мутатор с полной адаптацией"""

    def __init__(self,
                 min_val: int,
                 max_val: int,
                 mutation_strength: float = CONFIG.MUTATION_STRENGTH,
                 mutation_probability: float = CONFIG.MUTATION_PROBABILITY,
                 locked_positions: Optional[Set[int]] = None,
                 adaptive_mode: bool = True):

        self.min_val = min_val
        self.max_val = max_val
        self.range_size = max_val - min_val

        self.mutation_strength = mutation_strength
        self.mutation_probability = mutation_probability
        self.locked_positions = locked_positions or set()
        self.adaptive_mode = adaptive_mode

        self.rng = random.SystemRandom()
        self.triplet_chars = list(CONFIG.TRIPLET_MAP.values())

        # Статистика
        self.metrics = MutationMetrics()
        self._iteration = 0
        self._consecutive_failures = 0
        self._current_strength = mutation_strength
        self._last_mutated: Dict[int, int] = {}

        # ✅ Квантово-вдохновленные параметры
        self.amplitude_history: List[float] = []
        self.phase_offsets: Dict[int, float] = {}

    def mutate_adaptive(self,
                        base_triplets: str,
                        mutation_strength: Optional[float] = None,
                        use_quantum_interference: bool = False) -> Tuple[str, List[int]]:
        """✅ Адаптивная мутация с квантовым вдохновением"""

        self._iteration += 1
        strength = mutation_strength or self._current_strength
        self.metrics.total_mutations += 1

        chars = list(base_triplets)
        num_to_mutate = max(1, int(len(chars) * strength))

        # ✅ Исключаем заблокированные позиции
        available = [i for i in range(len(chars))
                     if i not in self.locked_positions
                     and self._iteration - self._last_mutated.get(i, 0) > 3]

        if not available:
            # Полностью случайный прыжок
            rand_int = self.rng.randint(self.min_val, self.max_val)
            result = TripletConverter.int_to_triplets(rand_int)
            self.metrics.random_jumps += 1
            return result, list(range(len(result)))

        # Выбираем позиции для мутации
        positions = self.rng.sample(available, min(num_to_mutate, len(available)))

        for pos in positions:
            current = chars[pos]
            choices = [c for c in self.triplet_chars if c != current]

            if choices:
                # ✅ Квантовое вдохновение: выбираем на основе фазы
                if use_quantum_interference and pos in self.phase_offsets:
                    phase = self.phase_offsets[pos]
                    # Позволяем фазе влиять на выбор
                    idx = int((phase % 1.0) * len(choices))
                    chars[pos] = choices[idx % len(choices)]
                else:
                    chars[pos] = self.rng.choice(choices)

                self._last_mutated[pos] = self._iteration

        result = ''.join(chars)

        # ✅ Проверка диапазона
        try:
            result_int = TripletConverter.triplets_to_int(result)
            in_range = self.min_val <= result_int <= self.max_val
        except:
            in_range = False

        if not in_range:
            self.metrics.failed_out_of_range += 1
            self._consecutive_failures += 1

            # Адаптивное снижение силы
            if self.adaptive_mode and self._consecutive_failures > 5:
                self._current_strength = max(0.05, self._current_strength * 0.9)
                self.metrics.adaptive_strength_changes += 1
                self._consecutive_failures = 0

            # Случайный перезапуск
            rand_int = self.rng.randint(self.min_val, self.max_val)
            result = TripletConverter.int_to_triplets(rand_int)
            self.metrics.random_jumps += 1
            self.metrics.failed_drifts += 1
        else:
            self.metrics.successful_in_range += 1
            self._consecutive_failures = 0

            # Адаптивное повышение силы при успехах
            if self.adaptive_mode and self.metrics.successful_in_range % 10 == 0:
                self._current_strength = min(0.5, self._current_strength * 1.05)
                self.metrics.adaptive_strength_changes += 1

            self.metrics.successful_drifts += 1

        self.metrics.chars_mutated_total += len(positions)
        self.metrics.update_exploration()

        return result, positions

    def generate_random(self) -> str:
        """Сгенерировать полностью случайный триплет"""
        rand_int = self.rng.randint(self.min_val, self.max_val)
        return TripletConverter.int_to_triplets(rand_int)

    def update_phase_for_position(self, pos: int, phase: float):
        """✅ Обновить фазу для квантового вдохновения"""
        self.phase_offsets[pos] = phase

    def get_metrics(self) -> Dict[str, Any]:
        """Получить метрики"""
        metrics_dict = self.metrics.to_dict()
        metrics_dict["current_strength"] = f"{self._current_strength:.3f}"
        metrics_dict["iteration"] = self._iteration
        return metrics_dict

    def reset_metrics(self):
        """Сбросить метрики"""
        self.metrics = MutationMetrics()


# ═══════════════════════════════════════════════
# 🔧 ОПТИМИЗИРОВАННЫЙ БАТЧ-ПРОЦЕССОР
# ═══════════════════════════════════════════════

class OptimizedBatchProcessor:
    """✅ Оптимизированная обработка батчей с минимальным оверхедом"""

    def __init__(self, worker_id: int, queue: multiprocessing.Queue):
        self.worker_id = worker_id
        self.queue = queue

        self.processed_total = 0
        self.start_time = time.time()
        self._hash_obj = _hash_pool.acquire()

    def process_batch(self,
                      triplet_batch: List[str],
                      mutator: OptimizedTripletMutator,
                      compute_fn=None) -> Dict[str, Any]:
        """✅ Обработать батч с вычислениями"""

        results = {
            "processed": 0,
            "hashes": [],
            "values": [],
            "diversity": 0.0
        }

        hashes = set()

        for triplet_str in triplet_batch:
            try:
                # Конвертируем в число
                val = TripletConverter.triplets_to_int(triplet_str)

                # Хешируем (демонстрация вычисления)
                self._hash_obj = hashlib.sha256(str(val).encode())
                hash_val = self._hash_obj.hexdigest()[:16]

                results["hashes"].append(hash_val)
                results["values"].append(val)
                hashes.add(hash_val)
                results["processed"] += 1
                self.processed_total += 1

                # Опциональная функция вычисления
                if compute_fn:
                    compute_fn(val, triplet_str)

            except Exception as e:
                logger.debug(f"Batch processing error: {e}")
                continue

        # Метрика разнообразия
        if results["processed"] > 0:
            results["diversity"] = len(hashes) / results["processed"]

        return results

    def get_speed(self) -> float:
        """Вычислить скорость обработки"""
        elapsed = max(0.001, time.time() - self.start_time)
        return self.processed_total / elapsed


# ═══════════════════════════════════════════════
# 🔧 ВОРКЕР С ОПТИМИЗАЦИЯМИ
# ═══════════════════════════════════════════════

def optimized_worker_process(
        worker_id: int,
        min_val: int,
        max_val: int,
        queue: multiprocessing.Queue,
        shutdown_event: multiprocessing.Event,
        mutation_mode: str = "random_curve",
        mutation_strength: float = None,
        mutation_probability: float = None,
        update_base_interval: int = None,
        locked_positions: Optional[List[int]] = None,
        adaptive_mode: bool = True,
        quantum_inspired: bool = False
) -> None:
    """✅ Оптимизированный воркер без криптографического целеполагания"""

    def send_msg(msg_type: str, data: Dict[str, Any]):
        """Безопасно отправить сообщение"""
        try:
            msg = {"type": msg_type, "worker_id": worker_id, **data}
            queue.put(msg, timeout=CONFIG.QUEUE_TIMEOUT)
        except:
            pass

    # ✅ Инициализация
    mut_strength = mutation_strength or CONFIG.MUTATION_STRENGTH
    mut_prob = mutation_probability or CONFIG.MUTATION_PROBABILITY
    base_interval = update_base_interval or CONFIG.BASE_UPDATE_INTERVAL

    send_msg("log", {
        "message": f"Worker {worker_id} started | Range: [{min_val}, {max_val}]",
        "level": "info"
    })

    # Инициализируем мутатор
    mutator = OptimizedTripletMutator(
        min_val=min_val,
        max_val=max_val,
        mutation_strength=mut_strength,
        mutation_probability=mut_prob,
        locked_positions=set(locked_positions) if locked_positions else set(),
        adaptive_mode=adaptive_mode
    )

    # Инициализируем батч-процессор
    processor = OptimizedBatchProcessor(worker_id, queue)

    # ✅ Начальное состояние
    mid_val = (min_val + max_val) // 2
    base_triplets = TripletConverter.int_to_triplets(mid_val)
    batch: List[str] = []

    iterations_since_base = 0
    total_batches = 0
    last_stats_time = time.time()

    try:
        while not shutdown_event.is_set():
            # ✅ Выбираем стратегию мутации
            if mutation_mode == "random_curve":
                if random.random() < mut_prob:
                    next_triplets, changed_pos = mutator.mutate_adaptive(
                        base_triplets,
                        use_quantum_interference=quantum_inspired
                    )
                    iterations_since_base += 1

                    # Обновляем базовую точку
                    if base_interval > 0 and iterations_since_base >= base_interval:
                        base_triplets = mutator.generate_random()
                        iterations_since_base = 0
                else:
                    next_triplets = mutator.generate_random()
                    changed_pos = list(range(len(next_triplets)))

            elif mutation_mode == "pure_random":
                next_triplets = mutator.generate_random()
                changed_pos = list(range(len(next_triplets)))

            elif mutation_mode == "quantum_inspired":
                # Квантово-вдохновленный режим с фазой
                phase = (mutator._iteration % 100) / 100.0 * 2 * 3.14159
                for pos in range(len(base_triplets)):
                    mutator.update_phase_for_position(pos, phase)

                next_triplets, changed_pos = mutator.mutate_adaptive(
                    base_triplets,
                    use_quantum_interference=True
                )

            else:  # adaptive mode
                next_triplets, changed_pos = mutator.mutate_adaptive(base_triplets)

            batch.append(next_triplets)

            # ✅ Обработка батча при достижении размера
            if len(batch) >= CONFIG.BATCH_SIZE:
                batch_results = processor.process_batch(batch, mutator)
                total_batches += 1
                batch.clear()

                # ✅ Периодическая статистика
                now = time.time()
                if now - last_stats_time >= CONFIG.STATS_INTERVAL:
                    elapsed = now - last_stats_time
                    speed = processor.processed_total / (now - processor.start_time)

                    send_msg("stats", {
                        "processed": processor.processed_total,
                        "batches": total_batches,
                        "speed": f"{speed:.0f} triplets/s",
                        "elapsed": f"{elapsed:.2f}s",
                        "avg_diversity": f"{batch_results['diversity']:.3f}",
                        "mutation_metrics": mutator.get_metrics()
                    })

                    last_stats_time = now

                    # Сбрасываем метрики каждые 10 батчей
                    if total_batches % 10 == 0:
                        mutator.reset_metrics()

        # ✅ Финальная обработка оставшихся триплетов
        if batch:
            batch_results = processor.process_batch(batch, mutator)
            processor.processed_total += batch_results["processed"]

        # ✅ Финальный отчёт
        total_time = time.time() - processor.start_time
        avg_speed = processor.processed_total / max(0.001, total_time)

        send_msg("stats", {
            "processed": processor.processed_total,
            "batches": total_batches,
            "speed": f"{avg_speed:.0f} triplets/s",
            "total_time": f"{total_time:.2f}s",
            "final_metrics": mutator.get_metrics()
        })

        send_msg("log", {
            "message": f"Worker {worker_id} completed | "
                       f"Processed: {processor.processed_total:,} | "
                       f"Speed: {avg_speed:.0f} triplets/s",
            "level": "info"
        })

        send_msg("worker_finished", {
            "processed": processor.processed_total,
            "speed": avg_speed,
            "time": total_time
        })

    except Exception as e:
        logger.exception(f"Worker {worker_id} error")
        send_msg("log", {
            "message": f"ERROR: {type(e).__name__}: {str(e)[:100]}",
            "level": "error"
        })


# ═══════════════════════════════════════════════
# 🔧 ГЛАВНЫЙ КОНТРОЛЛЕР
# ═══════════════════════════════════════════════

class OptimizedMatrixEngine:
    """✅ Главный контроллер оптимизированного движка"""

    def __init__(self):
        self.processes: Dict[int, multiprocessing.Process] = {}
        self.shutdown_event = multiprocessing.Event()
        self.queue = multiprocessing.Queue()
        self.is_running = False

        # Параметры
        self.mutation_strength = CONFIG.MUTATION_STRENGTH
        self.mutation_probability = CONFIG.MUTATION_PROBABILITY
        self.update_base_interval = CONFIG.BASE_UPDATE_INTERVAL
        self.locked_positions: Set[int] = set()
        self.adaptive_mode = True
        self.quantum_inspired = False

        # Статистика
        self._total_processed = 0
        self._start_time = 0
        self._last_stats = {}

    def start_search(self,
                     num_workers: int = 4,
                     mutation_mode: str = "random_curve",
                     mutation_strength: float = None,
                     mutation_probability: float = None,
                     quantum_inspired: bool = False,
                     adaptive_mode: bool = True) -> bool:
        """✅ Запустить поиск"""

        if self.is_running:
            logger.warning("Search already running")
            return False

        self.shutdown_event.clear()
        self.is_running = True
        self._total_processed = 0
        self._start_time = time.time()
        self.quantum_inspired = quantum_inspired

        # Параметры
        mut_strength = mutation_strength or self.mutation_strength
        mut_prob = mutation_probability or self.mutation_probability

        # Разделяем диапазон поиска
        total_range = CONFIG.SEARCH_SPACE_SIZE
        chunk = total_range // num_workers

        for wid in range(num_workers):
            start = wid * chunk
            end = (wid + 1) * chunk if wid < num_workers - 1 else total_range

            p = multiprocessing.Process(
                target=optimized_worker_process,
                args=(wid, start, end, self.queue, self.shutdown_event,
                      mutation_mode),
                kwargs={
                    "mutation_strength": mut_strength,
                    "mutation_probability": mut_prob,
                    "locked_positions": list(self.locked_positions),
                    "adaptive_mode": adaptive_mode,
                    "quantum_inspired": quantum_inspired
                }
            )
            p.daemon = True
            p.start()
            self.processes[wid] = p

        logger.info(f"✅ Started {num_workers} workers | "
                    f"Mode: {mutation_mode} | Quantum: {quantum_inspired}")
        return True

    def stop_search(self, timeout: float = 2.0) -> None:
        """Остановить поиск"""
        if not self.is_running:
            return

        logger.info("Shutting down workers...")
        self.shutdown_event.set()

        for worker_id, proc in list(self.processes.items()):
            if proc.is_alive():
                try:
                    proc.join(timeout=timeout)
                    if proc.is_alive():
                        proc.terminate()
                        proc.join(timeout=0.5)
                        if proc.is_alive():
                            proc.kill()
                except Exception as e:
                    logger.warning(f"Error stopping worker {worker_id}: {e}")

        self.processes.clear()
        self.is_running = False
        logger.info("Workers stopped")

    def get_queue(self) -> multiprocessing.Queue:
        """Получить очередь"""
        return self.queue

    def process_queue_messages(self, timeout: float = 0.1):
        """Обработать сообщения из очереди"""
        try:
            msg = self.queue.get(timeout=timeout)

            if msg["type"] == "log":
                level = msg.get("level", "info")
                message = msg.get("message", "")
                wid = msg.get("worker_id", "?")
                print(f"[Worker {wid}] {message}")

            elif msg["type"] == "stats":
                wid = msg.get("worker_id", "?")
                processed = msg.get("processed", 0)
                speed = msg.get("speed", "?")
                self._total_processed += processed
                print(f"[Worker {wid}] Processed: {processed:,} | Speed: {speed}")

                if "mutation_metrics" in msg:
                    metrics = msg["mutation_metrics"]
                    print(f"        Mutations: {metrics.get('mutations', 0)} | "
                          f"Success: {metrics.get('success_rate', '?')} | "
                          f"Exploration: {metrics.get('exploration_efficiency', '?')}")

            elif msg["type"] == "worker_finished":
                wid = msg.get("worker_id", "?")
                processed = msg.get("processed", 0)
                speed = msg.get("speed", 0)
                time_taken = msg.get("time", 0)
                print(f"[Worker {wid}] ✅ FINISHED | "
                      f"Processed: {processed:,} | "
                      f"Speed: {speed:.0f} triplets/s | "
                      f"Time: {time_taken:.2f}s")

            return msg

        except:
            return None

    def print_summary(self) -> None:
        """Печать итогового резюме"""
        elapsed = max(0.001, time.time() - self._start_time)
        avg_speed = self._total_processed / elapsed

        print("\n" + "=" * 70)
        print("📊 ИТОГОВОЕ РЕЗЮМЕ")
        print("=" * 70)
        print(f"Total processed: {self._total_processed:,} triplets")
        print(f"Total time: {elapsed:.2f} seconds")
        print(f"Average speed: {avg_speed:.0f} triplets/second")
        print(f"Active workers: {sum(1 for p in self.processes.values() if p.is_alive())}")
        print("=" * 70 + "\n")


# ═══════════════════════════════════════════════
# 🚀 ГЛАВНАЯ ДЕМОНСТРАЦИЯ
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🔷 OPTIMIZED MATRIX ENGINE — ДЕМОНСТРАЦИЯ")
    print("=" * 70 + "\n")

    engine = OptimizedMatrixEngine()

    # ✅ СЦЕНАРИЙ 1: Классическая случайная кривая с адаптацией
    print("📌 СЦЕНАРИЙ 1: Random Curve с адаптацией")
    print("-" * 70)

    engine.start_search(
        num_workers=4,
        mutation_mode="random_curve",
        mutation_strength=0.15,
        adaptive_mode=True,
        quantum_inspired=False
    )

    try:
        for _ in range(60):  # 60 секунд демонстрации
            engine.process_queue_messages(timeout=0.1)
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n⏸️  Interrupted by user")

    engine.stop_search()
    engine.print_summary()

    # Очистка очереди
    while True:
        msg = engine.process_queue_messages(timeout=0.01)
        if msg is None:
            break

    print("\n" + "=" * 70 + "\n")

    # ✅ СЦЕНАРИЙ 2: Квантово-вдохновленный режим
    print("📌 СЦЕНАРИЙ 2: Квантово-вдохновленная мутация")
    print("-" * 70)

    engine2 = OptimizedMatrixEngine()
    engine2.start_search(
        num_workers=4,
        mutation_mode="quantum_inspired",
        mutation_strength=0.2,
        adaptive_mode=True,
        quantum_inspired=True
    )

    try:
        for _ in range(60):  # 60 секунд демонстрации
            engine2.process_queue_messages(timeout=0.1)
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n⏸️  Interrupted by user")

    engine2.stop_search()
    engine2.print_summary()

    print("\n✅ Демонстрация завершена!\n")
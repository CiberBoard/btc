# core/matrix_logic.py
from __future__ import annotations

import time
import random
import logging
import hashlib
import multiprocessing
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, field

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
# 🔧 КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════

@dataclass(frozen=True)
class MatrixConfig:
    TRIPLET_MAP: Dict[str, str] = field(default_factory=lambda: {
        '000': 'A', '001': 'B', '010': 'C', '011': 'D',
        '100': 'E', '101': 'F', '110': 'G', '111': 'H'
    })
    BASE58_ALPHABET: str = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

    WORKER_BIT_LENGTH: int = 256
    KEY_BYTES: int = 32
    COMPRESSED_PUBKEY: bool = True
    MIN_PRIVATE_KEY: int = 1
    MAX_PRIVATE_KEY: int = config.MAX_KEY

    BATCH_SIZE: int = 100
    STATS_INTERVAL: float = 0.5
    QUEUE_TIMEOUT: float = 0.1

    MUTATION_PROBABILITY: float = 0.7
    MUTATION_STRENGTH: float = 0.15
    BASE_UPDATE_INTERVAL: int = 1000
    MUTATION_VISUALIZE: bool = False
    SEED: Optional[int] = None
    TRACK_MUTATION_STATS: bool = True


MATRIX_CONFIG: MatrixConfig = MatrixConfig()
REVERSE_MAP: Dict[str, str] = {v: k for k, v in MATRIX_CONFIG.TRIPLET_MAP.items()}


# ═══════════════════════════════════════════════
# 🔧 СООБЩЕНИЯ
# ═══════════════════════════════════════════════

def create_found_message(address: str, hex_key: str, wif_key: str, worker_id: int) -> Dict[str, Any]:
    return {
        "type": "found",
        "address": address,
        "hex_key": hex_key,
        "wif_key": wif_key,
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "worker_id": worker_id,
        "source": "MATRIX"
    }


def create_stats_message(scanned: int, found: int, speed: float, progress: int,
                         worker_id: int, mutation_stats: Optional[Dict] = None) -> Dict[str, Any]:
    msg = {
        "type": "stats",
        "scanned": scanned,
        "found": found,
        "speed": speed,
        "progress": progress,
        "worker_id": worker_id,
        "timestamp": time.time()
    }
    if mutation_stats:
        msg["mutation_stats"] = mutation_stats
    return msg


def create_log_message(message: str, level: str = "info") -> Dict[str, str]:
    return {"type": "log", "message": message, "level": level}


def create_visual_state_message(triplets: str, hex_key: str, address: str,
                                changed_positions: List[int], worker_id: int) -> Dict[str, Any]:
    """Сообщение для визуального обновления состояния в UI"""
    return {
        "type": "search_state",
        "triplets": triplets,
        "hex_key": hex_key,
        "address": address,
        "changed_positions": changed_positions,
        "worker_id": worker_id,
        "matched": False
    }


# ═══════════════════════════════════════════════
# 🔧 МАТРИЦА: КОНВЕРТАЦИЯ
# ═══════════════════════════════════════════════

class MatrixConverter:
    @staticmethod
    def int_to_triplets(n: int, bit_len: int = MATRIX_CONFIG.WORKER_BIT_LENGTH) -> str:
        """Конвертирует целое число в строку триплетов"""
        bin_str = bin(n)[2:].zfill(bit_len)
        padding = (3 - len(bin_str) % 3) % 3
        bin_str = '0' * padding + bin_str
        triplets = [bin_str[i:i + 3] for i in range(0, len(bin_str), 3)]
        return ''.join(MATRIX_CONFIG.TRIPLET_MAP[t] for t in triplets)

    @staticmethod
    def triplets_to_int(triplet_str: str) -> int:
        """Конвертирует строку триплетов в целое число"""
        bin_str = ''.join(REVERSE_MAP[c.upper()] for c in triplet_str)
        return int(bin_str.lstrip('0') or '0', 2)

    @staticmethod
    def hex_to_triplets(hex_str: str) -> str:
        return MatrixConverter.int_to_triplets(int(hex_str, 16))

    @staticmethod
    def triplets_to_hex(triplet_str: str) -> str:
        return hex(MatrixConverter.triplets_to_int(triplet_str))[2:].zfill(64)

    @staticmethod
    def is_in_range(triplet_str: str, start_triplets: str, end_triplets: str) -> bool:
        val = MatrixConverter.triplets_to_int(triplet_str)
        return (MatrixConverter.triplets_to_int(start_triplets) <= val <=
                MatrixConverter.triplets_to_int(end_triplets))

    @staticmethod
    def get_range_stats(start_hex: str, end_hex: str) -> Dict[str, Any]:
        start_int = int(start_hex, 16) if start_hex else 0
        end_int = int(end_hex, 16) if end_hex else 0
        total = max(0, end_int - start_int)
        return {
            "start_int": start_int,
            "end_int": end_int,
            "total_keys": total,
            "total_triplets": len(MatrixConverter.int_to_triplets(start_int)) if total > 0 else 0,
            "hex_length": 64
        }

    @staticmethod
    def split_range(start_hex: str, end_hex: str, num_workers: int) -> List[Tuple[str, str]]:
        """Разделяет диапазон на поддиапазоны для каждого воркера"""
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


# ═══════════════════════════════════════════════
# 🔐 ADDRESS GENERATOR
# ═══════════════════════════════════════════════

# ═══════════════════════════════════════════════
# 🔐 ADDRESS GENERATOR (ИСПРАВЛЕННЫЙ)
# ═══════════════════════════════════════════════

class MatrixAddressGenerator:
    def __init__(self, target_address: str):
        self.target_address = target_address.strip()
        # ✅ Оставляем только sha256 (это фабрика/функция)
        self._sha256 = hashlib.sha256

    def generate_address(self, priv_int: int) -> Optional[str]:
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

            pub_sha = self._sha256(pub).digest()

            # ✅ ИСПРАВЛЕНИЕ: создаём новый объект хеша при каждом вызове
            ripemd = hashlib.new('ripemd160')
            ripemd.update(pub_sha)
            pub_ripemd = ripemd.digest()

            return _generate_p2pkh(pub_ripemd)
        except Exception as e:
            # 🔴 Временно раскомментируйте для отладки:
            # logger.error(f"Ошибка генерации адреса: {e}")
            return None

    def check_match(self, address: Optional[str]) -> bool:
        return address is not None and address == self.target_address


# ═══════════════════════════════════════════════
# 🎲 MUTATOR (с поддержкой locked positions)
# ═══════════════════════════════════════════════

@dataclass
class MutationStats:
    total_mutations: int = 0
    out_of_range_fallbacks: int = 0
    random_jumps: int = 0
    chars_mutated_total: int = 0
    in_range_successes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        total = self.total_mutations + self.random_jumps
        return {
            "total_operations": total,
            "mutations": self.total_mutations,
            "random_jumps": self.random_jumps,
            "in_range_rate": f"{(self.in_range_successes / max(1, self.total_mutations) * 100):.1f}%",
            "fallback_rate": f"{(self.out_of_range_fallbacks / max(1, self.total_mutations) * 100):.1f}%",
            "avg_chars_changed": f"{(self.chars_mutated_total / max(1, self.total_mutations)):.2f}"
        }


class TripletMutator:
    def __init__(self, start_triplets: str, end_triplets: str,
                 rng: Optional[random.Random] = None,
                 mutation_strength: float = None,
                 mutation_probability: float = None,
                 locked_positions: Optional[Set[int]] = None):
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
        self._last_mutated: Dict[int, int] = {}
        self._iteration = 0

    def set_locked_positions(self, positions: Set[int]):
        """Устанавливает зафиксированные позиции, которые не будут мутировать"""
        self.locked_positions = positions

    def mutate_random_triplet(self, base_triplets: str,
                              mutation_strength: float = None,
                              visualize: bool = False) -> Tuple[str, List[int]]:
        """
        Мутирует триплеты с учётом зафиксированных позиций.
        Возвращает: (новый_триплет, список_изменённых_позиций)
        """
        self._iteration += 1
        mutation_strength = mutation_strength or self.mutation_strength
        self.stats.total_mutations += 1

        chars = list(base_triplets)
        num_to_mutate = max(1, int(len(chars) * mutation_strength))

        # 🔒 Исключаем зафиксированные позиции из мутации
        available_positions = [
            i for i in range(len(chars))
            if i not in self.locked_positions
               and self._iteration - self._last_mutated.get(i, 0) > 5
        ]
        if len(available_positions) < num_to_mutate:
            available_positions = [i for i in range(len(chars)) if i not in self.locked_positions]
        if not available_positions:
            # Если все позиции зафиксированы - делаем случайный прыжок в диапазоне
            rand_int = self.rng.randint(self.start_int, self.end_int)
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

        # 🔍 Проверка диапазона
        if not MatrixConverter.is_in_range(result, self.start_triplets, self.end_triplets):
            self.stats.out_of_range_fallbacks += 1
            rand_int = self.rng.randint(self.start_int, self.end_int)
            result = MatrixConverter.int_to_triplets(rand_int)
            chars_mutated = list(range(len(result)))  # Все позиции изменились
        else:
            self.stats.in_range_successes += 1

        self.stats.chars_mutated_total += len(chars_mutated)
        return result, chars_mutated

    def generate_random_in_range(self) -> str:
        self.stats.random_jumps += 1
        rand_int = self.rng.randint(self.start_int, self.end_int)
        return MatrixConverter.int_to_triplets(rand_int)

    def get_stats(self) -> Dict[str, Any]:
        return self.stats.to_dict()

    def reset_stats(self):
        self.stats = MutationStats()
        self._last_mutated.clear()
        self._iteration = 0


# ═══════════════════════════════════════════════
# 🔧 ОБРАБОТКА ПАКЕТОВ
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
                logger.error(f"Ошибка отправки found: {e}")
            found_count += 1

        # ✅ Отправка визуального состояния периодически
        if send_visual and idx % visual_interval == 0:
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
                pass  # Не критично

    return found_count


# ═══════════════════════════════════════════════
# 🔧 ВОРКЕР: ИСПРАВЛЕННЫЙ (свои диапазоны + locked positions)
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
        locked_positions: Optional[List[int]] = None  # ✅ НОВЫЙ ПАРАМЕТР
) -> None:
    """
    Воркер с индивидуальным поддиапазоном и поддержкой зафиксированных позиций.
    """

    def _safe_log(msg: str, level: str = "info"):
        try:
            print(f"[MatrixWorker-{worker_id}] {msg}", flush=True)
        except:
            pass

    if COINCURVE_AVAILABLE:
        try:
            from coincurve import PrivateKey  # noqa: F401
        except Exception as e:
            logger.error(f"Worker {worker_id}: coincurve import failed: {e}")

    mut_strength = mutation_strength if mutation_strength is not None else MATRIX_CONFIG.MUTATION_STRENGTH
    mut_prob = mutation_probability if mutation_probability is not None else MATRIX_CONFIG.MUTATION_PROBABILITY
    base_interval = update_base_interval if update_base_interval is not None else MATRIX_CONFIG.BASE_UPDATE_INTERVAL

    # ✅ РАЗДЕЛЕНИЕ ДИАПАЗОНА: каждый воркер получает свой поддиапазон
    sub_ranges = MatrixConverter.split_range(start_hex, end_hex, total_workers)
    worker_start_hex, worker_end_hex = sub_ranges[worker_id] if worker_id < len(sub_ranges) else (start_hex, end_hex)

    _safe_log(f"Started [{mutation_mode}] range:{worker_start_hex[:16]}...{worker_end_hex[-16:]}")

    start_triplets = MatrixConverter.hex_to_triplets(worker_start_hex)
    end_triplets = MatrixConverter.hex_to_triplets(worker_end_hex)

    generator = MatrixAddressGenerator(target_address)
    mutator = TripletMutator(
        start_triplets, end_triplets,
        mutation_strength=mut_strength,
        mutation_probability=mut_prob,
        locked_positions=set(locked_positions) if locked_positions else set()  # ✅ Применяем locked
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
        try:
            queue.put(create_log_message(
                f"Worker {worker_id}: инициализирован [{worker_start_hex[:16]}...{worker_end_hex[:16]}]"),
                      timeout=MATRIX_CONFIG.QUEUE_TIMEOUT)
        except:
            _safe_log("Failed to send init message")

        while not shutdown_event.is_set():
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
                next_triplets = mutator.generate_random_in_range()
                changed_positions = list(range(len(next_triplets)))

            # 🎨 Визуальное обновление
            if visualize_mutations and total_scanned % 50 == 0:
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

            if len(batch) >= MATRIX_CONFIG.BATCH_SIZE:
                found = process_triplet_batch(
                    batch, target_address, worker_id, queue, generator,
                    send_visual=visualize_mutations
                )
                total_found += found
                total_scanned += len(batch)
                batch.clear()

                now = time.time()
                if now - last_update >= MATRIX_CONFIG.STATS_INTERVAL:
                    elapsed = max(0.001, now - last_update)
                    speed = (total_scanned - last_scanned) / elapsed
                    mutation_stats = mutator.get_stats() if MATRIX_CONFIG.TRACK_MUTATION_STATS else None

                    safe_queue_put(queue, create_stats_message(
                        total_scanned, total_found, speed, 0, worker_id, mutation_stats
                    ), timeout=MATRIX_CONFIG.QUEUE_TIMEOUT)
                    last_update = now
                    last_scanned = total_scanned

                    if total_scanned % 10000 == 0 and mutation_stats:
                        mutator.reset_stats()

        # 🏁 Финальная обработка
        if batch:
            found = process_triplet_batch(batch, target_address, worker_id, queue, generator)
            total_found += found
            total_scanned += len(batch)

        elapsed = max(0.001, time.time() - start_time)
        avg_speed = total_scanned / elapsed
        final_mutation_stats = mutator.get_stats() if MATRIX_CONFIG.TRACK_MUTATION_STATS else None

        safe_queue_put(queue, create_stats_message(
            total_scanned, total_found, avg_speed, 100, worker_id, final_mutation_stats
        ), timeout=MATRIX_CONFIG.QUEUE_TIMEOUT)

        safe_queue_put(queue, create_log_message(
            f"Worker {worker_id} завершён | {avg_speed:.0f} keys/s"
        ), timeout=MATRIX_CONFIG.QUEUE_TIMEOUT)

        safe_queue_put(queue, {"type": "worker_finished", "worker_id": worker_id,
                               "scanned": total_scanned, "found": total_found},
                       timeout=MATRIX_CONFIG.QUEUE_TIMEOUT)

    except Exception as e:
        logger.exception(f"Critical error in MatrixWorker {worker_id}")
        try:
            safe_queue_put(queue, create_log_message(
                f"Worker {worker_id} ошибка: {type(e).__name__}: {e}", level="error"
            ), timeout=MATRIX_CONFIG.QUEUE_TIMEOUT)
        except:
            pass
    finally:
        try:
            safe_queue_put(queue, {"type": "worker_finished", "worker_id": worker_id},
                           timeout=MATRIX_CONFIG.QUEUE_TIMEOUT)
        except:
            pass


# ═══════════════════════════════════════════════
# 🔧 УПРАВЛЕНИЕ ПРОЦЕССАМИ
# ═══════════════════════════════════════════════

def stop_matrix_search(
        processes: Dict[int, multiprocessing.Process],
        shutdown_event: multiprocessing.Event
) -> None:
    logger.info("Остановка Matrix процессов...")
    shutdown_event.set()
    for worker_id, process in list(processes.items()):
        if process.is_alive():
            try:
                process.terminate()
                process.join(timeout=1.0)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=0.5)
            except Exception as e:
                logger.warning(f"Ошибка остановки воркера {worker_id}: {e}")
    processes.clear()
    if shutdown_event.is_set():
        shutdown_event.clear()
    logger.info("Matrix процессы остановлены")


# ═══════════════════════════════════════════════
# 🔧 MatrixLogic — интерфейс для главного потока
# ═══════════════════════════════════════════════

class MatrixLogic(QObject):
    """Интерфейс для главного потока"""

    update_stats = pyqtSignal(dict)
    log_message = pyqtSignal(str)
    key_found = pyqtSignal(dict)
    worker_finished = pyqtSignal(int)
    visual_state_update = pyqtSignal(dict)  # ✅ Для визуального обновления

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
        self.locked_positions: Set[int] = set()  # ✅ Зафиксированные позиции

        # Статистика
        self._total_scanned = 0
        self._total_found = 0

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
            locked_positions: Optional[List[int]] = None  # ✅ Новый параметр
    ) -> bool:
        if self.is_running:
            return False

        import threading
        if threading.current_thread() is not threading.main_thread():
            self.log_message.emit("❌ start_search вызван не из главного потока!")
            return False

        try:
            start_int = int(start_hex, 16)
            end_int = int(end_hex, 16)
            if start_int >= end_int:
                raise ValueError("start >= end")
        except Exception as e:
            self.log_message.emit(f"❌ Ошибка диапазона: {e}")
            return False

        if not COINCURVE_AVAILABLE:
            self.log_message.emit("❌ coincurve не установлен! pip install coincurve")
            return False

        self.shutdown_event.clear()
        self.is_running = True
        self._total_scanned = 0
        self._total_found = 0

        # Применяем параметры
        mut_strength = mutation_strength if mutation_strength is not None else self.mutation_strength
        mut_prob = mutation_probability if mutation_probability is not None else self.mutation_probability
        base_interval = update_base_interval if update_base_interval is not None else self.update_base_interval
        do_viz = visualize_mutations if visualize_mutations is not None else self.visualize_mutations
        locked = set(locked_positions) if locked_positions else self.locked_positions

        # ✅ РАЗДЕЛЕНИЕ ДИАПАЗОНА
        sub_ranges = MatrixConverter.split_range(start_hex, end_hex, num_workers)

        for wid in range(num_workers):
            # ✅ Каждый воркер получает свой поддиапазон
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
                    "locked_positions": list(locked)  # ✅ Передаём зафиксированные позиции
                }
            )
            p.daemon = True
            p.start()
            self.processes[wid] = p
            self.log_message.emit(f"🚀 Воркер {wid} запущен [{worker_start[:16]}...{worker_end[:16]}]")

        self.log_message.emit(
            f"✅ Поиск запущен: {num_workers} воркеров, режим: {mutation_mode}, "
            f"сила мутации: {mut_strength:.0%}, зафиксировано позиций: {len(locked)}"
        )
        return True

    def stop_search(self) -> None:
        if not self.is_running:
            return
        stop_matrix_search(self.processes, self.shutdown_event)
        self.is_running = False
        self.log_message.emit("🛑 Поиск остановлен")

    def get_queue(self) -> multiprocessing.Queue:
        return self.queue

    def update_mutation_params(self, strength: float = None, probability: float = None,
                               update_interval: int = None, visualize: bool = None):
        if strength is not None:
            self.mutation_strength = max(0.01, min(0.5, strength))
        if probability is not None:
            self.mutation_probability = max(0.0, min(1.0, probability))
        if update_interval is not None:
            self.update_base_interval = max(0, update_interval)
        if visualize is not None:
            self.visualize_mutations = visualize

    def update_locked_positions(self, positions: List[int]):
        """✅ Обновляет зафиксированные позиции для всех воркеров"""
        self.locked_positions = set(positions)
        # Примечание: для применения к запущенным воркерам нужна перезагрузка или IPC

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
    'TripletMutator', 'MutationStats',
    'MatrixLogic', 'matrix_worker_main', 'stop_matrix_search',
    'create_found_message', 'create_stats_message', 'create_log_message',
    'create_visual_state_message'
]
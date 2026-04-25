#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔷 MATRIX SEARCH ENGINE v3.1 — Поиск приватного ключа по адресу
================================================================
Объединяет:
✅ Триплет-кодирование (3 бита → символ)
✅ Адаптивную мутацию с "квантовым вдохновением"
✅ Реальную генерацию Bitcoin-адресов (secp256k1 + SHA256 + RIPEMD160 + Base58)
✅ Параллельную обработку (multiprocessing)
✅ Сравнение с целевым адресом и вывод результата

⚠️  Требует: pip install coincurve
"""

from __future__ import annotations

import time
import random
import hashlib
import logging
import multiprocessing
import threading
from typing import Dict, List, Tuple, Optional, Set, Any, Callable
from dataclasses import dataclass, field
from collections import deque
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

# 🔐 Криптография Bitcoin
try:
    from coincurve import PrivateKey
    COINCURVE_AVAILABLE = True
except ImportError:
    COINCURVE_AVAILABLE = False
    PrivateKey = None
    print("⚠️  coincurve не установлен: pip install coincurve")

# 🔧 Конфигурация логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('matrix_search')


# ═══════════════════════════════════════════════
# 🔧 КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════

class MutationMode(Enum):
    RANDOM_CURVE = "random_curve"      # Случайная мутация + дрейф
    PURE_RANDOM = "pure_random"        # Полностью случайный поиск
    DRIFT = "drift"                    # Дрейф от базовой точки
    ADAPTIVE = "adaptive"              # Адаптивная сила мутации
    QUANTUM_INSPIRED = "quantum_inspired"  # С фазовой интерференцией


@dataclass(frozen=True)
class SearchConfig:
    """Глобальная конфигурация"""

    # 🧬 Триплет-кодирование
    TRIPLET_MAP: Dict[str, str] = field(default_factory=lambda: {
        '000': 'A', '001': 'B', '010': 'C', '011': 'D',
        '100': 'E', '101': 'F', '110': 'G', '111': 'H'
    })
    BASE58_ALPHABET: str = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

    # 🔢 Параметры ключа
    BIT_LENGTH: int = 256
    KEY_BYTES: int = 32
    COMPRESSED_PUBKEY: bool = True

    # 🎯 Параметры поиска
    BATCH_SIZE: int = 128
    STATS_INTERVAL: float = 1.0
    QUEUE_TIMEOUT: float = 0.1

    # 🎲 Мутация
    MUTATION_PROBABILITY: float = 0.7
    MUTATION_STRENGTH: float = 0.15
    BASE_UPDATE_INTERVAL: int = 1000
    ADAPTIVE_MODE: bool = True

    # ⚡ Оптимизация
    HASH_CACHE_SIZE: int = 256
    TRACK_MUTATIONS: bool = True
    QUANTUM_INSPIRED: bool = False  # Включить "фазовую" логику

    # 🔐 Целевой адрес (заполняется при запуске)
    TARGET_ADDRESS: str = ""


CONFIG = SearchConfig()
REVERSE_MAP: Dict[str, str] = {v: k for k, v in CONFIG.TRIPLET_MAP.items()}


# ═══════════════════════════════════════════════
# 🔧 КЭШИРОВАНИЕ ХЕШЕЙ
# ═══════════════════════════════════════════════

class HashPool:
    """Пул объектов hashlib для избежания аллокаций"""

    def __init__(self, size: int = CONFIG.HASH_CACHE_SIZE):
        self.pool: deque = deque(maxlen=size)
        self.lock = threading.Lock()
        for _ in range(size):
            self.pool.append(hashlib.new('ripemd160'))

    def acquire(self) -> Any:
        with self.lock:
            return self.pool.popleft() if self.pool else hashlib.new('ripemd160')

    def release(self, obj: Any):
        try:
            # Сбрасываем объект и возвращаем в пул
            obj = hashlib.new('ripemd160')
            with self.lock:
                if len(self.pool) < self.pool.maxlen:
                    self.pool.append(obj)
        except:
            pass


_hash_pool = HashPool()


# ═══════════════════════════════════════════════
# 🔧 КОНВЕРТАЦИЯ: int ↔ triplets ↔ hex
# ═══════════════════════════════════════════════

class TripletConverter:
    """Конвертация с кэшированием"""

    _int_cache: Dict[str, int] = {}
    _triplet_cache: Dict[int, str] = {}

    @classmethod
    def int_to_triplets(cls, n: int, bit_len: int = CONFIG.BIT_LENGTH) -> str:
        key = f"{n}:{bit_len}"
        if key in cls._triplet_cache:
            return cls._triplet_cache[key]

        bin_str = bin(n)[2:].zfill(bit_len)
        padding = (3 - len(bin_str) % 3) % 3
        bin_str = '0' * padding + bin_str
        triplets = [bin_str[i:i+3] for i in range(0, len(bin_str), 3)]
        result = ''.join(CONFIG.TRIPLET_MAP[t] for t in triplets)

        if len(cls._triplet_cache) > 5000:
            cls._triplet_cache.clear()
        cls._triplet_cache[key] = result
        return result

    @classmethod
    def triplets_to_int(cls, triplet_str: str) -> int:
        if triplet_str in cls._int_cache:
            return cls._int_cache[triplet_str]

        bin_str = ''.join(REVERSE_MAP[c.upper()] for c in triplet_str)
        result = int(bin_str.lstrip('0') or '0', 2)

        if len(cls._int_cache) > 5000:
            cls._int_cache.clear()
        cls._int_cache[triplet_str] = result
        return result

    @classmethod
    def int_to_hex(cls, n: int) -> str:
        return f"{n:064x}"

    @classmethod
    def hex_to_int(cls, hex_str: str) -> int:
        return int(hex_str, 16)

    @classmethod
    def is_in_range(cls, val: int, min_val: int, max_val: int) -> bool:
        return min_val <= val <= max_val


# ═══════════════════════════════════════════════
# 🔐 ГЕНЕРАЦИЯ BITCOIN-АДРЕСА (КЛЮЧЕВОЙ КОМПОНЕНТ)
# ═══════════════════════════════════════════════

class BitcoinAddressGenerator:
    """
    Генерация P2PKH-адреса из приватного ключа:
    privkey → secp256k1 pubkey → SHA256 → RIPEMD160 → Base58Check
    """

    def __init__(self, target_address: str):
        self.target = target_address.strip()
        self._sha256 = hashlib.sha256
        self._generated = 0
        self._matches = 0

    def generate(self, priv_int: int) -> Optional[str]:
        """Сгенерировать адрес из приватного ключа (целое число)"""
        if not (1 <= priv_int < 2**256):
            return None

        try:
            # 1. Приватный ключ → байты
            priv_bytes = priv_int.to_bytes(CONFIG.KEY_BYTES, 'big')

            # 2. Приватный → публичный ключ (secp256k1)
            if not COINCURVE_AVAILABLE:
                return None
            pk = PrivateKey(priv_bytes)
            pub = pk.public_key.format(compressed=CONFIG.COMPRESSED_PUBKEY)

            # 3. SHA256(pubkey)
            sha = self._sha256(pub).digest()

            # 4. RIPEMD160(SHA256) → Hash160 (20 байт)
            ripemd = _hash_pool.acquire()
            ripemd.update(sha)
            hash160 = ripemd.digest()
            _hash_pool.release(ripemd)

            # 5. Base58Check кодирование
            address = self._base58_check_encode(hash160, version_byte=0x00)

            self._generated += 1

            # 6. Проверка совпадения
            if address == self.target:
                self._matches += 1
                logger.warning(f"🎯 MATCH FOUND! priv={priv_int:064x}")

            return address

        except Exception as e:
            logger.debug(f"Address gen error: {e}")
            return None

    def _base58_check_encode(self, payload: bytes, version_byte: int = 0x00) -> str:
        """Base58Check кодирование: [00][hash160][checksum]"""
        # Добавляем версию
        prefixed = bytes([version_byte]) + payload

        # Вычисляем checksum = SHA256(SHA256(prefixed))[:4]
        checksum = hashlib.sha256(hashlib.sha256(prefixed).digest()).digest()[:4]

        # Полный payload для кодирования
        full = prefixed + checksum

        # Base58 кодирование
        alphabet = CONFIG.BASE58_ALPHABET
        n = int.from_bytes(full, 'big')
        b58 = ''
        while n > 0:
            n, rem = divmod(n, 58)
            b58 = alphabet[rem] + b58

        # Добавляем лидирующие '1' для нулевых байт
        leading_zeros = len(full) - len(full.lstrip(b'\x00'))
        return '1' * leading_zeros + b58

    def is_match(self, address: Optional[str]) -> bool:
        return address is not None and address == self.target

    def get_stats(self) -> Dict[str, int]:
        return {"generated": self._generated, "matches": self._matches}


# ═══════════════════════════════════════════════
# 🎲 АДАПТИВНЫЙ МУТАТОР ТРИПЛЕТОВ
# ═══════════════════════════════════════════════

@dataclass
class MutationStats:
    total: int = 0
    in_range: int = 0
    out_of_range: int = 0
    random_jumps: int = 0
    chars_mutated: int = 0
    successful_drifts: int = 0
    _iteration: int = 0
    _last_mutated: Dict[int, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        total = max(1, self.total + self.random_jumps)
        return {
            "operations": total,
            "success_rate": f"{self.in_range / max(1, self.total) * 100:.1f}%",
            "avg_chars": f"{self.chars_mutated / max(1, self.total):.2f}",
            "drifts": f"{self.successful_drifts}/{self.total}"
        }


class TripletMutator:
    """Интеллектуальный мутатор с адаптацией"""

    def __init__(self, min_val: int, max_val: int,
                 strength: float = None,
                 probability: float = None,
                 locked: Optional[Set[int]] = None,
                 adaptive: bool = True):

        self.min_val = min_val
        self.max_val = max_val
        self.strength = strength or CONFIG.MUTATION_STRENGTH
        self.probability = probability or CONFIG.MUTATION_PROBABILITY
        self.locked = locked or set()
        self.adaptive = adaptive

        self.rng = random.SystemRandom()
        self.chars = list(CONFIG.TRIPLET_MAP.values())
        self.stats = MutationStats()

        # "Квантово-вдохновлённые" параметры
        self._current_strength = self.strength
        self._consecutive_failures = 0
        self._phase_offsets: Dict[int, float] = {}

    def mutate(self, base: str, use_quantum: bool = False) -> Tuple[str, List[int]]:
        """Сгенерировать мутированный триплет"""
        self.stats.total += 1
        self.stats._iteration += 1

        chars = list(base)
        n_mutate = max(1, int(len(chars) * self._current_strength))

        # Доступные позиции (исключая заблокированные)
        available = [i for i in range(len(chars))
                     if i not in self.locked
                     and self.stats._iteration - self.stats._last_mutated.get(i, 0) > 3]

        if not available:
            # Полный случайный прыжок
            val = self.rng.randint(self.min_val, self.max_val)
            self.stats.random_jumps += 1
            return TripletConverter.int_to_triplets(val), list(range(len(chars)))

        # Выбираем позиции
        positions = self.rng.sample(available, min(n_mutate, len(available)))

        for pos in positions:
            current = chars[pos]
            choices = [c for c in self.chars if c != current]
            if choices:
                # "Квантовое" влияние фазы на выбор
                if use_quantum and pos in self._phase_offsets:
                    phase = self._phase_offsets[pos]
                    idx = int((phase % 1.0) * len(choices))
                    chars[pos] = choices[idx % len(choices)]
                else:
                    chars[pos] = self.rng.choice(choices)
                self.stats._last_mutated[pos] = self.stats._iteration

        result = ''.join(chars)

        # Проверка диапазона
        try:
            val = TripletConverter.triplets_to_int(result)
            in_range = self.min_val <= val <= self.max_val
        except:
            in_range = False

        if not in_range:
            self.stats.out_of_range += 1
            self.stats._consecutive_failures += 1

            # Адаптивное снижение силы
            if self.adaptive and self.stats._consecutive_failures > 5:
                self._current_strength = max(0.05, self._current_strength * 0.9)
                self.stats._consecutive_failures = 0

            # Случайный перезапуск
            val = self.rng.randint(self.min_val, self.max_val)
            result = TripletConverter.int_to_triplets(val)
            self.stats.random_jumps += 1
        else:
            self.stats.in_range += 1
            self.stats._consecutive_failures = 0
            self.stats.successful_drifts += 1

            # Адаптивное повышение силы
            if self.adaptive and self.stats.in_range % 10 == 0:
                self._current_strength = min(0.5, self._current_strength * 1.05)

        self.stats.chars_mutated += len(positions)
        return result, positions

    def random_in_range(self) -> str:
        """Полностью случайный триплет в диапазоне"""
        val = self.rng.randint(self.min_val, self.max_val)
        self.stats.random_jumps += 1
        return TripletConverter.int_to_triplets(val)

    def update_phase(self, pos: int, phase: float):
        """Обновить фазу для квантового режима"""
        self._phase_offsets[pos] = phase

    def get_stats(self) -> Dict[str, Any]:
        d = self.stats.to_dict()
        d["strength"] = f"{self._current_strength:.3f}"
        d["iteration"] = self.stats._iteration
        return d


# ═══════════════════════════════════════════════
# 🔧 ОБРАБОТКА БАТЧА С ПРОВЕРКОЙ АДРЕСА
# ═══════════════════════════════════════════════

def process_batch(
    triplets: List[str],
    generator: BitcoinAddressGenerator,
    on_found: Optional[Callable[[str, str, str], None]] = None
) -> Tuple[int, List[Dict[str, str]]]:
    """
    Обработать батч триплетов: конвертировать → сгенерировать адрес → проверить.
    Returns: (количество проверенных, список найденных)
    """
    found = []

    for triplet in triplets:
        try:
            priv_int = TripletConverter.triplets_to_int(triplet)
            address = generator.generate(priv_int)

            if generator.is_match(address):
                hex_key = TripletConverter.int_to_hex(priv_int)
                wif = _privkey_to_wif(hex_key) if COINCURVE_AVAILABLE else hex_key
                found.append({
                    "address": address,
                    "hex_key": hex_key,
                    "wif_key": wif,
                    "triplet": triplet
                })
                if on_found:
                    on_found(address, hex_key, wif)

        except Exception as e:
            logger.debug(f"Batch error: {e}")
            continue

    return len(triplets), found


def _privkey_to_wif(hex_key: str) -> str:
    """Конвертировать HEX приватного ключа в WIF (Base58Check)"""
    # Добавляем префикс 0x80 для mainnet
    key_bytes = bytes.fromhex(hex_key)
    prefixed = b'\x80' + key_bytes

    # Добавляем суффикс 0x01 для сжатого публичного ключа (если нужно)
    if CONFIG.COMPRESSED_PUBKEY:
        prefixed += b'\x01'

    # Checksum
    checksum = hashlib.sha256(hashlib.sha256(prefixed).digest()).digest()[:4]
    full = prefixed + checksum

    # Base58
    alphabet = CONFIG.BASE58_ALPHABET
    n = int.from_bytes(full, 'big')
    b58 = ''
    while n > 0:
        n, rem = divmod(n, 58)
        b58 = alphabet[rem] + b58

    leading = len(full) - len(full.lstrip(b'\x00'))
    return '1' * leading + b58


# ═══════════════════════════════════════════════
# 🔧 ВОРКЕР: ПАРАЛЛЕЛЬНЫЙ ПОИСК
# ═══════════════════════════════════════════════

def search_worker(
    worker_id: int,
    min_val: int,
    max_val: int,
    target_address: str,
    queue: multiprocessing.Queue,
    shutdown: multiprocessing.Event,
    mode: str = "random_curve",
    strength: float = None,
    probability: float = None,
    locked: Optional[List[int]] = None,
    quantum: bool = False
):
    """Основной воркер поиска"""

    def send(msg_type: str, data: Dict):
        try:
            queue.put({"type": msg_type, "wid": worker_id, **data},
                     timeout=CONFIG.QUEUE_TIMEOUT)
        except:
            pass

    # Инициализация
    generator = BitcoinAddressGenerator(target_address)
    mutator = TripletMutator(
        min_val, max_val,
        strength=strength,
        probability=probability,
        locked=set(locked) if locked else None,
        adaptive=CONFIG.ADAPTIVE_MODE
    )

    base_triplets = TripletConverter.int_to_triplets((min_val + max_val) // 2)
    batch: List[str] = []

    scanned = 0
    found_count = 0
    start_time = time.time()
    last_stats = start_time

    send("log", {"msg": f"Started [{min_val:064x}...{max_val:064x}]", "level": "info"})

    try:
        while not shutdown.is_set():
            # Выбор стратегии
            if mode == "random_curve" and random.random() < mutator.probability:
                next_trip, _ = mutator.mutate(base_triplets, use_quantum=quantum)
            else:
                next_trip = mutator.random_in_range()

            batch.append(next_trip)

            # Обработка батча
            if len(batch) >= CONFIG.BATCH_SIZE:
                n_processed, found = process_batch(batch, generator)
                scanned += n_processed
                found_count += len(found)

                # Отправка найденных
                for item in found:
                    send("found", item)

                batch.clear()

                # Статистика
                now = time.time()
                if now - last_stats >= CONFIG.STATS_INTERVAL:
                    elapsed = now - last_stats
                    speed = n_processed / elapsed if elapsed > 0 else 0
                    send("stats", {
                        "scanned": scanned,
                        "found": found_count,
                        "speed": f"{speed:.0f} keys/s",
                        "mut_stats": mutator.get_stats() if CONFIG.TRACK_MUTATIONS else None
                    })
                    last_stats = now

            # "Квантовое" обновление фаз
            if quantum and CONFIG.QUANTUM_INSPIRED:
                phase = (mutator.stats._iteration % 100) / 100.0 * 2 * 3.14159
                for pos in range(len(base_triplets)):
                    mutator.update_phase(pos, phase)

        # Финальная обработка
        if batch:
            n_processed, found = process_batch(batch, generator)
            scanned += n_processed
            found_count += len(found)
            for item in found:
                send("found", item)

        # Итоговая статистика
        total_time = max(0.001, time.time() - start_time)
        send("stats", {
            "scanned": scanned,
            "found": found_count,
            "speed": f"{scanned/total_time:.0f} keys/s",
            "final": True
        })
        send("log", {"msg": f"Finished: {scanned:,} keys, {found_count} found", "level": "info"})

    except Exception as e:
        send("log", {"msg": f"ERROR: {e}", "level": "error"})


# ═══════════════════════════════════════════════
# 🔧 ГЛАВНЫЙ КОНТРОЛЛЕР
# ═══════════════════════════════════════════════

class MatrixSearchEngine:
    """Главный интерфейс для запуска поиска"""

    def __init__(self):
        self.processes: Dict[int, multiprocessing.Process] = {}
        self.shutdown = multiprocessing.Event()
        self.queue = multiprocessing.Queue()
        self.running = False
        self.target = ""

    def start(self,
              target_address: str,
              start_hex: str,
              end_hex: str,
              workers: int = 4,
              mode: str = "random_curve",
              strength: float = None,
              quantum: bool = False,
              locked: Optional[List[int]] = None) -> bool:
        """Запустить поиск"""

        if self.running:
            logger.error("Already running")
            return False

        if not COINCURVE_AVAILABLE:
            logger.error("coincurve required: pip install coincurve")
            return False

        # Парсинг диапазона
        try:
            min_val = int(start_hex, 16)
            max_val = int(end_hex, 16)
            if min_val >= max_val:
                raise ValueError("start >= end")
        except Exception as e:
            logger.error(f"Invalid range: {e}")
            return False

        self.target = target_address
        self.shutdown.clear()
        self.running = True

        # Разделение диапазона
        chunk = (max_val - min_val) // workers
        ranges = [(min_val + i*chunk, min_val + (i+1)*chunk if i < workers-1 else max_val)
                  for i in range(workers)]

        # Запуск воркеров
        for wid, (s, e) in enumerate(ranges):
            p = multiprocessing.Process(
                target=search_worker,
                args=(wid, s, e, target_address, self.queue, self.shutdown, mode),
                kwargs={
                    "strength": strength,
                    "locked": locked,
                    "quantum": quantum
                }
            )
            p.daemon = True
            p.start()
            self.processes[wid] = p
            logger.info(f"Worker {wid} started [{s:064x}...{e:064x}]")

        logger.info(f"✅ Search started: {workers} workers, target={target_address[:10]}...")
        return True

    def stop(self, timeout: float = 2.0):
        """Остановить поиск"""
        if not self.running:
            return
        self.shutdown.set()
        for p in self.processes.values():
            if p.is_alive():
                p.join(timeout=timeout)
                if p.is_alive():
                    p.terminate()
        self.processes.clear()
        self.running = False
        logger.info("🛑 Search stopped")

    def poll_queue(self, timeout: float = 0.1) -> Optional[Dict]:
        """Получить сообщение из очереди"""
        try:
            return self.queue.get(timeout=timeout)
        except:
            return None

    def run_loop(self, duration: float = None):
        """Основной цикл обработки сообщений"""
        start = time.time()
        try:
            while self.running:
                if duration and time.time() - start > duration:
                    break

                msg = self.poll_queue()
                if msg:
                    self._handle_message(msg)

                time.sleep(0.01)
        except KeyboardInterrupt:
            logger.info("⏸️ Interrupted")
        finally:
            self.stop()

    def _handle_message(self, msg: Dict):
        """Обработать сообщение от воркера"""
        mtype = msg.get("type")
        wid = msg.get("wid", "?")

        if mtype == "log":
            level = msg.get("level", "info")
            getattr(logger, level, logger.info)(f"[W{wid}] {msg.get('msg')}")

        elif mtype == "stats":
            scanned = msg.get("scanned", 0)
            found = msg.get("found", 0)
            speed = msg.get("speed", "?")
            prefix = "🎯 " if found > 0 else ""
            logger.info(f"{prefix}[W{wid}] Scanned: {scanned:,} | Found: {found} | Speed: {speed}")
            if msg.get("mut_stats"):
                ms = msg["mut_stats"]
                logger.debug(f"        Mutations: {ms.get('operations',0)} | Success: {ms.get('success_rate','?')}")

        elif mtype == "found":
            addr = msg.get("address")
            hex_key = msg.get("hex_key")
            wif = msg.get("wif_key")
            logger.critical(f"🔑 KEY FOUND!")
            logger.critical(f"   Address: {addr}")
            logger.critical(f"   HEX:     {hex_key}")
            logger.critical(f"   WIF:     {wif}")
            # Здесь можно сохранить в файл, отправить уведомление и т.д.

        elif mtype == "worker_finished":
            logger.info(f"[W{wid}] ✅ Finished")


# ═══════════════════════════════════════════════
# 🚀 ПРИМЕР ЗАПУСКА
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    print("\n" + "═" * 70)
    print("🔷 MATRIX SEARCH ENGINE — Поиск приватного ключа Bitcoin")
    print("═" * 70 + "\n")

    # 🎯 Целевой адрес (замените на свой)
    TARGET = "1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU"  # Puzzle #71

    # 📐 Диапазон (Puzzle #71: 2^70 ... 2^71-1)
    START_HEX = "0000000000000000000000000000000000000000000000600000000000000000"
    END_HEX = "00000000000000000000000000000000000000000000006fffffffffffffffff"

    # ⚙️ Параметры
    WORKERS = multiprocessing.cpu_count() // 2 or 2
    MODE = "random_curve"  # random_curve | pure_random | adaptive | quantum_inspired
    STRENGTH = 0.15
    QUANTUM_MODE = False  # Включить "фазовую" логику мутации

    print(f"Target:  {TARGET}")
    print(f"Range:   {START_HEX} → {END_HEX}")
    print(f"Workers: {WORKERS} | Mode: {MODE} | Quantum: {QUANTUM_MODE}")
    print(f"⚠️  Для остановки: Ctrl+C\n")

    # Запуск
    engine = MatrixSearchEngine()

    if not engine.start(
        target_address=TARGET,
        start_hex=START_HEX,
        end_hex=END_HEX,
        workers=WORKERS,
        mode=MODE,
        strength=STRENGTH,
        quantum=QUANTUM_MODE
    ):
        sys.exit(1)

    # Основной цикл
    engine.run_loop()

    print("\n✅ Done.")
#!/usr/bin/env python3
"""Нагрузочный скрипт для POST /process.

Повторяет поведение проверяющей системы: пары «маскирование → демаскирование»
по одному payload_id, keep-alive соединения, разгон и плато.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import multiprocessing
import random
import statistics
import threading
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from queue import Empty
from urllib.parse import urlsplit

DEFAULT_TEXTS = [
    "Иванов Иван Иванович",
    "Петрова Мария Сергеевна",
    "12.03.1985",
    "12 марта 1985 года",
    "место рождения: г. Ленинград",
    "уроженец Казани",
    "паспорт 4509 123456",
    "серия 4509 номер 123456",
    "гражданство: Россия",
    "гражданин Российской Федерации",
    "выдан ОУФМС России по г. Москве",
    "кем выдан: ГУ МВД России по г. Санкт-Петербургу",
    "код подразделения 770-001",
    "дата выдачи 12.05.2015",
    "водительское удостоверение 99 12 345678",
    "ВУ 77 АВ 123456",
    "г. Москва, ул. Ленина, д. 5, кв. 12",
    "123456, г. Саратов, ул. Тверская, д. 10",
    "ivanov@mail.ru",
    "+7 916 123-45-67",
    "8 999 123-45-67",
    "ИНН 500100732259",
    "карта 4276 3801 2345 6789",
    "CVV 123",
    "ПИН-код 4321",
    "держатель IVAN IVANOV",
    "Клиент Иванов Иван Иванович, паспорт 4509 123456, выдан ОУФМС России по г. Москве "
    "01.02.2010, код подразделения 770-001",
    "Карта 4276 3801 2345 6789, CVV 123, держатель IVAN IVANOV, ПИН-код 4321",
    "Адрес: 123456, г. Москва, ул. Ленина, д. 5, кв. 12, телефон +7 999 123-45-67, "
    "email ivanov@mail.ru",
    "Родился 12 марта 1985 года в г. Саратов, гражданство: Россия, ИНН 500100732259",
    "Клиент Петрова Мария Сергеевна, паспорт 4510 654321, выдан Отделом УФМС России по "
    "Московской обл. в Одинцовском р-не 12.05.2015, код подразделения 500-123, "
    "зарегистрирована по адресу: 143000, Московская обл., г. Одинцово, ул. Молодёжная, "
    "д. 7, кв. 45, телефон +7 916 123-45-67, email petrova@mail.ru, ИНН 500100732259, "
    "карта 4276 3801 2345 6789, CVV 123, ПИН-код 4321, держатель PETROVA MARIA",
    "Водительское удостоверение 99 12 345678 выдано 12.05.2015, гражданство: Российская "
    "Федерация, место рождения: г. Саратов, дата рождения 12 марта 1985 года, адрес "
    "регистрации: г. Москва, ул. Ленина, д. 5, кв. 12, телефон +7 999 123-45-67",
]

_BIG_SENTENCE = (
    "Клиент Иванов Иван Иванович, паспорт 4509 123456, выдан ОУФМС России по г. Москве "
    "01.02.2010, код подразделения 770-001, адрес: г. Москва, ул. Ленина, д. 5, кв. 12, "
    "телефон +7 999 123-45-67, email ivanov@mail.ru, ИНН 500100732259. "
)
BIG_TEXT = _BIG_SENTENCE * 30

WINDOW_SECONDS = 10
MAX_ATTEMPTS = 3


@dataclass(frozen=True, slots=True)
class RunConfig:
    host: str
    port: int
    path: str
    ramp: float
    steady: float
    request_timeout: float
    big_share: float
    retry_after_default: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Нагрузочный тест POST /process")
    parser.add_argument("url", help="Базовый URL сервиса, например http://host:port")
    parser.add_argument("--conns", type=int, default=200, help="Число соединений")
    parser.add_argument("--procs", type=int, default=4, help="Число процессов")
    parser.add_argument("--ramp", type=float, default=20, help="Разгон, секунд")
    parser.add_argument("--steady", type=float, default=60, help="Плато, секунд")
    parser.add_argument("--big-share", type=float, default=0.0, help="Доля больших текстов")
    parser.add_argument("--timeout", type=float, default=10, help="Таймаут запроса, секунд")
    parser.add_argument("--json", dest="json_out", help="Путь к JSON-файлу с итогом")
    return parser.parse_args()


def build_request(path: str, host: str, port: int, payload: str, payload_id: str) -> bytes:
    body = json.dumps({"payload": payload, "payload_id": payload_id}).encode("utf-8")
    head = (
        f"POST {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: keep-alive\r\n"
        "\r\n"
    ).encode("ascii")
    return head + body


async def read_response(reader: asyncio.StreamReader) -> tuple[int, dict[str, str], bytes]:
    status_line = await reader.readline()
    if not status_line:
        raise ConnectionError("connection closed")
    parts = status_line.decode("latin-1").split(" ", 2)
    status = int(parts[1])
    headers: dict[str, str] = {}
    while True:
        line = await reader.readline()
        if line in (b"\r\n", b"\n", b""):
            break
        name, _, value = line.decode("latin-1").partition(":")
        headers[name.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    body = await reader.readexactly(length) if length else b""
    return status, headers, body


class HttpConn:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None

    async def connect(self) -> None:
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)

    async def reconnect(self) -> None:
        await self.close()
        await self.connect()

    async def close(self) -> None:
        if self.writer is not None:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except OSError:
                pass
            self.writer = None
            self.reader = None

    async def request(self, body: bytes) -> tuple[int, dict[str, str], bytes]:
        if self.writer is None or self.reader is None:
            await self.connect()
        writer = self.writer
        reader = self.reader
        if writer is None or reader is None:
            raise ConnectionError("connection not established")
        writer.write(body)
        await writer.drain()
        status, headers, resp_body = await read_response(reader)
        if headers.get("connection", "").lower() == "close":
            await self.reconnect()
        return status, headers, resp_body


def parse_retry_after(headers: dict[str, str], default: float) -> float:
    value = headers.get("retry-after")
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def parse_result(body: bytes) -> str | None:
    try:
        data = json.loads(body)
        result = data.get("result")
        return result if isinstance(result, str) else None
    except (ValueError, AttributeError):
        return None


def pick_text(rng: random.Random, big_share: float) -> str:
    if big_share > 0 and rng.random() < big_share:
        return BIG_TEXT
    return rng.choice(DEFAULT_TEXTS)


async def post(
    conn: HttpConn,
    config: RunConfig,
    payload: str,
    payload_id: str,
    queue: multiprocessing.Queue,
) -> tuple[int, bytes]:
    body = build_request(config.path, config.host, config.port, payload, payload_id)
    last_status = 0
    for _ in range(MAX_ATTEMPTS):
        started = time.perf_counter()
        try:
            async with asyncio.timeout(config.request_timeout):
                status, headers, resp_body = await conn.request(body)
            latency = (time.perf_counter() - started) * 1000
            queue.put((time.time(), latency, status))
            last_status = status
            if status == 429:
                await asyncio.sleep(parse_retry_after(headers, config.retry_after_default))
                continue
            return status, resp_body
        except (asyncio.IncompleteReadError, OSError):
            latency = (time.perf_counter() - started) * 1000
            queue.put((time.time(), latency, 0))
            try:
                await conn.reconnect()
            except OSError:
                return 0, b""
            continue
    return last_status, b""


async def run_connection(
    config: RunConfig,
    start_delay: float,
    queue: multiprocessing.Queue,
    rng: random.Random,
) -> None:
    loop_start = time.monotonic()
    end_time = loop_start + config.ramp + config.steady
    if start_delay > 0:
        await asyncio.sleep(start_delay)
    conn = HttpConn(config.host, config.port)
    while time.monotonic() < end_time:
        try:
            await conn.connect()
            break
        except OSError:
            await asyncio.sleep(0.5)
    try:
        while time.monotonic() < end_time:
            text = pick_text(rng, config.big_share)
            payload_id = uuid.uuid4().hex
            status, masked = await post(conn, config, text, payload_id, queue)
            if status != 200:
                continue
            result = parse_result(masked)
            if result is None:
                continue
            status2, demasked = await post(conn, config, result, payload_id, queue)
            if status2 == 200:
                restored = parse_result(demasked)
                if restored is not None and restored != text:
                    queue.put(("discrepancy", text, restored))
    finally:
        await conn.close()


async def run_process(
    config: RunConfig,
    conns: int,
    queue: multiprocessing.Queue,
    start_offset: int,
    total_conns: int,
    rng: random.Random,
) -> None:
    tasks = []
    for j in range(conns):
        global_index = start_offset + j
        start_delay = (global_index / total_conns) * config.ramp
        tasks.append(asyncio.create_task(run_connection(config, start_delay, queue, rng)))
    await asyncio.gather(*tasks)


def worker_main(
    config: RunConfig,
    conns: int,
    queue: multiprocessing.Queue,
    start_offset: int,
    total_conns: int,
) -> None:
    rng = random.Random()
    asyncio.run(run_process(config, conns, queue, start_offset, total_conns, rng))


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(len(ordered) * p / 100))
    return ordered[idx]


def format_codes(codes: Counter) -> str:
    return ", ".join(f"{code}: {count}" for code, count in sorted(codes.items()))


def aggregate(
    records: list[tuple[float, float, int]],
    discrepancies: int,
    test_start: float,
    ramp: float,
    steady: float,
) -> dict:
    records.sort(key=lambda r: r[0])
    windows: dict[int, list[tuple[float, int]]] = {}
    for end_time, latency, status in records:
        window = int((end_time - test_start) / WINDOW_SECONDS)
        windows.setdefault(window, []).append((latency, status))

    print("Окно (с)      RPS      p50      p95      p99   коды")
    for window in sorted(windows):
        items = windows[window]
        latencies = [latency for latency, _ in items]
        codes = Counter(status for _, status in items)
        duration = WINDOW_SECONDS
        rps = len(items) / duration
        print(
            f"{window * WINDOW_SECONDS:>4}-{window * WINDOW_SECONDS + WINDOW_SECONDS:<4}"
            f"{rps:>9.1f}{percentile(latencies, 50):>9.1f}"
            f"{percentile(latencies, 95):>9.1f}{percentile(latencies, 99):>9.1f}"
            f"   {format_codes(codes)}"
        )

    total = len(records)
    codes = Counter(status for _, _, status in records)
    print(
        f"Итого: запросов {total}, коды {{{format_codes(codes)}}}, "
        f"расхождений демаскирования: {discrepancies}"
    )

    plateau_start = test_start + ramp
    plateau_end = test_start + ramp + steady
    plateau = [r for r in records if plateau_start <= r[0] < plateau_end]
    plateau_latencies = [latency for _, latency, _ in plateau]
    plateau_codes = Counter(status for _, _, status in plateau)
    success = plateau_codes.get(200, 0)
    success_rate = success / len(plateau) if plateau else 0.0
    plateau_rps = len(plateau) / steady if steady else 0.0
    mean = statistics.mean(plateau_latencies) if plateau_latencies else 0.0
    print(
        f"Плато: RPS {plateau_rps:.1f}, среднее {mean:.1f} мс, "
        f"p50 {percentile(plateau_latencies, 50):.1f}, "
        f"p95 {percentile(plateau_latencies, 95):.1f}, "
        f"p99 {percentile(plateau_latencies, 99):.1f}, "
        f"max {max(plateau_latencies, default=0.0):.1f}, успешных {success_rate * 100:.1f}%"
    )

    return {
        "total_requests": total,
        "codes": {str(code): count for code, count in sorted(codes.items())},
        "discrepancies": discrepancies,
        "plateau": {
            "rps": round(plateau_rps, 1),
            "mean_ms": round(mean, 1),
            "p50_ms": round(percentile(plateau_latencies, 50), 1),
            "p95_ms": round(percentile(plateau_latencies, 95), 1),
            "p99_ms": round(percentile(plateau_latencies, 99), 1),
            "max_ms": round(max(plateau_latencies, default=0.0), 1),
            "success_rate": round(success_rate, 4),
        },
    }


def _launch_workers(
    ctx: multiprocessing.context.BaseContext,
    config: RunConfig,
    conns: int,
    procs: int,
    queue: multiprocessing.Queue,
) -> list[multiprocessing.process.BaseProcess]:
    base = conns // procs
    extra = conns % procs
    workers: list[multiprocessing.process.BaseProcess] = []
    offset = 0
    for p in range(procs):
        n = base + (1 if p < extra else 0)
        proc = ctx.Process(target=worker_main, args=(config, n, queue, offset, conns))
        proc.start()
        workers.append(proc)
        offset += n
    return workers


def _drain_results(
    queue: multiprocessing.Queue,
    procs: list[multiprocessing.process.BaseProcess],
) -> tuple[list[tuple[float, float, int]], int]:
    records: list[tuple[float, float, int]] = []
    discrepancies = 0
    lock = threading.Lock()

    def drain() -> None:
        nonlocal discrepancies
        while True:
            try:
                item = queue.get(timeout=0.5)
            except Empty:
                if all(not proc.is_alive() for proc in procs):
                    break
                continue
            with lock:
                if item[0] == "discrepancy":
                    discrepancies += 1
                else:
                    records.append(item)

    drainer = threading.Thread(target=drain, daemon=True)
    drainer.start()
    for proc in procs:
        proc.join()
    drainer.join()
    return records, discrepancies


def main() -> None:
    args = parse_args()
    parts = urlsplit(args.url)
    host = parts.hostname or "localhost"
    port = parts.port or 80
    path = parts.path or "/process"
    if not path.startswith("/"):
        path = "/" + path

    config = RunConfig(
        host=host,
        port=port,
        path=path,
        ramp=args.ramp,
        steady=args.steady,
        request_timeout=args.timeout,
        big_share=args.big_share,
        retry_after_default=1,
    )

    ctx = multiprocessing.get_context("spawn")
    queue: multiprocessing.Queue = ctx.Queue()
    test_start = time.time()

    procs = _launch_workers(ctx, config, args.conns, args.procs, queue)
    records, discrepancies = _drain_results(queue, procs)

    summary = aggregate(records, discrepancies, test_start, args.ramp, args.steady)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

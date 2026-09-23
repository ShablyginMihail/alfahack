from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

from eval.pii_bench_metrics import (
    aggregate_domain_docs,
    aggregate_entity_docs,
    entity_status,
    parse_entities,
    time_stats,
    wilson_interval,
)
from pii_guard.config.loader import ConfigStore
from pii_guard.settings import Settings

REPO_ID = "hivetrace/pii-bench"
DATA_FILES = {
    "domain": "data/domain-00000-of-00001.parquet",
    "entity": "data/entity-00000-of-00001.parquet",
}
IN_SCOPE = frozenset(
    {
        "NAME",
        "PHONE_NUMBER",
        "EMAIL",
        "ADDRESS",
        "BANK_CARD_NUMBER",
        "CVC",
        "INN",
        "SNILS",
        "PASSPORT_NUMBER",
    }
)


def build_ml_stage() -> object:
    from pii_guard.core.ml_stage import MlStage
    from pii_guard.ml.model import TransformersNerModel
    from pii_guard.ml.recognizer import NerRecognizer

    model = TransformersNerModel(
        os.environ.get("PII_NER_MODEL", "LLAIMlegal/ru-legal-ner"),
        threads=int(os.environ.get("PII_NER_THREADS", "1")),
    )
    stage = MlStage(
        NerRecognizer(model),
        max_chars=int(os.environ.get("PII_NER_MAX_CHARS", "2000")),
        concurrency=int(os.environ.get("PII_NER_CONCURRENCY", "1")),
        wait_ms=int(os.environ.get("PII_NER_WAIT_MS", "20")),
    )
    stage.warm_up()
    return stage


def download_data(data_dir: Path) -> dict[str, Path]:
    data_dir.mkdir(parents=True, exist_ok=True)
    return {
        key: Path(
            hf_hub_download(
                repo_id=REPO_ID, filename=filename, repo_type="dataset", local_dir=data_dir
            )
        )
        for key, filename in DATA_FILES.items()
    }


def load_rows(path: Path) -> list[dict]:
    return pq.read_table(path).to_pylist()


def masked_positions(spans) -> set[int]:
    return {i for span in spans for i in range(span.start, span.end)}


def run_config(engine, profile, entity_rows: list[dict], domain_rows: list[dict]) -> dict:
    entity_docs, domain_docs, times = [], [], []
    for rows in (entity_rows, domain_rows):
        for row in rows:
            text = row["text"]
            entities = [e for e in parse_entities(row["entities"]) if e.type in IN_SCOPE]
            start = time.perf_counter()
            spans = engine.analyze(text, profile)
            times.append((time.perf_counter() - start) * 1000)
            masked = masked_positions(spans)
            if entities:
                statuses = [entity_status(text, e.start, e.end, masked) for e in entities]
                entity_docs.append((entities, statuses))
            elif not parse_entities(row["entities"]):
                domain_docs.append(bool(spans))
    per_type, leak_docs, total_docs = aggregate_entity_docs(entity_docs)
    fp_docs, total_domain = aggregate_domain_docs(domain_docs)
    time_mean, time_p95 = time_stats(times)
    return {
        "per_type": per_type,
        "leak": leak_docs,
        "total": total_docs,
        "fp": fp_docs,
        "total_domain": total_domain,
        "time_mean": time_mean,
        "time_p95": time_p95,
    }


def _ci(k: int, n: int) -> str:
    lo, hi = wilson_interval(k, n)
    return f"{k}/{n} ({lo:.3f}–{hi:.3f})"


def render_report(results: dict) -> str:
    lines = ["# Оценка на внешнем наборе hivetrace/pii-bench", "", "## Сводка", ""]
    lines.append(
        "| Конфигурация | Документов | Утечка (95% CI) | Ложные срабатывания (95% CI) | "
        "Время analyze, мс |"
    )
    lines.append("|---|---|---|---|---|")
    for name, res in results.items():
        lines.append(
            f"| {name} | {res['total']} | {_ci(res['leak'], res['total'])} | "
            f"{_ci(res['fp'], res['total_domain'])} | "
            f"{res['time_mean']:.2f} / p95 {res['time_p95']:.2f} |"
        )
    for name, res in results.items():
        lines += ["", f"## По типам — {name}", ""]
        lines.append("| Тип | Закрыто | Частично | Пропущено | Всего |")
        lines.append("|---|---|---|---|---|")
        for pii_type in sorted(res["per_type"]):
            stats = res["per_type"][pii_type]
            total = stats["closed"] + stats["partial"] + stats["missed"]
            lines.append(
                f"| {pii_type} | {stats['closed']} | {stats['partial']} | "
                f"{stats['missed']} | {total} |"
            )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Оценка на внешнем наборе hivetrace/pii-bench")
    parser.add_argument("--data", default="eval/data", help="каталог для данных датасета")
    parser.add_argument("--report", default="eval/out/pii_bench.md")
    parser.add_argument("--ner", action="store_true", help="включить NER-модель")
    args = parser.parse_args()

    paths = download_data(Path(args.data))
    entity_rows = load_rows(paths["entity"])
    domain_rows = load_rows(paths["domain"])

    settings = Settings()
    config_dir = Path(settings.config_dir)
    results: dict[str, dict] = {}

    def run(name: str, ml: object | None = None) -> None:
        store = ConfigStore(config_dir, settings.recognizer_modules, ml=ml)
        config, engine = store.current()
        results[name] = run_config(engine, config.profiles()["checker"], entity_rows, domain_rows)

    run("правила")
    if args.ner:
        run("правила + NER", build_ml_stage())

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(results), encoding="utf-8")

    for name, res in results.items():
        print(
            f"{name}: утечка {res['leak']}/{res['total']}, "
            f"ложные {res['fp']}/{res['total_domain']}, "
            f"время {res['time_mean']:.2f} мс / p95 {res['time_p95']:.2f} мс"
        )
    print(f"Отчёт: {report_path}")


if __name__ == "__main__":
    main()

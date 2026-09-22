from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path

from rapidfuzz.distance import Levenshtein

from eval.markup import GoldSpan, parse_markup
from pii_guard.core.demasking import unmask
from pii_guard.core.engine import Engine
from pii_guard.core.masking import DefaultMasker
from pii_guard.core.models import MappingRecord, Span
from pii_guard.core.policy import CHECKER_PROFILE, Profile
from pii_guard.core.registry import RecognizerRegistry
from pii_guard.core.types import default_type_registry
from pii_guard.settings import Settings


def _profile(name: str) -> Profile:
    if name == "strict":
        return Profile(name="strict", strict=True)
    return CHECKER_PROFILE


def _engine() -> Engine:
    registry = RecognizerRegistry.from_modules(Settings().recognizer_modules)
    return Engine(registry, DefaultMasker(default_type_registry()))


def load_golden(paths: list[str]) -> list[tuple[str, list[GoldSpan], str]]:
    phrases: list[tuple[str, list[GoldSpan], str]] = []
    for path in paths:
        category = "general"
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                category = line[1:].strip().lower()
                continue
            text, spans = parse_markup(line)
            phrases.append((text, spans, category))
    return phrases


def expected_mask(
    text: str,
    gold: list[GoldSpan],
    masker: DefaultMasker,
    profile: Profile,
    found_spans: list[Span],
) -> str:
    ordered = sorted(gold, key=lambda s: s.start)
    found_by_pos = {(s.start, s.end, s.pii_type): s for s in found_spans}
    spans = []
    for s in ordered:
        part = None
        found = found_by_pos.get((s.start, s.end, s.pii_type))
        if found is not None:
            part = found.part
        spans.append(Span(s.start, s.end, s.pii_type, 1.0, "gold", part=part))
    return masker.apply(text, spans, profile).text


def build_output(text: str, replacements) -> tuple[str, dict[int, int]]:
    ordered = sorted(replacements, key=lambda r: r.start)
    out_chars: list[str] = []
    orig_to_out: dict[int, int] = {}
    cursor = 0
    for r in ordered:
        for i in range(cursor, r.start):
            orig_to_out[i] = len(out_chars)
            out_chars.append(text[i])
        for k in range(len(r.masked)):
            orig_to_out[r.start + k] = len(out_chars)
            out_chars.append(r.masked[k])
        cursor = r.end
    for i in range(cursor, len(text)):
        orig_to_out[i] = len(out_chars)
        out_chars.append(text[i])
    return "".join(out_chars), orig_to_out


def leaked_count(text: str, replacements, gold: GoldSpan) -> tuple[int, int, int]:
    out, orig_to_out = build_output(text, replacements)
    covered = set()
    for r in replacements:
        for p in range(r.start, r.end):
            covered.add(p)
    total = 0
    leak = 0
    visible = 0
    for p in range(gold.start, gold.end):
        if not text[p].isalnum():
            continue
        total += 1
        if p not in covered:
            leak += 1
        elif p in orig_to_out and out[orig_to_out[p]].isalnum():
            visible += 1
    return leak, visible, total


def _overlap(a: Span, b: GoldSpan) -> bool:
    return a.start < b.end and a.end > b.start


def _exact(a: Span, b: GoldSpan) -> bool:
    return a.start == b.start and a.end == b.end


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(len(ordered) * p / 100))
    return ordered[idx]


def _new_type_stats() -> dict:
    return {
        "gold": 0,
        "pred": 0,
        "exact_tp": 0,
        "inter_tp": 0,
        "leak": 0,
        "visible": 0,
        "leak_total": 0,
        "misses": [],
        "fp": [],
    }


def _update_type_stats(
    stats: dict, text: str, golds: list[GoldSpan], preds: list[Span], replacements
) -> None:
    stats["gold"] += len(golds)
    stats["pred"] += len(preds)
    for p in preds:
        if any(_exact(p, g) for g in golds):
            stats["exact_tp"] += 1
        if any(_overlap(p, g) for g in golds):
            stats["inter_tp"] += 1
        else:
            stats["fp"].append((text, p.start, p.end))
    for g in golds:
        if not any(_overlap(p, g) for p in preds):
            stats["misses"].append((text, g.start, g.end))
        leak, visible, total = leaked_count(text, replacements, g)
        stats["leak"] += leak
        stats["visible"] += visible
        stats["leak_total"] += total


def _update_phrase(per_type: dict, text: str, gold: list[GoldSpan], result) -> None:
    pred_by_type: dict[str, list[Span]] = defaultdict(list)
    for span in result.replacements:
        pred_by_type[span.pii_type].append(Span(span.start, span.end, span.pii_type, 1.0, "pred"))
    gold_by_type: dict[str, list[GoldSpan]] = defaultdict(list)
    for g in gold:
        gold_by_type[g.pii_type].append(g)
    for pii_type in set(gold_by_type) | set(pred_by_type):
        stats = per_type[pii_type]
        _update_type_stats(
            stats,
            text,
            gold_by_type.get(pii_type, []),
            pred_by_type.get(pii_type, []),
            result.replacements,
        )


def evaluate(phrases, profile: Profile) -> dict:
    engine = _engine()
    masker = DefaultMasker(default_type_registry())
    per_type: dict[str, dict] = defaultdict(_new_type_stats)
    similarities: list[float] = []
    roundtrip_ok = 0
    trap_fp = 0
    trap_total = 0
    times: list[float] = []

    for text, gold, category in phrases:
        start = time.perf_counter()
        result = engine.mask(text, profile)
        times.append((time.perf_counter() - start) * 1000)

        found_spans = engine.analyze(text, profile)
        expected = expected_mask(text, gold, masker, profile, found_spans)
        similarities.append(1 - Levenshtein.normalized_distance(result.text, expected))

        if unmask(result.text, MappingRecord("fp", result.text, result.replacements)) == text:
            roundtrip_ok += 1

        if category == "traps":
            trap_total += 1
            if result.replacements:
                trap_fp += 1

        _update_phrase(per_type, text, gold, result)

    return {
        "phrases": len(phrases),
        "per_type": dict(per_type),
        "similarity": statistics.mean(similarities) if similarities else 0.0,
        "roundtrip": roundtrip_ok / len(phrases) if phrases else 0.0,
        "trap_fp": trap_fp / trap_total if trap_total else 0.0,
        "time_mean": statistics.mean(times) if times else 0.0,
        "time_p95": _percentile(times, 95) if times else 0.0,
    }


def _type_rows(per_type: dict) -> list[dict]:
    rows = []
    for pii_type, stats in sorted(per_type.items()):
        exact_p = stats["exact_tp"] / stats["pred"] if stats["pred"] else 0.0
        exact_r = stats["exact_tp"] / stats["gold"] if stats["gold"] else 0.0
        inter_p = stats["inter_tp"] / stats["pred"] if stats["pred"] else 0.0
        inter_r = stats["inter_tp"] / stats["gold"] if stats["gold"] else 0.0
        leak = stats["leak"] / stats["leak_total"] if stats["leak_total"] else 0.0
        visible = stats["visible"] / stats["leak_total"] if stats["leak_total"] else 0.0
        rows.append(
            {
                "type": pii_type,
                "exact_p": exact_p,
                "exact_r": exact_r,
                "exact_f1": _f1(exact_p, exact_r),
                "inter_p": inter_p,
                "inter_r": inter_r,
                "inter_f1": _f1(inter_p, inter_r),
                "leak": leak,
                "visible": visible,
                "misses": stats["misses"][:5],
                "fp": stats["fp"][:5],
            }
        )
    return rows


def render_report(results: dict) -> str:
    rows = _type_rows(results["per_type"])
    lines = ["# Отчёт оценки", ""]
    lines.append("## Сводка")
    lines.append("")
    lines.append(f"- Фраз: {results['phrases']}")
    lines.append(f"- Схожесть маски: {results['similarity']:.4f}")
    lines.append(f"- Roundtrip: {results['roundtrip']:.4f}")
    lines.append(f"- Ложные срабатывания на ловушках: {results['trap_fp']:.4f}")
    lines.append(
        f"- Время на фразу: среднее {results['time_mean']:.2f} мс, p95 {results['time_p95']:.2f} мс"
    )
    lines.append("")
    lines.append("## По типам")
    lines.append("")
    lines.append(
        "| Тип | P (точн.) | R (точн.) | F1 (точн.) | P (перес.) | R (перес.) | F1 (перес.) "
        "| Утечка | Видимо |"
    )
    lines.append("|-----|-----|-----|-----|-----|-----|-----|-----|-----|")
    for row in rows:
        lines.append(
            f"| {row['type']} | {row['exact_p']:.3f} | {row['exact_r']:.3f} "
            f"| {row['exact_f1']:.3f} "
            f"| {row['inter_p']:.3f} | {row['inter_r']:.3f} | {row['inter_f1']:.3f} "
            f"| {row['leak']:.3f} | {row['visible']:.3f} |"
        )
    lines.append("")
    lines.append("## Промахи")
    lines.append("")
    for row in rows:
        if not row["misses"]:
            continue
        lines.append(f"### {row['type']}")
        for text, start, end in row["misses"]:
            lines.append(f"- «{text}» — пропущен фрагмент [{start}:{end}]")
        lines.append("")
    lines.append("## Ложные срабатывания")
    lines.append("")
    for row in rows:
        if not row["fp"]:
            continue
        lines.append(f"### {row['type']}")
        for text, start, end in row["fp"]:
            lines.append(f"- «{text}» — найден фрагмент [{start}:{end}]")
        lines.append("")
    return "\n".join(lines)


def summary_json(results: dict) -> dict:
    return {
        "phrases": results["phrases"],
        "similarity": results["similarity"],
        "roundtrip": results["roundtrip"],
        "trap_fp": results["trap_fp"],
        "time_mean_ms": results["time_mean"],
        "time_p95_ms": results["time_p95"],
        "types": _type_rows(results["per_type"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Оценка качества маскирования")
    parser.add_argument("--data", nargs="+", default=["eval/golden.txt"])
    parser.add_argument("--profile", choices=["checker", "strict"], default="checker")
    parser.add_argument("--report", default="eval/out/report.md")
    args = parser.parse_args()

    phrases = load_golden(args.data)
    results = evaluate(phrases, _profile(args.profile))

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(results), encoding="utf-8")

    summary_path = report_path.parent / "summary.json"
    summary_path.write_text(
        json.dumps(summary_json(results), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Фраз: {results['phrases']}")
    print(f"Схожесть маски: {results['similarity']:.4f}")
    print(f"Roundtrip: {results['roundtrip']:.4f}")
    print(f"Ложные срабатывания на ловушках: {results['trap_fp']:.4f}")
    print(f"Отчёт: {report_path}")


if __name__ == "__main__":
    main()

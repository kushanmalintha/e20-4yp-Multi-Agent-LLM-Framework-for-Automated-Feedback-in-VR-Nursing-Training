from __future__ import annotations

from collections import Counter
from typing import Iterable, Sequence


def safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def precision(tp: int, fp: int) -> float:
    return safe_divide(tp, tp + fp)


def recall(tp: int, fn: int) -> float:
    return safe_divide(tp, tp + fn)


def f1_score(precision_value: float, recall_value: float) -> float:
    return safe_divide(2 * precision_value * recall_value, precision_value + recall_value)


def verdict_accuracy(expected: Sequence[str], predicted: Sequence[str]) -> float:
    if not expected:
        return 0.0
    correct = sum(1 for exp, pred in zip(expected, predicted) if exp == pred)
    return correct / len(expected)


def binary_classification_metrics(expected: Iterable[bool], predicted: Iterable[bool]) -> dict[str, float]:
    tp = fp = fn = tn = 0

    for exp, pred in zip(expected, predicted):
        if pred and exp:
            tp += 1
        elif pred and not exp:
            fp += 1
        elif not pred and exp:
            fn += 1
        else:
            tn += 1

    p = precision(tp, fp)
    r = recall(tp, fn)
    f1 = f1_score(p, r)

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": p,
        "recall": r,
        "f1": f1,
    }


def majority_vote(values: Sequence[str]) -> str:
    if not values:
        return ""
    counts = Counter(values)
    top_count = max(counts.values())
    winners = sorted(value for value, count in counts.items() if count == top_count)
    return winners[0]


def consistency_rate(values: Sequence[str]) -> float:
    if not values:
        return 0.0
    majority = majority_vote(values)
    agreeing = sum(1 for value in values if value == majority)
    return agreeing / len(values)


def confusion_matrix(
    expected: Sequence[str],
    predicted: Sequence[str],
    labels: Sequence[str],
) -> list[list[int]]:
    index_by_label = {label: idx for idx, label in enumerate(labels)}
    matrix = [[0 for _ in labels] for _ in labels]

    for exp, pred in zip(expected, predicted):
        if exp not in index_by_label or pred not in index_by_label:
            continue
        matrix[index_by_label[exp]][index_by_label[pred]] += 1

    return matrix

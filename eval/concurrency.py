"""Small bounded-concurrency helpers for offline evaluation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Callable, Iterable
from typing import TypeVar, cast

T = TypeVar("T")
R = TypeVar("R")


def map_bounded(
    items: Iterable[T],
    function: Callable[[T], R],
    *,
    max_workers: int,
    on_complete: Callable[[int, T, R], None] | None = None,
) -> list[R]:
    """Evaluate independent items concurrently and return results in input order."""
    if max_workers < 1:
        raise ValueError("max_workers must be positive")

    values = list(items)
    if not values:
        return []
    if max_workers == 1:
        results = []
        for index, value in enumerate(values):
            result = function(value)
            results.append(result)
            if on_complete is not None:
                on_complete(index, value, result)
        return results

    results: list[R | None] = [None] * len(values)
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="rag-eval") as pool:
        futures = {pool.submit(function, value): index for index, value in enumerate(values)}
        for future in as_completed(futures):
            index = futures[future]
            result = future.result()
            results[index] = result
            if on_complete is not None:
                on_complete(index, values[index], result)
    return cast(list[R], results)

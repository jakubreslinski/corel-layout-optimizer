"""Benchmark the optimizer against saved layouts from the training folder."""

import statistics
import time
from collections import defaultdict
from pathlib import Path

from main import PARAMETER_RESULTS_PATH
from new_optimizer import run_genetic_algorithm_auto
from parameter_search.search import SEED, load_training_cases, split_train_test

TRAINING_DIR = Path(__file__).resolve().parent / "data" / "training"
PROGRESS_EVERY = 10
MIN_ITEMS = 30
SUBSET = "test"


def print_stats(label, times, deltas, failed):
    print(
        f"{label} | done: {len(times)} | failed: {failed} | "
        f"avg time: {statistics.mean(times):.3f}s | "
        f"avg diff vs saved: {statistics.mean(deltas):+.2f}%"
    )


def run_benchmark():
    cases = load_training_cases(TRAINING_DIR)
    if not cases:
        print(f"No JSON files found in {TRAINING_DIR}")
        return

    train, test = split_train_test(cases)
    selected = {"test": test, "train": train, "all": test + train}[SUBSET]
    selected = [case for case in selected if len(case["items"]) > MIN_ITEMS]
    skipped = len({c["case_id"] for c in cases}) - len(selected)

    print(
        f"Loaded {len(cases)} layouts (train={len(train)}, test={len(test)}); "
        f"running subset '{SUBSET}' with > {MIN_ITEMS} items: {len(selected)} layouts\n"
    )
    if not selected:
        print("Nothing to run.")
        return

    times = []
    deltas = []  # percent difference; negative = better (shorter) than saved
    by_category = defaultdict(list)
    better = worse = equal = failed = 0

    for index, case in enumerate(selected, start=1):
        items = case["items"]
        machine_width = case["machine_width"]
        saved_height = case["target_height"]
        name = case["case_id"]
        try:
            if not items or saved_height <= 0:
                raise ValueError("empty layout or invalid saved height")

            started = time.perf_counter()
            height, _packer = run_genetic_algorithm_auto(
                items,
                machine_width,
                str(PARAMETER_RESULTS_PATH),
                seed=SEED,
                packer="skyline",
            )
            elapsed = time.perf_counter() - started
        except Exception as error:
            failed += 1
            print(f"[{index}/{len(selected)}] FAILED {name}: {error!r}")
            continue

        delta = (height - saved_height) / saved_height * 100
        times.append(elapsed)
        deltas.append(delta)
        by_category[case["size_category"]].append(delta)

        if delta < -1e-9:
            better += 1
        elif delta > 1e-9:
            worse += 1
        else:
            equal += 1

        print(
            f"[{index}/{len(selected)}] {name} ({case['size_category']}): {len(items)} items, "
            f"saved={saved_height:.1f}mm, new={height:.1f}mm, "
            f"diff={delta:+.2f}%, time={elapsed:.3f}s"
        )

        if len(times) % PROGRESS_EVERY == 0:
            print_stats("  >> PROGRESS", times, deltas, failed)

    print("\n" + "=" * 70)
    print(f"Subset: {SUBSET} | skipped (not selected or <= {MIN_ITEMS} items): {skipped}")
    if not times:
        print(f"No layouts were processed successfully (failed: {failed}).")
        return

    print_stats("FINAL", times, deltas, failed)
    print(f"Total time: {sum(times):.2f}s")
    print(f"Better than saved: {better} | equal: {equal} | worse: {worse}")
    print(f"Median diff: {statistics.median(deltas):+.2f}%")
    print(f"Best: {min(deltas):+.2f}% | worst: {max(deltas):+.2f}%")
    for category in ("short", "medium", "tall"):
        values = by_category.get(category)
        if values:
            print(
                f"  {category:<6} n={len(values):<3} avg={statistics.mean(values):+.2f}% "
                f"median={statistics.median(values):+.2f}% worst={max(values):+.2f}%"
            )
    print("(negative % = new result is shorter, i.e. better, than the saved one)")


if __name__ == "__main__":
    run_benchmark()
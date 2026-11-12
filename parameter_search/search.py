"""Parameter search against saved AI-training layouts."""

from __future__ import annotations

import json
import time
import random
from pathlib import Path
from typing import Any

import optuna

from new_optimizer.benchmark import run_genetic_algorithm
from new_optimizer.genetic_algorithm import StackOption

SIZE_CATEGORIES = ("short", "medium", "tall")

SEED = 7
SPLIT_SEED = 7

def load_items(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Items in original orientation, sorted by name, with unique IDs."""
    items = []
    for element in elements:
        w, h = float(element["w"]), float(element["h"])
        if element.get("obrocony"):
            w, h = h, w  # saved dims are rotated, swap back
        name = element.get("nazwa", element.get("id", "item"))
        items.append({
            "nazwa": name,
            "base_id": element.get("id", name),
            "typ": element.get("typ", "unknown"),
            "w": w,
            "h": h,
        })
    items.sort(key=lambda item: item["nazwa"])
    return [
        {"id": f"{item['base_id']} [{index}]", "nazwa": item["nazwa"],
         "typ": item["typ"], "w": item["w"], "h": item["h"]}
        for index, item in enumerate(items, 1)
    ]


def load_training_cases(directory: str | Path) -> list[dict[str, Any]]:
    """Load saved layouts"""
    directory = Path(directory)
    cases = []
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        items = load_items(data.get("elementy", []))
        if not items or "wysokosc_rolki" not in data:
            continue
        cases.append({
            "case_id": path.stem,
            "source": str(path),
            "machine_width": int(data.get("szerokosc_maszyny", 443)),
            "target_height": float(data["wysokosc_rolki"]),
            "items": items,
        })
    return cases


def split_train_test(
    cases: list[dict[str, Any]],
    per_category: int = 30,
    seed: int = SPLIT_SEED,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Random per_category cases from each height tercile for training, the rest for testing."""
    rng = random.Random(seed)
    ordered = sorted(cases, key=lambda c: (c["target_height"], c["case_id"]))
    n = len(ordered)
    groups = [ordered[: n // 3], ordered[n // 3: 2 * n // 3], ordered[2 * n // 3:]]
    train, test = [], []
    for category, group in zip(SIZE_CATEGORIES, groups):
        picked = rng.sample(group, min(per_category, len(group)))
        picked_ids = {c["case_id"] for c in picked}
        train += [{**c, "size_category": category} for c in picked]
        test += [{**c, "size_category": category} for c in group if c["case_id"] not in picked_ids]
    return train, test


def stratified_cases(cases, per_category=30, seed=SPLIT_SEED):
    return split_train_test(cases, per_category, seed)[0]


def load_and_select_training_cases(root, per_category=30, seed=SPLIT_SEED):
    cases = load_training_cases(Path(root) / "data" / "training")
    return split_train_test(cases, per_category, seed)[0]


def search_parameters_all(
    cases: list[dict[str, Any]],
    **kwargs: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Search one parameter set against all supplied training cases."""
    return _search_parameters(cases, **kwargs)


def search_parameters_by_category(
    cases: list[dict[str, Any]],
    **kwargs: Any,
) -> dict[str, tuple[list[dict[str, Any]], dict[str, Any]]]:
    """Search independent parameter sets for short, medium, and tall cases."""
    results = {}
    for category in ("short", "medium", "tall"):
        category_cases = [
            case for case in cases if case.get("size_category") == category
        ]
        if not category_cases:
            results[category] = ([], {})
            continue
        category_kwargs = dict(kwargs)
        for key in ("results_path", "study_path"):
            path = category_kwargs.get(key)
            if path is not None:
                path = Path(path)
                category_kwargs[key] = path.with_name(
                    f"{path.stem}_{category}{path.suffix}"
                )
        results[category] = _search_parameters(category_cases, **category_kwargs)
    return results


def search_parameters(
    cases: list[dict[str, Any]],
    **kwargs: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Backward-compatible alias for the all-cases search."""
    return search_parameters_all(cases, **kwargs)


def _search_parameters(
    cases: list[dict[str, Any]],
    n_trials: int = 50,
    seed: int = 0,
    packer: str = "skyline",
    results_path: str | Path | None = None,
    study_path: str | Path | None = None,
    time_weight: float = 0.10,
    time_reference_seconds: float = 1.0,
    max_population_size: int = 100,
    max_generations: int = 150,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Use Optuna to minimize height quality with a runtime penalty."""
    if not cases:
        return [], {}
    if n_trials < 1:
        raise ValueError("n_trials must be at least 1.")
    if not 0 <= time_weight <= 1:
        raise ValueError("time_weight must be between 0 and 1.")
    if time_reference_seconds <= 0:
        raise ValueError("time_reference_seconds must be positive.")
    if max_population_size < 20 or max_population_size % 5:
        raise ValueError("max_population_size must be at least 20 and divisible by 5.")
    if max_generations < 20 or max_generations % 5:
        raise ValueError("max_generations must be at least 20 and divisible by 5.")

    measurements: list[dict[str, Any]] = []
    if results_path is not None:
        results_path = Path(results_path)
        results_path.parent.mkdir(parents=True, exist_ok=True)
        if results_path.exists():
            measurements = json.loads(results_path.read_text(encoding="utf-8"))

    def objective(trial: optuna.Trial) -> float:
        options = _suggest_parameters(
            trial,
            max_population_size=max_population_size,
            max_generations=max_generations,
        )
        height_ratios = []
        seconds = []
        for case_index, case in enumerate(cases):
            started = time.perf_counter()
            height, _ = run_genetic_algorithm(
                case["items"], case["machine_width"], seed=seed,
                verbose=False, packer=packer, **options,
            )
            elapsed = time.perf_counter() - started
            seconds.append(elapsed)
            height_ratios.append(height / max(case["target_height"], 1.0))
            measurements.append({
                "trial": trial.number,
                **_json_safe(options),
                "case_id": case["case_id"],
                "size_category": case.get("size_category", ""),
                "item_count": len(case["items"]),
                "target_height": case["target_height"],
                "height": float(height),
                "height_gap": float(height - case["target_height"]),
                "height_ratio": float(height_ratios[-1]),
                "seconds": float(elapsed),
            })
            if results_path is not None:
                results_path.write_text(
                    json.dumps(measurements, indent=2),
                    encoding="utf-8",
                )
            partial_height = sum(height_ratios) / len(height_ratios)
            partial_time = sum(seconds) / len(seconds)
            trial.report(
                _combined_objective(
                    partial_height,
                    partial_time,
                    time_weight,
                    time_reference_seconds,
                ),
                case_index,
            )
            if trial.should_prune():
                raise optuna.TrialPruned()
        mean_height = sum(height_ratios) / len(height_ratios)
        mean_seconds = sum(seconds) / len(seconds)
        if results_path is not None:
            results_path.write_text(
                json.dumps(measurements, indent=2),
                encoding="utf-8",
            )
        return _combined_objective(
            mean_height,
            mean_seconds,
            time_weight,
            time_reference_seconds,
        )

    sampler = optuna.samplers.TPESampler(seed=seed)
    storage = None
    if study_path is not None:
        study_path = Path(study_path)
        study_path.parent.mkdir(parents=True, exist_ok=True)
        storage = f"sqlite:///{study_path.resolve().as_posix()}"
    study = optuna.create_study(
        direction="minimize",
        sampler=sampler,
        pruner=optuna.pruners.MedianPruner(n_startup_trials=5),
        storage=storage,
        study_name="layout_optimizer",
        load_if_exists=storage is not None,
    )
    # ``n_trials`` is the total budget for a persisted study, not the number
    # of additional trials to run on every notebook execution. Pruned trials
    # still consume the budget, so count every trial in the study.
    remaining_trials = max(0, n_trials - len(study.trials))
    if remaining_trials:
        study.optimize(objective, n_trials=remaining_trials)

    completed_trials = [
        trial
        for trial in study.trials
        if trial.state == optuna.trial.TrialState.COMPLETE
        and trial.value is not None
    ]
    rows = []
    for trial in completed_trials:
        trial_measurements = [
            measurement
            for measurement in measurements
            if measurement.get("trial") == trial.number
        ]
        height_ratio = (
            sum(item["height_ratio"] for item in trial_measurements)
            / len(trial_measurements)
            if trial_measurements
            else None
        )
        mean_seconds = (
            sum(item["seconds"] for item in trial_measurements)
            / len(trial_measurements)
            if trial_measurements
            else None
        )
        category_metrics = {}
        for category in ("short", "medium", "tall"):
            category_measurements = [
                item for item in trial_measurements
                if item.get("size_category") == category
            ]
            if category_measurements:
                category_metrics[f"{category}_quality_objective"] = sum(
                    item["height_ratio"] for item in category_measurements
                ) / len(category_measurements)
                category_metrics[f"{category}_mean_seconds"] = sum(
                    item["seconds"] for item in category_measurements
                ) / len(category_measurements)
        rows.append({
            "trial": trial.number,
            **trial.params,
            "quality_objective": height_ratio,
            "mean_seconds": mean_seconds,
            "time_penalty": (
                _time_penalty(mean_seconds, time_reference_seconds)
                if mean_seconds is not None else None
            ),
            "objective": trial.value,
            "state": trial.state.name,
            **category_metrics,
        })
    rows.sort(key=lambda row: row["objective"])
    return rows, rows[0] if rows else {}


def load_item_count_profiles(
    results_path: str | Path,
    *,
    cases: list[dict[str, Any]] | None = None,
    time_weight: float = 0.10,
    time_reference_seconds: float = 1.0,
) -> dict[str, dict[str, Any]]:
    """Choose the best completed parameter set for each item-count bucket."""
    measurements = json.loads(Path(results_path).read_text(encoding="utf-8"))
    case_counts = {
        case["case_id"]: len(case["items"])
        for case in cases or []
    }
    grouped: dict[tuple[int, int | None], dict[int, list[dict[str, Any]]]] = {}
    for measurement in measurements:
        item_count = measurement.get("item_count")
        if item_count is None:
            item_count = case_counts.get(measurement.get("case_id"))
        if item_count is None:
            continue
        bucket = _item_count_bucket(int(item_count))
        grouped.setdefault(bucket, {}).setdefault(
            int(measurement["trial"]), []
        ).append(measurement)

    profiles: dict[str, dict[str, Any]] = {}
    for bucket, trials in grouped.items():
        candidates = []
        for trial_number, trial_measurements in trials.items():
            quality = sum(
                item["height_ratio"] for item in trial_measurements
            ) / len(trial_measurements)
            seconds = sum(
                item["seconds"] for item in trial_measurements
            ) / len(trial_measurements)
            target_heights = [
                item["target_height"]
                for item in trial_measurements
                if "target_height" in item
            ]
            first = trial_measurements[0]
            parameters = {
                key: first[key]
                for key in (
                    "population_size",
                    "generations",
                    "mutation_rate",
                    "stagnation_generations",
                    "elite_count",
                    "crossover_probability",
                    "orientation_mutation_rate",
                    "swap_mutation_rate",
                    "stack_options",
                )
                if key in first
            }
            if "stack_options" in parameters:
                parameters["stack_options"] = tuple(
                    tuple(option) for option in parameters["stack_options"]
                )
            candidates.append({
                "trial": trial_number,
                "objective": _combined_objective(
                    quality, seconds, time_weight, time_reference_seconds
                ),
                "parameters": parameters,
                "sample_count": len(trial_measurements),
                "target_height_mean": (
                    sum(target_heights) / len(target_heights)
                    if target_heights else None
                ),
            })
        if candidates:
            best = min(candidates, key=lambda candidate: candidate["objective"])
            profiles[_bucket_name(bucket)] = {
                **best,
                "item_count_min": bucket[0],
                "item_count_max": bucket[1],
            }
    return profiles


def load_category_profiles(
    results_path: str | Path,
    *,
    time_weight: float = 0.10,
    time_reference_seconds: float = 1.0,
) -> dict[str, dict[str, Any]]:
    """Load the best Optuna parameters for each trained height category.

    ``results_path`` may be the common base path produced by the notebook
    or one category-specific results file.
    """
    path = Path(results_path)
    paths: dict[str, Path] = {}
    for category in SIZE_CATEGORIES:
        category_path = path.with_name(
            f"{path.stem}_{category}{path.suffix}"
        )
        if category_path.exists():
            paths[category] = category_path
    if not paths and path.exists():
        for category in SIZE_CATEGORIES:
            if f"_{category}" in path.stem:
                paths[category] = path
                break
        else:
            paths["medium"] = path

    profiles = {}
    for category, category_path in paths.items():
        measurements = json.loads(category_path.read_text(encoding="utf-8"))
        by_trial: dict[int, list[dict[str, Any]]] = {}
        for measurement in measurements:
            by_trial.setdefault(int(measurement["trial"]), []).append(measurement)
        complete_sample_count = max(
            (len(trial_measurements) for trial_measurements in by_trial.values()),
            default=0,
        )
        candidates = []
        for trial_number, trial_measurements in by_trial.items():
            if len(trial_measurements) != complete_sample_count:
                continue
            quality = sum(
                item["height_ratio"] for item in trial_measurements
            ) / len(trial_measurements)
            seconds = sum(
                item["seconds"] for item in trial_measurements
            ) / len(trial_measurements)
            target_heights = [
                item["target_height"]
                for item in trial_measurements
                if "target_height" in item
            ]
            first = trial_measurements[0]
            parameters = _parameters_from_measurement(first)
            candidates.append({
                "trial": trial_number,
                "objective": _combined_objective(
                    quality, seconds, time_weight, time_reference_seconds
                ),
                "parameters": parameters,
                "sample_count": len(trial_measurements),
                "target_height_mean": (
                    sum(target_heights) / len(target_heights)
                    if target_heights else None
                ),
            })
        if candidates:
            profiles[category] = min(
                candidates, key=lambda candidate: candidate["objective"]
            )
    return profiles


def infer_size_category(
    items: list[dict[str, Any]],
    machine_width: int,
    profiles: dict[str, dict[str, Any]],
) -> str:
    """Estimate the trained height category from the order's occupied area."""
    if machine_width <= 0:
        raise ValueError("machine_width must be positive.")
    estimates = {
        category: profile.get("target_height_mean")
        for category, profile in profiles.items()
        if profile.get("target_height_mean") is not None
    }
    if len(estimates) != len(SIZE_CATEGORIES):
        raise ValueError(
            "Automatic category inference requires target heights in all "
            "short, medium and tall result files."
        )
    estimated_height = sum(
        float(item["w"]) * float(item["h"]) for item in items
    ) / machine_width *1.1
    return min(
        estimates,
        key=lambda category: abs(estimated_height - estimates[category]),
    )


def parameters_for_category(
    profiles: dict[str, dict[str, Any]],
    category: str,
) -> dict[str, Any]:
    """Return the Optuna-selected parameters for ``short``, ``medium`` or ``tall``."""
    if category not in SIZE_CATEGORIES:
        raise ValueError(
            f"category must be one of {', '.join(SIZE_CATEGORIES)}."
        )
    profile = profiles.get(category)
    if profile is None:
        raise ValueError(f"No Optuna profile is available for category {category!r}.")
    return dict(profile["parameters"])


def _parameters_from_measurement(measurement: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "population_size",
        "generations",
        "mutation_rate",
        "stagnation_generations",
        "elite_count",
        "crossover_probability",
        "orientation_mutation_rate",
        "swap_mutation_rate",
        "stack_options",
    )
    parameters = {key: measurement[key] for key in keys if key in measurement}
    if "stack_options" in parameters:
        parameters["stack_options"] = tuple(
            tuple(option) for option in parameters["stack_options"]
        )
    return parameters


def parameters_for_item_count(
    profiles: dict[str, dict[str, Any]],
    item_count: int,
) -> dict[str, Any]:
    """Return a copy of the profile matching ``item_count``."""
    if item_count < 0:
        raise ValueError("item_count must not be negative.")
    bucket = _bucket_name(_item_count_bucket(item_count))
    profile = profiles.get(bucket)
    if profile is None:
        return {}
    return dict(profile["parameters"])


def _item_count_bucket(item_count: int) -> tuple[int, int | None]:
    for minimum, maximum in ITEM_COUNT_BUCKETS:
        if maximum is None or item_count <= maximum:
            return minimum, maximum
    raise AssertionError("ITEM_COUNT_BUCKETS must cover every item count.")


def _bucket_name(bucket: tuple[int, int | None]) -> str:
    return f"{bucket[0]}+" if bucket[1] is None else f"{bucket[0]}-{bucket[1]}"


def _time_penalty(seconds: float, reference_seconds: float) -> float:
    """Keep the penalty gentle through the target time, then increase sharply."""
    ratio = seconds / reference_seconds
    return 0.05 * min(ratio, 1.0) + max(ratio - 1.0, 0.0) ** 2


def _combined_objective(
    quality: float,
    seconds: float,
    time_weight: float,
    time_reference_seconds: float,
) -> float:
    return (
        (1 - time_weight) * quality
        + time_weight * _time_penalty(seconds, time_reference_seconds)
    )


def _suggest_parameters(
    trial: optuna.Trial,
    *,
    max_population_size: int,
    max_generations: int,
) -> dict[str, Any]:
    """Suggest every optimizer parameter, including stack construction."""
    return {
        "population_size": trial.suggest_int(
            "population_size", 20, max_population_size, step=10
        ),
        "generations": trial.suggest_int(
            "generations", 20, max_generations, step=10
        ),
        "mutation_rate": trial.suggest_float("mutation_rate", 0.05, 0.40),
        "stagnation_generations": trial.suggest_int(
            "stagnation_generations", 5, 40, step=5
        ),
        "elite_count": trial.suggest_int("elite_count", 2, 5),
        "crossover_probability": trial.suggest_float(
            "crossover_probability", 0.5, 1.0
        ),
        "orientation_mutation_rate": trial.suggest_float(
            "orientation_mutation_rate", 0.02, 0.25
        ),
        "swap_mutation_rate": trial.suggest_float(
            "swap_mutation_rate", 0.05, 0.60
        ),
        "stack_options": ((
            trial.suggest_float("min_width_ratio", 0.60, 0.98),
            trial.suggest_int("mix_categories", 0, 2),
            trial.suggest_float("epsilon", 0.02, 0.20),
            trial.suggest_categorical("prefer_higher", [False, True]),
            trial.suggest_float("acceptance", 0.80, 1.0),
        ),),
    }


def _json_safe(values: dict[str, Any]) -> dict[str, Any]:
    """Convert tuple-based stack options to JSON-compatible values."""
    return {
        key: [
            list(option) if isinstance(option, tuple) else option
            for option in value
        ]
        if key == "stack_options" and isinstance(value, tuple)
        else value
        for key, value in values.items()
    }


def stack_option_grid(
    min_width_ratios: list[float],
    mix_categories: list[int],
    epsilons: list[float],
    prefer_higher: list[bool],
    acceptance: list[float],
    max_options: int | None = None,
) -> list[tuple[StackOption, ...]]:
    """Create independent one-option stack configurations for the search."""
    options = [
        ((ratio, mix, epsilon, higher, accepted),)
        for ratio, mix, epsilon, higher, accepted in product(
            min_width_ratios,
            mix_categories,
            epsilons,
            prefer_higher,
            acceptance,
        )
    ]
    return options[:max_options] if max_options is not None else options

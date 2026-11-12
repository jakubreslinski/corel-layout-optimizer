"""Basic genetic optimization for Item and ItemStack genes."""

from __future__ import annotations

import random
import time
from collections.abc import Callable

from .create_item_stacks import create_item_stacks
from .fitness import (
    Gene,
    _layout_score,
    _skyline_layout_score,
    _stackless_skyline_layout_score,
    gene_dimensions,
)
from .genetic_operators import (
    Candidate as _Candidate,
    OperatorStats as _OperatorStats,
    mutate_genes as _mutate_genes,
    ordered_crossover as _ordered_crossover,
    tournament as _tournament,
)
from .utilities import (
    Item,
    ItemStack,
    UnpackedItems,
    unpack_gene as expand_gene,
    unpack_genes,
)

StackOption = tuple[float, int, float, bool, float]
DEFAULT_STACK_OPTIONS: tuple[StackOption, ...] = (
    (0.85, 0, 0.1, False, 0.95),
)


def genetic_algorithm(
    genes: list[Gene] | tuple[Gene, ...],
    max_width: float,
    population_size: int = 50,
    generations: int = 80,
    mutation_rate: float = 0.15,
    seed: int | None = None,
    verbose: bool = False,
    packer: str = "skyline",
    stagnation_generations: int = 10,
    elite_count: int = 2,
    crossover_probability: float = 0.7,
    orientation_mutation_rate: float | None = None,
    swap_mutation_rate: float = 0.3,
    stack_options: tuple[StackOption, ...] | None = None,
) -> list[Gene]:
    """Return a good ordering of Item and ItemStack genes.

    Genes remain atomic during evolution: an ItemStack is never split or
    exchanged for its members. Only standalone Item orientations may mutate.
    """
    _validate_inputs(
        max_width,
        population_size,
        generations,
        mutation_rate,
        stagnation_generations,
        packer,
        elite_count,
        crossover_probability,
        orientation_mutation_rate if orientation_mutation_rate is not None else mutation_rate,
        swap_mutation_rate,
        stack_options,
    )
    if not genes:
        return []
    
    # Scoring and run-level statistics.
    source_items = tuple(gene for gene in genes if isinstance(gene, Item))
    if packer == "rectpack":
        scorer = _layout_score
    elif source_items and any(isinstance(gene, ItemStack) for gene in genes):
        scorer = lambda candidate, width: _stackless_skyline_layout_score(
            candidate, width, source_items
        )
    else:
        scorer = _skyline_layout_score
    _clear_score_cache(scorer)
    if scorer is not _stackless_skyline_layout_score:
        _stackless_skyline_layout_score.cache_clear()
    started = time.perf_counter()
    phase_times: dict[str, float] = {}
    improvements: dict[str, float] = {}
    operator_stats = _OperatorStats()
    rng = random.Random(seed)

    # Build and evolve every representation independently.
    representations_started = time.perf_counter()
    representations = _representations(
        tuple(genes),
        max_width,
        DEFAULT_STACK_OPTIONS if stack_options is None else stack_options,
    )
    phase_times["representations"] = time.perf_counter() - representations_started
    _timing(
        verbose, "representations", time.perf_counter() - representations_started,
        f"count={len(representations)}",)
    best = _find_best_representation(
        representations,
        max_width,
        population_size,
        generations,
        mutation_rate,
        stagnation_generations,
        elite_count,
        crossover_probability,
        orientation_mutation_rate if orientation_mutation_rate is not None else mutation_rate,
        swap_mutation_rate,
        rng,
        verbose,
        phase_times,
        operator_stats,
        scorer,
        improvements,
    )

    # Unpack the selected representation for the caller.
    unpack_started = time.perf_counter()
    result = _unpack_result(best, genes)
    _record_phase(phase_times, "unpacking", time.perf_counter() - unpack_started)
    _timing(verbose, "unpacking", phase_times["unpacking"])
    total_time = time.perf_counter() - started
    _timing(verbose, "genetic algorithm total", total_time)
    if verbose:
        _print_profile(
            total_time, phase_times, operator_stats, improvements,
            genes, max_width, best, scorer,
        )
    return result


def _validate_inputs(
    max_width: float,
    population_size: int,
    generations: int,
    mutation_rate: float,
    stagnation_generations: int,
    packer: str,
    elite_count: int,
    crossover_probability: float,
    orientation_mutation_rate: float,
    swap_mutation_rate: float,
    stack_options: tuple[StackOption, ...] | None,
) -> None:
    if max_width <= 0:
        raise ValueError("max_width must be positive.")
    if population_size < 2:
        raise ValueError("population_size must be at least 2.")
    if generations < 0:
        raise ValueError("generations must not be negative.")
    if not 0 <= mutation_rate <= 1:
        raise ValueError("mutation_rate must be between 0 and 1.")
    if stagnation_generations < 1:
        raise ValueError("stagnation_generations must be at least 1.")
    if packer not in {"rectpack", "skyline"}:
        raise ValueError("packer must be 'rectpack' or 'skyline'.")
    if not 2 <= elite_count <= 5:
        raise ValueError("elite_count must be between 2 and 5.")
    if elite_count >= population_size:
        raise ValueError("elite_count must be smaller than population_size.")
    if not 0 <= crossover_probability <= 1:
        raise ValueError("crossover_probability must be between 0 and 1.")
    if not 0 <= orientation_mutation_rate <= 1:
        raise ValueError("orientation_mutation_rate must be between 0 and 1.")
    if not 0 <= swap_mutation_rate <= 1:
        raise ValueError("swap_mutation_rate must be between 0 and 1.")
    if stack_options is not None:
        if not stack_options:
            raise ValueError("stack_options must contain at least one option.")
        for option in stack_options:
            if len(option) != 5:
                raise ValueError(
                    "Each stack option must contain five values."
                )
            min_width_ratio, mix_categories, epsilon, prefer_higher, acceptance = option
            if not 0 < min_width_ratio <= 1:
                raise ValueError("min_width_ratio must be in (0, 1].")
            if mix_categories < 0:
                raise ValueError("mix_categories must not be negative.")
            if epsilon < 0:
                raise ValueError("epsilon must not be negative.")
            if not 0 < acceptance <= 1:
                raise ValueError("stack acceptance must be in (0, 1].")


def _find_best_representation(
    representations: list[tuple[Gene, ...]],
    max_width: float,
    population_size: int,
    generations: int,
    mutation_rate: float,
    stagnation_generations: int,
    elite_count: int,
    crossover_probability: float,
    orientation_mutation_rate: float,
    swap_mutation_rate: float,
    rng: random.Random,
    verbose: bool,
    phase_times: dict[str, float],
    operator_stats: _OperatorStats,
    score_function: Callable[[tuple[Gene, ...], float], float],
    improvements: dict[str, float],
) -> _Candidate:
    best: _Candidate | None = None
    for index, representation in enumerate(representations, start=1):
        started = time.perf_counter()
        candidate = _run_representation(
            representation, max_width, population_size, generations,
            mutation_rate, stagnation_generations, elite_count,
            crossover_probability, orientation_mutation_rate,
            swap_mutation_rate, rng, verbose, phase_times, operator_stats,
            improvements, score_function,
        )
        _timing(
            verbose,
            f"representation {index}/{len(representations)}",
            time.perf_counter() - started,
            f"genes={len(representation)} score={candidate.score:.2f}",
        )
        if best is None or candidate.score < best.score:
            best = candidate
    return best


def _unpack_result(
    best: _Candidate,
    source: list[Gene] | tuple[Gene, ...],
) -> list[Item]:
    source_items = {
        item.id: item
        for item in source
        if isinstance(item, Item)
    }
    return UnpackedItems(
        unpack_genes(best.genes, source_items or None),
        best.genes,
    )


def _clear_score_cache(score_function: Callable) -> None:
    cache_clear = getattr(score_function, "cache_clear", None)
    if cache_clear is not None:
        cache_clear()


def _record_phase(
    phase_times: dict[str, float],
    name: str,
    elapsed: float,
) -> None:
    phase_times[name] = phase_times.get(name, 0.0) + elapsed


def _representations(
    source: tuple[Gene, ...],
    max_width: float,
    stack_options: tuple[StackOption, ...],
) -> list[tuple[Gene, ...]]:
    """Return distinct gene representations to optimize independently."""
    representations = [source]
    if not all(isinstance(gene, Item) for gene in source):
        return representations

    items = list(source)
    for (
        min_width_ratio,
        mix_categories,
        epsilon,
        prefer_higher,
        acceptance,
    ) in stack_options:
        stacked = tuple(
            create_item_stacks(
                items,
                max_width=max_width,
                min_width_ratio=min_width_ratio,
                mix_categories=mix_categories,
                epsilon=epsilon,
                prefer_higher=prefer_higher,
                dfs_acceptance_ratio=acceptance,
            )
        )
        if stacked not in representations:
            representations.append(stacked)
    return representations


def _run_representation(
    source: tuple[Gene, ...],
    max_width: float,
    population_size: int,
    generations: int,
    mutation_rate: float,
    stagnation_generations: int,
    elite_count: int,
    crossover_probability: float,
    orientation_mutation_rate: float,
    swap_mutation_rate: float,
    rng: random.Random,
    verbose: bool = False,
    phase_times: dict[str, float] | None = None,
    operator_stats: _OperatorStats | None = None,
    improvements: dict[str, float] | None = None,
    score_function=_layout_score,
) -> _Candidate:
    """Evolve one fixed gene representation."""
    # Create seeded and randomized candidates.
    population_started = time.perf_counter()
    seeded_orders = (
        source,
        tuple(
            sorted(
                source,
                key=lambda gene: max(gene_dimensions(gene)),
                reverse=True,
)
        ),
        tuple(
            sorted(
                source,
                key=lambda gene: gene_dimensions(gene)[0] * gene_dimensions(gene)[1],
                reverse=True,
            )
        ),
        tuple(sorted(source, key=lambda gene: gene_dimensions(gene)[0], reverse=True)),
        tuple(sorted(source, key=lambda gene: gene_dimensions(gene)[1], reverse=True)),
        tuple(sorted(source, key=lambda gene: getattr(gene, "typ", ""),)),
    )
    if all(isinstance(gene, Item) for gene in source):
        seeded_orders += (
            tuple(gene._replace(flip=True) for gene in seeded_orders[2]),
            tuple(gene._replace(flip=True) for gene in source),
        )
    population = [
        _Candidate(order, score_function(order, max_width))
        for order in seeded_orders[:population_size]
    ]
    while len(population) < population_size:
        candidate = list(source)
        rng.shuffle(candidate)
        candidate = _mutate_genes(
            tuple(candidate),
            mutation_rate,
            orientation_mutation_rate,
            swap_mutation_rate,
            rng,
            stats=operator_stats,
        )
        population.append(
            _Candidate(candidate, score_function(candidate, max_width))
        )
    population_time = time.perf_counter() - population_started
    if phase_times is not None:
        phase_times["population initialization"] = (
            phase_times.get("population initialization", 0.0) + population_time
        )
    _timing(verbose, "population initialization", population_time)

    # Select, cross, mutate, and preserve the best candidate.
    evolution_started = time.perf_counter()
    best = min(population, key=lambda candidate: candidate.score)
    if improvements is not None:
        improvements["seed_best"] = min(
            improvements.get("seed_best", float("inf")),
            best.score,
        )
    generations_without_improvement = 0
    for _ in range(generations):
        population.sort(key=lambda candidate: candidate.score)
        next_population = population[:elite_count]
        while len(next_population) < population_size:
            first = _tournament(population, rng, stats=operator_stats)
            second = _tournament(population, rng, stats=operator_stats)
            if rng.random() < crossover_probability:
                child = _ordered_crossover(
                    first.genes, second.genes, rng, stats=operator_stats
                )
            else:
                child = first.genes
            parent_score = min(first.score, second.score)
            crossover_score = score_function(child, max_width)
            crossover_gain = parent_score - crossover_score
            if crossover_gain > 0 and operator_stats is not None:
                operator_stats.crossover_improvement += crossover_gain
                operator_stats.crossover_successes += 1
            if operator_stats is not None:
                operator_stats.crossover_best_attempts += 1
                if crossover_score < best.score:
                    operator_stats.crossover_best_successes += 1
                    operator_stats.crossover_best_improvement += (
                        best.score - crossover_score
                    )
            child = _mutate_genes(
                child,
                mutation_rate,
                orientation_mutation_rate,
                swap_mutation_rate,
                rng,
                stats=operator_stats,
            )
            mutated_score = score_function(child, max_width)
            mutation_gain = crossover_score - mutated_score
            if mutation_gain > 0 and operator_stats is not None:
                operator_stats.mutation_improvement += mutation_gain
                operator_stats.mutation_successes += 1
            if operator_stats is not None:
                operator_stats.mutation_best_attempts += 1
                if mutated_score < best.score:
                    operator_stats.mutation_best_successes += 1
                    operator_stats.mutation_best_improvement += (
                        best.score - mutated_score
                    )
            next_population.append(
                _Candidate(child, mutated_score)
            )
        population = next_population
        generation_best = min(population, key=lambda candidate: candidate.score)
        if generation_best.score < best.score:
            best = generation_best
            generations_without_improvement = 0
        else:
            generations_without_improvement += 1
            if generations_without_improvement >= stagnation_generations:
                _timing(
                    verbose,
                    "early stopping",
                    0.0,
                    f"no improvement for {stagnation_generations} generations",
                )
                break
    evolution_time = time.perf_counter() - evolution_started
    if phase_times is not None:
        phase_times["evolution"] = phase_times.get("evolution", 0.0) + evolution_time
    _timing(verbose, "evolution", evolution_time)
    if improvements is not None:
        improvements["evolved_best"] = min(
            improvements.get("evolved_best", float("inf")),
            best.score,
        )
    return best


def _timing(verbose: bool, section: str, elapsed: float, details: str = "") -> None:
    if verbose:
        suffix = f" ({details})" if details else ""
        print(f"[new_optimizer] {section}: {elapsed:.3f}s{suffix}")


def _print_profile(
    total_time: float,
    phase_times: dict[str, float],
    operator_stats: _OperatorStats,
    improvements: dict[str, float],
    source: list[Gene] | tuple[Gene, ...],
    max_width: float,
    best: _Candidate,
    score_function,
) -> None:
    # Print runtime distribution and operator contribution statistics.
    def percent(value: float) -> float:
        return value / total_time * 100 if total_time else 0.0

    phases = ", ".join(
        f"{name}={elapsed:.3f}s ({percent(elapsed):.1f}%)"
        for name, elapsed in phase_times.items()
    )
    baseline = score_function(tuple(source), max_width)
    improvement = baseline - best.score
    print(f"[new_optimizer] profile: total={total_time:.3f}s; {phases}")
    print(operator_stats.report(total_time))
    seed_best = improvements.get("seed_best", best.score)
    evolution_gain = seed_best - improvements.get("evolved_best", best.score)
    representation_gain = baseline - seed_best
    print(
        "[new_optimizer] improvement by feature: "
        f"stack/seeds={representation_gain:.2f}, "
        f"evolution={evolution_gain:.2f}, "
        f"total={improvement:.2f} "
        f"({improvement / baseline * 100:.1f}%)"
        if baseline
        else "[new_optimizer] improvement by feature: baseline=0.00, total=0.00"
    )
    print(operator_stats.improvement_report())
    print(operator_stats.best_report())
    cache_info = getattr(score_function, "cache_info", None)
    if cache_info is not None:
        info = cache_info()
        print(
            "[new_optimizer] score cache: "
            f"hits={info.hits}, misses={info.misses}, size={info.currsize}"
        )

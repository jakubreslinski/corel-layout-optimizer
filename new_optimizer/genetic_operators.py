"""Evolutionary operators used by the genetic layout optimizer."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

from .fitness import Gene


@dataclass(frozen=True)
class Candidate:
    """A gene ordering and its evaluated fitness score."""

    genes: tuple[Gene, ...]
    score: float


@dataclass
class OperatorStats:
    """Runtime and improvement counters collected during one optimization run."""

    mutation_time: float = 0.0
    mutation_calls: int = 0
    tournament_time: float = 0.0
    tournament_calls: int = 0
    crossover_time: float = 0.0
    crossover_calls: int = 0
    crossover_improvement: float = 0.0
    crossover_successes: int = 0
    mutation_improvement: float = 0.0
    mutation_successes: int = 0
    mutation_best_attempts: int = 0
    mutation_best_successes: int = 0
    mutation_best_improvement: float = 0.0
    crossover_best_attempts: int = 0
    crossover_best_successes: int = 0
    crossover_best_improvement: float = 0.0

    def report(self, total_time: float) -> str:
        def percent(value: float) -> float:
            return value / total_time * 100 if total_time else 0.0

        return (
            "[new_optimizer] operators: "
            f"mutation={self.mutation_time:.3f}s ({percent(self.mutation_time):.1f}%, "
            f"{self.mutation_calls} calls), "
            f"tournament={self.tournament_time:.3f}s ({percent(self.tournament_time):.1f}%, "
            f"{self.tournament_calls} calls), "
            f"crossover={self.crossover_time:.3f}s ({percent(self.crossover_time):.1f}%, "
            f"{self.crossover_calls} calls)"
        )

    def improvement_report(self) -> str:
        observed_improvement = (
            self.crossover_improvement + self.mutation_improvement
        )

        def percent(value: float) -> float:
            return (
                value / observed_improvement * 100
                if observed_improvement > 0
                else 0.0
            )

        return (
            "[new_optimizer] operator improvement (observed; share of "
            f"{observed_improvement:.2f} operator gain): "
            f"crossover={self.crossover_improvement:.2f} "
            f"({percent(self.crossover_improvement):.1f}%, "
            f"{self.crossover_successes} improvements), "
            f"mutation={self.mutation_improvement:.2f} "
            f"({percent(self.mutation_improvement):.1f}%, "
            f"{self.mutation_successes} improvements)"
        )

    def best_report(self) -> str:
        def percent(successes: int, attempts: int) -> float:
            return successes / attempts * 100 if attempts else 0.0

        return (
            "[new_optimizer] current-best impact: "
            f"crossover={self.crossover_best_improvement:.2f} "
            f"({self.crossover_best_successes}/{self.crossover_best_attempts}, "
            f"{percent(self.crossover_best_successes, self.crossover_best_attempts):.1f}%), "
            f"mutation={self.mutation_best_improvement:.2f} "
            f"({self.mutation_best_successes}/{self.mutation_best_attempts}, "
            f"{percent(self.mutation_best_successes, self.mutation_best_attempts):.1f}%)"
        )


def mutate_gene(gene: Gene, mutation_rate: float, rng: random.Random) -> Gene:
    """Toggle a gene orientation according to the mutation rate."""
    if rng.random() < mutation_rate:
        return gene._replace(flip=not gene.flip)
    return gene


def mutate_genes(
    genes: tuple[Gene, ...],
    mutation_probability: float,
    orientation_rate: float,
    swap_rate: float,
    rng: random.Random,
    stats: OperatorStats | None = None,
) -> tuple[Gene, ...]:
    """Mutate orientations and make a biased downward move in the sequence."""
    started = time.perf_counter()
    if rng.random() >= mutation_probability:
        result = genes
        if stats is not None:
            stats.mutation_calls += 1
            stats.mutation_time += time.perf_counter() - started
        return result

    mutated = [
        mutate_gene(gene, orientation_rate, rng)
        for gene in genes
    ]
    if len(mutated) < 2 or rng.random() >= swap_rate:
        result = tuple(mutated)
        if stats is not None:
            stats.mutation_calls += 1
            stats.mutation_time += time.perf_counter() - started
        return result

    # Prefer positions near the top while keeping every position reachable.
    weights = [0.5**index for index in range(len(mutated) - 1)]
    source = rng.choices(range(len(mutated) - 1), weights=weights, k=1)[0]
    distance = 1
    while rng.random() > 0.6 and source + distance < len(mutated):
        distance += 1

    gene = mutated.pop(source)
    mutated.insert(source + distance, gene)
    result = tuple(mutated)
    if stats is not None:
        stats.mutation_calls += 1
        stats.mutation_time += time.perf_counter() - started
    return result


def tournament(
    population: list[Candidate],
    rng: random.Random,
    size: int = 3,
    stats: OperatorStats | None = None,
) -> Candidate:
    """Select the best candidate from randomly sampled contestants."""
    started = time.perf_counter()
    contestants = [rng.choice(population) for _ in range(size)]
    result = min(contestants, key=lambda candidate: candidate.score)
    if stats is not None:
        stats.tournament_calls += 1
        stats.tournament_time += time.perf_counter() - started
    return result


def ordered_crossover(
    first: tuple[Gene, ...],
    second: tuple[Gene, ...],
    rng: random.Random,
    stats: OperatorStats | None = None,
) -> tuple[Gene, ...]:
    """Create an ordered child while preserving duplicate gene occurrences."""
    started = time.perf_counter()
    if len(first) < 2:
        if stats is not None:
            stats.crossover_calls += 1
            stats.crossover_time += time.perf_counter() - started
        return first

    start, end = sorted(rng.sample(range(len(first)), 2))
    child: list[Gene | None] = [None] * len(first)
    child[start:end] = first[start:end]
    used: dict[str, int] = {}
    for gene in child[start:end]:
        if gene is not None:
            used[gene.id] = used.get(gene.id, 0) + 1

    remaining_genes: list[Gene] = []
    for gene in second:
        count = used.get(gene.id, 0)
        if count:
            used[gene.id] = count - 1
        else:
            remaining_genes.append(gene)
    remaining = iter(remaining_genes)
    for index, gene in enumerate(child):
        if gene is None:
            child[index] = next(remaining)
    result = tuple(gene for gene in child if gene is not None)
    if stats is not None:
        stats.crossover_calls += 1
        stats.crossover_time += time.perf_counter() - started
    return result

"""DEAP operators and population construction."""

import random

from deap import base, creator, tools

from .fitness import evaluate_layout


def _ensure_deap_types():
    if not hasattr(creator, "FitnessMin"):
        creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
    if not hasattr(creator, "Individual"):
        creator.create("Individual", list, fitness=creator.FitnessMin, rot=None)


def create_population(items, population_size, machine_width):
    """Create deterministic seed candidates followed by random candidates."""
    indices = list(range(len(items)))
    forced_rotations = [item["w"] > machine_width for item in items]
    population = [
        (
            sorted(indices, key=lambda i: items[i]["w"] * items[i]["h"], reverse=True),
            forced_rotations.copy(),
        ),
        (sorted(indices, key=lambda i: items[i]["w"] * items[i]["h"], reverse=True), [True] * len(items)),
        (sorted(indices, key=lambda i: items[i]["typ"]), forced_rotations.copy()),
    ]

    while len(population) < population_size:
        population.append(
            (
                random.sample(indices, len(items)),
                [forced or random.choice([True, False]) for forced in forced_rotations],
            )
        )
    return population[:population_size]


def evaluate_individual(individual, items, machine_width, main_weight, sub_weight, line_weight):
    fitness, _ = evaluate_layout(
        (individual, individual.rot),
        items,
        machine_width,
        main_weight,
        sub_weight,
        line_weight,
    )
    return (fitness,)


def crossover(individual_a, individual_b):
    if len(individual_a) < 2:
        return individual_a, individual_b
    tools.cxOrdered(individual_a, individual_b)
    for index in range(len(individual_a.rot)):
        if random.random() < 0.5:
            individual_a.rot[index], individual_b.rot[index] = (
                individual_b.rot[index],
                individual_a.rot[index],
            )
    return individual_a, individual_b


def mutate(individual, probability=0.3):
    if random.random() < probability and len(individual) >= 2:
        first, second = random.sample(range(len(individual)), 2)
        individual[first], individual[second] = individual[second], individual[first]
    for index in range(len(individual.rot)):
        if random.random() < probability * 0.4:
            individual.rot[index] = not individual.rot[index]
    return (individual,)


def build_individual(sequence, rotations):
    _ensure_deap_types()
    individual = creator.Individual(sequence)
    individual.rot = rotations
    return individual

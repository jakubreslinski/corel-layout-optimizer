"""Genetic algorithm orchestration."""

import multiprocessing
import random

from deap import base, tools

from .fitness import evaluate_layout
from .genetic import build_individual, crossover, create_population, evaluate_individual, mutate


def run_genetic_algorithm(
    items,
    machine_width,
    population_size=50,
    generations=50,
    main_weight=0.0,
    sub_weight=0.0,
    line_weight=0.0,
):
    """Optimize one item collection and return its height and packed layout."""
    toolbox = base.Toolbox()
    worker_count = min(4, multiprocessing.cpu_count())
    toolbox.register("evaluate", evaluate_individual, items=items, machine_width=machine_width,
                     main_weight=main_weight, sub_weight=sub_weight, line_weight=line_weight)
    toolbox.register("mate", crossover)
    toolbox.register("mutate", mutate, probability=0.3)
    toolbox.register("select", tools.selTournament, tournsize=3)

    individuals = [build_individual(sequence, rotations) for sequence, rotations in create_population(
        items, population_size, machine_width
    )]
    hall_of_fame = tools.HallOfFame(1)

    with multiprocessing.Pool(processes=worker_count) as pool:
        toolbox.register("map", pool.map)
        _evaluate_invalid(toolbox, individuals)
        hall_of_fame.update(individuals)

        for _ in range(generations):
            offspring = list(map(toolbox.clone, toolbox.select(individuals, len(individuals) - 1)))
            for first, second in zip(offspring[::2], offspring[1::2]):
                if random.random() < 0.7:
                    toolbox.mate(first, second)
                    del first.fitness.values
                    del second.fitness.values
            for individual in offspring:
                toolbox.mutate(individual)
                del individual.fitness.values
            _evaluate_invalid(toolbox, offspring)
            individuals[:] = offspring + [toolbox.clone(hall_of_fame[0])]
            hall_of_fame.update(individuals)

    best = hall_of_fame[0]
    _, height, packer = evaluate_layout(
        (best, best.rot), items, machine_width, main_weight, sub_weight, line_weight, return_packer=True
    )
    return height, packer


def _evaluate_invalid(toolbox, individuals):
    invalid = [individual for individual in individuals if not individual.fitness.valid]
    for individual, fitness in zip(invalid, toolbox.map(toolbox.evaluate, invalid)):
        individual.fitness.values = fitness

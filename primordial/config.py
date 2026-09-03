from dataclasses import dataclass


@dataclass
class Config:
    # population
    pop_size: int = 150
    elitism: int = 2              # top genomes of a species copied untouched
    survival: float = 0.4         # fraction of a species allowed to breed
    p_crossover: float = 0.75
    stagnation: int = 20          # generations without improvement before a cull
    target_species: int = 12      # threshold auto-tunes towards this

    # speciation
    compat_threshold: float = 1.2
    c_disjoint: float = 1.0
    c_weight: float = 0.5
    small_genome: int = 20

    # mutation
    p_weight: float = 0.8
    p_weight_replace: float = 0.1
    weight_step: float = 0.35
    weight_init_std: float = 1.0
    weight_cap: float = 8.0
    p_add_conn: float = 0.15
    p_add_node: float = 0.04
    p_toggle: float = 0.01
    p_inherit_disabled: float = 0.75
    add_conn_tries: int = 20

    # world
    world_w: int = 1000
    world_h: int = 720
    n_food: int = 90
    n_poison: int = 45
    ticks: int = 1400
    n_rays: int = 6
    fov: float = 2.4              # radians, total field of view
    sight: float = 220.0
    creature_r: float = 7.0
    max_speed: float = 3.2
    turn_rate: float = 0.10
    start_energy: float = 220.0
    energy_drain: float = 0.16
    food_energy: float = 110.0
    poison_energy: float = -140.0

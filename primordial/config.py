from dataclasses import dataclass


@dataclass
class Config:
    # --- world ---
    world_w: int = 1600
    world_h: int = 1200
    start_pop: int = 200
    max_pop: int = 800
    neighbours: int = 24         # how many nearby things an organism can attend to
    seed: int = 7

    # --- energy economy ---
    # everything in the dish is paid for out of light; nothing is free
    photo_rate: float = 0.9        # energy per photo cell per tick, before shading
    core_photo: float = 0.30       # the bare core feeds a little on its own
    shade_radius: float = 55.0
    shade_factor: float = 0.22     # how hard neighbours steal your light
    start_energy: float = 100.0
    energy_drain: float = 0.11
    toxin_cost: float = 0.09
    move_cost: float = 0.05
    max_age: int = 5000          # baseline; each organism inherits its own jitter
    lifespan_jitter: float = 0.18

    # --- movement / senses ---
    cell_r: float = 4.5
    max_speed: float = 2.6
    turn_rate: float = 0.11
    sight: float = 200.0
    n_rays: int = 6
    fov: float = 2.6
    bite_reach: float = 3.0
    bite_rate: float = 3.2         # energy drained per eater cell per tick

    # --- reproduction ---
    split_energy: float = 1.7      # multiple of capacity needed to divide
    split_cost: float = 0.15       # fraction of energy lost in the split
    p_sex: float = 0.12            # chance a split borrows genes from a neighbour
    mate_radius: float = 90.0

    # --- brain mutation ---
    p_weight: float = 0.8
    p_weight_replace: float = 0.1
    weight_step: float = 0.35
    weight_init_std: float = 1.0
    weight_cap: float = 8.0
    p_add_conn: float = 0.09
    p_add_node: float = 0.025
    p_toggle: float = 0.01
    p_inherit_disabled: float = 0.75
    add_conn_tries: int = 20

    # --- body mutation ---
    p_cell_add: float = 0.18
    p_cell_type: float = 0.10
    p_cell_drop: float = 0.04
    max_cells: int = 64

    # --- speciation (labels and colours only, selection is what it is) ---
    compat_threshold: float = 1.2
    c_disjoint: float = 1.0
    c_weight: float = 0.5
    small_genome: int = 20
    target_species: int = 14
    speciate_every: int = 240      # ticks

    # --- view ---
    view_w: int = 1180
    view_h: int = 800
    panel_w: int = 440
    stats_h: int = 205
    ui_scale: float = 1.0

    # --- terrain and weather ---
    n_obstacles: int = 16
    obstacle_r: tuple = (24.0, 70.0)
    p_event: float = 0.0009      # per tick chance a natural event starts
    event_len: tuple = (400, 1400)
    meteor_r: tuple = (120.0, 300.0)

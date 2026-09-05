from dataclasses import dataclass


@dataclass
class Config:
    # --- world ---
    world_w: int = 4000
    world_h: int = 3000
    start_pop: int = 400
    max_pop: int = 1800
    neighbours: int = 24         # how many nearby things an organism can attend to
    seed: int = 7

    # --- energy economy ---
    # everything in the dish is paid for out of light; nothing is free
    photo_rate: float = 2.4        # per photo cell, before daylight/field/shading
    core_photo: float = 0.30       # the bare core feeds a little on its own
    shade_radius: float = 78.0
    # light is not uniform: it is concentrated in the middle of the world, so
    # the centre is worth fighting over and the edges are marginal ground
    light_spread: float = 0.30   # smaller = tighter fertile zone
    light_edge: float = 0.04     # floor, so the rim is poor but not dead
    seed_radius: float = 0.50    # founders start inside the fertile zone

    # Light is a local, exhaustible resource. Feeding in one spot draws that
    # patch down and it recovers slowly, so standing still starves you no
    # matter how bright the ground was when you arrived. This is the whole
    # reason moving, sensing a gradient and remembering where you have already
    # grazed are worth anything: without depletion the optimal strategy is to
    # sit in the brightest spot forever, which needs no brain at all.
    patch_size: float = 44.0     # world units per light cell
    light_regen: float = 0.0022  # share of the shortfall recovered per tick
    light_drain: float = 0.0015  # patch drawn down per unit of energy taken

    # the world is never stationary: a lineage tuned to today's conditions has
    # to keep paying attention, which is what stops the dish settling
    day_len: int = 700           # ticks per day/night cycle
    night_light: float = 0.35    # light left at midnight; lean, survivable
    season_len: int = 42000      # ticks per season cycle
    season_swing: float = 0.55   # how much the fertile zone breathes
    drift_len: int = 260000      # ticks for the fertile zone to circle once
    drift_amp: float = 0.22      # how far it wanders, as a fraction of the world
    shade_factor: float = 0.25     # depletion now does most of the crowding
    start_energy: float = 100.0
    energy_drain: float = 0.11
    toxin_cost: float = 0.09
    move_cost: float = 0.05
    # a brain is expensive tissue - roughly a fifth of a human's resting budget
    # goes to one. Without a price, networks bloat with neurons that do nothing
    # and the cost lands on the simulation instead of the organism.
    neuron_cost: float = 0.00015
    synapse_cost: float = 0.00002
    max_age: int = 5000          # baseline; each organism inherits its own jitter
    lifespan_jitter: float = 0.18

    # --- movement / senses ---
    cell_r: float = 4.5
    max_speed: float = 2.6
    turn_rate: float = 0.11
    sight: float = 200.0
    n_rays: int = 6
    # Spare capacity, reserved on purpose. Genomes carry more input and output
    # nodes than the world currently uses, and bodies carry more trait slots
    # than are currently meaningful. Adding a new sense, a new action or a new
    # kind of cell later means giving meaning to a slot that already exists,
    # which leaves every genome structurally unchanged - so a live run never has
    # to be thrown away to grow a new capability.
    max_inputs: int = 96
    max_outputs: int = 12
    init_density: float = 0.12   # share of possible input->output links at birth
    fov: float = 2.6
    bite_reach: float = 3.0
    bite_rate: float = 1.4         # energy drained per eater cell per tick
    # only a fraction of what you drain becomes yours. Lindeman's law: real
    # food chains lose about 90% per trophic level, which is exactly what stops
    # predators from outnumbering the things they eat
    bite_efficiency: float = 0.40
    digest_cap: float = 0.75       # even a specialist gut cannot beat physics
    # carrion must never be worth more than what died, or death becomes an
    # energy source and the dish runs away
    corpse_keep: float = 0.5       # the rest is lost to decomposition
    corpse_decay: float = 0.04     # rots away per tick
    max_corpses: int = 900
    # predation is expensive to run, which is what stops a bloom of eaters
    # stripping the herbivore base down to nothing
    eater_cost: float = 0.11       # extra upkeep per eater cell per tick

    # sound: cheap, omnidirectional, works at night and past obstacles
    hearing: float = 460.0
    chirp_cost: float = 0.02

    # --- reproduction ---
    split_energy: float = 1.7      # multiple of capacity needed to divide
    split_cost: float = 0.15       # fraction of energy lost in the split
    cell_build: float = 9.0        # energy a child pays per cell of its body
    p_sex: float = 0.12            # chance a split borrows genes from a neighbour
    mate_radius: float = 90.0

    # --- brain mutation ---
    p_weight: float = 0.8
    p_weight_replace: float = 0.1
    weight_step: float = 0.35
    weight_init_std: float = 1.0
    weight_cap: float = 8.0
    p_add_conn: float = 0.09
    p_recurrent: float = 0.25      # share of new connections allowed to loop back
    # duplication is how genomes actually get big; adding one neuron at a time
    # grows linearly and can never reach a large brain
    p_duplicate: float = 0.11
    duplicate_share: float = 0.35  # fraction of the hidden layer copied at once
    duplicate_jitter: float = 0.25
    # a fruit fly runs on about 135,000 neurons. That is the scale this is
    # aimed at, and it fits: such a brain evaluates in ~2.4 ms and its genome
    # is ~45 MB. What does not fit is many of them at once, hence the budget.
    max_neurons: int = 250_000
    # total neurons across the whole population. Duplication is refused above
    # this, so the dish cannot mutate its way into swapping out the machine.
    neuron_budget: int = 4_000_000
    p_add_node: float = 0.025
    p_toggle: float = 0.01
    p_inherit_disabled: float = 0.75
    add_conn_tries: int = 20

    # --- body mutation ---
    p_cell_add: float = 0.18
    p_segment: float = 0.07        # duplicate a block of the body plan
    segment_share: float = 0.5
    # an organism is born as a single cell and builds the rest as it can afford
    # it, so a large body is a life's work rather than an inheritance
    grow_reserve: float = 0.42     # share of capacity kept back before growing
    grow_every: int = 12           # ticks between growth steps
    p_cell_drop: float = 0.04
    p_trait: float = 0.12          # chance an expressed trait drifts
    p_trait_new: float = 0.015     # chance a dormant trait switches on
    trait_step: float = 0.14
    trait_cap: float = 1.6
    trait_cost: float = 0.055      # upkeep per unit of capability, anywhere
    size_capacity_bonus: float = 0.35  # intrinsic capacity gained per extra cell
    bite_blinds: float = 0.65      # how fast predation shuts photosynthesis off
    max_cells: int = 256

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
    stats_h: int = 240
    ui_scale: float = 0.0        # 0 = pick from the desktop resolution

    # --- terrain and weather ---
    n_obstacles: int = 16
    obstacle_r: tuple = (24.0, 70.0)
    p_event: float = 0.0009      # per tick chance a natural event starts
    event_len: tuple = (400, 1400)
    meteor_r: tuple = (120.0, 300.0)

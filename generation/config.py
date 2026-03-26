from dataclasses import dataclass

@dataclass
class GalaxyConfig:
    seed: int
    galaxy_radius_ly: float
    num_arms: int
    arm_tightness: float
    arm_width: float
    bulge_radius_fraction: float
    bulge_density_multiplier: float
    edge_falloff_exponent: float
    noise_scale_ly: float
    noise_amplitude: float
    chunk_size_ly: float
    max_stars_per_chunk: int
    visual_au_to_ly: float = 0.6

DEFAULT_CONFIG = GalaxyConfig(
    seed                    = 42,
    galaxy_radius_ly        = 50_000,
    num_arms                = 4,
    arm_tightness           = 0.30,
    arm_width               = 0.38,
    bulge_radius_fraction   = 0.10,
    bulge_density_multiplier= 3.5,
    edge_falloff_exponent   = 2.5,
    noise_scale_ly          = 3_000,
    noise_amplitude         = 0.55,
    chunk_size_ly           = 200,
    max_stars_per_chunk     = 40,
)

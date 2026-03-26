"""
Stellar density field — spiral arms + central bulge + noise perturbation.
Port of src/galaxy/DensityField.ts.
"""
import math
from .noise import ValueNoise2D
from .config import GalaxyConfig


class DensityField:
    def __init__(self, config: GalaxyConfig) -> None:
        self.config = config
        self.noise = ValueNoise2D(config.seed ^ 0xDEADBEEF)

    def get_density(self, world_x: float, world_y: float) -> float:
        config = self.config
        r = math.sqrt(world_x * world_x + world_y * world_y)
        max_r = config.galaxy_radius_ly

        if r > max_r * 1.1:
            return 0.0

        theta = math.atan2(world_y, world_x)
        r_norm = r / max_r

        # ── Component 1: Spiral arms ─────────────────────────────────────────
        arm_density = 0.0
        if r > 0:
            for i in range(config.num_arms):
                arm_base_angle = (2 * math.pi * i) / config.num_arms
                arm_center_angle = arm_base_angle + config.arm_tightness * math.log(r / 200 + 1)

                angular_dist = abs(((theta - arm_center_angle + math.pi) % (2 * math.pi)) - math.pi)

                arm_contrib = math.exp(
                    -(angular_dist * angular_dist) / (2 * config.arm_width * config.arm_width)
                )
                arm_density = max(arm_density, arm_contrib)
        else:
            arm_density = 1.0

        radial_envelope = (
            math.exp(-math.pow(r_norm, config.edge_falloff_exponent) * 3.5)
            * (1 - math.exp(-r_norm * 8))
        )
        arm_density *= radial_envelope

        # ── Component 2: Central bulge ────────────────────────────────────────
        bulge_r = config.bulge_radius_fraction * max_r
        bulge_density = (
            config.bulge_density_multiplier
            * math.exp(-(r * r) / (2 * bulge_r * bulge_r))
            / config.bulge_density_multiplier
        )

        # ── Combine ───────────────────────────────────────────────────────────
        density = max(arm_density, bulge_density * config.bulge_density_multiplier * 0.3)
        density = max(0.0, min(1.0, density))

        # ── Component 3: Noise perturbation ───────────────────────────────────
        if density > 0.001:
            nx = world_x / config.noise_scale_ly
            ny = world_y / config.noise_scale_ly
            noise_val = self.noise.fbm(nx, ny, 4)
            perturbation = (noise_val - 0.5) * config.noise_amplitude
            density = max(0.0, min(1.0, density + density * perturbation))

        return density

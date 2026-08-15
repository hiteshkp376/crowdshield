"""
social_force_model.py — Module F1: core crowd physics simulation.

Implements a simplified, vectorized version of Helbing & Molnar's Social
Force Model (1995) -- the established pedestrian-dynamics technique used
across crowd-safety engineering research (same lineage as Fruin LOS,
which Module A already uses).

Each agent experiences three forces:
  1. DRIVE force   -- pulls the agent toward its goal at a desired speed
  2. AGENT REPULSION -- pushes agents apart as they get close (isotropic
     exponential repulsion, per Helbing's original formulation)
  3. WALL REPULSION -- pushes agents away from walls/obstacles, computed
     via a distance-transform field over the venue's walkable-space mask

PANIC-PROPAGATION LAYER (the addition that answers the "panic
propagation" functional requirement -- see module docstring in
simulation_engine.py for the important honesty note about what this
is and is not claiming to do):
  - Each agent carries a stress value in [0, 1] (calm -> panicked)
  - Stress rises when an agent's local density crosses the same
    crush-risk threshold Module A/fruin_los.py already uses
  - Stress spreads to nearby agents (contagion) and decays over time
    in low-density conditions
  - A trigger event can inject sudden stress at a specific point in
    space/time (e.g. "person falls near VIP corridor" -- the actual
    Karur mechanism), and panicked agents move faster and less
    predictably, which is how real panic contributes to crush dynamics
"""

from dataclasses import dataclass
import numpy as np

# --- Social force model constants (standard-ish values from SFM literature,
# tuned to reasonable pedestrian scale: meters, seconds) ---
DESIRED_SPEED_MPS = 1.3          # average adult walking speed
PANICKED_SPEED_MULTIPLIER = 1.6  # panicked agents rush
RELAXATION_TIME_S = 0.5          # how quickly agents accelerate toward desired velocity

AGENT_REPULSION_STRENGTH = 2.1
AGENT_REPULSION_RANGE_M = 0.3
AGENT_RADIUS_M = 0.25            # ~shoulder width personal space

WALL_REPULSION_STRENGTH = 5.0
WALL_REPULSION_RANGE_M = 0.2

MAX_SPEED_MPS = 3.0              # hard cap, panicked agents included

# --- Panic contagion constants ---
CRUSH_RISK_DENSITY_PEOPLE_PER_M2 = 4.0   # matches fruin_los.py's threshold
LOCAL_DENSITY_RADIUS_M = 1.5
STRESS_RISE_RATE = 0.15           # per second, when in high-density condition
STRESS_CONTAGION_RATE = 0.25      # per second, pulled toward neighbors' avg stress
STRESS_DECAY_RATE = 0.08          # per second, when in low-density condition
STRESS_CONTAGION_RADIUS_M = 2.0
PANIC_THRESHOLD = 0.6             # stress value above which an agent is "panicked"


@dataclass
class SimulationState:
    positions_m: np.ndarray   # (N, 2) agent positions in meters
    velocities_mps: np.ndarray  # (N, 2)
    stress: np.ndarray        # (N,) in [0, 1]
    goals_m: np.ndarray       # (N, 2) each agent's current goal position


class SocialForceSimulation:
    """
    Vectorized multi-agent social force simulation with a panic-contagion
    layer. Operates entirely in meters/seconds; the caller (simulation_engine)
    handles converting to/from pixel space for rendering.
    """

    def __init__(self, positions_m: np.ndarray, goals_m: np.ndarray,
                 wall_distance_field_m: np.ndarray, field_origin_m: tuple[float, float],
                 field_resolution_m_per_cell: float, dt_s: float = 0.15,
                 agent_radius_m: float = AGENT_RADIUS_M,
                 agent_repulsion_range_m: float = AGENT_REPULSION_RANGE_M):
        # agent_radius_m / agent_repulsion_range_m are configurable because
        # simulation_engine.py uses "super-agents" that each represent
        # multiple real people (for hackathon-scale performance). A
        # super-agent's effective personal-space footprint must scale up
        # accordingly (by sqrt(people_per_agent), since space scales with
        # area) -- otherwise many real people get compressed into an
        # unrealistically small simulated area and density readings come
        # out inflated. See simulation_engine.py's run_simulation().
        self.agent_radius_m = agent_radius_m
        self.agent_repulsion_range_m = agent_repulsion_range_m
        n = positions_m.shape[0]
        self.state = SimulationState(
            positions_m=positions_m.copy(),
            velocities_mps=np.zeros((n, 2)),
            stress=np.zeros(n),
            goals_m=goals_m.copy(),
        )
        self.wall_distance_field_m = wall_distance_field_m  # 2D grid, meters to nearest wall
        self.field_origin_m = field_origin_m
        self.field_resolution_m_per_cell = field_resolution_m_per_cell
        self.dt_s = dt_s
        self.n = n
        self._pending_triggers: list[dict] = []
        self.time_s = 0.0

    def inject_trigger_event(self, location_m: tuple[float, float], radius_m: float = 3.0,
                              at_time_s: float = 0.0):
        """Schedule a panic trigger: agents within radius_m of location_m
        at the given simulation time have their stress set to max.
        Models a discrete disturbance event, e.g. someone falling."""
        self._pending_triggers.append({
            "location_m": np.array(location_m),
            "radius_m": radius_m,
            "at_time_s": at_time_s,
            "fired": False,
        })

    def _sample_wall_distance(self, positions_m: np.ndarray) -> np.ndarray:
        """Nearest-cell lookup of the precomputed wall-distance field."""
        ox, oy = self.field_origin_m
        col = ((positions_m[:, 0] - ox) / self.field_resolution_m_per_cell).astype(int)
        row = ((positions_m[:, 1] - oy) / self.field_resolution_m_per_cell).astype(int)
        h, w = self.wall_distance_field_m.shape
        col = np.clip(col, 0, w - 1)
        row = np.clip(row, 0, h - 1)
        return self.wall_distance_field_m[row, col]

    def _wall_repulsion_force(self, positions_m: np.ndarray) -> np.ndarray:
        """Direction away from the nearest wall, magnitude via exponential
        decay with distance (finite-difference gradient of the distance field)."""
        eps = 0.15
        dist_center = self._sample_wall_distance(positions_m)

        dx = positions_m.copy(); dx[:, 0] += eps
        dist_dx = self._sample_wall_distance(dx)
        dy = positions_m.copy(); dy[:, 1] += eps
        dist_dy = self._sample_wall_distance(dy)

        grad_x = (dist_dx - dist_center) / eps
        grad_y = (dist_dy - dist_center) / eps
        grad = np.stack([grad_x, grad_y], axis=1)
        norm = np.linalg.norm(grad, axis=1, keepdims=True)
        norm[norm < 1e-6] = 1.0
        direction = grad / norm  # points toward increasing distance = away from wall

        magnitude = WALL_REPULSION_STRENGTH * np.exp(-dist_center / WALL_REPULSION_RANGE_M)
        return direction * magnitude[:, None]

    def _agent_repulsion_force(self, positions_m: np.ndarray) -> np.ndarray:
        """Pairwise isotropic exponential repulsion (vectorized, O(N^2) --
        fine for hackathon-scale agent counts)."""
        diff = positions_m[:, None, :] - positions_m[None, :, :]  # (N, N, 2)
        dist = np.linalg.norm(diff, axis=2)
        np.fill_diagonal(dist, np.inf)

        direction = diff / dist[:, :, None]
        magnitude = AGENT_REPULSION_STRENGTH * np.exp(
            (2 * self.agent_radius_m - dist) / self.agent_repulsion_range_m
        )
        magnitude[dist > 5.0] = 0  # negligible influence beyond 5m, skip for stability
        force = (direction * magnitude[:, :, None]).sum(axis=1)
        return force

    def _local_density(self, positions_m: np.ndarray) -> np.ndarray:
        """People per m^2 within LOCAL_DENSITY_RADIUS_M of each agent."""
        diff = positions_m[:, None, :] - positions_m[None, :, :]
        dist = np.linalg.norm(diff, axis=2)
        neighbor_count = (dist <= LOCAL_DENSITY_RADIUS_M).sum(axis=1)  # includes self
        area = np.pi * LOCAL_DENSITY_RADIUS_M ** 2
        return neighbor_count / area

    def _update_stress(self, positions_m: np.ndarray, stress: np.ndarray) -> np.ndarray:
        density = self._local_density(positions_m)
        high_density = density >= CRUSH_RISK_DENSITY_PEOPLE_PER_M2

        # Contagion: pull each agent's stress toward the mean stress of
        # nearby agents (within STRESS_CONTAGION_RADIUS_M).
        diff = positions_m[:, None, :] - positions_m[None, :, :]
        dist = np.linalg.norm(diff, axis=2)
        neighbor_mask = dist <= STRESS_CONTAGION_RADIUS_M
        neighbor_counts = neighbor_mask.sum(axis=1)
        neighbor_stress_sum = (neighbor_mask * stress[None, :]).sum(axis=1)
        neighbor_avg_stress = np.divide(
            neighbor_stress_sum, neighbor_counts,
            out=np.zeros_like(stress), where=neighbor_counts > 0
        )

        new_stress = stress.copy()
        new_stress += np.where(high_density, STRESS_RISE_RATE * self.dt_s, 0)
        new_stress += (neighbor_avg_stress - stress) * STRESS_CONTAGION_RATE * self.dt_s
        new_stress -= np.where(~high_density, STRESS_DECAY_RATE * self.dt_s, 0)
        return np.clip(new_stress, 0.0, 1.0)

    def _apply_triggers(self):
        for trigger in self._pending_triggers:
            if trigger["fired"] or self.time_s < trigger["at_time_s"]:
                continue
            dist = np.linalg.norm(self.state.positions_m - trigger["location_m"], axis=1)
            affected = dist <= trigger["radius_m"]
            self.state.stress[affected] = 1.0
            trigger["fired"] = True

    def step(self):
        self._apply_triggers()

        pos = self.state.positions_m
        vel = self.state.velocities_mps
        stress = self.state.stress
        goals = self.state.goals_m

        to_goal = goals - pos
        dist_to_goal = np.linalg.norm(to_goal, axis=1, keepdims=True)
        dist_to_goal[dist_to_goal < 1e-6] = 1e-6
        direction_to_goal = to_goal / dist_to_goal

        panicked = stress >= PANIC_THRESHOLD
        speed = np.where(panicked, DESIRED_SPEED_MPS * PANICKED_SPEED_MULTIPLIER, DESIRED_SPEED_MPS)

        # Panicked agents get directional noise -- erratic movement is a
        # real, documented feature of panic-driven crowd motion.
        noise = np.zeros_like(direction_to_goal)
        n_panicked = panicked.sum()
        if n_panicked > 0:
            noise[panicked] = np.random.normal(0, 0.3, size=(n_panicked, 2))

        desired_velocity = (direction_to_goal + noise) * speed[:, None]
        drive_force = (desired_velocity - vel) / RELAXATION_TIME_S

        total_force = (
            drive_force
            + self._agent_repulsion_force(pos)
            + self._wall_repulsion_force(pos)
        )

        new_vel = vel + total_force * self.dt_s
        speed_now = np.linalg.norm(new_vel, axis=1)
        over_limit = speed_now > MAX_SPEED_MPS
        if over_limit.any():
            new_vel[over_limit] *= (MAX_SPEED_MPS / speed_now[over_limit])[:, None]

        new_pos = pos + new_vel * self.dt_s
        new_stress = self._update_stress(new_pos, stress)

        self.state.positions_m = new_pos
        self.state.velocities_mps = new_vel
        self.state.stress = new_stress
        self.time_s += self.dt_s

    def current_density_per_agent(self) -> np.ndarray:
        return self._local_density(self.state.positions_m)

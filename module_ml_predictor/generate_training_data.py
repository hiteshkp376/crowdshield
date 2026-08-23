"""
generate_training_data.py — runs many varied Module F1 simulations and
extracts (features, label) rows for training the early-warning model.

Varies: which of the 5 real venue maps, venue scale (small/large),
turnout, and whether/where/when a trigger event fires -- so the
resulting dataset covers both calm and dangerous scenarios across
different venue geometries, not just one repeated setup.

Run:
    python generate_training_data.py --n-runs 400 --output training_data.csv
"""

import argparse
import csv
import random
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).parent.parent / "module_a"))
sys.path.insert(0, str(Path(__file__).parent.parent / "module_f"))
from blueprint_pipeline import analyze_blueprint  # noqa: E402
from simulation_engine import run_simulation  # noqa: E402
from feature_extraction import extract_zone_window_features, FEATURE_COLUMNS  # noqa: E402

MAPS_DIR = Path(__file__).parent.parent / "module_a" / "test_data" / "maps"
MAP_FILES = [
    "corridor_rally.png", "twin_gate_funnel.png", "procession_route.png",
    "temple_radial.png", "stadium_multi_exit.png",
]


def random_scenario(rng: random.Random) -> dict:
    map_file = rng.choice(MAP_FILES)
    scale = rng.uniform(0.03, 0.18)          # small to large venue
    turnout = rng.choice([300, 800, 2000, 5000, 10000, 20000, 30000])
    duration = rng.uniform(20.0, 35.0)

    trigger = None
    if rng.random() < 0.55:  # ~55% of runs get a trigger -- enough
                              # positive examples without making every
                              # run dangerous (the model needs to see
                              # calm scenarios too)
        trigger = {
            "zone_id": None,  # filled in after we know real zone_ids
            "at_time_s": rng.uniform(2.0, 8.0),
            "radius_m": rng.uniform(8.0, 25.0),
        }
    return {
        "map_file": map_file, "scale": scale, "turnout": turnout,
        "duration": duration, "trigger": trigger,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-runs", type=int, default=400)
    parser.add_argument("--output", default="training_data.csv")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    n_label_1 = 0
    n_label_0 = 0
    total_rows = 0

    # Write incrementally (not all-at-once at the end) so a long run
    # still leaves usable partial data if interrupted.
    with open(args.output, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(FEATURE_COLUMNS + ["label_danger_later"])

        for i in range(args.n_runs):
            scenario = random_scenario(rng)
            img_path = MAPS_DIR / scenario["map_file"]
            img = cv2.imread(str(img_path))

            try:
                blueprint_output = analyze_blueprint(
                    img, scale_m_per_px=scenario["scale"], expected_turnout=scenario["turnout"],
                )
                if "error" in blueprint_output or not blueprint_output.get("zones"):
                    continue

                trigger = scenario["trigger"]
                if trigger is not None:
                    trigger["zone_id"] = rng.choice(blueprint_output["zones"])["zone_id"]

                f1_result = run_simulation(
                    blueprint_output, expected_turnout=scenario["turnout"],
                    duration_s=scenario["duration"], trigger_event=trigger,
                    random_seed=rng.randint(0, 1_000_000),
                )

                zone_features = extract_zone_window_features(blueprint_output, f1_result)
                for zf in zone_features:
                    row = [getattr(zf, col) for col in FEATURE_COLUMNS] + [zf.label_danger_later]
                    writer.writerow(row)
                    total_rows += 1
                    if zf.label_danger_later == 1:
                        n_label_1 += 1
                    else:
                        n_label_0 += 1
                f.flush()

            except Exception as e:
                print(f"  run {i} failed ({scenario['map_file']}, turnout={scenario['turnout']}): {e}")
                continue

            if (i + 1) % 25 == 0:
                print(f"  {i + 1}/{args.n_runs} runs done -- {total_rows} zone-rows so far "
                      f"({n_label_1} danger, {n_label_0} safe)")

    print(f"\nDone. {total_rows} total zone-rows written to {args.output}")
    if total_rows > 0:
        print(f"  label=1 (danger later): {n_label_1} ({100*n_label_1/total_rows:.1f}%)")
        print(f"  label=0 (safe): {n_label_0} ({100*n_label_0/total_rows:.1f}%)")


if __name__ == "__main__":
    main()

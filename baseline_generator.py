import subprocess
import json
import os

CACHE_DIR = "baselines"

def run_pike(scenario_path):
    """Run Pike on a scenario directory and return the action list."""
    result = subprocess.run(
        ["pike", "scan", "-d", scenario_path, "-o", "json"],
        capture_output=True,
        text=True
    )

    if not result.stdout.strip():
        raise RuntimeError(f"Pike returned empty output for {scenario_path}. stderr: {result.stderr}")

    pike_output = json.loads(result.stdout)
    actions = pike_output["Statement"][0]["Action"]
    return actions

def get_baseline(scenario_path):
    """
    Return cached baseline if it exists, otherwise run Pike and cache it.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)

    # Use the scenario directory name as the cache key
    scenario_name = os.path.basename(scenario_path)
    cache_file = os.path.join(CACHE_DIR, f"{scenario_name}.json")

    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            return json.load(f)

    # Cache miss — run Pike and save
    actions = run_pike(scenario_path)
    baseline = {"Action": actions}

    with open(cache_file, "w") as f:
        json.dump(baseline, f, indent=2)

    return baseline
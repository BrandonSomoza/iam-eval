import json
import os
from collections import defaultdict

RESULTS_DIR = "results"

def load_results():
    all_results = []
    for fname in os.listdir(RESULTS_DIR):
        if fname.endswith(".json") and fname != "results.json":
            with open(os.path.join(RESULTS_DIR, fname)) as f:
                data = json.load(f)
                all_results.extend(data)
    return all_results

def print_table(results, model, prompt_version, tier):
    filtered = [r for r in results if r["model"] == model and r["prompt_version"] == prompt_version and r["tier"] == tier]
    if not filtered:
        return

    print(f"\nModel: {model} | Prompt: {prompt_version} | Tier: {tier.upper()}")
    header = f"{'Scenario':<45} {'Coverage':>10} {'Over-Priv':>10} {'Extra':>7} {'Missing':>9} {'Wildcard':>9} {'ParseErr':>9}"
    print(header)
    print("-" * len(header))
    for r in filtered:
        name = r["scenario"].replace("scenarios/", "")
        print(
            f"{name:<45} "
            f"{r['coverage']:>10.2f} "
            f"{r['over_privilege']:>10.2f} "
            f"{r['extra']:>7} "
            f"{r['missing']:>9} "
            f"{str(r['wildcard']):>9} "
            f"{str(r.get('parse_error', False)):>9}"
        )

def print_summary(results, model, prompt_version, tier):
    filtered = [r for r in results if r["model"] == model and r["prompt_version"] == prompt_version and r["tier"] == tier]
    if not filtered:
        return
    n = len(filtered)
    print(f"\n  Averages ({n} scenarios):")
    print(f"    Coverage:      {sum(r['coverage'] for r in filtered)/n:.2f}")
    print(f"    Over-Priv:     {sum(r['over_privilege'] for r in filtered)/n:.2f}")
    print(f"    Extra Actions: {sum(r['extra'] for r in filtered)/n:.1f}")
    print(f"    Missing:       {sum(r['missing'] for r in filtered)/n:.1f}")
    print(f"    Parse Errors:  {sum(1 for r in filtered if r.get('parse_error', False))}")
    print(f"    Exact Matches: {sum(1 for r in filtered if r.get('exact_match', False))}")

def print_cross_model_summary(results):
    models = sorted(set(r["model"] for r in results))
    prompts = sorted(set(r["prompt_version"] for r in results))
    tiers = sorted(set(r["tier"] for r in results))

    print("\n" + "="*80)
    print("CROSS-MODEL SUMMARY (Coverage | Over-Priv | Parse Errors)")
    print("="*80)

    for tier in tiers:
        print(f"\nTier: {tier.upper()}")
        header = f"{'Model':<45} {'Prompt':>8} {'Coverage':>10} {'Over-Priv':>10} {'Missing':>9} {'ParseErr':>9}"
        print(header)
        print("-" * len(header))
        for model in models:
            short = model.split("/")[-1]
            for prompt in prompts:
                filtered = [r for r in results if r["model"] == model and r["prompt_version"] == prompt and r["tier"] == tier]
                if not filtered:
                    continue
                n = len(filtered)
                avg_cov = sum(r["coverage"] for r in filtered) / n
                avg_op = sum(r["over_privilege"] for r in filtered) / n
                avg_miss = sum(r["missing"] for r in filtered) / n
                parse_err = sum(1 for r in filtered if r.get("parse_error", False))
                print(f"{short:<45} {prompt:>8} {avg_cov:>10.2f} {avg_op:>10.2f} {avg_miss:>9.1f} {parse_err:>9}")

def main():
    results = load_results()
    print(f"Loaded {len(results)} total scenario results")

    models = sorted(set(r["model"] for r in results))
    prompts = sorted(set(r["prompt_version"] for r in results))
    tiers = sorted(set(r["tier"] for r in results))

    for model in models:
        for prompt in prompts:
            for tier in tiers:
                print_table(results, model, prompt, tier)
                print_summary(results, model, prompt, tier)

    print_cross_model_summary(results)

if __name__ == "__main__":
    main()
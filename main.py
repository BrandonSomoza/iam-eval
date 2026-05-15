import json
import os
import time
import argparse
from baseline_generator import get_baseline
from llm_generator import generate_actions
from evaluator import evaluate_policy


MODELS = [
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "Qwen/Qwen2.5-7B-Instruct-Turbo",
    "meta-llama/Meta-Llama-3-8B-Instruct-Lite",
]

scenarios = {
    "simple": [
        "scenarios/simple/vpc_only",
        "scenarios/simple/vpc_igw",
        "scenarios/simple/vpc_public_subnet",
        "scenarios/simple/vpc_private_subnet",
        "scenarios/simple/vpc_two_subnets",
        "scenarios/simple/vpc_security_group",
        "scenarios/simple/vpc_pub_priv_subnets",
        "scenarios/simple/vpc_single_sg_rules",
        "scenarios/simple/vpc_two_sg",
        "scenarios/simple/vpc_igw_two_public_subnets",
        "scenarios/simple/vpc_private_subnets_only",
        "scenarios/simple/vpc_igw_sg",
        "scenarios/simple/vpc_three_subnets",
        "scenarios/simple/vpc_three_sg",
        "scenarios/simple/vpc_igw_private_subnet",
        "scenarios/simple/vpc_sg_icmp",
        "scenarios/simple/vpc_four_subnets",
        "scenarios/simple/vpc_sg_udp",
        "scenarios/simple/vpc_secondary_cidr",
        "scenarios/simple/vpc_igw_sg_subnet",
        "scenarios/simple/vpc_dedicated_tenancy",
        "scenarios/simple/vpc_no_dns",
        "scenarios/simple/vpc_multiple_route_tables",
        "scenarios/simple/vpc_sg_self_ref",
        "scenarios/simple/vpc_eip_only",
    ],
    "medium": [
        "scenarios/medium/main",
        "scenarios/medium/vpc_nat_no_bastion",
        "scenarios/medium/vpc_multi_az_nat",
        "scenarios/medium/vpc_vpn",
        "scenarios/medium/vpc_peering",
        "scenarios/medium/vpc_nacl",
        "scenarios/medium/vpc_flow_logs",
        "scenarios/medium/vpc_endpoints",
        "scenarios/medium/vpc_dhcp",
        "scenarios/medium/vpc_ipv6",
        "scenarios/medium/vpc_nat_sg",
        "scenarios/medium/vpc_nacl_sg",
        "scenarios/medium/vpc_peering_sg",
        "scenarios/medium/vpc_endpoints_sg",
        "scenarios/medium/vpc_multi_az_nat_sg",
        "scenarios/medium/vpc_ipv6_sg",
        "scenarios/medium/vpc_vpn_sg",
        "scenarios/medium/vpc_dhcp_nat",
        "scenarios/medium/vpc_nacl_nat",
        "scenarios/medium/vpc_endpoints_nat",
        "scenarios/medium/vpc_peering_nat",
        "scenarios/medium/vpc_secondary_cidr_nat",
        "scenarios/medium/vpc_nacl_endpoints",
        "scenarios/medium/vpc_three_tier_nacl",
        "scenarios/medium/vpc_flow_logs_nat",
    ],
}

# v1: original prompt (baseline)
PROMPT_V1 = """
Given the following Terraform configuration:

{terraform}

Generate ALL AWS IAM actions required to fully manage these resources,
including create, read, update, delete, and any supporting API calls
Terraform makes internally (tagging, describing, attribute modification).

Follow the principle of least privilege.

Return ONLY valid JSON:

{{
    "Action": ["service:Action1"]
}}
"""

# v2: explicit Terraform internals hint
PROMPT_V2 = """
Given the following Terraform configuration:

{terraform}

Generate ALL AWS IAM actions required to fully manage these resources.

Important: Terraform's AWS provider makes many internal API calls beyond
the obvious CRUD operations. These include:
- Describe/List calls to verify resource state after creation
- Attribute modification calls (e.g. ModifyXxxAttribute)
- Account-level describe calls (e.g. ec2:DescribeAccountAttributes)
- Tagging operations on every resource type

Follow the principle of least privilege.

Return ONLY valid JSON:

{{
    "Action": ["service:Action1"]
}}
"""

# v3: verification prompt — model sees both Terraform config and Pike ground truth
PROMPT_V3 = """
Given the following Terraform configuration:

{terraform}

A static analysis tool (Pike) generated the following IAM actions:

{pike_output}

Is this output correct and complete for managing these Terraform resources?

Identify:
1. Any actions in the list that are NOT required (false positives)
2. Any actions that are MISSING from the list (false negatives)

Then return the corrected final list as ONLY valid JSON:

{{
    "Action": ["service:Action1"]
}}
"""

PROMPTS = {
    "v1": PROMPT_V1,
    "v2": PROMPT_V2,
    "v3": PROMPT_V3,
}


def load_terraform(path):
    tf_file = os.path.join(path, "main.tf")
    with open(tf_file, "r") as f:
        lines = f.readlines()
    lines = [l for l in lines if not l.strip().startswith("#") and l.strip() != ""]
    return "".join(lines)


def wrap_policy(actions):
    return {
        "Statement": [{
            "Effect": "Allow",
            "Action": actions
        }]
    }


def print_table(tier_results, model, prompt_version):
    print(f"\nModel: {model} | Prompt: {prompt_version}")
    header = f"{'Scenario':<45} {'Coverage':>10} {'Over-Priv':>10} {'Extra':>7} {'Missing':>9} {'Wildcard':>9}"
    print(header)
    print("-" * len(header))
    for r in tier_results:
        name = r["scenario"].replace("scenarios/", "")
        print(
            f"{name:<45} "
            f"{r['coverage']:>10.2f} "
            f"{r['over_privilege']:>10.2f} "
            f"{r['extra']:>7} "
            f"{r['missing']:>9} "
            f"{str(r['wildcard']):>9}"
        )


def print_tier_summary(tier_results):
    avg_coverage = sum(r["coverage"] for r in tier_results) / len(tier_results)
    avg_over_priv = sum(r["over_privilege"] for r in tier_results) / len(tier_results)
    avg_extra = sum(r["extra"] for r in tier_results) / len(tier_results)
    avg_missing = sum(r["missing"] for r in tier_results) / len(tier_results)
    parse_errors = sum(1 for r in tier_results if r.get("parse_error", False))

    print(f"\n  Tier Averages:")
    print(f"    Coverage:      {avg_coverage:.2f}")
    print(f"    Over-Priv:     {avg_over_priv:.2f}")
    print(f"    Extra Actions: {avg_extra:.1f}")
    print(f"    Missing:       {avg_missing:.1f}")
    print(f"    Parse Errors:  {parse_errors}")


def save_results(all_results, model, prompt_version):
    # Sanitize model name for use as filename
    model_slug = model.replace("/", "_").replace(".", "-")
    path = f"results/{model_slug}_{prompt_version}.json"
    os.makedirs("results", exist_ok=True)
    with open(path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to {path}")


def run_model(model, tiers_to_run, prompt_version):
    all_results = []
    prompt_template = PROMPTS[prompt_version]

    for tier, paths in tiers_to_run.items():
        print(f"\n{'='*60}")
        print(f"Tier: {tier.upper()} | Prompt: {prompt_version}")
        print(f"{'='*60}")

        tier_results = []

        for path in paths:
            terraform = load_terraform(path)
            baseline = get_baseline(path)
            prompt = prompt_template.format(terraform=terraform, pike_output=json.dumps(baseline["Action"], indent=2))

            parse_error = False
            llm_actions = []

            try:
                llm_actions = generate_actions(prompt, model=model)
                if isinstance(llm_actions, dict):
                    llm_actions = llm_actions["Action"]
            except Exception as e:
                print(f"  [PARSE ERROR] {path}: {e}")
                parse_error = True

            truth_policy = wrap_policy(baseline["Action"])
            pred_policy = wrap_policy(llm_actions)

            results = evaluate_policy(pred_policy, truth_policy)

            entry = {
                "model": model,
                "prompt_version": prompt_version,
                "tier": tier,
                "scenario": path,
                "parse_error": parse_error,
                "coverage": results["coverage"],
                "over_privilege": results["over_privilege"],
                "exact_match": results["exact_match"],
                "wildcard": results["uses_wildcard"],
                "extra": len(results["extra_actions"]),
                "missing": len(results["missing_actions"]),
                "extra_actions": sorted(results["extra_actions"]),
                "missing_actions": sorted(results["missing_actions"]),
            }

            tier_results.append(entry)
            all_results.append(entry)
            time.sleep(1)

        print_table(tier_results, model, prompt_version)
        print_tier_summary(tier_results)

    save_results(all_results, model, prompt_version)
    return all_results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tier",
        choices=["simple", "medium", "all"],
        default="all",
        help="Which complexity tier to run"
    )
    parser.add_argument(
        "--model",
        choices=MODELS + ["all"],
        default=MODELS[0],
        help="Which model to use, or 'all' to run all models"
    )
    parser.add_argument(
        "--prompt",
        choices=["v1", "v2", "v3", "all"],
        default="all",
        help="Which prompt version to use, or 'all' to run both"
    )
    args = parser.parse_args()

    tiers_to_run = (
        {args.tier: scenarios[args.tier]}
        if args.tier != "all"
        else scenarios
    )

    models_to_run = MODELS if args.model == "all" else [args.model]
    prompts_to_run = list(PROMPTS.keys()) if args.prompt == "all" else [args.prompt]

    for model in models_to_run:
        for prompt_version in prompts_to_run:
            print(f"\n{'#'*60}")
            print(f"# Model: {model} | Prompt: {prompt_version}")
            print(f"{'#'*60}")
            run_model(model, tiers_to_run, prompt_version)
            time.sleep(5)


if __name__ == "__main__":
    main()
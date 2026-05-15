def extract_actions(policy_json):
    """
    Normalize IAM policy into allow/deny sets.
    """
    allow = set()
    deny = set()

    statements = policy_json.get("Statement", [])
    if not isinstance(statements, list):
        statements = [statements]

    for stmt in statements:
        effect = stmt.get("Effect")
        actions = stmt.get("Action", [])

        if isinstance(actions, str):
            actions = [actions]

        actions = set(a.lower() for a in actions)

        if effect == "Allow":
            allow |= actions
        elif effect == "Deny":
            deny |= actions

    return {
        "allow": allow,
        "deny": deny
    }


# --- Metrics ---

def exact_match(pred, truth):
    return (
        pred["allow"] == truth["allow"] and
        pred["deny"] == truth["deny"]
    )


def permission_coverage(pred, truth):
    required = truth["allow"]

    if not required:
        return 1.0

    granted = pred["allow"]
    return len(required & granted) / len(required)


def over_privilege_rate(pred, truth):
    predicted = pred["allow"]
    required = truth["allow"]

    if not predicted:
        return 0.0

    extra = predicted - required
    return len(extra) / len(predicted)


def deny_violations(pred, truth):
    denied = truth["deny"]
    granted = pred["allow"]

    return len(denied & granted)


# --- Main evaluator ---

def evaluate_policy(pred_policy_json, truth_policy_json):
    pred = extract_actions(pred_policy_json)
    truth = extract_actions(truth_policy_json)

    extra = pred["allow"] - truth["allow"]
    missing = truth["allow"] - pred["allow"]
    wildcard = any("*" in action for action in pred["allow"])

    return {
        # original debug info (keep this, it's useful)
        "extra_actions": list(extra),
        "missing_actions": list(missing),
        "uses_wildcard": wildcard,

        # new metrics
        "exact_match": exact_match(pred, truth),
        "coverage": permission_coverage(pred, truth),
        "over_privilege": over_privilege_rate(pred, truth),
        "deny_violations": deny_violations(pred, truth),
    }
"""
Rules Engine — the competitive moat.
Pure functions, no DB calls, fully testable in isolation.
Input:  value (mg/dL), context (fasting|post_meal|random), user_profile dict
Output: classification dict with status, severity, color, thresholds used
"""

# Standard ADA thresholds (mg/dL)
THRESHOLDS = {
    "fasting": {
        "low":             70,
        "normal_max":      99,
        "prediabetes_max": 125,
        # above prediabetes_max → high
    },
    "post_meal": {
        "low":             70,
        "normal_max":      139,
        "prediabetes_max": 199,
    },
    "random": {
        "low":             70,
        "normal_max":      139,
        "prediabetes_max": 199,
    },
}

COLOR_MAP = {
    "low":         "red",
    "normal":      "green",
    "prediabetes": "yellow",
    "high":        "red",
}

SEVERITY_MAP = {
    "low":         "critical",
    "normal":      "good",
    "prediabetes": "warning",
    "high":        "critical",
}

DISPLAY_LABELS = {
    "low":         "Low",
    "normal":      "Normal",
    "prediabetes": "Borderline",
    "high":        "High",
}


def classify(value: int, context: str = "random", doctor_targets: dict = None) -> dict:
    """
    Classify a glucose reading.

    If doctor_targets are set, apply them for fasting/post_meal context
    and fall back to ADA standards otherwise.
    """
    context = context if context in THRESHOLDS else "random"
    thresholds = _resolve_thresholds(context, doctor_targets)

    if value < thresholds["low"]:
        status = "low"
    elif value <= thresholds["normal_max"]:
        status = "normal"
    elif value <= thresholds["prediabetes_max"]:
        status = "prediabetes"
    else:
        status = "high"

    return {
        "status":         status,
        "severity":       SEVERITY_MAP[status],
        "color":          COLOR_MAP[status],
        "display_label":  DISPLAY_LABELS[status],
        "value":          value,
        "context":        context,
        "thresholds":     thresholds,
    }


def _resolve_thresholds(context: str, doctor_targets: dict = None) -> dict:
    """Use doctor targets when set, otherwise ADA defaults."""
    base = dict(THRESHOLDS[context])

    if doctor_targets:
        if context == "fasting":
            base["normal_max"] = doctor_targets.get("fasting_max", base["normal_max"])
            base["low"] = doctor_targets.get("fasting_min", base["low"])
        elif context == "post_meal":
            base["normal_max"] = doctor_targets.get("post_meal_max", base["normal_max"])

    return base


def is_urgent(classification: dict) -> bool:
    """True if the reading needs immediate attention."""
    value = classification["value"]
    return classification["status"] == "low" or value >= 300

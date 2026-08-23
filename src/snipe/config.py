"""Configuration loader for SNIPE scanner."""

from pathlib import Path

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"


def load_config(config_path: Path | None = None) -> dict:
    """Load SNIPE configuration from YAML file.

    Args:
        config_path: Path to config file. Defaults to project root config.yaml.

    Returns:
        Configuration dictionary with all thresholds and parameters.
    """
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        config = yaml.safe_load(f)

    _validate_config(config)
    return config


def _validate_config(config: dict) -> None:
    """Validate that all required config sections and keys exist."""
    required_sections = [
        "universe",
        "trend_template",
        "vcp",
        "stage_analysis",
        "breakout",
        "canslim",
        "edge_scoring",
        "market_regime",
        "position_sizing",
        "sell_rules",
        "pipeline",
        "data",
    ]
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required config section: {section}")

    # Validate edge scoring weights sum to 100
    es = config["edge_scoring"]
    total_weight = (
        es["weight_edge_count"]
        + es["weight_vcp_quality"]
        + es["weight_trend_template"]
        + es["weight_canslim"]
        + es["weight_volume_ratio"]
    )
    if total_weight != 100:
        raise ValueError(
            f"Edge scoring weights must sum to 100, got {total_weight}"
        )

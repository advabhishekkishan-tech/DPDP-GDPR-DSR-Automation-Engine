from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any


@dataclass
class JurisdictionRule:
    name: str
    response_days: int | None
    extension_days: int
    notes: str


class RulesEngine:
    """Configuration-driven legal timing and retention decision layer.

    This prototype deliberately avoids treating one deadline as universal law.
    Production deployments should load current legal rules from a governed source.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def deadline(self, jurisdiction: str, created_at: date) -> date | None:
        rule = self.config["jurisdictions"].get(jurisdiction)
        if not rule or rule.get("response_days") is None:
            return None
        return created_at + timedelta(days=int(rule["response_days"]))

    def retention_action(self, tags: list[str]) -> str:
        rules = self.config.get("retention_rules", {})
        actions = [rules[tag]["action"] for tag in tags if tag in rules]
        if "PRESERVE" in actions:
            return "PRESERVE"
        if "RESTRICT" in actions:
            return "RESTRICT"
        if "ANONYMIZE" in actions:
            return "ANONYMIZE"
        return "ERASE"

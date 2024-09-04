from dataclasses import dataclass, asdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import HealthStatusMixin
else:
    HealthStatusMixin = Any


@dataclass
class CheckResult:
    """The result for a particular device check."""

    title: str
    key: str
    passed: bool | None
    feedback: str


class CheckResults(list[CheckResult]):
    """A list of device check results."""

    @classmethod
    def run_checks(cls, obj: HealthStatusMixin) -> "CheckResults":
        """Run checks for a node and return the results."""
        results = cls()
        for check in obj.health_checks:
            check_func = check.get("func", bool)
            key = check["key"]
            setting_value = None
            # Metric is an attribute of the node
            if hasattr(obj, key):
                value = getattr(obj, key)
            else:
                # Metric is a function on the node
                get_func = getattr(obj, f"get_{check['key']}")
                value = get_func()
            if "setting" in check:
                settings = obj.get_settings()
                if settings:
                    setting_value = getattr(settings, check["setting"])
                    # Pass the setting value to the check func as well as the metric
                    if value is not None and setting_value is not None:
                        passed = check_func(value, setting_value)
                        feedbackType = passed
                    else:
                        passed = None
                        feedbackType = "NO_SETTING"
                else:
                    passed = None
                    feedbackType = "NO_SETTING"
            else:
                # Just pass the metric, the check doesn't depend on settings
                if value is not None:
                    passed = check_func(value)
                    feedbackType = passed
                else:
                    passed = None
                    feedbackType = "NO_DATA"
            results.append(
                CheckResult(
                    title=check["title"],
                    key=key,
                    passed=passed,
                    feedback=check["feedback"][feedbackType],
                )
            )
        return results

    @property
    def num_failed(self) -> int:
        """Get the number of failed checks."""
        return sum(1 for c in self if c.passed is False)

    @property
    def num_passed(self) -> int:
        """Get the number of passed checks."""
        return sum(1 for c in self if c.passed is True)

    @property
    def num_run(self) -> int:
        """Get the number of check that were run (i.e. passed != None)."""
        return sum(1 for c in self if c.passed is not None)

    def oll_korrect(self) -> bool:
        """Check whether all checks passed."""
        return self.num_failed == 0

    def fewer_than_half_failed(self) -> bool:
        """Check whether fewer than half failed."""
        return self.num_failed <= self.num_run / 2

    def more_than_half_failed_but_not_all(self) -> bool:
        """Check whether more than half of the checks failed (but not all)."""
        return self.num_failed > self.num_run / 2 and self.num_passed != 0

    def all_failed(self) -> bool:
        """Check whether all of the checks failed."""
        return self.num_passed == 0

    def alert_summary(self) -> str:
        """Summary of failing checks, used to generate alerts."""
        return "\n".join(f"{c.title}: {c.feedback}" for c in self if not c.passed)

    def serialize(self) -> list[dict]:
        """Serialize results as a list of primitive dicts."""
        return [asdict(c) for c in self]

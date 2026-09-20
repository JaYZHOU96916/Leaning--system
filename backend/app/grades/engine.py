from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


def decimal(value: int | float | str | Decimal) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid numeric grade value: {value!r}") from exc


@dataclass(frozen=True)
class GradeItem:
    id: int
    name: str
    points_possible: Decimal
    score: Decimal | None = None

    @property
    def is_remaining(self) -> bool:
        return self.score is None


@dataclass(frozen=True)
class GradeGroup:
    name: str
    weight_percent: Decimal
    items: tuple[GradeItem, ...]


@dataclass(frozen=True)
class GradeCalculation:
    current_weighted_percent: Decimal
    current_normalized_percent: Decimal | None
    max_possible_percent: Decimal
    remaining_weight_percent: Decimal


@dataclass(frozen=True)
class RequiredScore:
    target_percent: Decimal
    required_average_percent: Decimal | None
    required_points: Decimal | None
    max_possible_percent: Decimal
    feasible: bool
    reason: str | None = None


class WeightedGradeCalculator:
    def __init__(self, groups: tuple[GradeGroup, ...] | list[GradeGroup]):
        self.groups = tuple(groups)
        if not self.groups:
            raise ValueError("At least one assignment group is required")
        for group in self.groups:
            if group.weight_percent < 0:
                raise ValueError("Assignment group weights cannot be negative")
            if any(item.points_possible <= 0 for item in group.items):
                raise ValueError("points_possible must be greater than zero")

    def _linear_projection(
        self,
        assumed_remaining_percent: Decimal | None = None,
    ) -> tuple[Decimal, Decimal, Decimal]:
        constant = Decimal("0")
        coefficient = Decimal("0")
        graded_weight = Decimal("0")
        for group in self.groups:
            possible = sum((item.points_possible for item in group.items), Decimal("0"))
            graded_points = sum(
                (item.score for item in group.items if item.score is not None),
                Decimal("0"),
            )
            remaining_points = possible - sum(
                (item.points_possible for item in group.items if item.score is not None),
                Decimal("0"),
            )
            weight = group.weight_percent / Decimal("100")
            constant += weight * graded_points / possible * Decimal("100")
            if graded_points > 0 or remaining_points < possible:
                graded_weight += group.weight_percent
            if assumed_remaining_percent is None:
                coefficient += weight * remaining_points / possible
            else:
                constant += weight * assumed_remaining_percent * remaining_points / possible
        max_possible = constant + coefficient * Decimal("100")
        return constant, coefficient, max_possible

    def calculate(self) -> GradeCalculation:
        constant, coefficient, max_possible = self._linear_projection()
        remaining_weight = sum(
            (
                group.weight_percent
                for group in self.groups
                if any(item.is_remaining for item in group.items)
            ),
            Decimal("0"),
        )
        normalized = (
            constant / graded_weight * Decimal("100")
            if (graded_weight := Decimal("100") - remaining_weight) > 0
            else None
        )
        return GradeCalculation(
            current_weighted_percent=constant,
            current_normalized_percent=normalized,
            max_possible_percent=max_possible,
            remaining_weight_percent=remaining_weight,
        )

    def required_average_on_remaining(
        self,
        target_percent: int | float | str | Decimal,
    ) -> RequiredScore:
        target = decimal(target_percent)
        constant, coefficient, max_possible = self._linear_projection()
        if coefficient == 0:
            feasible = constant >= target
            return RequiredScore(
                target,
                Decimal("0") if feasible else None,
                Decimal("0") if feasible else None,
                max_possible,
                feasible,
                None if feasible else "No ungraded assessment capacity remains.",
            )
        required = (target - constant) / coefficient
        feasible = Decimal("0") <= required <= Decimal("100")
        if required < 0:
            return RequiredScore(target, Decimal("0"), Decimal("0"), max_possible, True)
        if required > 100:
            return RequiredScore(
                target,
                required,
                None,
                max_possible,
                False,
                "Target exceeds the maximum achievable weighted score.",
            )
        remaining_points = sum(
            (
                item.points_possible
                for group in self.groups
                for item in group.items
                if item.is_remaining
            ),
            Decimal("0"),
        )
        return RequiredScore(
            target,
            required,
            required / Decimal("100") * remaining_points,
            max_possible,
            feasible,
        )

    def required_score_for_item(
        self,
        item_id: int,
        target_percent: int | float | str | Decimal,
        *,
        assumed_other_remaining_percent: int | float | str | Decimal = 0,
    ) -> RequiredScore:
        target = decimal(target_percent)
        assumed = decimal(assumed_other_remaining_percent)
        selected: GradeItem | None = None
        constant = Decimal("0")
        coefficient = Decimal("0")
        max_possible = Decimal("0")
        for group in self.groups:
            possible = sum((item.points_possible for item in group.items), Decimal("0"))
            weight = group.weight_percent / Decimal("100")
            group_known = Decimal("0")
            selected_points = Decimal("0")
            other_remaining_points = Decimal("0")
            for item in group.items:
                if item.id == item_id:
                    selected = item
                    selected_points += item.points_possible
                elif item.score is not None:
                    group_known += item.score
                else:
                    other_remaining_points += item.points_possible
            constant += (
                weight
                * (group_known + assumed * other_remaining_points)
                / possible
                * Decimal("100")
            )
            coefficient += weight * selected_points / possible
            max_possible += (
                weight
                * (group_known + Decimal("100") * (selected_points + other_remaining_points))
                / possible
                * Decimal("100")
            )
        if selected is None or not selected.is_remaining:
            raise ValueError("item_id must identify an ungraded assessment")
        if coefficient == 0:
            return RequiredScore(
                target,
                None,
                None,
                max_possible,
                False,
                "Selected assessment has no weight.",
            )
        required = (target - constant) / coefficient
        feasible = Decimal("0") <= required <= Decimal("100")
        return RequiredScore(
            target,
            required,
            required / Decimal("100") * selected.points_possible if feasible else None,
            max_possible,
            feasible,
            None if feasible else "Target is outside the selected assessment's achievable range.",
        )

import abc
import dataclasses
import statistics
from collections import deque
from datetime import datetime, timedelta
from logging import getLogger
from typing import NamedTuple

from .const import MINIMUM_READINGS_TO_DECIDE_NEW_BASELINE
from .state_machine.base import (
    BaseState,
    BaseStateTransition,
    BaseStateMachine,
)
from .utils import RollingMedian

logger = getLogger(__name__)

# TODO mypy


class IdleState(BaseState):
    state_key = "idle"


class WaitingForConfirmationState(BaseState):
    state_key = "waiting_for_confirmation"


class CatPresentConfirmedState(BaseState):
    state_key = "cat_present"


class AfterCatState(BaseState):
    state_key = "after_cat"


class Reading(NamedTuple):
    time: datetime
    weight: float


@dataclasses.dataclass
class LitterboxContext:
    # Immutable parameters
    cat_weight_threshold: int
    min_presence_time: timedelta
    leave_timeout: timedelta
    after_cat_standard_deviation: int
    name: str

    # Mutable data
    cat_weight: float | None = None
    waste_weight: float | None = None
    recent_readings: deque[Reading] = dataclasses.field(default_factory=deque)
    recent_presence_readings: RollingMedian = RollingMedian()
    baseline_weight: float | None = None
    cat_arrived_datetime: datetime | None = (
        None  # TODO probably can be generalized with time_in_this_state
    )
    cat_confirmed_datetime: datetime | None = None

    @property
    def trigger_level(self) -> float | None:
        if self.baseline_weight is None:
            return None
        return self.baseline_weight + self.cat_weight_threshold

    # TODO: convert to ReadingsDeque
    def add_reading(self, reading: Reading):
        """Add a new reading (weight) with a timestamp, and prune old data."""
        logger.debug(
            f"{self.name}: Adding reading -> weight={reading.weight:.2f}, time={reading.time}"
        )
        self.recent_readings.append(reading)
        max_keep = timedelta(minutes=5)
        oldest_allowed = reading.time - max_keep

        while self.recent_readings and self.recent_readings[0].time < oldest_allowed:
            popped = self.recent_readings.popleft()
            logger.debug(f"{self.name}: Pruning old reading -> {popped}")  # TODO name everywhere


class BaseLitterboxTransition(BaseStateTransition[Reading, LitterboxContext], abc.ABC):
    @classmethod
    def on_triggered(cls, data: Reading, context: LitterboxContext):
        logger.debug(
            f"Transitioning from {cls.from_state.state_key} to {cls.to_state.state_key}: time: {data.time}, weight: {data.weight}"
        )


class CatDetectedTransition(BaseLitterboxTransition):
    from_state = IdleState
    to_state = WaitingForConfirmationState

    @classmethod
    def is_triggered(cls, data: Reading, context: LitterboxContext) -> bool:
        return data.weight > context.trigger_level

    @classmethod
    def on_triggered(cls, data: Reading, context: LitterboxContext):
        # Cat detected
        super().on_triggered(data, context)
        context.cat_arrived_datetime = data.time
        if context.recent_presence_readings:
            logger.error(
                "Presence readings were not cleared as expected. This may indicate a bug in the cat scale integration. Please report this issue at https://github.com/djbios/home-assistant-cat-scale/issues and include relevant logs."
            )
            context.recent_presence_readings.clear()
        context.recent_presence_readings.append(data.weight)

    @classmethod
    def on_not_triggered(cls, data: Reading, context: LitterboxContext):
        # Cat was not detected
        super().on_not_triggered(data, context)
        if context.recent_readings:
            median = statistics.median(r.weight for r in context.recent_readings)
            context.baseline_weight = median
            logger.debug(
                f"{context.name}: Updated baseline to median of recent: {context.baseline_weight:.2f}",
            )


class CatConfirmedTransition(BaseLitterboxTransition):
    from_state = WaitingForConfirmationState
    to_state = CatPresentConfirmedState

    @classmethod
    def is_triggered(cls, data: Reading, context: LitterboxContext) -> bool:
        return (
            data.weight >= context.trigger_level
            and (data.time - context.cat_arrived_datetime) >= context.min_presence_time
        )

    @classmethod
    def on_triggered(cls, data: Reading, context: LitterboxContext):
        super().on_triggered(data, context)
        context.cat_confirmed_datetime = data.time

    @classmethod
    def on_not_triggered(cls, data: Reading, context: LitterboxContext):
        super().on_not_triggered(data, context)
        context.recent_presence_readings.append(data.weight)


class CatNotConfirmed(BaseLitterboxTransition):
    from_state = WaitingForConfirmationState
    to_state = IdleState

    @classmethod
    def is_triggered(cls, data: Reading, context: LitterboxContext) -> bool:
        return data.weight < context.trigger_level

    @classmethod
    def on_triggered(cls, data: Reading, context: LitterboxContext):
        super().on_triggered(data, context)
        context.baseline_weight = data.weight
        context.recent_readings.clear()
        context.recent_presence_readings.clear()


class CatLeftTransition(BaseLitterboxTransition):
    from_state = CatPresentConfirmedState
    to_state = AfterCatState

    @classmethod
    def is_triggered(cls, data: Reading, context: LitterboxContext) -> bool:
        return data.weight < context.trigger_level

    @classmethod
    def on_triggered(cls, data: Reading, context: LitterboxContext):
        super().on_triggered(data, context)
        median_weight = context.recent_presence_readings.median or data.weight
        cat_weight = median_weight - context.baseline_weight
        if cat_weight < 0:
            logger.warning(
                f"{context.name}: Negative cat weight {cat_weight:.2f} detected. Possibly sensor drift/noise"
            )
            cat_weight = 0.0
        context.cat_weight = cat_weight

    @classmethod
    def on_not_triggered(cls, data: Reading, context: LitterboxContext):
        super().on_not_triggered(data, context)
        context.recent_presence_readings.append(data.weight)


class NotACatTransition(BaseLitterboxTransition):
    from_state = CatPresentConfirmedState
    to_state = IdleState

    @classmethod
    def is_triggered(cls, data: Reading, context: LitterboxContext) -> bool:
        return data.time - context.cat_confirmed_datetime > context.leave_timeout

    @classmethod
    def on_triggered(cls, data: Reading, context: LitterboxContext):
        super().on_triggered(data, context)
        context.baseline_weight = data.weight
        context.recent_readings.clear()
        context.recent_presence_readings.clear()


class BaselineNormalizedTransition(BaseLitterboxTransition):
    from_state = AfterCatState
    to_state = IdleState

    @classmethod
    def is_triggered(cls, data: Reading, context: LitterboxContext) -> bool:
        stand_dev = statistics.stdev(r.weight for r in context.recent_readings)
        return (
            stand_dev <= context.after_cat_standard_deviation
            and len(context.recent_readings) >= MINIMUM_READINGS_TO_DECIDE_NEW_BASELINE
        )

    @classmethod
    def on_triggered(cls, data: Reading, context: LitterboxContext):
        context.waste_weight = max(data.weight - context.baseline_weight, 0.0)
        context.baseline_weight = data.weight
        context.recent_readings.clear()


class LitterboxStateMachine(BaseStateMachine[Reading, LitterboxContext]):
    transitions = [
        CatDetectedTransition,
        CatConfirmedTransition,
        CatNotConfirmed,
        CatLeftTransition,
        NotACatTransition,
        BaselineNormalizedTransition,
    ]

    def process_data(self, data: Reading) -> type[BaseState]:
        # Set baseline on first call
        if self.context.baseline_weight is None:
            self.context.baseline_weight = data.weight

        # Always update recent readings
        self.context.add_reading(data)

        # Call transitions
        return super().process_data(data)

    def force_set_cat_weight(self, weight: float):
        self.context.cat_weight = weight

    # Public properties to not leak context
    @property
    def cat_weight(self):
        return self.context.cat_weight

    @property
    def waste_weight(self):
        return self.context.waste_weight

    @property
    def baseline_weight(self):
        return self.context.baseline_weight

import pytest

from custom_components.cat_scale.state_machine.base import (
    BaseState,
    BaseStateMachine,
    BaseStateTransition,
)


# ----- Test fixtures: simple states -----
class Idle(BaseState):
    state_key = "idle"


class Working(BaseState):
    state_key = "working"


class Done(BaseState):
    state_key = "done"


# Global counters to verify which transitions are evaluated
CALL_COUNTER = {
    "IdleToWorking": 0,
    "WorkingToDone": 0,
    "WorkingToIdle": 0,
    "WorkingToDoneForced": 0,
}


class IdleToWorking(BaseStateTransition[str, dict]):
    from_state = Idle
    to_state = Working

    @classmethod
    def should_change(cls, data: str, context: dict) -> bool:
        CALL_COUNTER["IdleToWorking"] += 1
        return data == "go"


class WorkingToDone(BaseStateTransition[str, dict]):
    from_state = Working
    to_state = Done

    @classmethod
    def should_change(cls, data: str, context: dict) -> bool:
        CALL_COUNTER["WorkingToDone"] += 1
        return bool(context.get("ready")) and data == "finish"


class WorkingToIdle(BaseStateTransition[str, dict]):
    from_state = Working
    to_state = Idle

    @classmethod
    def should_change(cls, data: str, context: dict) -> bool:
        CALL_COUNTER["WorkingToIdle"] += 1
        return data == "reset"


class WorkingToDoneForced(BaseStateTransition[str, dict]):
    """Higher-priority transition to Done when data == 'force'.
    Placed before WorkingToDone in transitions to test order sensitivity.
    """

    from_state = Working
    to_state = Done

    @classmethod
    def should_change(cls, data: str, context: dict) -> bool:
        CALL_COUNTER["WorkingToDoneForced"] += 1
        return data == "force"


class TestMachine(BaseStateMachine[str, dict]):
    # Order matters: the first matching transition that should_change wins
    transitions = [IdleToWorking, WorkingToDoneForced, WorkingToDone, WorkingToIdle]


# ----- Helper -----
def make_machine(initial_state=Idle, initial_context=None) -> TestMachine:
    if initial_context is None:
        initial_context = {}
    # Reset counters for isolation
    for k in CALL_COUNTER:
        CALL_COUNTER[k] = 0
    return TestMachine(initial_state, initial_context)


# ----- Tests -----
def test_no_transition_when_no_match():
    m = make_machine(initial_state=Idle)
    before = m.state
    result = m.process_data("noop")
    assert result is before
    assert m.state is Idle
    # Only transitions from Idle are checked
    assert CALL_COUNTER["IdleToWorking"] == 1
    assert CALL_COUNTER["WorkingToDone"] == 0
    assert CALL_COUNTER["WorkingToIdle"] == 0
    assert CALL_COUNTER["WorkingToDoneForced"] == 0


def test_simple_transition_happens():
    m = make_machine(initial_state=Idle)
    result = m.process_data("go")
    assert result is Working
    assert m.state is Working


def test_no_transition_if_condition_false_in_current_state():
    m = make_machine(initial_state=Working, initial_context={"ready": False})
    # Neither 'finish' with ready nor other triggers provided
    result = m.process_data("noop")
    assert result is Working
    assert m.state is Working
    # All Working* transitions should have been evaluated once
    assert CALL_COUNTER["WorkingToDoneForced"] == 1
    assert CALL_COUNTER["WorkingToDone"] == 1
    assert CALL_COUNTER["WorkingToIdle"] == 1


def test_context_used_by_transition():
    m = make_machine(initial_state=Working, initial_context={"ready": True})
    result = m.process_data("finish")
    assert result is Done
    assert m.state is Done


def test_order_sensitivity_first_match_wins():
    m = make_machine(initial_state=Working)
    # 'force' should trigger WorkingToDoneForced before other Working transitions
    result = m.process_data("force")
    assert result is Done
    assert m.state is Done
    # Ensure WorkingToDoneForced was evaluated and used, other Working transitions may still be checked
    assert CALL_COUNTER["WorkingToDoneForced"] >= 1


def test_multiple_steps_flow():
    m = make_machine(initial_state=Idle)
    assert m.state is Idle
    # Step 1: go -> Working
    assert m.process_data("go") is Working
    assert m.state is Working
    # Step 2: reset -> Idle
    assert m.process_data("reset") is Idle
    assert m.state is Idle


def test_get_all_states_returns_all_configured_states():
    states = TestMachine.get_all_states()
    assert states == {Idle, Working, Done}


def test_process_data_returns_current_state_when_no_change():
    m = make_machine(initial_state=Idle)
    assert m.process_data("noop") is Idle
    assert m.state is Idle


def test_bad_transition_same_from_to_raises():
    # Define a misconfigured transition dynamically to catch the assertion
    with pytest.raises(AssertionError):

        class Bad(BaseStateTransition[str, dict]):
            from_state = Idle
            to_state = Idle

            @classmethod
            def should_change(cls, data: str, context: dict) -> bool:  # pragma: no cover
                return True

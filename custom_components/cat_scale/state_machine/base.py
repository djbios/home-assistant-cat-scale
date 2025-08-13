import abc
from abc import abstractmethod
from typing import ClassVar, TypeVar, Generic

DataType = TypeVar("DataType")
ContextType = TypeVar("ContextType")


class BaseState:
    state_key: ClassVar[str] = NotImplemented


# TODO static meta
class BaseStateTransition(Generic[DataType, ContextType], abc.ABC):
    # state and next_state?
    from_state: ClassVar[type[BaseState]] = NotImplemented
    to_state: ClassVar[type[BaseState]] = NotImplemented

    @classmethod
    @abstractmethod
    def should_change(cls, data: DataType, context: ContextType) -> bool:  # TODO better naming
        """Return True if the state should change"""

    @classmethod
    def on_change(cls, data: DataType, context: ContextType):
        """Called when transition is triggered"""

    @classmethod
    def on_stay(cls, data: DataType, context: ContextType):
        """Called when transition is checked but not triggered"""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.from_state is not NotImplemented and cls.to_state is not NotImplemented:
            assert cls.from_state != cls.to_state, (
                f"Transition to the same state is not allowed {cls}"
            )


class BaseStateMachine(Generic[DataType, ContextType]):
    # It's BaseStateTransition[DataType, ContextType] by meaning, but mypy doesn't like it
    transitions: ClassVar[list[type[BaseStateTransition]]]
    # Warning: transitions are order-sensitive, the first match is used

    def __init__(self, initial_state: type[BaseState], initial_context: ContextType):
        self.state = initial_state
        self.context = initial_context

    @classmethod
    def get_all_states(cls) -> set[type[BaseState]]:
        return {state for t in cls.transitions for state in (t.to_state, t.from_state)}

    def process_data(self, data: DataType) -> type[BaseState]:
        possible_transitions = [t for t in self.transitions if t.from_state == self.state]
        # transitions = [t for t in possible_transitions if should_change]
        # assert, raise ???
        for transition in possible_transitions:
            if transition.should_change(data, self.context):
                self.state = transition.to_state
                transition.on_change(data, self.context)
                return self.state
            else:
                transition.on_stay(data, self.context)
        # how to understand if we actually hang?
        return self.state

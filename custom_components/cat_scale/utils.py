import abc
import heapq
import inspect
from typing import Any, NoReturn


class RollingMedian:
    def __init__(self):
        self.low = []  # max-heap (store negatives)
        self.high = []  # min-heap
        self.count = 0

    @property
    def median(self):
        if self.count == 0:
            return None
        if len(self.low) == len(self.high):
            return (-self.low[0] + self.high[0]) / 2
        return float(-self.low[0])  # low has one extra

    def append(self, x: float):
        self.count += 1
        if not self.low or x <= -self.low[0]:
            heapq.heappush(self.low, -x)
        else:
            heapq.heappush(self.high, x)

        # rebalance
        if len(self.low) > len(self.high) + 1:
            heapq.heappush(self.high, -heapq.heappop(self.low))
        elif len(self.high) > len(self.low):
            heapq.heappush(self.low, -heapq.heappop(self.high))

    def clear(self):
        """Reset the median calculator to its initial state."""
        self.low.clear()
        self.high.clear()
        self.count = 0

    def __bool__(self):
        return bool(self.count)


class StaticClassMetaclass(type):
    """
    Metaclass for 'static classes':
      - Can't be instantiated.
      - All methods declared in the class body must be @staticmethod or @classmethod.
      - Disallows adding plain functions as attributes after class creation.
    """

    # Methods Python treats as class-level implicitly (no decorator needed)
    _IMPLICIT_CLASS_LEVEL = {"__init_subclass__", "__class_getitem__", "__subclasshook__"}

    def __new__(mcls, name: str, bases: tuple[type, ...], namespace: dict[str, Any], **kwargs: Any):
        # Forbid defining instance constructor hooks — they imply instantiation.
        if "__init__" in namespace:
            raise TypeError(
                f"{name}: __init__ is not allowed; static classes cannot be instantiated."
            )
        if "__new__" in namespace:
            # Even though __new__ is *looked up like* a staticmethod, having it implies instantiation intent.
            raise TypeError(
                f"{name}: __new__ is not allowed; static classes cannot be instantiated."
            )

        # Enforce callable attributes are classmethod/staticmethod (or implicitly class-level dunders).
        for attr, value in namespace.items():
            if inspect.isfunction(value):
                if attr in mcls._IMPLICIT_CLASS_LEVEL:
                    continue  # allowed without explicit decorator
                raise TypeError(
                    f"{name}.{attr} must be declared as @staticmethod or @classmethod; "
                    f"instance methods are not allowed in static classes."
                )
            # classmethod/staticmethod objects are fine
            # descriptors like property are allowed (they're not methods), but they're useless since no instances

        cls = super().__new__(mcls, name, bases, namespace, **kwargs)
        return cls

    def __call__(cls, *args: Any, **kwargs: Any) -> NoReturn:  # helps readability for type checkers
        raise TypeError(f"{cls.__name__} is a static class and cannot be instantiated.")

    # Prevent monkey-patching plain functions later
    def __setattr__(cls, name: str, value: Any) -> None:
        if inspect.isfunction(value):
            if name not in cls._IMPLICIT_CLASS_LEVEL:
                raise TypeError(
                    f"{cls.__name__}.{name} must be set to a @staticmethod or @classmethod, "
                    f"not a plain function."
                )
        super().__setattr__(name, value)


class StaticABCMeta(StaticClassMetaclass, abc.ABCMeta):
    """ABC + static-class rules. Order ensures cooperative super() works."""

    pass

import heapq


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

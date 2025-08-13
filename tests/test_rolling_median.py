import statistics
from random import randint

import pytest
from custom_components.cat_scale.utils import RollingMedian


@pytest.mark.parametrize(
    ("stream_len",),
    [
        (1,),
        (2,),
        (3,),
        (10,),
        (10**3,),
        (10**6,),
    ],
)
def test_rolling_median(stream_len):
    stream = [randint(-100, 100) for _ in range(stream_len)]

    rolling_median = RollingMedian()
    for x in stream:
        rolling_median.append(x)

    assert rolling_median.median == statistics.median(stream)

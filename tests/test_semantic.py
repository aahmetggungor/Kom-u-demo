import math

import pytest
from komsu.semantic import vector_literal


@pytest.mark.parametrize(
    "vector", [[0.0] * 1024, [1.0] * 1023, [math.nan] * 1024, [math.inf] * 1024, [True] * 1024]
)
def test_invalid_vectors_rejected(vector):
    with pytest.raises(ValueError):
        vector_literal(vector)

import pytest

from tests.engine_helpers import simulate


@pytest.mark.parametrize("seed", range(150))
def test_full_random_game(seed: int) -> None:
    result = simulate(seed)
    assert 2 <= result["players"] <= 10


def test_simulation_is_deterministic() -> None:
    assert simulate(42) == simulate(42)

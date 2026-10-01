from tools.scorer_eval import accuracy


def test_accuracy():
    pairs = [(90, True), (70, True), (60, False), (30, False), (None, False), (80, False)]
    assert accuracy(pairs, 65) == 5 / 6
    assert accuracy(pairs, 85) == 5 / 6
    assert accuracy(pairs, 95) == 4 / 6
    assert accuracy([], 65) == 0.0

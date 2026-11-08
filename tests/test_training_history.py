from loader.config import cat  # puts scripts/ on the path

import generate_training_history as generate
import history_catalog as hc


def test_raising_the_size_only_appends_records(monkeypatch):
    small = generate.build()
    monkeypatch.setattr(hc, "PER_CLASS", hc.PER_CLASS + 5)
    large = generate.build()
    for before, after in zip(small, large):
        assert after[:len(before)] == before and len(after) > len(before)
    assert len(large[0]) == (hc.PER_CLASS) * len(cat.REQUEST_TYPES)

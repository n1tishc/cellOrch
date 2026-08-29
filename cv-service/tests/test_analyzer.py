"""Concurrent stub inference must remain deterministic and race-free."""
from concurrent.futures import ThreadPoolExecutor

from app import analyzer


def test_concurrent_analyze_calls_are_safe(monkeypatch):
    monkeypatch.setattr(analyzer, "CV_MODE", "stub")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda index: analyzer.analyze(1, index), range(24)))

    assert all(result["mode"] == "stub" for result in results)
    assert [result["confluence"] for result in results] == [
        analyzer.stub_reading(index)["confluence"] for index in range(24)
    ]

from django.core.cache import cache

from metrics import cache as metric_cache


def test_version_starts_at_one_and_bumps():
    assert metric_cache.get_version(1, "m") == 1
    assert metric_cache.bump_version(1, "m") == 2
    assert metric_cache.get_version(1, "m") == 2


def test_bump_without_existing_counter_starts_at_two():
    assert metric_cache.bump_version(7, "fresh") == 2


def test_cached_query_hits_after_first_call():
    calls = []

    def compute():
        calls.append(1)
        return {"answer": 42}

    first, hit1 = metric_cache.cached_query("k", 1, "m", {"a": 1}, compute)
    second, hit2 = metric_cache.cached_query("k", 1, "m", {"a": 1}, compute)
    assert first == second == {"answer": 42}
    assert (hit1, hit2) == (False, True)
    assert len(calls) == 1


def test_cached_query_distinguishes_params():
    metric_cache.cached_query("k", 1, "m", {"a": 1}, lambda: 1)
    value, hit = metric_cache.cached_query("k", 1, "m", {"a": 2}, lambda: 2)
    assert (value, hit) == (2, False)


def test_invalidate_orphans_previous_entries():
    metric_cache.cached_query("k", 1, "m", {}, lambda: "old")
    metric_cache.invalidate({(1, "m")})
    value, hit = metric_cache.cached_query("k", 1, "m", {}, lambda: "new")
    assert (value, hit) == ("new", False)


def test_falsy_values_are_cached():
    metric_cache.cached_query("k", 1, "m", {}, lambda: [])
    value, hit = metric_cache.cached_query("k", 1, "m", {}, lambda: ["recomputed"])
    assert (value, hit) == ([], True)
    assert cache.get("does-not-exist") is None

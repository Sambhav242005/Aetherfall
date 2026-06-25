from app.engine.fields import WorldFields, POWER_PRINCIPLES


class TestWorldFields:
    def test_scalar_channels_in_range(self):
        f = WorldFields(2026)
        for gx in range(0, 500, 23):
            for name in ("height", "moisture", "heat", "flow", "danger", "civilization"):
                v = getattr(f, name)(gx, gx * 0.5)
                assert 0.0 <= v <= 1.0

    def test_power_has_six_named_keys(self):
        p = WorldFields(2026).power(100, 100)
        assert tuple(p.keys()) == POWER_PRINCIPLES
        for v in p.values():
            assert 0.0 <= v <= 1.0

    def test_deterministic(self):
        a, b = WorldFields(7), WorldFields(7)
        assert a.height(50, 60) == b.height(50, 60)
        assert a.power(50, 60) == b.power(50, 60)

    def test_channels_decorrelated(self):
        # Different salted channels must not be the same field.
        f = WorldFields(7)
        diffs = sum(1 for gx in range(0, 400, 7) if f.height(gx, gx) != f.moisture(gx, gx))
        assert diffs > 50

    def test_different_seed_differs(self):
        assert WorldFields(1).height(10, 10) != WorldFields(2).height(10, 10)

    def test_outputs_rounded_to_4dp(self):
        v = WorldFields(7).height(13, 17)
        assert round(v, 4) == v

    def test_modifiers_default_empty(self):
        # Forward hook for sub-project #2; unused here.
        assert WorldFields(7).modifiers == ()

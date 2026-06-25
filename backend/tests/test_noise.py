from app.engine.noise import value_noise, fbm


class TestValueNoise:
    def test_in_range(self):
        for i in range(200):
            v = value_noise(42, 1, i * 0.37, i * 0.61)
            assert 0.0 <= v <= 1.0

    def test_deterministic(self):
        assert value_noise(42, 1, 3.5, 2.25) == value_noise(42, 1, 3.5, 2.25)

    def test_continuous(self):
        # A tiny spatial step produces a tiny change (smooth function).
        a = value_noise(7, 1, 3.5, 2.5)
        b = value_noise(7, 1, 3.5 + 1e-3, 2.5)
        assert abs(a - b) < 1e-2

    def test_varies_with_seed_and_salt(self):
        base = value_noise(1, 1, 5.5, 5.5)
        assert value_noise(2, 1, 5.5, 5.5) != base
        assert value_noise(1, 2, 5.5, 5.5) != base

    def test_negative_coords_deterministic(self):
        assert value_noise(9, 3, -4.5, -2.5) == value_noise(9, 3, -4.5, -2.5)
        assert 0.0 <= value_noise(9, 3, -4.5, -2.5) <= 1.0


class TestFbm:
    def test_in_range(self):
        for i in range(200):
            v = fbm(42, 1, i * 1.3, i * 0.7, octaves=5, frequency=1 / 64)
            assert 0.0 <= v <= 1.0

    def test_deterministic(self):
        a = fbm(42, 1, 10.0, 20.0, octaves=4, frequency=1 / 32)
        b = fbm(42, 1, 10.0, 20.0, octaves=4, frequency=1 / 32)
        assert a == b

    def test_single_octave_equals_value_noise(self):
        # One octave with frequency 1.0 reduces to plain value noise.
        assert fbm(42, 5, 3.3, 4.4, octaves=1, frequency=1.0) == value_noise(42, 5, 3.3, 4.4)

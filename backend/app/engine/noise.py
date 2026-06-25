from __future__ import annotations
import math

MASK64 = 0xFFFFFFFFFFFFFFFF


def _hash01(seed: int, salt: int, ix: int, iy: int) -> float:
    """Deterministic hash of an integer lattice point -> float in [0, 1).

    splitmix64-style finalizer; all arithmetic masked to 64 bits for
    cross-platform stability. No RNG state, no wall clock.
    """
    h = ((ix & MASK64) * 0x1F1F1F1F1F1F1F1F) & MASK64
    h = (h ^ ((iy & MASK64) * 0x9E3779B97F4A7C15)) & MASK64
    h = (h ^ (seed & MASK64) ^ (salt & MASK64)) & MASK64
    h = ((h ^ (h >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    h = ((h ^ (h >> 27)) * 0x94D049BB133111EB) & MASK64
    h ^= h >> 31
    return (h & 0xFFFFFFFF) / 0x100000000  # [0, 1)


def _fade(t: float) -> float:
    """Perlin quintic smoothstep: 6t^5 - 15t^4 + 10t^3."""
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def value_noise(seed: int, salt: int, x: float, y: float) -> float:
    """Coherent value noise in [0, 1] at continuous (x, y)."""
    ix = math.floor(x)
    iy = math.floor(y)
    fx = x - ix
    fy = y - iy

    v00 = _hash01(seed, salt, ix, iy)
    v10 = _hash01(seed, salt, ix + 1, iy)
    v01 = _hash01(seed, salt, ix, iy + 1)
    v11 = _hash01(seed, salt, ix + 1, iy + 1)

    u = _fade(fx)
    v = _fade(fy)
    return _lerp(_lerp(v00, v10, u), _lerp(v01, v11, u), v)


def fbm(seed: int, salt: int, x: float, y: float, *, octaves: int = 4,
        lacunarity: float = 2.0, gain: float = 0.5, frequency: float = 1.0) -> float:
    """Fractional Brownian motion: sum of octaves, normalized to [0, 1]."""
    total = 0.0
    amplitude = 1.0
    freq = frequency
    norm = 0.0
    for octave in range(octaves):
        total += amplitude * value_noise(seed, salt + octave, x * freq, y * freq)
        norm += amplitude
        freq *= lacunarity
        amplitude *= gain
    return total / norm if norm else 0.0

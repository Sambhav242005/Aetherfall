from __future__ import annotations
from app.engine.noise import fbm

POWER_PRINCIPLES = ("magic", "aura", "alchemy", "mechanical", "biological", "mind")

# Distinct per-channel salts so channels are decorrelated.
SALT_HEIGHT = 0x48454947
SALT_MOISTURE = 0x4D4F4953
SALT_HEAT = 0x48454154
SALT_FLOW = 0x464C4F57
SALT_DANGER = 0x44414E47
SALT_CIV = 0x43495649
SALT_POWER = (0x504D4147, 0x50415552, 0x50414C43, 0x504D4543, 0x5042494F, 0x504D494E)


def _freq(feature_size: float) -> float:
    return 1.0 / feature_size


class WorldFields:
    """Coherent global terrain fields bound to a world seed.

    Every method is a pure function of (seed, global x, global y). `modifiers`
    is a forward hook for Stage-2 sub-project #2 (story-biased fields); it is
    unused here and defaults to empty (a no-op base field).
    """

    def __init__(self, seed: int, modifiers: tuple = ()):
        self.seed = int(seed)
        self.modifiers = tuple(modifiers)

    def height(self, gx: float, gy: float) -> float:
        return round(fbm(self.seed, SALT_HEIGHT, gx, gy, octaves=5, frequency=_freq(256)), 4)

    def moisture(self, gx: float, gy: float) -> float:
        return round(fbm(self.seed, SALT_MOISTURE, gx, gy, octaves=4, frequency=_freq(200)), 4)

    def heat(self, gx: float, gy: float) -> float:
        return round(fbm(self.seed, SALT_HEAT, gx, gy, octaves=3, frequency=_freq(320)), 4)

    def flow(self, gx: float, gy: float) -> float:
        return round(fbm(self.seed, SALT_FLOW, gx, gy, octaves=4, frequency=_freq(180)), 4)

    def danger(self, gx: float, gy: float) -> float:
        return round(fbm(self.seed, SALT_DANGER, gx, gy, octaves=2, frequency=_freq(220)), 4)

    def civilization(self, gx: float, gy: float) -> float:
        return round(fbm(self.seed, SALT_CIV, gx, gy, octaves=2, frequency=_freq(220)), 4)

    def power(self, gx: float, gy: float) -> dict[str, float]:
        return {
            name: round(fbm(self.seed, salt, gx, gy, octaves=2, frequency=_freq(220)), 4)
            for name, salt in zip(POWER_PRINCIPLES, SALT_POWER)
        }

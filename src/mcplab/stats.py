"""Deterministic seeds and Wilson confidence intervals (standard library only).

Rates in this lab are proportions (did the attack succeed, did the task succeed),
so every reported rate carries a Wilson score interval rather than a bare
fraction. The Wilson interval behaves well for the small per-cell sample sizes a
model comparison produces and never leaves the ``[0, 1]`` range.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

# 95% two-sided normal quantile. Hard-coded so the core needs no SciPy.
Z_95 = 1.959963984540054


def stable_seed(*parts: object) -> int:
    """Return a deterministic 32-bit seed from the string form of ``parts``.

    Using a hash of the identifying parts (model, scenario, arm, repetition)
    makes every run reproducible and independent of iteration order.
    """
    joined = "\x1f".join(str(part) for part in parts)
    digest = hashlib.blake2b(joined.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(digest, "big")


@dataclass(frozen=True)
class Interval:
    """A point estimate with a confidence interval, all in ``[0, 1]``."""

    rate: float
    low: float
    high: float
    successes: int
    total: int

    def as_pct(self) -> str:
        """Render as ``12.5% [8.1, 18.4]`` for Markdown tables."""
        if self.total == 0:
            return "n/a"
        return f"{self.rate * 100:.1f}% [{self.low * 100:.1f}, {self.high * 100:.1f}]"


def wilson(successes: int, total: int, z: float = Z_95) -> Interval:
    """Wilson score interval for ``successes`` out of ``total`` Bernoulli trials."""
    if total < 0 or successes < 0 or successes > total:
        raise ValueError("need 0 <= successes <= total")
    if total == 0:
        return Interval(0.0, 0.0, 0.0, 0, 0)
    phat = successes / total
    denom = 1.0 + z * z / total
    centre = (phat + z * z / (2 * total)) / denom
    margin = (z / denom) * math.sqrt(phat * (1 - phat) / total + z * z / (4 * total * total))
    low = max(0.0, centre - margin)
    high = min(1.0, centre + margin)
    return Interval(phat, low, high, successes, total)

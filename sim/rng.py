"""
SimCraft RNG — HMAC-SHA256 with rejection sampling.

Captures live simulation state at quit time and combines it with OS entropy
using HMAC-SHA256 (NIST SP 800-90A approved) to produce unbiased random numbers.

Entropy analysis:
  - Per cloud: 5 IEEE 754 doubles (x, y, vx, vy, mass) plus its element index; black holes
    add spin/accretion, neutron stars their pulse phase. After chaotic n-body evolution,
    conservatively ~64 bits min-entropy per entity.
  - Per universe: the barrier membrane (240 radii + velocities) — a dense integrated record
    of every gravitational event in that universe's history.
  - At quit time: up to 10,000 clouds (MULTIVERSE_MAX_CLOUDS) = 640,000+ bits of simulation
    entropy. SHA-256 compresses to 256 bits — the hash is the bottleneck, not the source.
  - os.urandom(32): 256 bits from OS CSPRNG.
  - HMAC-SHA256 combination: even if simulation state contributes 0 bits (attacker
    reads memory), os.urandom alone provides full 256-bit security. The simulation
    state provides defense-in-depth.
  - Rejection sampling bias: for range ~9x10^19, rejection probability is ~10^-57
    per attempt — effectively zero. The loop exists for formal correctness.
"""

import hashlib
import hmac
import os
import struct
import sys
from datetime import datetime

import numpy as np

MIN = 10000000000000000000  # Lower bound of RNG output range (20-digit minimum)
MAX = 99999999999999999999  # Upper bound of RNG output range (20-digit maximum)


def serialize_state(state_obj):
    """Pack live SimulationState into bytes for hashing.

    Header: 12 bytes — struct.pack('<3I', mc_count, bh_count, ns_count)
    Then, per universe, little-endian raw array blocks:
      clouds   — (n, 5) float64 [x, y, vx, vy, mass] + (n,) int64 element indices
      holes    — per hole '<7d' x, y, vx, vy, mass, angular_momentum, accretion_mass
      stars    — per star '<6d' x, y, vx, vy, mass, time_since_last_pulse
      barrier  — '<2d' center + (num_points,) float64 radii + radii velocities

    The cloud field serializes straight from the SoA arrays (no per-row packing), and the
    barrier membrane state is included: its deformation integrates every gravitational event
    in the universe's history, so it is a dense chaotic record the hash gets for free.

    Returns (state_bytes, entity_count).
    """
    universes = state_obj.universes
    mc_count = sum(u.clouds.n for u in universes)
    bh_count = sum(len(u.black_holes) for u in universes)
    ns_count = sum(len(u.neutron_stars) for u in universes)

    parts = [struct.pack('<3I', mc_count, bh_count, ns_count)]

    for u in universes:
        c = u.clouds
        if c.n:
            block = np.empty((c.n, 5))
            block[:, 0] = c.X
            block[:, 1] = c.Y
            block[:, 2] = c.VX
            block[:, 3] = c.VY
            block[:, 4] = c.M
            parts.append(block.astype('<f8', copy=False).tobytes())
            parts.append(c.ELEM.astype('<i8', copy=False).tobytes())
        for e in u.black_holes:
            parts.append(struct.pack('<7d', e.x, e.y, e.vx, e.vy, e.mass,
                                     e.angular_momentum, e.accretion_mass))
        for e in u.neutron_stars:
            parts.append(struct.pack('<6d', e.x, e.y, e.vx, e.vy, e.mass,
                                     e.time_since_last_pulse))
        b = u.barrier
        parts.append(struct.pack('<2d', b.center[0], b.center[1]))
        parts.append(b.radii.astype('<f8', copy=False).tobytes())
        parts.append(b.radii_vel.astype('<f8', copy=False).tobytes())

    entity_count = mc_count + bh_count + ns_count
    return b''.join(parts), entity_count


def generate(state_bytes, min_val, max_val):
    """Generate a single random number using HMAC-SHA256 with rejection sampling.

    key   = SHA-256(state_bytes)
    msg   = os.urandom(32)
    combined = HMAC-SHA256(key, msg)

    Rejection sampling eliminates modulo bias:
      threshold = 2^256 - (2^256 % range_size)
      if raw_int >= threshold: resample with fresh os.urandom
    """
    state_hash = hashlib.sha256(state_bytes).digest()
    range_size = max_val - min_val + 1
    threshold = (1 << 256) - ((1 << 256) % range_size)

    attempts = 0
    while True:
        attempts += 1
        os_random = os.urandom(32)
        combined = hmac.new(key=state_hash, msg=os_random, digestmod=hashlib.sha256).digest()
        raw_int = int.from_bytes(combined, 'big')
        if raw_int < threshold:
            break

    random_number = min_val + (raw_int % range_size)

    # Entity count comes from the serialized header (byte length is no longer a fixed
    # multiple of an entity: the payload also carries elements and barrier membrane state).
    if len(state_bytes) >= 12:
        entity_count = sum(struct.unpack('<3I', state_bytes[:12]))
    else:
        entity_count = 0
    state_entropy_bits = entity_count * 64

    return {
        'random_number': random_number,
        'generation_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'entity_count': entity_count,
        'state_entropy_bits': state_entropy_bits,
        'attempts': attempts,
    }


def rng(min_val, max_val, state_bytes=None, generations=1):
    """Generate random numbers. Uses os.urandom(256) as synthetic state when
    state_bytes is None (standalone/batch mode)."""
    if state_bytes is None:
        state_bytes = os.urandom(256)

    results = []
    for _ in range(generations):
        result = generate(state_bytes, min_val, max_val)
        print(f"{result['random_number']}")

        if generations == 1:
            return result

        results.append({
            'random_number': result['random_number'],
            'generation_time': result['generation_time'],
            'entity_count': result['entity_count'],
            'state_entropy_bits': result['state_entropy_bits'],
            'attempts': result['attempts'],
        })

    import pandas as pd
    return pd.DataFrame(results)


def randomness(df):
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    ax1.hist(df['random_number'], bins=50, alpha=0.7, color='blue')
    ax1.set_title('Distribution')
    ax1.set_xlabel('Number')
    ax1.set_ylabel('Frequency')
    ax1.grid(True, alpha=0.3)

    ax2.plot(df.index, df['random_number'], 'o-', alpha=0.7, color='blue')
    ax2.set_title('Randomness')
    ax2.set_xlabel('Generation')
    ax2.set_ylabel('Number')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()
    plt.close()


def main():
    num_generations = 1
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        num_generations = int(sys.argv[1])

    if num_generations > 1:
        df = rng(MIN, MAX, generations=num_generations)
        randomness(df)
    else:
        result = rng(MIN, MAX)

if __name__ == "__main__":
    main()

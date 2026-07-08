"""
SimCraft RNG — HKDF (extract-then-expand) salted by a running entropy pool.

The simulation is the salt. An EntropyPool accumulates a record of the whole
trajectory — cheap chaotic observables every frame (frame-time jitter, tick count,
per-universe counts/masses, barrier membrane sums, sample cloud positions) plus a
periodic fold of the fully serialized multiverse — so the salt reflects how the
universe got here, not just where it ended up. Draws ratchet the pool forward, so
consecutive outputs never see the same salt.

Each output is HKDF-SHA256 (RFC 5869): PRK = HMAC(salt, os.urandom(32)), then
expand with a domain-separation info string. Rejection sampling removes modulo bias.

Entropy analysis:
  - Per cloud: 5 IEEE 754 doubles (x, y, vx, vy, mass) plus its element index; black holes
    add spin/accretion, neutron stars their pulse phase. After chaotic n-body evolution,
    conservatively ~64 bits min-entropy per entity.
  - Per universe: the barrier membrane (radii + velocities) — a dense integrated record
    of every gravitational event in that universe's history; ~16 bits/point conservative.
  - The pool folds this state repeatedly over the run and never forgets: entropy only
    accumulates. SHA-256/BLAKE2b compress to 256 bits — the hash is the bottleneck,
    not the source.
  - os.urandom(32) is the IKM every draw: even if simulation state contributes 0 bits
    (attacker reads memory), the OS CSPRNG alone provides full 256-bit security. The
    simulation state is defense-in-depth.
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

# Output range: 39-digit decimal, carrying ≥129 bits of entropy per draw — at or above the
# 128-bit floor for cryptographic key material (the HKDF-SHA256 pipeline behind it can back
# up to 256 bits; the decimal length is the deliberate display/usability tradeoff).
MIN = 10 ** 38              # Lower bound of RNG output range (39-digit minimum)
MAX = 10 ** 39 - 1          # Upper bound of RNG output range (39-digit maximum)

SERIALIZE_VERSION = 3
_HKDF_INFO = b'simcraft-rng-v1'       # domain separation for output derivation
_POOL_PERSON = b'simcraft-pool-v1'    # blake2b personalization (16-byte max)
_HEADER = struct.Struct('<B6I')       # version, n_universes, mc, bh, ns, mag, barrier_pts


def serialize_state(state_obj):
    """Pack live SimulationState into bytes for hashing. The encoding is framed and
    versioned so it is injective: no two distinct states produce the same bytes.

    Global header: _HEADER — version, universe count, total clouds/holes/stars/magnetars,
    total barrier points. Then per universe:
      frame     — struct.pack('<5I', n_clouds, n_holes, n_stars, n_magnetars, n_barrier_points)
      clouds    — (n, 5) float64 [x, y, vx, vy, mass] + (n,) int64 element indices
      holes     — per hole '<7d' x, y, vx, vy, mass, angular_momentum, accretion_mass
      stars     — per star '<6d' x, y, vx, vy, mass, time_since_last_pulse
      magnetars — per magnetar '<7d' x, y, vx, vy, mass, field_time, color_phase
      barrier   — '<2d' center + (num_points,) float64 radii + radii velocities

    The cloud field serializes straight from the SoA arrays (no per-row packing), and the
    barrier membrane state is included: its deformation integrates every gravitational event
    in the universe's history, so it is a dense chaotic record the hash gets for free.

    Returns (state_bytes, entity_count).
    """
    universes = state_obj.universes
    mc_count = sum(u.clouds.n for u in universes)
    bh_count = sum(len(u.black_holes) for u in universes)
    ns_count = sum(len(u.neutron_stars) for u in universes)
    mag_count = sum(len(u.magnetars) for u in universes)
    barrier_points = sum(len(u.barrier.radii) for u in universes)

    parts = [_HEADER.pack(SERIALIZE_VERSION, len(universes),
                          mc_count, bh_count, ns_count, mag_count, barrier_points)]

    for u in universes:
        c = u.clouds
        parts.append(struct.pack('<5I', c.n, len(u.black_holes), len(u.neutron_stars),
                                 len(u.magnetars), len(u.barrier.radii)))
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
        for e in u.magnetars:
            parts.append(struct.pack('<7d', e.x, e.y, e.vx, e.vy, e.mass,
                                     e.field_time, e.color_phase))
        b = u.barrier
        parts.append(struct.pack('<2d', b.center[0], b.center[1]))
        parts.append(b.radii.astype('<f8', copy=False).tobytes())
        parts.append(b.radii_vel.astype('<f8', copy=False).tobytes())

    entity_count = mc_count + bh_count + ns_count + mag_count
    return b''.join(parts), entity_count


def _parse_header(state_bytes):
    """Return (entity_count, entropy_bits_estimate) from serialized state bytes."""
    if len(state_bytes) < _HEADER.size:
        return 0, 0
    version, _, mc, bh, ns, mag, barrier_points = _HEADER.unpack_from(state_bytes)
    if version != SERIALIZE_VERSION:
        return 0, 0
    entity_count = mc + bh + ns + mag
    # ~64 bits/entity (5+ chaotic doubles), ~16 bits/barrier point (radius + velocity).
    return entity_count, entity_count * 64 + barrier_points * 16


class EntropyPool:
    """Running 256-bit record of the simulation trajectory.

    fold_frame() mixes cheap per-frame observables in continuously and folds the full
    serialized state every FULL_FOLD_INTERVAL frames; generate() ratchets the pool
    forward after every draw, so no two draws share a salt and past pool states are
    unrecoverable from the current one.
    """

    FULL_FOLD_INTERVAL = 120  # frames between full-state folds (~2 s at 60 fps)
    SAMPLE_CLOUDS = 4         # leading cloud positions folded each frame

    def __init__(self):
        self.pool = os.urandom(32)
        self.folds = 0
        self.entity_count = 0    # from the most recent full-state fold
        self.entropy_bits = 0    # conservative estimate for that snapshot

    def fold(self, data):
        self.pool = hashlib.blake2b(data, key=self.pool, digest_size=32,
                                    person=_POOL_PERSON).digest()
        self.folds += 1

    def fold_state(self, state_obj):
        state_bytes, self.entity_count = serialize_state(state_obj)
        _, self.entropy_bits = _parse_header(state_bytes)
        self.fold(state_bytes)

    def fold_frame(self, state_obj, tick_ms, raw_frame_ms):
        """Cheap per-frame fold: OS-scheduling jitter (raw frame ms), tick count, and
        per-universe chaotic observables. Full state every FULL_FOLD_INTERVAL frames."""
        parts = [struct.pack('<QIi', self.folds, tick_ms & 0xFFFFFFFF, raw_frame_ms)]
        for u in state_obj.universes:
            c = u.clouds
            parts.append(struct.pack('<5I3d',
                                     c.n, len(u.black_holes), len(u.neutron_stars),
                                     len(u.magnetars), len(u.black_hole_pulses),
                                     float(u.barrier.radii.sum()),
                                     float(u.barrier.radii_vel.sum()),
                                     float(c.M.sum()) if c.n else 0.0))
            k = min(c.n, self.SAMPLE_CLOUDS)
            if k:
                parts.append(np.ascontiguousarray(c.X[:k], dtype='<f8').tobytes())
                parts.append(np.ascontiguousarray(c.Y[:k], dtype='<f8').tobytes())
        self.fold(b''.join(parts))
        if self.folds % self.FULL_FOLD_INTERVAL == 0:
            self.fold_state(state_obj)


def _hkdf_extract(salt, ikm):
    return hmac.new(salt, ikm, hashlib.sha256).digest()


def _hkdf_expand(prk, info, length):
    okm = b''
    block = b''
    counter = 1
    while len(okm) < length:
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        okm += block
        counter += 1
    return okm[:length]


def generate(salt, min_val, max_val):
    """Generate one random number via HKDF-SHA256 with rejection sampling.

    salt: an EntropyPool (live sim — pool is ratcheted forward after the draw) or raw
    serialized state bytes (one-shot).

      PRK = HKDF-Extract(salt, os.urandom(32))
      OKM = HKDF-Expand(PRK, 'simcraft-rng-v1', 32)

    Rejection sampling eliminates modulo bias:
      threshold = 2^256 - (2^256 % range_size)
      if raw_int >= threshold: resample with fresh os.urandom
    """
    pool = salt if isinstance(salt, EntropyPool) else None
    if pool is not None:
        salt_bytes = pool.pool
        entity_count, entropy_bits = pool.entity_count, pool.entropy_bits
    else:
        salt_bytes = hashlib.sha256(salt).digest()
        entity_count, entropy_bits = _parse_header(salt)

    range_size = max_val - min_val + 1
    threshold = (1 << 256) - ((1 << 256) % range_size)

    attempts = 0
    while True:
        attempts += 1
        prk = _hkdf_extract(salt_bytes, os.urandom(32))
        okm = _hkdf_expand(prk, _HKDF_INFO, 32)
        raw_int = int.from_bytes(okm, 'big')
        if raw_int < threshold:
            break

    if pool is not None:
        pool.fold(okm)  # ratchet: the next draw sees a different salt

    return {
        'random_number': min_val + (raw_int % range_size),
        'generation_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'entity_count': entity_count,
        'state_entropy_bits': entropy_bits,
        'pool_folds': pool.folds if pool is not None else 0,
        'attempts': attempts,
    }


def rng(min_val, max_val, state_bytes=None, generations=1):
    """Generate random numbers. Uses os.urandom(256) as synthetic state when
    state_bytes is None (standalone/batch mode). Batch draws share one pool and
    ratchet between draws instead of re-hashing the state every time."""
    pool = EntropyPool()
    if state_bytes is None:
        pool.fold(os.urandom(256))
    else:
        pool.entity_count, pool.entropy_bits = _parse_header(state_bytes)
        pool.fold(state_bytes)

    results = []
    for _ in range(generations):
        result = generate(pool, min_val, max_val)
        print(f"{result['random_number']}")

        if generations == 1:
            return result

        results.append(result)

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

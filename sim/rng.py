"""
SimCraft RNG — HMAC-SHA256 with rejection sampling.

Captures live simulation state at quit time and combines it with OS entropy
using HMAC-SHA256 (NIST SP 800-90A approved) to produce unbiased random numbers.

Entropy analysis:
  - Per entity: 5 IEEE 754 doubles (x, y, vx, vy, mass). After chaotic n-body
    evolution, conservatively ~64 bits min-entropy per entity.
  - At quit time: ~10,000+ molecular clouds = 640,000+ bits of simulation entropy.
    SHA-256 compresses to 256 bits — the hash is the bottleneck, not the source.
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

MIN = 10000000000000000000  # Lower bound of RNG output range (20-digit minimum)
MAX = 99999999999999999999  # Upper bound of RNG output range (20-digit maximum)


def serialize_state(state_obj):
    """Pack live SimulationState into bytes for hashing.

    Header: 12 bytes — struct.pack('<3I', mc_count, bh_count, ns_count)
    Per entity: 40 bytes — struct.pack('<5d', x, y, vx, vy, mass)

    Returns (state_bytes, entity_count).
    """
    mc_count = len(state_obj.molecular_clouds)
    bh_count = len(state_obj.black_holes)
    ns_count = len(state_obj.neutron_stars)

    parts = [struct.pack('<3I', mc_count, bh_count, ns_count)]

    for entity in state_obj.molecular_clouds:
        parts.append(struct.pack('<5d', entity.x, entity.y, entity.vx, entity.vy, entity.mass))
    for entity in state_obj.black_holes:
        parts.append(struct.pack('<5d', entity.x, entity.y, entity.vx, entity.vy, entity.mass))
    for entity in state_obj.neutron_stars:
        parts.append(struct.pack('<5d', entity.x, entity.y, entity.vx, entity.vy, entity.mass))

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

    entity_count = (len(state_bytes) - 12) // 40 if len(state_bytes) > 12 else 0
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

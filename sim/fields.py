"""CloudField: structure-of-arrays storage for molecular clouds.

The arrays ARE the simulation state — gravity, integration, containment, and collisions all
operate on them directly with no per-frame gather/scatter. A cloud is a row index; rare,
branchy logic (supernovae, streaming, rips) addresses rows by index. Draw-only per-cloud data
(block offsets, cached sprites) lives in parallel storage compacted in lockstep.
"""
import math
import random

import numpy as np

from sim.config import *


def pick_element(abundance=None):
    """Same element draw as the original MolecularCloud.__init__: one random.random() scanned
    against a cumulative abundance table; falls through to the heaviest element."""
    rand = random.random()
    for i, (start, end) in enumerate(abundance or ELEMENTAL_ABUNDANCE):
        if start <= rand < end:
            return i
    return len(MOLECULAR_CLOUD_START_COLORS) - 1


def _random_offsets():
    """Block-cluster offsets, one cloud's worth — same distribution as the original __init__
    (radius ~ U[0.05, 0.22], angle ~ U[0, 2pi] per block), drawn vectorized from numpy's
    stream instead of 28 scalar draws from `random`."""
    r = np.random.uniform(0.05, 0.22, 7)
    th = np.random.uniform(0.0, 2.0 * math.pi, 7)
    return np.stack((r * np.cos(th), r * np.sin(th)), axis=1)


def blend_abundance(base, enriched, z):
    """Interpolate two cumulative abundance tables (same element order) by metallicity z in
    [0, 1] — how a universe's ejecta composition drifts metal-rich as it chemically ages."""
    if z <= 0.0:
        return base
    z = min(z, 1.0)
    return [(b0 + z * (e0 - b0), b1 + z * (e1 - b1))
            for (b0, b1), (e0, e1) in zip(base, enriched)]


class CloudField:
    """Dense arrays of the live clouds in one universe. Rows [0, n) are alive; capacity grows
    by doubling. Compaction (`keep`) preserves order, matching the list-filter semantics the
    object version had."""

    __slots__ = ('n', 'cap', 'x', 'y', 'vx', 'vy', 'mass', 'elem', 'emission_count',
                 'is_star', 'has_civ', 'size', 'shock', 'giant', 'offsets', 'sprites', 'sprite_keys')

    def __init__(self, cap=256):
        self.n = 0
        self.cap = cap
        self.x = np.zeros(cap)
        self.y = np.zeros(cap)
        self.vx = np.zeros(cap)
        self.vy = np.zeros(cap)
        self.mass = np.zeros(cap)
        self.elem = np.zeros(cap, dtype=np.int64)
        self.emission_count = np.zeros(cap, dtype=np.int64)
        self.is_star = np.zeros(cap, dtype=bool)
        self.has_civ = np.zeros(cap, dtype=bool)  # rare Dyson-swarm civilization on this star
        self.size = np.zeros(cap)
        self.shock = np.zeros(cap)   # seconds of "compressed by a wavefront" remaining (triggered star formation)
        self.giant = np.zeros(cap)   # seconds of red-giant phase remaining; 0 = main sequence (set when the WD retirement roll hits)
        self.offsets = np.zeros((cap, 7, 2))
        self.sprites = [None] * cap      # cached pygame sprites, draw-only
        # Visual cache key per row: (size, r, g, b, opacity) as int64, -1 = stale/no sprite.
        # An array (not a list of tuples) so the renderer can diff all rows in one vector op.
        self.sprite_keys = np.full((cap, 5), -1, dtype=np.int64)

    # ── views over the alive rows (setters allow `field.VX += ...` on the view) ──
    @property
    def X(self): return self.x[:self.n]
    @X.setter
    def X(self, v): self.x[:self.n] = v
    @property
    def Y(self): return self.y[:self.n]
    @Y.setter
    def Y(self, v): self.y[:self.n] = v
    @property
    def VX(self): return self.vx[:self.n]
    @VX.setter
    def VX(self, v): self.vx[:self.n] = v
    @property
    def VY(self): return self.vy[:self.n]
    @VY.setter
    def VY(self, v): self.vy[:self.n] = v
    @property
    def M(self): return self.mass[:self.n]
    @property
    def ELEM(self): return self.elem[:self.n]
    @property
    def SIZE(self): return self.size[:self.n]
    @property
    def IS_STAR(self): return self.is_star[:self.n]
    @property
    def HAS_CIV(self): return self.has_civ[:self.n]
    @property
    def SHOCK(self): return self.shock[:self.n]
    @SHOCK.setter
    def SHOCK(self, v): self.shock[:self.n] = v
    @property
    def GIANT(self): return self.giant[:self.n]
    @GIANT.setter
    def GIANT(self, v): self.giant[:self.n] = v

    def _ensure(self, extra):
        need = self.n + extra
        if need <= self.cap:
            return
        new_cap = self.cap
        while new_cap < need:
            new_cap *= 2
        for name in ('x', 'y', 'vx', 'vy', 'mass', 'elem', 'emission_count', 'is_star', 'has_civ', 'size', 'shock', 'giant'):
            old = getattr(self, name)
            grown = np.zeros(new_cap, dtype=old.dtype)
            grown[:self.n] = old[:self.n]
            setattr(self, name, grown)
        grown_off = np.zeros((new_cap, 7, 2))
        grown_off[:self.n] = self.offsets[:self.n]
        self.offsets = grown_off
        self.sprites += [None] * (new_cap - self.cap)
        grown_keys = np.full((new_cap, 5), -1, dtype=np.int64)
        grown_keys[:self.n] = self.sprite_keys[:self.n]
        self.sprite_keys = grown_keys
        self.cap = new_cap

    def spawn(self, x, y, mass, abundance=None, elem=None, vx=0.0, vy=0.0, offsets=None):
        """Add one cloud; returns its row index.

        When `offsets` is None, the RNG draws happen here in the historical
        MolecularCloud.__init__ order (offsets, then element — the element draw always happens,
        matching the old construct-then-overwrite emission path). Event code that must consume
        its draws inline (mid-event-loop, like the old inline constructions) passes pre-drawn
        `offsets` and `elem`, and no draws happen here."""
        self._ensure(1)
        k = self.n
        self.n += 1
        if offsets is None:
            offs = _random_offsets()
            drawn = pick_element(abundance)
            el = drawn if elem is None else elem
        else:
            offs = offsets
            el = elem
        self.x[k] = x
        self.y[k] = y
        self.vx[k] = vx
        self.vy[k] = vy
        self.mass[k] = mass
        self.elem[k] = el
        self.emission_count[k] = 0
        self.is_star[k] = mass >= PROTOSTAR_THRESHOLD
        self.has_civ[k] = False
        self.size[k] = self._size_for(mass, self.is_star[k])
        self.shock[k] = 0.0
        self.giant[k] = 0.0
        self.offsets[k] = offs
        self.sprites[k] = None
        self.sprite_keys[k] = -1
        return k

    def spawn_batch(self, items):
        """Append many clouds at once — event ejecta arrive in bursts (a supernova storm can
        spawn ~1000 clouds in a frame). Equivalent to spawn() per item with pre-drawn elements;
        block offsets for the whole batch come from ONE vectorized draw (same distribution as
        _random_offsets, different draw stream — statistics, not bits, as ever).

        items: sequence of (x, y, mass, elem, vx, vy)."""
        m = len(items)
        if m == 0:
            return
        self._ensure(m)
        k0 = self.n
        k1 = k0 + m
        self.n = k1
        xs, ys, ms, els, vxs, vys = (np.asarray(col, dtype=float) for col in zip(*items))
        self.x[k0:k1] = xs
        self.y[k0:k1] = ys
        self.vx[k0:k1] = vxs
        self.vy[k0:k1] = vys
        self.mass[k0:k1] = ms
        self.elem[k0:k1] = els.astype(np.int64)
        self.emission_count[k0:k1] = 0
        is_star = ms >= PROTOSTAR_THRESHOLD
        self.is_star[k0:k1] = is_star
        self.has_civ[k0:k1] = False
        # Same size formulas as _size_for, vectorized (int() and astype both truncate toward 0).
        shrink = ((ms - MOLECULAR_CLOUD_START_MASS) * MOLECULAR_CLOUD_GROWTH_RATE).astype(np.int64)
        cloud_size = np.maximum(MOLECULAR_CLOUD_MIN_SIZE, MOLECULAR_CLOUD_START_SIZE - shrink)
        star_size = np.select([ms >= STAR_TIER_HIGH_MASS, ms >= STAR_TIER_MEDIUM_MASS],
                              [PROTOSTAR_HIGH_SIZE, PROTOSTAR_MEDIUM_SIZE], PROTOSTAR_LOW_SIZE)
        self.size[k0:k1] = np.where(is_star, star_size, cloud_size)
        self.shock[k0:k1] = 0.0
        self.giant[k0:k1] = 0.0
        r = np.random.uniform(0.05, 0.22, (m, 7))
        th = np.random.uniform(0.0, 2.0 * math.pi, (m, 7))
        self.offsets[k0:k1, :, 0] = r * np.cos(th)
        self.offsets[k0:k1, :, 1] = r * np.sin(th)
        self.sprite_keys[k0:k1] = -1
        for k in range(k0, k1):
            self.sprites[k] = None

    @staticmethod
    def _size_for(mass, is_star):
        # Star tier (and so size) is set by mass, the real determinant of a star's nature.
        if is_star:
            if mass >= STAR_TIER_HIGH_MASS:
                return PROTOSTAR_HIGH_SIZE
            if mass >= STAR_TIER_MEDIUM_MASS:
                return PROTOSTAR_MEDIUM_SIZE
            return PROTOSTAR_LOW_SIZE
        return max(MOLECULAR_CLOUD_MIN_SIZE,
                   MOLECULAR_CLOUD_START_SIZE - int((mass - MOLECULAR_CLOUD_START_MASS) * MOLECULAR_CLOUD_GROWTH_RATE))

    def refresh(self):
        """Vectorized twin of the old MolecularCloud.update(): clamp mass, apply the one-time
        protostar mass boost on threshold crossing, derive is_star and visual/collision size."""
        n = self.n
        if n == 0:
            return
        mass = self.mass[:n]
        elem = self.elem[:n]
        np.minimum(mass, MOLECULAR_CLOUD_MAX_MASS, out=mass)
        newly = (mass >= PROTOSTAR_THRESHOLD) & ~self.is_star[:n]
        if newly.any():
            # Ignition boost by the cloud's own metallicity: pristine H/He gas fragments less
            # and ignites as giants (Population III); enriched gas ignites smaller stars.
            boost = np.where(elem < STAR_ENRICHED_ELEMENT_MIN,
                             PROTOSTAR_PRISTINE_MASS_BOOST, PROTOSTAR_ENRICHED_MASS_BOOST)
            mass[newly] = np.minimum(mass[newly] + boost[newly], MOLECULAR_CLOUD_MAX_MASS)
        self.is_star[:n] = mass >= PROTOSTAR_THRESHOLD
        # Non-star size: START - trunc((mass-START_MASS)*GROWTH), floored at MIN (same int() trunc)
        shrink = ((mass - MOLECULAR_CLOUD_START_MASS) * MOLECULAR_CLOUD_GROWTH_RATE).astype(np.int64)
        size = np.maximum(MOLECULAR_CLOUD_MIN_SIZE, MOLECULAR_CLOUD_START_SIZE - shrink).astype(float)
        # Star tier by MASS (temperature/size/fate all follow mass in reality).
        star_size = np.select(
            [mass >= STAR_TIER_HIGH_MASS, mass >= STAR_TIER_MEDIUM_MASS],
            [PROTOSTAR_HIGH_SIZE, PROTOSTAR_MEDIUM_SIZE], PROTOSTAR_LOW_SIZE)
        self.size[:n] = np.where(self.is_star[:n], star_size, size)

    def keep(self, mask):
        """Compact to the rows where mask is True, preserving order (list-filter semantics)."""
        if mask.all():
            return
        self.select(np.nonzero(mask)[0])

    def select(self, idx):
        """Reorder/compact the field to exactly the given row indices, in the given order
        (mirrors list.sort + truncate / shuffle semantics of the old object lists)."""
        n = self.n
        idx = np.asarray(idx, dtype=np.int64)
        m = len(idx)
        for name in ('x', 'y', 'vx', 'vy', 'mass', 'elem', 'emission_count', 'is_star', 'has_civ', 'size', 'shock', 'giant'):
            arr = getattr(self, name)
            arr[:m] = arr[:n][idx]
        self.offsets[:m] = self.offsets[:n][idx]
        self.sprite_keys[:m] = self.sprite_keys[:n][idx]  # fancy index copies — no aliasing
        self.sprite_keys[m:n] = -1
        # Snapshot before reordering: an in-place `sprites[new] = sprites[old]` loop corrupts
        # entries when idx is unsorted (mass-sort trims, rip shuffles) — old slots get
        # overwritten before they're read, desyncing sprites from their keys.
        self.sprites[:m] = [self.sprites[old_k] for old_k in idx]
        for k in range(m, n):
            self.sprites[k] = None
        self.n = m

    def move_rows(self, dst, rows):
        """Move the given row indices into `dst` (appended in the given order), removing them
        here. Returns the destination indices."""
        out = self.copy_rows(dst, rows)
        drop = np.zeros(self.n, dtype=bool)
        drop[np.asarray(rows, dtype=np.int64)] = True
        self.keep(~drop)
        return out

    def copy_rows(self, dst, rows):
        """Append copies of the given rows to `dst` without removing them here (caller drops
        them later in one compaction). Returns the destination indices."""
        rows = np.asarray(rows, dtype=np.int64)
        dst._ensure(len(rows))
        out = []
        for r in rows:
            k = dst.n
            dst.n += 1
            dst.x[k] = self.x[r]
            dst.y[k] = self.y[r]
            dst.vx[k] = self.vx[r]
            dst.vy[k] = self.vy[r]
            dst.mass[k] = self.mass[r]
            dst.elem[k] = self.elem[r]
            dst.emission_count[k] = self.emission_count[r]
            dst.is_star[k] = self.is_star[r]
            dst.has_civ[k] = self.has_civ[r]
            dst.size[k] = self.size[r]
            dst.shock[k] = self.shock[r]
            dst.giant[k] = self.giant[r]
            dst.offsets[k] = self.offsets[r]
            dst.sprites[k] = self.sprites[r]
            dst.sprite_keys[k] = self.sprite_keys[r]
            out.append(k)
        return out

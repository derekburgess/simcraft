"""Cloud/star mutual gravity backends.

Every backend computes the SAME physics — tiered gravitational charge (stars pull
STAR_GRAVITY_MULTIPLIER x their mass), Plummer-style softening — so switching backends changes
speed and (for Barnes-Hut) approximation error, never the rules.

Dispatch order (config-gated):
  1. Taichi GPU, exact all-pairs        — primary; ~0.3 ms per 500-cloud universe
  2. Cython Barnes-Hut quadtree         — approximate long-range, the CPU workhorse
  3. numpy brute-force, exact all-pairs — reference implementation & last-resort fallback
  4. local cell-neighborhood model      — only when BOTH flags are off: the original cheap
     short-range physics (a deliberately different, local-clumping universe)
"""
import numpy as np

from sim.config import *

try:
    from sim import fastphysics as _fastphysics
except Exception:
    _fastphysics = None


def grav_masses(mass, is_star):
    """Tiered gravitational charge: stars pull as a stronger tier than clouds."""
    return mass * np.where(is_star, STAR_GRAVITY_MULTIPLIER, 1.0)


# ── Taichi GPU backend ─────────────────────────────────────────────────────────────────────
_ti_state = {"ready": False, "ok": False, "kernel": None}


def _init_gpu():
    if _ti_state["ready"]:
        return _ti_state["ok"]
    _ti_state["ready"] = True
    try:
        import taichi as ti
        ti.init(arch=ti.gpu)

        @ti.kernel
        def grav_kernel(pos: ti.types.ndarray(dtype=ti.f32, ndim=2),
                        gm: ti.types.ndarray(dtype=ti.f32, ndim=1),
                        force: ti.types.ndarray(dtype=ti.f32, ndim=2),
                        n: ti.i32, G: ti.f32, soft2: ti.f32):
            for i in range(n):
                fx = 0.0
                fy = 0.0
                xi = pos[i, 0]
                yi = pos[i, 1]
                mi = gm[i]
                for j in range(n):
                    if j != i:
                        dx = pos[j, 0] - xi
                        dy = pos[j, 1] - yi
                        d2 = dx * dx + dy * dy + soft2
                        inv = 1.0 / ti.sqrt(d2)
                        f = G * mi * gm[j] / d2
                        fx += dx * inv * f
                        fy += dy * inv * f
                force[i, 0] = fx
                force[i, 1] = fy

        _ti_state["kernel"] = grav_kernel
        _ti_state["ok"] = True
    except Exception as e:
        print("GPU gravity unavailable, falling back to CPU:", e)
        _ti_state["ok"] = False
    return _ti_state["ok"]


def forces_gpu(x, y, gm):
    n = len(x)
    pos = np.empty((n, 2), np.float32)
    pos[:, 0] = x
    pos[:, 1] = y
    force = np.zeros((n, 2), np.float32)
    _ti_state["kernel"](pos, gm.astype(np.float32), force, n,
                        float(MOLECULAR_CLOUD_GRAVITY_CONSTANT), float(BARNES_HUT_SOFTENING ** 2))
    return force[:, 0].astype(np.float64), force[:, 1].astype(np.float64)


# ── numpy brute-force (exact; also the reference the others are tested against) ────────────
def forces_brute(x, y, gm):
    dx = x[None, :] - x[:, None]
    dy = y[None, :] - y[:, None]
    d2 = dx * dx + dy * dy + BARNES_HUT_SOFTENING ** 2
    inv = 1.0 / np.sqrt(d2)
    # The i==j term is dx=dy=0 so its directional contribution is exactly zero — no masking needed.
    f = (MOLECULAR_CLOUD_GRAVITY_CONSTANT * gm[:, None] * gm[None, :]) / d2
    fx = np.sum(dx * inv * f, axis=1)
    fy = np.sum(dy * inv * f, axis=1)
    return fx, fy


# ── Cython Barnes-Hut ──────────────────────────────────────────────────────────────────────
def forces_barnes_hut(x, y, gm):
    n = len(x)
    fx = np.zeros(n)
    fy = np.zeros(n)
    ok = _fastphysics.bh_forces(
        np.ascontiguousarray(x), np.ascontiguousarray(y), np.ascontiguousarray(gm),
        fx, fy, n,
        MOLECULAR_CLOUD_GRAVITY_CONSTANT, BARNES_HUT_SOFTENING ** 2,
        BARNES_HUT_THETA, BARNES_HUT_MAX_DEPTH)
    if not ok:  # tree overflow (pathological input) — fall back to the exact sum
        return forces_brute(x, y, gm)
    return fx, fy


# ── local short-range model (the original spatial-hash physics, cell-mask vectorized) ──────
def forces_local(x, y, gm):
    """Original third-tier physics: each cloud only feels clouds in its 3x3 grid-cell
    neighborhood (cell = SPATIAL_HASH_CELL_SIZE), unsoftened, with a <1px exclusion."""
    cx = np.floor(x / SPATIAL_HASH_CELL_SIZE).astype(np.int64)
    cy = np.floor(y / SPATIAL_HASH_CELL_SIZE).astype(np.int64)
    near = (np.abs(cx[None, :] - cx[:, None]) <= 1) & (np.abs(cy[None, :] - cy[:, None]) <= 1)
    dx = x[None, :] - x[:, None]
    dy = y[None, :] - y[:, None]
    d2 = dx * dx + dy * dy
    valid = near & (d2 >= 1.0)
    d2s = np.where(valid, d2, 1.0)
    inv = 1.0 / np.sqrt(d2s)
    f = np.where(valid, (MOLECULAR_CLOUD_GRAVITY_CONSTANT * gm[:, None] * gm[None, :]) / d2s, 0.0)
    fx = np.sum(dx * inv * f, axis=1)
    fy = np.sum(dy * inv * f, axis=1)
    return fx, fy


def cloud_forces(x, y, mass, is_star):
    """Backend dispatch. Returns (fx, fy) acceleration-force arrays for v += f*dt."""
    gm = grav_masses(mass, is_star)
    if GPU_GRAVITY_ENABLED and _init_gpu():
        return forces_gpu(x, y, gm)
    if BARNES_HUT_ENABLED:
        if _fastphysics is not None and hasattr(_fastphysics, 'bh_forces'):
            return forces_barnes_hut(x, y, gm)
        return forces_brute(x, y, gm)  # same long-range physics, exact
    return forces_local(x, y, gm)

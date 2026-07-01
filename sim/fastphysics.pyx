# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
"""Compiled hot physics loops. Same algorithms as the pure-Python versions in sim.py — just typed
and compiled (nogil-capable, so they can be threaded later). Behavior is preserved exactly."""

from libc.math cimport sqrt, fabs, pow
from libc.stdlib cimport rand, RAND_MAX


cpdef void collide(double[::1] x, double[::1] y, double[::1] size, double[::1] mass,
                   double[::1] vx, double[::1] vy, long[::1] elem, unsigned char[::1] removed,
                   Py_ssize_t n, double merge_chance, double protostar_threshold, double max_mass,
                   double start_size, double min_size, double start_mass, double growth_rate) nogil:
    """Cloud collision detection + merge — same logic as the Python handle_collisions, compiled.
    All-pairs (cheap in C at capped counts, finds the same colliding pairs as the spatial hash).
    Modifies mass/vx/vy/size and the `removed` flags in place. RNG is C rand (probability-equivalent)."""
    cdef Py_ssize_t i, j, surv, cons
    cdef bint is_proto, compat
    cdef double merged, total, s
    for i in range(n):
        if removed[i]:
            continue
        for j in range(n):
            if j == i or removed[j]:
                continue
            is_proto = mass[i] >= protostar_threshold or mass[j] >= protostar_threshold
            compat = is_proto or (elem[i] - elem[j] <= 1 and elem[j] - elem[i] <= 1)
            if not compat:
                continue
            # AABB overlap (same as MolecularCloud.collides_with)
            if not (x[i] < x[j] + size[j] and x[i] + size[i] > x[j]
                    and y[i] < y[j] + size[j] and y[i] + size[i] > y[j]):
                continue
            if (<double>rand() / RAND_MAX) >= merge_chance:
                continue
            # Higher element index survives (tie -> i), matching the Python version.
            if elem[j] > elem[i]:
                surv = j
                cons = i
            else:
                surv = i
                cons = j
            merged = mass[surv] + mass[cons]
            total = merged
            if total > 0.0:
                vx[surv] = (mass[surv] * vx[surv] + mass[cons] * vx[cons]) / total
                vy[surv] = (mass[surv] * vy[surv] + mass[cons] * vy[cons]) / total
            mass[surv] = merged if merged < max_mass else max_mass
            s = start_size - (mass[surv] - start_mass) * growth_rate
            size[surv] = s if s > min_size else min_size
            removed[cons] = 1
            if cons == i:
                break


cpdef double pulse_force(double[::1] xs, double[::1] ys, double[::1] vx, double[::1] vy,
                         Py_ssize_t n, double px, double py, double radius, double band,
                         double inner_sq, double outer_sq, double coeff, double exponent,
                         double dt, double energy_budget) nogil:
    """Apply one expanding pulse's radial force to a set of entities, in order, draining a shared
    energy budget and stopping when it's spent — identical to the Python loop, but compiled.
    Modifies vx/vy in place; returns the remaining energy budget."""
    cdef Py_ssize_t i
    cdef double dx, dy, dsq, distance, ripple, effect, force
    for i in range(n):
        if energy_budget <= 0.0:
            break
        dx = xs[i] - px
        dy = ys[i] - py
        dsq = dx * dx + dy * dy
        if dsq < inner_sq or dsq > outer_sq:
            continue
        distance = sqrt(dsq)
        ripple = fabs(distance - radius)
        if ripple < band and distance > 0.0:
            effect = 1.0 - ripple / band
            force = coeff * effect / pow(ripple + 1.0, exponent)
            vx[i] += (dx / distance) * force * dt
            vy[i] += (dy / distance) * force * dt
            energy_budget -= force * dt * 0.01
    return energy_budget

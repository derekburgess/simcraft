# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
"""Compiled hot physics loops.

- collide:   cloud-cloud merge detection/resolution (sequential logic with RNG — the one hot
             loop that genuinely can't vectorize). Reads/writes the CloudField arrays in place.
- bh_forces: Barnes-Hut cloud gravity — flat-array quadtree, nogil. Computes the same force
             formula as the GPU and numpy-brute backends (tiered grav-mass, softening); theta
             controls the approximation. Returns 0 if the node pool overflows (pathological
             input), in which case the caller falls back to the exact numpy sum.
"""

import numpy as np
from libc.math cimport sqrt
from libc.stdlib cimport rand, RAND_MAX


cpdef void collide(double[::1] x, double[::1] y, double[::1] size, double[::1] mass,
                   double[::1] vx, double[::1] vy, long[::1] elem, unsigned char[::1] removed,
                   Py_ssize_t n, double merge_chance, double protostar_threshold, double max_mass,
                   double start_size, double min_size, double start_mass, double growth_rate) nogil:
    """Cloud collision detection + merge. All-pairs (cheap in C at capped counts).
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
            # AABB overlap (same as the historical MolecularCloud.collides_with)
            if not (x[i] < x[j] + size[j] and x[i] + size[i] > x[j]
                    and y[i] < y[j] + size[j] and y[i] + size[i] > y[j]):
                continue
            if (<double>rand() / RAND_MAX) >= merge_chance:
                continue
            # Higher element index survives (tie -> i).
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


cpdef bint bh_forces(double[::1] x, double[::1] y, double[::1] gm,
                     double[::1] fx, double[::1] fy, Py_ssize_t n,
                     double G, double soft2, double theta, int max_depth):
    """Barnes-Hut mutual gravity over the whole field. Flat-array quadtree: nodes are rows in
    preallocated arrays, leaf bodies are linked lists. Same physics as forces_brute; theta is
    the opening angle (0 = exact)."""
    if n < 2:
        return True

    cdef Py_ssize_t cap_nodes = 8 * n + 4 * max_depth + 64
    cdef int[::1] child = np.full(cap_nodes * 4, -1, dtype=np.int32)
    cdef double[::1] ncx = np.zeros(cap_nodes)
    cdef double[::1] ncy = np.zeros(cap_nodes)
    cdef double[::1] nm = np.zeros(cap_nodes)
    cdef double[::1] nx0 = np.zeros(cap_nodes)
    cdef double[::1] ny0 = np.zeros(cap_nodes)
    cdef double[::1] nsz = np.zeros(cap_nodes)
    cdef int[::1] ndepth = np.zeros(cap_nodes, dtype=np.int32)
    cdef signed char[::1] internal = np.zeros(cap_nodes, dtype=np.int8)
    cdef int[::1] first_body = np.full(cap_nodes, -1, dtype=np.int32)
    cdef int[::1] next_body = np.full(n, -1, dtype=np.int32)
    cdef int[::1] job_body = np.zeros(n + 8, dtype=np.int32)
    cdef int[::1] job_node = np.zeros(n + 8, dtype=np.int32)
    cdef int[::1] job_com = np.zeros(n + 8, dtype=np.int32)
    cdef int[::1] tstack = np.zeros(cap_nodes + 8, dtype=np.int32)

    cdef Py_ssize_t i
    cdef int node_count, node, b, ob, q, ch, sp, jsp, do_com
    cdef double minx, maxx, miny, maxy, size0, half, total
    cdef double xi, yi, mi, dx, dy, d2, dist_sq, inv, f, accx, accy
    cdef double theta2 = theta * theta
    cdef bint ok = True

    with nogil:
        # ── bounding square ──
        minx = x[0]; maxx = x[0]; miny = y[0]; maxy = y[0]
        for i in range(1, n):
            if x[i] < minx: minx = x[i]
            if x[i] > maxx: maxx = x[i]
            if y[i] < miny: miny = y[i]
            if y[i] > maxy: maxy = y[i]
        size0 = maxx - minx
        if maxy - miny > size0:
            size0 = maxy - miny
        if size0 < 1.0:
            size0 = 1.0
        size0 = size0 * 1.0001 + 1.0

        # ── build ──
        node_count = 1
        nx0[0] = minx; ny0[0] = miny; nsz[0] = size0; ndepth[0] = 0

        for i in range(n):
            jsp = 0
            job_body[jsp] = <int>i
            job_node[jsp] = 0
            # a job folds COM at its start node unless it's a re-insertion after subdivision
            # (the node's COM already counts that body) — the flag travels with the job
            job_com[jsp] = 1
            jsp += 1
            while jsp > 0:
                jsp -= 1
                b = job_body[jsp]
                node = job_node[jsp]
                do_com = job_com[jsp]
                while True:
                    if do_com:
                        if nm[node] == 0.0:
                            ncx[node] = x[b]
                            ncy[node] = y[b]
                        else:
                            total = nm[node] + gm[b]
                            ncx[node] = (ncx[node] * nm[node] + x[b] * gm[b]) / total
                            ncy[node] = (ncy[node] * nm[node] + y[b] * gm[b]) / total
                        nm[node] += gm[b]
                    do_com = 1
                    if internal[node] == 0:
                        if first_body[node] == -1:
                            first_body[node] = b
                            next_body[b] = -1
                            break
                        if ndepth[node] >= max_depth:
                            next_body[b] = first_body[node]
                            first_body[node] = b
                            break
                        # subdivide: re-queue resident bodies (COM here already counts them)
                        internal[node] = 1
                        ob = first_body[node]
                        first_body[node] = -1
                        while ob != -1:
                            job_body[jsp] = ob
                            job_node[jsp] = node
                            job_com[jsp] = 0
                            jsp += 1
                            ob = next_body[ob]
                        # fall through: place b into a child (COM at this node already folded)
                    # descend
                    half = nsz[node] * 0.5
                    q = 0
                    dx = nx0[node]
                    dy = ny0[node]
                    if x[b] >= nx0[node] + half:
                        q += 1
                        dx = nx0[node] + half
                    if y[b] >= ny0[node] + half:
                        q += 2
                        dy = ny0[node] + half
                    ch = child[node * 4 + q]
                    if ch == -1:
                        if node_count >= cap_nodes:
                            ok = False
                            break
                        ch = node_count
                        node_count += 1
                        nx0[ch] = dx
                        ny0[ch] = dy
                        nsz[ch] = half
                        ndepth[ch] = ndepth[node] + 1
                        child[node * 4 + q] = ch
                    node = ch
                if not ok:
                    break
            if not ok:
                break

        # ── traverse ──
        if ok:
            for i in range(n):
                xi = x[i]
                yi = y[i]
                mi = gm[i]
                accx = 0.0
                accy = 0.0
                sp = 0
                tstack[sp] = 0
                sp += 1
                while sp > 0:
                    sp -= 1
                    node = tstack[sp]
                    if internal[node] == 0:
                        b = first_body[node]
                        while b != -1:
                            if b != <int>i:
                                dx = x[b] - xi
                                dy = y[b] - yi
                                d2 = dx * dx + dy * dy + soft2
                                inv = 1.0 / sqrt(d2)
                                f = G * mi * gm[b] / d2
                                accx += dx * inv * f
                                accy += dy * inv * f
                            b = next_body[b]
                        continue
                    dx = ncx[node] - xi
                    dy = ncy[node] - yi
                    dist_sq = dx * dx + dy * dy
                    # Opening criterion: treat the node as a single mass when size/dist < theta.
                    if nsz[node] * nsz[node] < theta2 * dist_sq:
                        d2 = dist_sq + soft2
                        inv = 1.0 / sqrt(d2)
                        f = G * mi * nm[node] / d2
                        accx += dx * inv * f
                        accy += dy * inv * f
                    else:
                        for q in range(4):
                            ch = child[node * 4 + q]
                            if ch != -1:
                                tstack[sp] = ch
                                sp += 1
                fx[i] = accx
                fy[i] = accy

    return ok

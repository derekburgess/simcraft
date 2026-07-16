# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
"""Compiled hot physics loops.

- collide:   cloud-cloud merge detection/resolution (sequential logic with RNG — the one hot
             loop that genuinely can't vectorize). Reads/writes the CloudField arrays in place.
             Enumeration is grid-bucketed: merges are AABB-overlap-gated and cell size is the
             field's max cloud size, so adjacent cells contain every overlapping pair — the
             grid is an exact filter, not an approximation. Falls back to the dense loop when
             the field's extent would make the grid bigger than the pair matrix.
- collide_shocked: the shock-triggered merge pass over a small index list. Upper-triangle on
             purpose — one merge roll per pair per pass, matching the historical Python loop
             (the dense collide rolls each ordered pair, effectively 1-(1-p)^2; routing shocks
             through it would silently raise the shock merge rate).
- bh_forces: Barnes-Hut cloud gravity — flat-array quadtree, nogil. Computes the same force
             formula as the GPU and numpy-brute backends (tiered grav-mass, softening); theta
             controls the approximation. Returns 0 if the node pool overflows (pathological
             input), in which case the caller falls back to the exact numpy sum.
"""

import numpy as np
from libc.math cimport sqrt, floor
from libc.stdlib cimport rand, RAND_MAX


cdef inline bint _try_merge(double[::1] x, double[::1] y, double[::1] size, double[::1] mass,
                            double[::1] vx, double[::1] vy, long[::1] elem,
                            unsigned char[::1] removed, Py_ssize_t i, Py_ssize_t j,
                            double merge_chance, double protostar_threshold, double max_mass,
                            double start_size, double min_size, double start_mass,
                            double growth_rate) noexcept nogil:
    """One candidate pair: compatibility -> AABB overlap -> merge roll -> resolve.
    Returns True when i was consumed (the caller's outer loop must stop scanning i)."""
    cdef Py_ssize_t surv, cons
    cdef bint is_proto, compat
    cdef double merged, s
    is_proto = mass[i] >= protostar_threshold or mass[j] >= protostar_threshold
    compat = is_proto or (elem[i] - elem[j] <= 1 and elem[j] - elem[i] <= 1)
    if not compat:
        return False
    # AABB overlap (same as the historical MolecularCloud.collides_with)
    if not (x[i] < x[j] + size[j] and x[i] + size[i] > x[j]
            and y[i] < y[j] + size[j] and y[i] + size[i] > y[j]):
        return False
    if (<double>rand() / RAND_MAX) >= merge_chance:
        return False
    # Higher element index survives (tie -> i).
    if elem[j] > elem[i]:
        surv = j
        cons = i
    else:
        surv = i
        cons = j
    merged = mass[surv] + mass[cons]
    if merged > 0.0:
        vx[surv] = (mass[surv] * vx[surv] + mass[cons] * vx[cons]) / merged
        vy[surv] = (mass[surv] * vy[surv] + mass[cons] * vy[cons]) / merged
    mass[surv] = merged if merged < max_mass else max_mass
    s = start_size - (mass[surv] - start_mass) * growth_rate
    size[surv] = s if s > min_size else min_size
    removed[cons] = 1
    return cons == i


cpdef void collide(double[::1] x, double[::1] y, double[::1] size, double[::1] mass,
                   double[::1] vx, double[::1] vy, long[::1] elem, unsigned char[::1] removed,
                   Py_ssize_t n, double merge_chance, double protostar_threshold, double max_mass,
                   double start_size, double min_size, double start_mass, double growth_rate):
    """Cloud collision detection + merge. Grid-bucketed candidate enumeration (exact — see
    module docstring); same ordered-pair roll semantics as the historical dense loop, whose
    row-order outer scan is preserved. Only the inner enumeration ORDER differs from the dense
    loop, i.e. the RNG interleaving — statistically identical, bitwise different (by design;
    runs are unrepeatable anyway). Modifies mass/vx/vy/size and `removed` in place."""
    if n < 2:
        return
    cdef Py_ssize_t i, j, k, gi, gj, gx0, gx1, gy0, gy1, c
    cdef double minx, maxx, miny, maxy, smax, cs
    cdef Py_ssize_t gw, gh, ncells
    cdef bint i_dead

    # Field extent and max size set the cell: overlap needs |dx| < max(size_i, size_j) <= smax,
    # so every overlapping partner of i lives within +-1 cell of i's cell.
    minx = x[0]; maxx = x[0]; miny = y[0]; maxy = y[0]; smax = size[0]
    for i in range(1, n):
        if x[i] < minx: minx = x[i]
        if x[i] > maxx: maxx = x[i]
        if y[i] < miny: miny = y[i]
        if y[i] > maxy: maxy = y[i]
        if size[i] > smax: smax = size[i]
    cs = smax if smax > 1.0 else 1.0
    gw = <Py_ssize_t>((maxx - minx) / cs) + 1
    gh = <Py_ssize_t>((maxy - miny) / cs) + 1
    ncells = gw * gh

    if ncells > 4 * n * n or ncells > (1 << 22):
        # Pathological spread: grid would dwarf the pair matrix — dense scan is cheaper.
        with nogil:
            for i in range(n):
                if removed[i]:
                    continue
                for j in range(n):
                    if j == i or removed[j]:
                        continue
                    if _try_merge(x, y, size, mass, vx, vy, elem, removed, i, j,
                                  merge_chance, protostar_threshold, max_mass,
                                  start_size, min_size, start_mass, growth_rate):
                        break
        return

    # Counting sort of bodies into cells (row order preserved within each cell).
    cell_np = np.empty(n, dtype=np.intp)
    start_np = np.zeros(ncells + 1, dtype=np.intp)
    order_np = np.empty(n, dtype=np.intp)
    cdef Py_ssize_t[::1] cell = cell_np
    cdef Py_ssize_t[::1] cstart = start_np
    cdef Py_ssize_t[::1] order = order_np

    with nogil:
        for i in range(n):
            gi = <Py_ssize_t>((x[i] - minx) / cs)
            gj = <Py_ssize_t>((y[i] - miny) / cs)
            cell[i] = gj * gw + gi
            cstart[cell[i] + 1] += 1
        for c in range(ncells):
            cstart[c + 1] += cstart[c]
        for i in range(n):
            order[cstart[cell[i]]] = i
            cstart[cell[i]] += 1
        for c in range(ncells, 0, -1):   # undo the in-place bump: cstart[c] = first index of cell c
            cstart[c] = cstart[c - 1]
        cstart[0] = 0

        for i in range(n):
            if removed[i]:
                continue
            gi = cell[i] % gw
            gj = cell[i] / gw
            gx0 = gi - 1 if gi > 0 else 0
            gx1 = gi + 1 if gi + 1 < gw else gw - 1
            gy0 = gj - 1 if gj > 0 else 0
            gy1 = gj + 1 if gj + 1 < gh else gh - 1
            i_dead = False
            for gj in range(gy0, gy1 + 1):
                for gi in range(gx0, gx1 + 1):
                    c = gj * gw + gi
                    for k in range(cstart[c], cstart[c + 1]):
                        j = order[k]
                        if j == i or removed[j]:
                            continue
                        if _try_merge(x, y, size, mass, vx, vy, elem, removed, i, j,
                                      merge_chance, protostar_threshold, max_mass,
                                      start_size, min_size, start_mass, growth_rate):
                            i_dead = True
                            break
                    if i_dead:
                        break
                if i_dead:
                    break


cpdef void collide_shocked(long[::1] idx, double[::1] x, double[::1] y, double[::1] size,
                           double[::1] mass, double[::1] vx, double[::1] vy, long[::1] elem,
                           unsigned char[::1] removed, Py_ssize_t m, double merge_chance,
                           double protostar_threshold, double max_mass, double start_size,
                           double min_size, double start_mass, double growth_rate) nogil:
    """Shock-triggered merge pass: upper-triangle over the shocked index list `idx` (length m),
    one roll per pair per pass — the exact statistics of the historical Python loop in
    physics._triggered_mergers, which stays as the semantic reference/fallback."""
    cdef Py_ssize_t a, b, i, j
    for a in range(m):
        i = idx[a]
        if removed[i]:
            continue
        for b in range(a + 1, m):
            j = idx[b]
            if removed[j]:
                continue
            if _try_merge(x, y, size, mass, vx, vy, elem, removed, i, j,
                          merge_chance, protostar_threshold, max_mass,
                          start_size, min_size, start_mass, growth_rate):
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

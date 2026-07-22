"""The cosmic boundary ring: a deformable closed loop of radii. All per-vertex state is numpy;
per-cloud interactions (deformation accumulation, containment) are vectorized over the
universe's CloudField, while the handful of compact objects (holes, neutron stars) stay scalar.
"""
import math
import random

import numpy as np

from sim.config import *


class Barrier:
    def __init__(self, center, screen_size, num_points):
        self.center = center
        self.num_points = num_points
        self.angles = (2 * math.pi / num_points) * np.arange(num_points)
        self.cos_a = np.cos(self.angles)
        self.sin_a = np.sin(self.angles)

        r = max(screen_size[0], screen_size[1]) / 2.0
        self.rest_radius = r

        # CMB perturbations. Scalar math.sin on purpose: bit-identical to the historical init
        # (np.sin differs in the last ulp, which is enough to flip knife-edge merge decisions
        # and break seeded A/B comparisons). One-time cost, ~4k sin calls.
        perturbation = [0.0] * num_points
        for mode in range(1, CMB_PERTURBATION_MODES + 1):
            amplitude = random.gauss(0, CMB_PERTURBATION_SCALE / mode)
            phase = random.uniform(0, 2 * math.pi)
            for i in range(num_points):
                perturbation[i] += amplitude * math.sin(mode * float(self.angles[i]) + phase)
        self.perturbation = np.array(perturbation)

        self.radii = np.array([r * (1.0 + perturbation[i]) for i in range(num_points)])
        self.radii_vel = np.zeros(num_points)
        self.flash = np.zeros(num_points)

    # ── radius lookup ──
    def radius_at(self, angles):
        """Vectorized linear interpolation of the ring radius at the given angles (array)."""
        step = 2 * math.pi / self.num_points
        idx = (np.asarray(angles) % (2 * math.pi)) / step
        i0 = idx.astype(np.int64) % self.num_points
        i1 = (i0 + 1) % self.num_points
        t = idx - np.floor(idx)
        return self.radii[i0] * (1 - t) + self.radii[i1] * t

    def get_radius_at_angle(self, angle):
        """Scalar variant, kept for the sparse callers (overlap resolution, pulse clipping)."""
        angle = angle % (2 * math.pi)
        step = 2 * math.pi / self.num_points
        idx = angle / step
        i0 = int(idx) % self.num_points
        i1 = (i0 + 1) % self.num_points
        t = idx - int(idx)
        return self.radii[i0] * (1 - t) + self.radii[i1] * t

    def _entity_angle_and_dist(self, entity):
        dx = entity.x - self.center[0]
        dy = entity.y - self.center[1]
        dist = math.hypot(dx, dy)
        angle = math.atan2(dy, dx) % (2 * math.pi)
        return angle, dist, dx, dy

    # ── physics ──
    def apply_gravity(self, universe, delta_time):
        # The barrier only pulls on black holes. Clouds and other matter are organized purely by
        # black-hole gravity, so they clump into galaxies that get carried along as the barrier
        # tugs each hole around. (Containment of clouds is still handled separately by enforce().)
        cx, cy = self.center
        for bh in universe.black_holes:
            angle, dist, dx, dy = self._entity_angle_and_dist(bh)
            barrier_r = self.get_radius_at_angle(angle)
            target_dx = cx + barrier_r * math.cos(angle) - bh.x
            target_dy = cy + barrier_r * math.sin(angle) - bh.y
            target_dist = max(math.hypot(target_dx, target_dy), 1)
            force = (BARRIER_GRAVITY_CONSTANT * math.sqrt(bh.mass) / (target_dist ** 2)) * BLACK_HOLE_BARRIER_GRAVITY_FACTOR
            bh.vx += (target_dx / target_dist) * force * delta_time
            bh.vy += (target_dy / target_dist) * force * delta_time

    def _accum_deformation_scalar(self, entity, mass_accum, step, proximity_threshold, factor):
        angle, dist, _, _ = self._entity_angle_and_dist(entity)
        barrier_r = self.get_radius_at_angle(angle)
        if abs(dist - barrier_r) < proximity_threshold:
            idx = angle / step
            i0 = int(idx) % self.num_points
            i1 = (i0 + 1) % self.num_points
            t = idx - int(idx)
            effective_mass = math.sqrt(entity.mass) * factor
            mass_accum[i0] += effective_mass * (1 - t)
            mass_accum[i1] += effective_mass * t

    def update_deformation(self, universe, delta_time):
        n = self.num_points
        mass_accum = np.zeros(n)
        step = 2 * math.pi / n
        proximity_threshold = self.rest_radius * BARRIER_DEFORMATION_PROXIMITY_FACTOR

        clouds = universe.clouds
        if clouds.n:
            # Own gate, below stardom: heavy clouds (>= BARRIER_DEFORM_CLOUD_MASS) dent at the
            # cloud factor, stars at theirs. Gating on PROTOSTAR_THRESHOLD here made the cloud
            # factor unreachable — any cloud that heavy ignites into a star on the next refresh.
            heavy = clouds.M >= BARRIER_DEFORM_CLOUD_MASS
            if heavy.any():
                dx = clouds.X[heavy] - self.center[0]
                dy = clouds.Y[heavy] - self.center[1]
                dist = np.hypot(dx, dy)
                angle = np.arctan2(dy, dx) % (2 * math.pi)
                barrier_r = self.radius_at(angle)
                near = np.abs(dist - barrier_r) < proximity_threshold
                if near.any():
                    factor = np.where(clouds.IS_STAR[heavy][near],
                                      STAR_BARRIER_DEFORM_FACTOR, MOLECULAR_CLOUD_BARRIER_DEFORM_FACTOR)
                    idx = angle[near] / step
                    i0 = idx.astype(np.int64) % n
                    i1 = (i0 + 1) % n
                    t = idx - np.floor(idx)
                    eff = np.sqrt(clouds.M[heavy][near]) * factor
                    np.add.at(mass_accum, i0, eff * (1 - t))
                    np.add.at(mass_accum, i1, eff * t)

        for bh in universe.black_holes:
            self._accum_deformation_scalar(bh, mass_accum, step, proximity_threshold, BLACK_HOLE_BARRIER_DEFORM_FACTOR)
        for ns in (*universe.neutron_stars, *universe.magnetars):
            self._accum_deformation_scalar(ns, mass_accum, step, proximity_threshold, NEUTRON_STAR_BARRIER_DEFORM_FACTOR)

        # Magnetic grip, two ranges. IN-FIELD (field radius): wall and magnetar attract each
        # other — vertices bow toward the magnetar (bounded relaxation toward its radial
        # distance, which can't run away like a constant pull) and the magnetar is drawn to
        # the wall, ramping to full stick at contact so it slides in and stays. LATCHED
        # (denting proximity band): the field reels the WHOLE ring in evenly — the
        # contraction counterpart to pulse-driven expansion. Even pull + tension keeps the
        # ring round; reeling only the facing vertices digs a runaway trench that slings the
        # magnetar to the center. Barrier damping bounds the speeds, and the natal-radius
        # soft floor means a magnetar can squeeze a universe back toward Big-Bang size but
        # not crush it.
        natal_radius = BARRIER_INITIAL_SIZE / 2
        for m in universe.magnetars:
            bx = self.center[0] + self.radii * self.cos_a
            by = self.center[1] + self.radii * self.sin_a
            vdist = np.hypot(bx - m.x, by - m.y)
            infield = vdist < MAGNETAR_FIELD_RADIUS
            if infield.any():
                m_dist = math.hypot(m.x - self.center[0], m.y - self.center[1])
                target = max(m_dist, natal_radius)
                falloff = 1.0 - vdist[infield] / MAGNETAR_FIELD_RADIUS
                self.radii_vel[infield] += ((target - self.radii[infield])
                                            * MAGNETAR_BARRIER_ATTRACT_RATE * falloff * delta_time)
                near_i = int(np.argmin(vdist))
                sx = float(bx[near_i]) - m.x
                sy = float(by[near_i]) - m.y
                sd = max(math.hypot(sx, sy), 1e-9)
                ramp = 1.0 - sd / MAGNETAR_FIELD_RADIUS
                m.vx += (sx / sd) * MAGNETAR_WALL_STICK * ramp * delta_time
                m.vy += (sy / sd) * MAGNETAR_WALL_STICK * ramp * delta_time
            latched = vdist < proximity_threshold
            m.latched = bool(latched.any())  # read by Magnetar.update_field (suppresses flares)
            if m.latched:
                above_floor = self.radii > natal_radius
                self.radii_vel[above_floor] -= math.sqrt(m.mass) * MAGNETAR_BARRIER_CONTRACT_FACTOR * delta_time

        damping = BARRIER_DAMPING ** delta_time
        self.radii_vel -= mass_accum * 2.0 * delta_time
        self.radii_vel *= damping
        old_radii = self.radii.copy()
        self.radii = np.maximum(self.radii + self.radii_vel * delta_time, 1.0)
        self.flash[np.abs(self.radii - old_radii) > BARRIER_DEFORM_THRESHOLD] = 1.0

        # Membrane tension: relax each vertex toward its neighbours (Laplacian smoothing on the
        # closed loop) so the barrier deforms as a smooth elastic curve instead of a spiky web.
        smooth = min(0.9, BARRIER_TENSION * delta_time)
        neighbor_avg = 0.5 * (np.roll(self.radii, 1) + np.roll(self.radii, -1))
        self.radii += (neighbor_avg - self.radii) * smooth

        self.flash *= math.exp(-BARRIER_FLASH_DECAY * delta_time)

    def enforce(self, universe, delta_time):
        cx, cy = self.center
        step = 2 * math.pi / self.num_points

        clouds = universe.clouds
        if clouds.n:
            X, Y, VX, VY = clouds.X, clouds.Y, clouds.VX, clouds.VY
            dx = X - cx
            dy = Y - cy
            dist = np.hypot(dx, dy)
            angle = np.arctan2(dy, dx) % (2 * math.pi)
            barrier_r = self.radius_at(angle)
            out = dist >= barrier_r
            if out.any():
                # Pin to just inside the ring and cancel any outward radial velocity component.
                # (dist >= barrier_r >= 1 here — the radii floor in update_deformation — so
                # the division below is always safe.)
                X[out] = cx + barrier_r[out] * 0.99 * np.cos(angle[out])
                Y[out] = cy + barrier_r[out] * 0.99 * np.sin(angle[out])
                oi = np.nonzero(out)[0]
                dxo, dyo, do = dx[oi], dy[oi], dist[oi]
                radial = (VX[oi] * dxo + VY[oi] * dyo) / do
                outward = radial > 0
                oi = oi[outward]
                if len(oi):
                    dxo, dyo, do, radial = dxo[outward], dyo[outward], do[outward], radial[outward]
                    VX[oi] -= (dxo / do) * radial
                    VY[oi] -= (dyo / do) * radial

        compact_angles_masses = []
        for bh in universe.black_holes:
            a, _, _, _ = self._entity_angle_and_dist(bh)
            compact_angles_masses.append((a, bh.mass))
        for ns in (*universe.neutron_stars, *universe.magnetars):
            a, _, _, _ = self._entity_angle_and_dist(ns)
            compact_angles_masses.append((a, ns.mass))

        def _section_mass(angle):
            return sum(m for a, m in compact_angles_masses
                       if abs((a - angle + math.pi) % (2 * math.pi) - math.pi) < step * BARRIER_SECTION_SEARCH_RANGE)

        # Magnetars are neutron stars: same containment physics. White dwarfs are far less
        # dense but still compact — the same containment path holds them in.
        for ns in (*universe.neutron_stars, *universe.magnetars, *universe.white_dwarfs):
            angle, dist, dx, dy = self._entity_angle_and_dist(ns)
            barrier_r = self.get_radius_at_angle(angle)
            if dist >= barrier_r:
                ns.x = cx + barrier_r * 0.99 * math.cos(angle)
                ns.y = cy + barrier_r * 0.99 * math.sin(angle)
                if dist > 0:
                    radial_vx = (dx / dist) * ((ns.vx * dx + ns.vy * dy) / dist)
                    radial_vy = (dy / dist) * ((ns.vx * dx + ns.vy * dy) / dist)
                    if ns.vx * dx + ns.vy * dy > 0:
                        ns.vx -= radial_vx
                        ns.vy -= radial_vy
                weakness = min(_section_mass(angle) / BARRIER_HEAVY_MASS_THRESHOLD, 1.0)
                containment = 1.0 - weakness * NEUTRON_STAR_BARRIER_WEAKENING_FACTOR
                if dist > 0 and containment > BARRIER_CONTAINMENT_THRESHOLD:
                    push_strength = NEUTRON_STAR_BARRIER_PUSH_STRENGTH * containment
                    ns.vx -= (dx / dist) * push_strength * delta_time
                    ns.vy -= (dy / dist) * push_strength * delta_time

        for bh in universe.black_holes:
            angle, dist, dx, dy = self._entity_angle_and_dist(bh)
            barrier_r = self.get_radius_at_angle(angle)
            if dist >= barrier_r:
                weakness = min(_section_mass(angle) / BARRIER_HEAVY_MASS_THRESHOLD, 1.0)
                containment = 1.0 - weakness * BLACK_HOLE_BARRIER_WEAKENING_FACTOR
                if dist > 0 and containment > BARRIER_CONTAINMENT_THRESHOLD:
                    push_strength = BLACK_HOLE_BARRIER_PUSH_STRENGTH * containment
                    bh.vx -= (dx / dist) * push_strength * delta_time
                    bh.vy -= (dy / dist) * push_strength * delta_time

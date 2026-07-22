"""Simcraft main loop: input, timing, heat death. All physics lives in
sim.physics (stepping), sim.entities / sim.barrier / sim.fields (state), sim.gravity
(cloud gravity backends); all drawing in sim.render.
"""
import math
import subprocess
import pygame

from sim.config import *
from sim import physics
from sim import render
from sim.render import WorldRenderer, draw_stats, draw_ticker, draw_elements, draw_hotkeys, hotkeys_alpha
from sim.rng import generate, MIN as RNG_MIN, MAX as RNG_MAX


def copy_to_clipboard(text):
    """Best-effort clipboard copy: SDL's clipboard first (works on X11/Wayland/etc. when a
    window exists), then the common CLI tools."""
    try:
        pygame.scrap.init()
        pygame.scrap.put_text(text)
        return True
    except Exception:
        pass
    for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "-ib"]):
        try:
            subprocess.run(cmd, input=text.encode(), check=True, timeout=2,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            continue
    return False


def screen_to_world(screen_x, screen_y, zoom, view_center_x, view_center_y):
    screen_w, screen_h = pygame.display.get_surface().get_size()
    view_w = screen_w / zoom
    view_h = screen_h / zoom
    view_left = view_center_x - view_w / 2
    view_top = view_center_y - view_h / 2
    world_x = view_left + screen_x / zoom
    world_y = view_top + screen_y / zoom
    return world_x, world_y


def handle_input(zoom, view_center_x, view_center_y, target_zoom, target_center_x, target_center_y):
    """Wheel input adjusts the zoom/center TARGETS; the loop eases the displayed view toward
    them each frame, so rapid ticks accumulate into one continuous glide instead of hard
    cuts. The cursor's world point is computed against the CURRENT (displayed) view — the
    thing the user is actually pointing at."""
    running = True
    toggle_ticker = False
    toggle_barrier = False
    toggle_hotkeys = False
    toggle_gravity_waves = False
    reset_requested = False
    copy_rng = False

    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
            running = False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_l:
            toggle_ticker = True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_b:
            toggle_barrier = True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_h:
            toggle_hotkeys = True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_g:
            toggle_gravity_waves = True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
            reset_requested = True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if render.RNG_CELL_RECT is not None and render.RNG_CELL_RECT.collidepoint(event.pos):
                copy_rng = True
        if event.type == pygame.MOUSEWHEEL:
            mouse_sx, mouse_sy = pygame.mouse.get_pos()
            world_x, world_y = screen_to_world(mouse_sx, mouse_sy, zoom, view_center_x, view_center_y)
            old_target = target_zoom
            target_zoom = max(ZOOM_MIN, min(ZOOM_MAX, target_zoom * ZOOM_STEP_FACTOR ** event.y))
            if target_zoom != old_target:
                # The world point under the cursor becomes the new view center, zooming in
                # OR out — no forced recentering (the renderer clamps the view at the wide
                # end, so zoomed way out you see the whole scene regardless of center).
                target_center_x = world_x
                target_center_y = world_y

    return (running, target_zoom, target_center_x, target_center_y,
            toggle_ticker, toggle_barrier, toggle_hotkeys, toggle_gravity_waves,
            reset_requested, copy_rng)


def run_simulation(screen, state):
    try:
        running = True
        clock = pygame.time.Clock()
        current_year = 0.0
        last_frame_time = pygame.time.get_ticks()
        heat_death_timer = 0.0
        zoom = 1.0
        view_center_x = SCREEN_WIDTH / 2.0
        view_center_y = SCREEN_HEIGHT / 2.0
        target_zoom = zoom
        target_center_x = view_center_x
        target_center_y = view_center_y
        renderer = WorldRenderer()
        show_ticker = False  # start quiet; [L] brings the event log up
        show_barrier = True
        show_gravity_waves = True
        show_hotkeys = True
        hotkeys_age = 0.0  # seconds since last shown; drives the fade in hotkeys_alpha()
        ticker = []  # [text, age, count] event lines, newest last; dropped once faded (no scrollback)
        rng_number = None
        rng_flash = 0.0  # copied-to-clipboard flash on the RNG cell, 1 → 0

        while running:
            current_time = pygame.time.get_ticks()
            delta_time = (current_time - last_frame_time) / 1000.0
            delta_time = min(delta_time, MAX_DELTA_TIME)
            last_frame_time = current_time

            (running, target_zoom, target_center_x, target_center_y,
             toggle_ticker, toggle_barrier, toggle_hotkeys, toggle_gravity_waves,
             reset_requested, copy_rng) = handle_input(
                zoom, view_center_x, view_center_y, target_zoom, target_center_x, target_center_y)
            if not running:
                break

            # Ease the displayed view toward its targets (zoom in log space so the glide is
            # perceptually uniform), snapping when close so the zoom==1.0 fast path re-engages.
            blend = 1.0 - math.exp(-ZOOM_SMOOTH_RATE * delta_time)
            zoom = math.exp(math.log(zoom) + (math.log(target_zoom) - math.log(zoom)) * blend)
            view_center_x += (target_center_x - view_center_x) * blend
            view_center_y += (target_center_y - view_center_y) * blend
            if abs(zoom - target_zoom) < 0.001:
                zoom = target_zoom
            if abs(view_center_x - target_center_x) < 0.1 and abs(view_center_y - target_center_y) < 0.1:
                view_center_x, view_center_y = target_center_x, target_center_y
            if toggle_ticker:
                show_ticker = not show_ticker
            if toggle_barrier:
                show_barrier = not show_barrier
            if toggle_gravity_waves:
                show_gravity_waves = not show_gravity_waves
            if toggle_hotkeys:
                show_hotkeys = not show_hotkeys
                if show_hotkeys:
                    hotkeys_age = 0.0
            if copy_rng and rng_number is not None:
                if copy_to_clipboard(str(rng_number)):
                    rng_flash = 1.0

            for universe in state.universes:
                universe.barrier.update_deformation(universe, delta_time)
                physics.step(universe, universe.barrier, delta_time)

            # Each black-hole birth this step opens a new universe (capped) outside the existing ones.
            physics.process_universe_spawns(state)
            physics.enforce_total_cloud_cap(state)

            # Dark flow: the whole cluster drifts toward its mass-weighted centroid; then
            # keep universes from overlapping (larger shoves smaller aside).
            physics.apply_dark_flow(state, delta_time)
            physics.resolve_barrier_overlaps(state, delta_time)

            # A universe that runs out of matter is removed (its final events and an epitaph
            # pass to the ticker), freeing a slot for a future spawn. The last surviving
            # universe is never reaped, so multiverse heat death can linger/reset as before.
            physics.reap_dead_universes(state)
            physics.prune_child_links(state)

            # Drain each universe's astrophysical events into the HUD ticker; identical
            # events landing within a beat coalesce into one line (shown without a count).
            # Entries are dropped once they've fully faded — no scrollback to preserve them for.
            for universe in state.universes:
                for text in universe.event_log:
                    if ticker and ticker[-1][0] == text and ticker[-1][1] < 1.0:
                        ticker[-1][2] += 1
                    else:
                        ticker.append([text, 0.0, 1])
                universe.event_log.clear()
            for entry in ticker:
                entry[1] += delta_time
            ticker = [e for e in ticker if e[1] < UI_TICKER_LIFETIME]
            rng_flash = max(0.0, rng_flash - 2.0 * delta_time)

            # Fold this frame's trajectory into the entropy pool: OS timing jitter plus
            # chaotic observables (full state every FULL_FOLD_INTERVAL frames).
            state.entropy_pool.fold_frame(state, current_time, clock.get_rawtime())

            # Heat death of the whole multiverse (every universe gone) lingers for
            # HEAT_DEATH_LINGER_DURATION before resetting, so the empty scene isn't a
            # jump-cut; a manual [R] reset fires the same reset immediately.
            if not state.universes or state.entity_count() == 0 or state.total_mass() <= 0:
                heat_death_timer += delta_time
            else:
                heat_death_timer = 0.0
            if reset_requested or heat_death_timer >= HEAT_DEATH_LINGER_DURATION:
                print(f"Manual reset at year {current_year}" if reset_requested
                      else f"Reset at year {current_year}")
                entropy_pool = state.entropy_pool
                entropy_pool.fold(b'manual-reset' if reset_requested else b'heat-death-reset')
                state = physics.initialize_state()
                state.entropy_pool = entropy_pool  # the pool remembers past universes
                current_year = 0.0
                zoom = target_zoom = 1.0
                view_center_x = target_center_x = SCREEN_WIDTH / 2.0
                view_center_y = target_center_y = SCREEN_HEIGHT / 2.0
                heat_death_timer = 0.0

            renderer.render(screen, state, zoom, view_center_x, view_center_y, show_barrier, show_gravity_waves)

            # Fresh RNG output every frame, drawn from the running entropy pool
            # (which folds the live state continuously — no full re-serialize here).
            try:
                rng_number = generate(state.entropy_pool, RNG_MIN, RNG_MAX)['random_number']
            except Exception as rng_err:
                print(f"HUD RNG failed: {rng_err}")
                rng_number = None

            if show_ticker:
                draw_ticker(screen, ticker)
            draw_stats(screen, clock.get_fps(), current_year, len(state.universes),
                       state.entity_count(), rng_number,
                       state.mean_metallicity(), rng_flash)

            # Help overlay: hotkeys + entity key (top right) and the element inventory row
            # (above the stats table) show and fade together.
            if show_hotkeys:
                hotkeys_age += delta_time
                alpha = hotkeys_alpha(hotkeys_age)
                if alpha <= 0:
                    show_hotkeys = False
                else:
                    draw_hotkeys(screen, alpha)
                    draw_elements(screen, state.present_elements(), alpha)

            # Log-time cosmic clock: dy = ln10/decade * (y + 1000) dt integrates to a fixed
            # wall-time per factor-of-10 of years (see COSMIC_DECADE_SECONDS in config). That
            # rate has no ceiling on its own — it compounds forever, so it never stops feeling
            # like it's speeding up. Capping it turns the curve linear once it would exceed the
            # pace that felt right (reached right around the billions mark), instead of letting
            # it keep exponentially accelerating for the rest of the session.
            year_rate = min(MAX_YEAR_RATE, (math.log(10) / COSMIC_DECADE_SECONDS) * (current_year + 1000.0))
            current_year += delta_time * year_rate

            pygame.display.flip()
            clock.tick(TARGET_FPS)

        print("Exited simulation")

        try:
            state.entropy_pool.fold_state(state)
            result = generate(state.entropy_pool, RNG_MIN, RNG_MAX)
            print(f"RANDOM: {result['random_number']}")
        except Exception as rng_err:
            print(f"RNG FAILED: {rng_err}")

    except Exception as e:
        import traceback
        print(f"Error occurred in simulation loop: {e}")
        traceback.print_exc()
    finally:
        pygame.quit()


def main():
    pygame.init()
    pygame.display.set_caption("A long time ago in a universe far, far away...")
    # RESIZABLE puts the maximize button in the title bar. Rendering happens at the window's
    # actual size (the display surface auto-resizes with the window), so maximizing or
    # fullscreening any aspect ratio fills the window edge-to-edge — no letterbox bars.
    # SCREEN_WIDTH x SCREEN_HEIGHT is only the initial window size.
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
    print("Populating space with molecular clouds")
    state = physics.initialize_state()

    print("Starting simulation")
    run_simulation(screen, state)


if __name__ == "__main__":
    main()

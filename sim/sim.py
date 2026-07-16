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
from sim.render import WorldRenderer, draw_ui, draw_stats, draw_ticker, draw_legend
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
    toggle_legend = False
    ticker_scroll = 0
    copy_rng = False

    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
            running = False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_l:
            toggle_legend = True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
            pygame.display.toggle_fullscreen()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if render.RNG_CELL_RECT is not None and render.RNG_CELL_RECT.collidepoint(event.pos):
                copy_rng = True
        if event.type == pygame.MOUSEWHEEL:
            mouse_sx, mouse_sy = pygame.mouse.get_pos()
            # Over the event readout, the wheel scrolls the log; anywhere else it zooms.
            if render.TICKER_PANEL_RECT is not None and render.TICKER_PANEL_RECT.collidepoint((mouse_sx, mouse_sy)):
                ticker_scroll += event.y
                continue
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
            toggle_legend, ticker_scroll, copy_rng)


def run_simulation(screen, font, state):
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
        show_legend = False
        ticker = []  # [text, age, count] event lines, newest last (UI_TICKER_HISTORY kept for scrollback)
        ticker_offset = 0  # 0 = live feed; >0 = scrolled that many entries back
        rng_number = None
        rng_flash = 0.0  # copied-to-clipboard flash on the RNG cell, 1 → 0

        while running:
            current_time = pygame.time.get_ticks()
            delta_time = (current_time - last_frame_time) / 1000.0
            delta_time = min(delta_time, MAX_DELTA_TIME)
            last_frame_time = current_time

            (running, target_zoom, target_center_x, target_center_y,
             toggle_legend, ticker_scroll, copy_rng) = handle_input(
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
            if toggle_legend:
                show_legend = not show_legend
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
            # Expired entries are kept (up to UI_TICKER_HISTORY) so the wheel can scroll back.
            appended = 0
            for universe in state.universes:
                for text in universe.event_log:
                    if ticker and ticker[-1][0] == text and ticker[-1][1] < 1.0:
                        ticker[-1][2] += 1
                    else:
                        ticker.append([text, 0.0, 1])
                        appended += 1
                universe.event_log.clear()
            for entry in ticker:
                entry[1] += delta_time
            trimmed = max(0, len(ticker) - UI_TICKER_HISTORY)
            ticker = ticker[-UI_TICKER_HISTORY:]
            if ticker_offset > 0:
                # Keep the same entries in view while reading history (terminal-scrollback
                # style): new arrivals push the anchor back, trims from the front pull it in.
                ticker_offset += appended - trimmed
            ticker_offset = max(0, min(ticker_offset + ticker_scroll,
                                       max(0, len(ticker) - UI_TICKER_MAX_LINES)))
            rng_flash = max(0.0, rng_flash - 2.0 * delta_time)

            # Fold this frame's trajectory into the entropy pool: OS timing jitter plus
            # chaotic observables (full state every FULL_FOLD_INTERVAL frames).
            state.entropy_pool.fold_frame(state, current_time, clock.get_rawtime())

            # Heat death of the whole multiverse: every universe is gone. Start fresh.
            if not state.universes or state.entity_count() == 0 or state.total_mass() <= 0:
                heat_death_timer += delta_time
                if heat_death_timer >= HEAT_DEATH_LINGER_DURATION:
                    print(f"Reset at year {current_year}")
                    entropy_pool = state.entropy_pool
                    entropy_pool.fold(b'heat-death-reset')
                    state = physics.initialize_state()
                    state.entropy_pool = entropy_pool  # the pool remembers past universes
                    current_year = 0.0
                    zoom = target_zoom = 1.0
                    view_center_x = target_center_x = SCREEN_WIDTH / 2.0
                    view_center_y = target_center_y = SCREEN_HEIGHT / 2.0
                    heat_death_timer = 0.0
            else:
                heat_death_timer = 0.0

            renderer.render(screen, state, zoom, view_center_x, view_center_y)

            # Fresh RNG output every frame, drawn from the running entropy pool
            # (which folds the live state continuously — no full re-serialize here).
            try:
                rng_number = generate(state.entropy_pool, RNG_MIN, RNG_MAX)['random_number']
            except Exception as rng_err:
                print(f"HUD RNG failed: {rng_err}")
                rng_number = None

            draw_ticker(screen, ticker, ticker_offset)
            draw_stats(screen, clock.get_fps(), current_year, len(state.universes),
                       state.entity_count(), state.entropy_pool.folds, rng_number,
                       state.mean_metallicity(), rng_flash)
            if show_legend:
                draw_legend(screen)

            #draw_ui(screen, font, current_year, zoom)

            current_year += delta_time * YEAR_RATE

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
    font = pygame.font.SysFont('Monospace', 14)
    print("Populating space with molecular clouds")
    state = physics.initialize_state()

    print("Starting simulation")
    run_simulation(screen, font, state)


if __name__ == "__main__":
    main()

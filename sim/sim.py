"""Simcraft main loop: input, timing, heat death, screenshots. All physics lives in
sim.physics (stepping), sim.entities / sim.barrier / sim.fields (state), sim.gravity
(cloud gravity backends); all drawing in sim.render.
"""
import os
import pygame

from sim.config import *
from sim import physics
from sim.render import WorldRenderer, draw_ui, draw_stats
from sim.rng import generate, MIN as RNG_MIN, MAX as RNG_MAX


def screen_to_world(screen_x, screen_y, zoom, view_center_x, view_center_y):
    view_w = SCREEN_WIDTH / zoom
    view_h = SCREEN_HEIGHT / zoom
    view_left = view_center_x - view_w / 2
    view_top = view_center_y - view_h / 2
    world_x = view_left + screen_x / zoom
    world_y = view_top + screen_y / zoom
    return world_x, world_y


def handle_input(zoom, view_center_x, view_center_y):
    running = True
    take_screenshot = False

    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
            running = False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            take_screenshot = True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
            pygame.display.toggle_fullscreen()
        if event.type == pygame.MOUSEWHEEL:
            mouse_sx, mouse_sy = pygame.mouse.get_pos()
            world_x, world_y = screen_to_world(mouse_sx, mouse_sy, zoom, view_center_x, view_center_y)
            old_zoom = zoom
            zoom += event.y * ZOOM_STEP
            zoom = max(ZOOM_MIN, min(ZOOM_MAX, zoom))
            if zoom != old_zoom:
                if zoom <= 1.0:
                    view_center_x = SCREEN_WIDTH / 2.0
                    view_center_y = SCREEN_HEIGHT / 2.0
                else:
                    view_center_x = world_x - (mouse_sx - SCREEN_WIDTH / 2) / zoom
                    view_center_y = world_y - (mouse_sy - SCREEN_HEIGHT / 2) / zoom

    return running, zoom, view_center_x, view_center_y, take_screenshot


def _save_screenshot(screen, state):
    try:
        state.entropy_pool.fold_state(state)
        result = generate(state.entropy_pool, RNG_MIN, RNG_MAX)
        rng_number = result['random_number']
    except Exception:
        rng_number = None

    # Crop to centered square using window height
    crop_size = SCREEN_HEIGHT
    crop_x = (SCREEN_WIDTH - crop_size) // 2
    crop_rect = pygame.Rect(crop_x, 0, crop_size, crop_size)
    shot = screen.subsurface(crop_rect).copy()

    # Full-width white bar at bottom with centered number
    label = str(rng_number) if rng_number is not None else "RNG ERROR"
    shot_font = pygame.font.SysFont('notosansmono', 80, bold=True)
    text_surf = shot_font.render(label, True, (0, 0, 0))
    padding = 8
    box_h = text_surf.get_height() + padding * 2
    box_y = crop_size - box_h
    pygame.draw.rect(shot, (255, 255, 255), (0, box_y, crop_size, box_h))
    text_x = (crop_size - text_surf.get_width()) // 2
    shot.blit(text_surf, (text_x, box_y + padding))

    mnemonic_dir = os.path.join(os.path.dirname(__file__), 'mnemonic')
    filename = os.path.join(mnemonic_dir, f"{rng_number}.png")
    pygame.image.save(shot, filename)
    print(f"Screenshot saved: {rng_number}")


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
        renderer = WorldRenderer()

        while running:
            current_time = pygame.time.get_ticks()
            delta_time = (current_time - last_frame_time) / 1000.0
            delta_time = min(delta_time, MAX_DELTA_TIME)
            last_frame_time = current_time

            running, zoom, view_center_x, view_center_y, take_screenshot = handle_input(
                zoom, view_center_x, view_center_y
            )
            if not running:
                break

            for universe in state.universes:
                universe.barrier.update_deformation(universe, delta_time)
                physics.step(universe, universe.barrier, delta_time)

            # Each black-hole birth this step opens a new universe (capped) outside the existing ones.
            physics.process_universe_spawns(state)
            physics.enforce_total_cloud_cap(state)

            # Keep universes from overlapping (larger shoves smaller aside).
            physics.resolve_barrier_overlaps(state, delta_time)

            # A universe that runs out of matter is removed, freeing a slot for a future spawn.
            # The last surviving universe is kept so heat death can linger/reset as before.
            if len(state.universes) > 1:
                state.universes = [u for u in state.universes if physics._universe_alive(u)]
            physics.prune_child_links(state)

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
                    zoom = 1.0
                    view_center_x = SCREEN_WIDTH / 2.0
                    view_center_y = SCREEN_HEIGHT / 2.0
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

            draw_stats(screen, clock.get_fps(), current_year, len(state.universes),
                       state.entity_count(), state.entropy_pool.folds, rng_number)

            #draw_ui(screen, font, current_year, zoom)

            current_year += delta_time * YEAR_RATE

            pygame.display.flip()
            clock.tick(TARGET_FPS)

            if take_screenshot:
                _save_screenshot(screen, state)

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
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    font = pygame.font.SysFont('Monospace', 14)
    print("Populating space with molecular clouds")
    state = physics.initialize_state()

    print("Starting simulation")
    run_simulation(screen, font, state)


if __name__ == "__main__":
    main()

import sys
import types
import unittest

# Create minimal pygame stub
class DummySurface:
    def __init__(self, size, flags=0):
        self.size = size
    def blit(self, source, pos):
        pass

class DummyFont:
    def render(self, *args, **kwargs):
        return DummySurface((10, 10))

def SysFont(name, size):
    return DummyFont()

class DummyRect:
    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.width = w
        self.height = h
    def inflate(self, dx, dy):
        return DummyRect(self.x, self.y, self.width + dx, self.height + dy)
    def collidepoint(self, x, y):
        return False

pygame_stub = types.SimpleNamespace(
    Surface=DummySurface,
    Rect=DummyRect,
    SRCALPHA=0,
    init=lambda: None,
    display=types.SimpleNamespace(set_caption=lambda *a, **k: None,
                                  set_mode=lambda *a, **k: DummySurface((10,10))),
    font=types.SimpleNamespace(SysFont=SysFont),
    draw=types.SimpleNamespace(circle=lambda *a, **k: None,
                               rect=lambda *a, **k: None),
)

sys.modules['pygame'] = pygame_stub

# Stub out matplotlib modules used in sim
matplotlib_stub = types.ModuleType('matplotlib')
pyplot_stub = types.ModuleType('matplotlib.pyplot')
backend_stub = types.ModuleType('matplotlib.backends')
agg_stub = types.ModuleType('matplotlib.backends.backend_agg')
matplotlib_stub.pyplot = pyplot_stub
backend_stub.backend_agg = agg_stub
sys.modules['matplotlib'] = matplotlib_stub
sys.modules['matplotlib.pyplot'] = pyplot_stub
sys.modules['matplotlib.backends'] = backend_stub
sys.modules['matplotlib.backends.backend_agg'] = agg_stub

import os
os.environ.setdefault('SIMCRAFT_DATA', '.')

from sim.sim import NEUTRON_STAR

class TestNeutronStarDraw(unittest.TestCase):
    def test_draw_neutron_star(self):
        pygame_stub.init()
        surface = pygame_stub.Surface((10, 10))
        ns = NEUTRON_STAR(5, 5, 1.0)
        self.assertTrue(hasattr(ns, 'draw_neutron_star'))
        self.assertFalse(hasattr(ns, 'draw_neotron_star'))
        ns.draw_neutron_star(surface)
        self.assertIsInstance(surface, DummySurface)

if __name__ == '__main__':
    unittest.main()

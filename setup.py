from setuptools import setup, find_packages, Extension
from os import path

from Cython.Build import cythonize  # build requirement, declared in pyproject.toml
import numpy

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='Simcraft',
    version='1.0.0',
    description='A 2D zero-player game/universe simulator',
    long_description=long_description,
    license='GPL 2.0',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3.12',
    ],
    keywords='game, simulation, space',
    packages=find_packages(exclude=[]),

    # The compiled hot loops (collide + Barnes-Hut + shock mergers). Without this the
    # installed package silently fell back to the pure-Python collision loops — the
    # single biggest frame cost at multiverse scale.
    ext_modules=cythonize(
        [Extension("sim.fastphysics", ["sim/fastphysics.pyx"],
                   include_dirs=[numpy.get_include()])],
        compiler_directives={"language_level": "3"},
    ),

    install_requires=[
        'pygame',
        'numpy',
        'taichi',      # GPU gravity backend (sim falls back to CPU without a GPU)
        'cython',      # rebuilding sim/fastphysics in a working tree (install builds it via ext_modules)
        'pandas',      # rng.py batch mode
        'matplotlib',  # rng.py randomness plots
    ],

    entry_points={
       'console_scripts': [
           'simcraft = sim.sim:main',
           'rng = sim.rng:main'
       ],
    },
)

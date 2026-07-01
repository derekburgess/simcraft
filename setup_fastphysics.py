"""Build the compiled hot-physics extension:  python setup_fastphysics.py build_ext --inplace"""
from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy

setup(
    name="simcraft-fastphysics",
    ext_modules=cythonize(
        [Extension("sim.fastphysics", ["sim/fastphysics.pyx"])],
        compiler_directives={"language_level": "3"},
    ),
    include_dirs=[numpy.get_include()],
)

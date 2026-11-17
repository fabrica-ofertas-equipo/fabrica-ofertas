"""Pruebas del ranking reproducible de mercados. Ejecutar: .venv/bin/python -m unittest tests.mercados"""
import os
import unittest


def load_tests(loader, standard_tests, pattern):
    aqui = os.path.dirname(os.path.abspath(__file__))
    top = os.path.dirname(os.path.dirname(aqui))
    return loader.discover(aqui, pattern="test_*.py", top_level_dir=top)

"""Simulation module for IndexPilot testing and benchmarking

This module contains all simulation-related code that is not needed in production.
Simulation code can be safely removed for production deployments.

Modules:
    - simulator: Main simulation harness
    - stock_simulator: Stock market data simulation
    - simulation_verification: Feature verification during simulation
    - simulation_enhancements: Enhanced simulation patterns
    - advanced_simulation: Advanced patterns (e-commerce, analytics, chaos)
"""

from . import (
    advanced_simulation,
    simulation_enhancements,
    simulation_verification,
    simulator,
    stock_simulator,
)

# Explicitly expose modules for __all__
simulator_module = simulator
stock_simulator_module = stock_simulator
simulation_verification_module = simulation_verification
simulation_enhancements_module = simulation_enhancements
advanced_simulation_module = advanced_simulation

__all__ = [
    "simulator",
    "stock_simulator",
    "simulation_verification",
    "simulation_enhancements",
    "advanced_simulation",
]

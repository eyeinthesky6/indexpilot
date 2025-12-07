"""Academic algorithm implementations for IndexPilot

This package contains implementations of academic algorithms for database optimization.
Each algorithm is in its own module for better organization and testability.

Algorithms:
- CERT: Cardinality Estimation Restriction Testing (arXiv:2306.00355)
- QPG: Query Plan Guidance (arXiv:2312.17510) - TODO
- Cortex: Data Correlation Exploitation (arXiv:2012.06683) - TODO
- Predictive Indexing (arXiv:1901.07064) - TODO
- XGBoost Pattern Classification (arXiv:1603.02754) - TODO
"""

from src.algorithms.cert import validate_cardinality_with_cert

__all__ = ["validate_cardinality_with_cert"]



import pytest
from unittest.mock import MagicMock, patch
from src.algorithms.cert import validate_cardinality_with_cert
from src.algorithms.qpg import identify_bottlenecks, identify_logic_bugs, analyze_plan_diversity
from src.algorithms.cortex import calculate_correlation
from src.algorithms.predictive_indexing import predict_index_utility, refine_heuristic_decision
from src.algorithms.pgm_index import analyze_pgm_index_suitability
from src.algorithms.constraint_optimizer import ConstraintIndexOptimizer

@pytest.fixture
def mock_validation():
    with patch('src.validation.validate_table_name', side_effect=lambda x: x) as m1, \
         patch('src.validation.validate_field_name', side_effect=lambda x, y: x) as m2:
        yield m1, m2

@pytest.fixture
def mock_get_cursor(mock_cursor):
    with patch('src.algorithms.cert.get_cursor', return_value=MagicMock(__enter__=lambda x: mock_cursor)) as m:
        yield m

@pytest.fixture
def mock_cursor():
    cursor = MagicMock()
    return cursor

class TestCERT:
    """Audit tests for CERT algorithm math and logic"""
    
    def test_cert_validation_logic(self, mock_get_cursor, mock_cursor, mock_validation):
        # Scenario 1: Accurate estimate
        # Total rows: 1000, Distinct: 100 -> Actual Selectivity: 0.1
        # Estimated: 0.1
        mock_cursor.fetchone.side_effect = [
            {"total_rows": 1000},       # First query: COUNT(*)
            {"distinct_count": 100}     # Second query: COUNT(DISTINCT)
        ]
        
        result = validate_cardinality_with_cert("table", "field", 0.1)
        
        assert result["is_valid"] is True
        assert result["actual_selectivity"] == 0.1
        assert result["error_pct"] == 0.0
        assert result["confidence"] == 1.0

    def test_cert_stale_statistics(self, mock_get_cursor, mock_cursor, mock_validation):
        # Scenario 2: Stale statistics (Large error)
        # Total rows: 1000, Distinct: 500 -> Actual Selectivity: 0.5
        # Estimated: 0.1
        # Error: |0.5 - 0.1| / 0.1 * 100 = 400%
        mock_cursor.fetchone.side_effect = [
            {"total_rows": 1000},
            {"distinct_count": 500}
        ]
        
        result = validate_cardinality_with_cert("table", "field", 0.1)
        
        assert result["is_valid"] is False
        assert result["actual_selectivity"] == 0.5
        assert result["error_pct"] == 400.0
        assert result["statistics_stale"] is True
        # Confidence should be low
        assert result["confidence"] < 0.5

    def test_cert_empty_table(self, mock_get_cursor, mock_cursor, mock_validation):
        # Scenario 3: Empty table
        mock_cursor.fetchone.side_effect = [
            {"total_rows": 0}
        ]
        
        result = validate_cardinality_with_cert("table", "field", 0.1)
        
        assert result["is_valid"] is False
        assert result["reason"] == "empty_table"

class TestQPG:
    """Audit tests for QPG algorithm math and logic"""

    def test_identify_bottlenecks_high_cost_per_row(self):
        # Node with high cost per row
        # Cost: 1000, Rows: 5 -> Cost/Row: 200
        plan_node = {
            "Node Type": "Seq Scan",
            "Total Cost": 1000,
            "Actual Rows": 5,
            "Actual Total Time": 10
        }
        
        bottlenecks = identify_bottlenecks(plan_node)
        
        assert len(bottlenecks) == 1
        assert bottlenecks[0]["type"] == "expensive_node"
        assert bottlenecks[0]["cost_per_row"] == 200.0
        assert bottlenecks[0]["severity"] == "medium" # 200 > 100 but < 1000

    def test_identify_logic_bugs_statistics_mismatch(self):
        # Mismatch between planned and actual rows
        # Planned: 1000, Actual: 10
        # Discrepancy: |1000 - 10| / 1000 = 0.99
        plan_node = {
            "Node Type": "Seq Scan",
            "Plan Rows": 1000,
            "Actual Rows": 10
        }
        
        bugs = identify_logic_bugs(plan_node)
        
        assert len(bugs) == 1
        assert bugs[0]["type"] == "statistics_mismatch"
        assert bugs[0]["discrepancy_ratio"] == 0.99
        assert bugs[0]["severity"] == "medium" # 0.99 > 0.5 but < 2.0

    def test_analyze_plan_diversity_math(self):
        # Base cost: 100
        # Alt 1: 50
        # Alt 2: 200
        # Min: 50, Max: 200
        # Diversity: (200 - 50) / 200 = 0.75
        # Improvement: (100 - 50) / 100 * 100 = 50.0%
        
        base_plan = {"Total Cost": 100, "Node Type": "Seq Scan"}
        alternative_plans = [
            {"Total Cost": 50, "Node Type": "Index Scan"},
            {"Total Cost": 200, "Node Type": "Seq Scan"}
        ]
        
        result = analyze_plan_diversity(base_plan, alternative_plans)
        
        assert result["diversity_score"] == 0.75
        assert result["best_plan_cost"] == 50
        assert result["worst_plan_cost"] == 200
        assert result["potential_improvement"] == 50.0
        assert result["base_plan_is_optimal"] is False

class TestCortex:
    """Audit tests for Cortex algorithm math and logic"""
    
    @patch("src.algorithms.cortex.SCIPY_AVAILABLE", False)
    @patch("src.algorithms.cortex.SKLEARN_AVAILABLE", False)
    def test_calculate_correlation_fallback(self, mock_validation):
        # Test fallback logic: 1.0 - (unique_pairs / total_samples)
        # Col1: [1, 1, 2, 2]
        # Col2: [10, 10, 20, 20]
        # Pairs: (1,10), (1,10), (2,20), (2,20)
        # Unique: 2
        # Total: 4
        # Score: 1.0 - 0.5 = 0.5
        
        with patch('src.algorithms.cortex.get_cursor') as mock_get_cursor_ctx:
            mock_cursor = MagicMock()
            mock_get_cursor_ctx.return_value.__enter__.return_value = mock_cursor
            
            mock_cursor.fetchall.return_value = [
                {"col1": 1, "col2": 10},
                {"col1": 1, "col2": 10},
                {"col1": 2, "col2": 20},
                {"col1": 2, "col2": 20},
            ]
            
            # Need at least 10 samples normally, but we can verify logic if we bypass that check
            # or mock a larger dataset with same ratio.
            # Let's mock 20 samples with 10 unique pairs -> ratio 0.5 -> score 0.5
            
            samples = []
            for i in range(10):
                samples.append({"col1": i, "col2": i*10})
                samples.append({"col1": i, "col2": i*10})
            # 20 samples, 10 unique pairs.
            
            mock_cursor.fetchall.return_value = samples
            
            result = calculate_correlation("table", "col1", "col2")
            
            assert result is not None
            assert result["method"] == "co_occurrence"
            assert result["correlation_score"] == 0.5

class TestPredictiveIndexing:
    """Audit tests for Predictive Indexing algorithm math and logic"""
    
    @patch("src.algorithms.predictive_indexing.SKLEARN_AVAILABLE", False)
    @patch("src.algorithms.predictive_indexing.get_predictive_indexing_config")
    def test_predict_from_patterns_math(self, mock_config, mock_validation):
        # Disable ML and Historical to force pattern-based
        mock_config.return_value = {
            "enabled": True,
            "use_ml_model": False,
            "use_historical_data": False,
            "weight": 0.3
        }
        
        # Scenario:
        # Cost Benefit: 2.0 -> Score 1.0 (weight 0.35) -> 0.35
        # Queries: 5000 -> Score 1.0 (weight 0.25) -> 0.25
        # Selectivity: 0.05 -> Score 0.9 (weight 0.20) -> 0.18
        # Row Count: 20000 -> Score 1.0 (weight 0.10) -> 0.10
        # Overhead: 0 -> Score 1.0 (weight 0.10) -> 0.10
        # Total: 0.98
        
        result = predict_index_utility(
            table_name="table",
            field_name="field",
            estimated_build_cost=100.0,
            queries_over_horizon=5000.0,
            extra_cost_per_query_without_index=0.04, # Total cost = 5000 * 0.04 = 200. Ratio = 200/100 = 2.0
            table_size_info={"row_count": 20000, "index_overhead_percent": 0.0},
            field_selectivity=0.05
        )
        
        assert result["method"] == "pattern_based"
        assert abs(result["utility_score"] - 0.98) < 0.001

    @patch("src.algorithms.predictive_indexing.get_predictive_indexing_config")
    def test_refine_heuristic_decision(self, mock_config):
        mock_config.return_value = {
            "enabled": True,
            "weight": 0.3 # ML weight
        }
        
        # Heuristic: True (1.0), Confidence: 0.8
        # ML: Score 0.2, Confidence: 0.9
        
        # Combined Score: (1.0 * 0.7) + (0.2 * 0.3) = 0.7 + 0.06 = 0.76
        # Refined Decision: True (0.76 > 0.5)
        # Refined Confidence: (0.8 * 0.7) + (0.9 * 0.3) = 0.56 + 0.27 = 0.83
        
        utility_prediction = {
            "utility_score": 0.2,
            "confidence": 0.9,
            "method": "pattern_based"
        }
        
        decision, confidence, reason = refine_heuristic_decision(
            heuristic_decision=True,
            heuristic_confidence=0.8,
            utility_prediction=utility_prediction
        )
        
        assert decision is True
        assert abs(confidence - 0.83) < 0.001

class TestPGMIndex:
    """Audit tests for PGM-Index suitability math"""
    
    @patch("src.algorithms.pgm_index.get_table_size_info")
    @patch("src.algorithms.pgm_index._get_field_distribution")
    def test_analyze_pgm_index_suitability_math(self, mock_dist, mock_size, mock_validation):
        # Scenario:
        # Table size: 150K -> 0.25
        # Read/Write: 8.0 -> 0.2 (>=5)
        # Query Pattern: range -> 0.2
        # Distribution: sequential -> 0.15
        # Total: 0.8
        
        mock_size.return_value = {"row_count": 150000}
        mock_dist.return_value = {"distribution_type": "sequential", "is_ordered": False}
        
        result = analyze_pgm_index_suitability(
            table_name="table",
            field_name="field",
            query_patterns={"has_range": True},
            read_write_ratio=8.0
        )
        
        assert result["is_suitable"] is True
        assert abs(result["suitability_score"] - 0.8) < 0.001

class TestConstraintOptimizer:
    """Audit tests for Constraint Optimizer math"""
    
    @patch("src.algorithms.constraint_optimizer._config_loader")
    def test_check_performance_constraints_math(self, mock_loader):
        # Mock config values
        mock_loader.get_float.side_effect = lambda key, default: {
            "features.constraint_optimization.performance.max_query_time_ms": 100.0,
            "features.constraint_optimization.performance.min_improvement_pct": 20.0
        }.get(key, default)
        
        optimizer = ConstraintIndexOptimizer()
        
        # Improvement: 50.0% -> Score 0.5
        # Time: 20ms / 100ms = 0.2 -> Score 1.0 - 0.2 = 0.8
        # Constraint Score: (0.5 + 0.8) / 2 = 0.65
        
        satisfies, reason, score = optimizer.check_performance_constraints(
            estimated_query_time_ms=20.0,
            improvement_pct=50.0
        )
        
        assert satisfies is True
        assert reason == "performance_constraint_satisfied"
        assert abs(score - 0.65) < 0.001


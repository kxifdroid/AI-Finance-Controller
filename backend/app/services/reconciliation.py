"""
Reconciliation Service re-export module for backward compatibility.

Exports all reconciliation components from the app.services.reconciliation package.
"""

from app.services.reconciliation.evidence import EvidenceBuilder
from app.services.reconciliation.fee_calculator import FeeCalculator
from app.services.reconciliation.exact_matcher import ExactMatcher, can_auto_clear
from app.services.reconciliation.settlement_matcher import SettlementMatcher
from app.services.reconciliation.duplicate_detector import DuplicateDetector
from app.services.reconciliation.engine import ReconciliationEngine

# Alias for backward compatibility
ReconciliationService = ReconciliationEngine

__all__ = [
    "ReconciliationEngine",
    "ReconciliationService",
    "ExactMatcher",
    "SettlementMatcher",
    "FeeCalculator",
    "EvidenceBuilder",
    "DuplicateDetector",
    "can_auto_clear",
]

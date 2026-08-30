"""
Reconciliation Services Package.

Exports core reconciliation components:
- ReconciliationEngine: Main multi-source reconciliation pipeline orchestrator
- ExactMatcher: Layer 1 exact matching across normalized reference, amount, and date
- SettlementMatcher: Many-to-one batch settlement matching for gateway payouts
- FeeCalculator: Gateway MDR, GST, and net settlement calculation and validation
- EvidenceBuilder: Structured JSON audit evidence chain generator
- DuplicateDetector: Internal collision and duplicate entry scanner
- can_auto_clear: Control gate for auto-clearing matches based on confidence and materiality
- ReconciliationService: Alias for ReconciliationEngine for backward compatibility
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

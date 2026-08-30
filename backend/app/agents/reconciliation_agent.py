"""
AI Reconciliation Agent.

Problem Solved:
Analyzes complex, ambiguous candidate match cases that fall into the indeterminate
threshold window (0.70 <= score < 0.90) or contain non-obvious entity name/reference
divergence, returning structured financial reasoning.

Why It Exists:
To bridge the gap between pure deterministic exact matching and human audit oversight
by applying semantic reasoning without violating strict schema safety.

Input:
Candidate record details (Bank, Gateway, Invoice) and computed deterministic features.

Output:
Strictly validated decision: MATCH | REVIEW | EXCEPTION | DUPLICATE | MISSING,
accompanied by confidence, risk level, explanation, and recommended action.

Safety Guarantees:
1. If LLM call fails or times out, gracefully returns an escalated REVIEW status
   without interrupting pipeline execution.
2. Circuit breaker prevents wasting minutes on sequential failing HTTP calls.
3. API keys are never logged in error messages.
"""

import json
import logging
from typing import Dict, Any, Optional
from app.agents.llm_provider import (
    get_llm_client,
    BaseLLMClient,
    get_circuit_breaker,
    _redact_key,
)
from app.agents.prompts import (
    RECONCILIATION_SYSTEM_PROMPT,
    RECONCILIATION_USER_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)

# AI Verification Status enum values
AI_STATUS_VERIFIED = "VERIFIED"           # AI successfully verified the candidate
AI_STATUS_REVIEW_FALLBACK = "REVIEW_FALLBACK"  # AI failed, fell back to REVIEW
AI_STATUS_CIRCUIT_OPEN = "CIRCUIT_OPEN"   # Circuit breaker skipped AI call
AI_STATUS_NOT_REQUIRED = "NOT_REQUIRED"   # Score was outside AI verification range


class AIReconciliationAgent:
    """
    Agent responsible for AI-assisted verification of ambiguous reconciliation candidates.
    """

    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        self.llm_client = llm_client or get_llm_client()

    async def verify_candidate(
        self,
        bank_record: Optional[Dict[str, Any]],
        gateway_record: Optional[Dict[str, Any]],
        invoice_record: Optional[Dict[str, Any]],
        matching_features: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Submits candidate details to the LLM and validates structured response.
        
        Returns a dict with:
        - decision: MATCH | REVIEW | EXCEPTION | DUPLICATE | MISSING
        - confidence: float [0.0, 1.0]
        - risk_level: LOW | MEDIUM | HIGH
        - reason: str
        - recommended_action: str
        - verified_by_ai: bool
        - ai_verification_status: VERIFIED | REVIEW_FALLBACK | CIRCUIT_OPEN
        - raw_response: Optional[str]
        """
        # Check circuit breaker before making network call
        circuit = get_circuit_breaker()
        if circuit.should_skip():
            return {
                "decision": "REVIEW",
                "confidence": 0.70,
                "risk_level": "MEDIUM",
                "reason": "AI verification skipped — circuit breaker open due to repeated provider failures.",
                "recommended_action": "Manually verify transaction records.",
                "verified_by_ai": False,
                "ai_verification_status": AI_STATUS_CIRCUIT_OPEN,
                "raw_response": None,
            }

        user_prompt = RECONCILIATION_USER_PROMPT_TEMPLATE.format(
            bank_json=json.dumps(bank_record, default=str, indent=2) if bank_record else "None (Record Missing)",
            gateway_json=json.dumps(gateway_record, default=str, indent=2) if gateway_record else "None (Record Missing)",
            invoice_json=json.dumps(invoice_record, default=str, indent=2) if invoice_record else "None (Record Missing)",
            features_json=json.dumps(matching_features, default=str, indent=2),
        )

        try:
            logger.debug("AI verification started for candidate.")
            result = await self.llm_client.generate_structured_json(
                system_prompt=RECONCILIATION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )

            # Validate and sanitize response fields
            decision = str(result.get("decision", "REVIEW")).upper().strip()
            if decision not in ("MATCH", "REVIEW", "EXCEPTION", "DUPLICATE", "MISSING"):
                decision = "REVIEW"

            confidence = float(result.get("confidence", 0.75))
            confidence = max(0.0, min(1.0, confidence))

            risk_level = str(result.get("risk_level", "LOW")).upper().strip()
            if risk_level not in ("LOW", "MEDIUM", "HIGH"):
                risk_level = "MEDIUM"

            reason = str(result.get("reason", "AI verified candidate relationship."))
            recommended_action = str(result.get("recommended_action", "Proceed with reconciliation."))

            # Record success on circuit breaker
            circuit.record_success()
            logger.debug(f"AI verification completed: decision={decision}, confidence={confidence}")

            return {
                "decision": decision,
                "confidence": round(confidence, 4),
                "risk_level": risk_level,
                "reason": reason,
                "recommended_action": recommended_action,
                "verified_by_ai": True,
                "ai_verification_status": AI_STATUS_VERIFIED,
                "raw_response": json.dumps(result),
            }

        except Exception as exc:
            # Record failure on circuit breaker
            circuit.record_failure()
            safe_error = _redact_key(str(exc)[:120])
            logger.error(f"AI verification failed: {safe_error}. Falling back to REVIEW.")
            return {
                "decision": "REVIEW",
                "confidence": 0.70,
                "risk_level": "MEDIUM",
                "reason": f"AI verification service unavailable ({safe_error}). Escrowed for human operator review.",
                "recommended_action": "Manually verify transaction records.",
                "verified_by_ai": False,
                "ai_verification_status": AI_STATUS_REVIEW_FALLBACK,
                "raw_response": None,
            }

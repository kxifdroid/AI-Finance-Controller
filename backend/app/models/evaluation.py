"""
Evaluation result model for ground-truth benchmark metrics.
"""

from datetime import datetime
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class EvaluationResult(Base):
    """
    Stores calculated accuracy, precision, recall, and error rates against ground truth.
    Strictly generated after reconciliation completes without leaking during inference.
    """
    __tablename__ = "evaluation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("reconciliation_runs.run_id"), nullable=False, index=True)
    
    total_ground_truth_records: Mapped[int] = mapped_column(Integer, default=0)
    
    # Classification metrics
    accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    precision: Mapped[float] = mapped_column(Float, default=0.0)
    recall: Mapped[float] = mapped_column(Float, default=0.0)
    f1_score: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Confusion matrix
    true_positives: Mapped[int] = mapped_column(Integer, default=0)
    false_positives: Mapped[int] = mapped_column(Integer, default=0)
    false_negatives: Mapped[int] = mapped_column(Integer, default=0)
    true_negatives: Mapped[int] = mapped_column(Integer, default=0)
    
    # Rates
    false_positive_rate: Mapped[float] = mapped_column(Float, default=0.0)
    false_negative_rate: Mapped[float] = mapped_column(Float, default=0.0)
    exception_accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    run: Mapped["ReconciliationRun"] = relationship("ReconciliationRun", back_populates="evaluations")

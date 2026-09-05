from decimal import Decimal

from pydantic import BaseModel


class TermCollectionPoint(BaseModel):
    term_id: str
    term_name: str
    total_billed: Decimal
    total_paid: Decimal


class TopRiskInvoice(BaseModel):
    invoice_id: str
    student_id: str
    student_name: str
    class_name: str
    balance: Decimal
    risk_score: float
    risk_level: str


class DashboardAnalyticsResponse(BaseModel):
    total_collected: Decimal
    total_outstanding: Decimal
    overdue_count: int
    active_student_count: int
    collection_by_term: list[TermCollectionPoint]
    top_risk: list[TopRiskInvoice]

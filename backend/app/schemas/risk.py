from pydantic import BaseModel


class RiskFactorsResponse(BaseModel):
    history_score: float
    overdue_score: float
    balance_score: float
    reversal_score: float


class RiskAssessmentResponse(BaseModel):
    score: float
    level: str
    factors: RiskFactorsResponse
    explanation: str

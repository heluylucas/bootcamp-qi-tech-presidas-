from datetime import datetime
from typing import NamedTuple

from sqlalchemy import CHAR, Column, DateTime, Enum, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.orm import relationship

from models.base import Base
from utils.dates import add_months


VALIDITY_MONTHS = 24

InvestorProfile = Enum("CONSERVATIVE", "MODERATE", "AGGRESSIVE", name="investor_profile")


class ProfileRule(NamedTuple):
    minimum_score: int
    maximum_score: int
    maximum_risk_level: int


PROFILE_RULES = {
    "CONSERVATIVE": ProfileRule(minimum_score=7, maximum_score=13, maximum_risk_level=2),
    "MODERATE": ProfileRule(minimum_score=14, maximum_score=20, maximum_risk_level=3),
    "AGGRESSIVE": ProfileRule(minimum_score=21, maximum_score=28, maximum_risk_level=5),
}


def profile_for_score(score: int) -> str:
    return next(
        profile for profile, rule in PROFILE_RULES.items() if rule.minimum_score <= score <= rule.maximum_score
    )


class SuitabilityOption(Base):
    __tablename__ = "suitability_option"

    id = Column(Integer, primary_key=True)
    suitability_question_id = Column(Integer, ForeignKey("suitability_question.id"), nullable=False)
    code = Column(SmallInteger, nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    suitability_question = relationship("SuitabilityQuestion", back_populates="options")


class SuitabilityQuestion(Base):
    __tablename__ = "suitability_question"

    id = Column(Integer, primary_key=True)
    code = Column(String(3), nullable=False, unique=True)
    text = Column(Text, nullable=False)
    dimension = Column(String(30), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    options = relationship(SuitabilityOption, order_by=SuitabilityOption.code, back_populates="suitability_question")


class SuitabilityAssessment(Base):
    __tablename__ = "suitability_assessment"

    id = Column(Integer, primary_key=True)
    assessment_key = Column(CHAR(36), nullable=False, unique=True)
    customer_id = Column(Integer, ForeignKey("customer.id"), nullable=False)
    investor_profile = Column(InvestorProfile, nullable=False)
    score = Column(SmallInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    answers = relationship("SuitabilityAnswer", order_by="SuitabilityAnswer.id")

    @property
    def valid_until(self) -> datetime:
        return add_months(self.created_at, VALIDITY_MONTHS)

    @property
    def forced_by_rule(self) -> bool:
        rule = PROFILE_RULES[self.investor_profile]
        return not rule.minimum_score <= self.score <= rule.maximum_score

    @property
    def maximum_risk_level(self) -> int:
        return PROFILE_RULES[self.investor_profile].maximum_risk_level


class SuitabilityAnswer(Base):
    __tablename__ = "suitability_answer"

    id = Column(Integer, primary_key=True)
    suitability_assessment_id = Column(Integer, ForeignKey("suitability_assessment.id"), nullable=False)
    suitability_option_id = Column(Integer, ForeignKey("suitability_option.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    suitability_option = relationship(SuitabilityOption)

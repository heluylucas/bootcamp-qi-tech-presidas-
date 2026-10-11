from datetime import datetime
from typing import NamedTuple

from sqlalchemy import CHAR, Column, DateTime, Enum, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.orm import relationship

from models.base import Base
from utils.dates import add_months


# Validade do perfil, em meses (RN-SUI-05).
VALIDITY_MONTHS = 24

# Espelho do tipo ENUM do database.sql: o banco recusa qualquer perfil fora da lista.
InvestorProfile = Enum("CONSERVATIVE", "MODERATE", "AGGRESSIVE", name="investor_profile")


class ProfileRule(NamedTuple):
    minimum_score: int
    maximum_score: int
    maximum_risk_level: int


# Regras fixas de cada perfil, como a tarifa: a faixa de pontos (RN-SUI-03) e o risco máximo que aceita.
PROFILE_RULES = {
    "CONSERVATIVE": ProfileRule(minimum_score=7, maximum_score=13, maximum_risk_level=2),
    "MODERATE": ProfileRule(minimum_score=14, maximum_score=20, maximum_risk_level=3),
    "AGGRESSIVE": ProfileRule(minimum_score=21, maximum_score=28, maximum_risk_level=5),
}


def profile_for_score(score: int) -> str:
    """O perfil cuja faixa de pontos contém o score (RN-SUI-03). As faixas cobrem de 7 a 28 sem buraco."""
    return next(
        profile for profile, rule in PROFILE_RULES.items() if rule.minimum_score <= score <= rule.maximum_score
    )


class SuitabilityOption(Base):
    __tablename__ = "suitability_option"

    id = Column(Integer, primary_key=True)
    suitability_question_id = Column(Integer, ForeignKey("suitability_question.id"), nullable=False)
    # O código é também a pontuação: a opção N vale N pontos.
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
    """Uma linha por vez que o cliente responde. Nunca é editada: refazer cria outra (R4)."""

    __tablename__ = "suitability_assessment"

    id = Column(Integer, primary_key=True)
    assessment_key = Column(CHAR(36), nullable=False, unique=True)
    customer_id = Column(Integer, ForeignKey("customer.id"), nullable=False)
    investor_profile = Column(InvestorProfile, nullable=False)
    score = Column(SmallInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    answers = relationship("SuitabilityAnswer", order_by="SuitabilityAnswer.id")

    # Calculados a partir das colunas, não gravados: guardar seria repetir informação.
    @property
    def valid_until(self) -> datetime:
        """O perfil vale 24 meses a partir da resposta (RN-SUI-05)."""
        return add_months(self.created_at, VALIDITY_MONTHS)

    @property
    def forced_by_rule(self) -> bool:
        """A trava da Q3/Q5 forçou Conservador (RN-SUI-04): o perfil gravado não é o da faixa do score."""
        rule = PROFILE_RULES[self.investor_profile]
        return not rule.minimum_score <= self.score <= rule.maximum_score

    @property
    def maximum_risk_level(self) -> int:
        """O risco máximo de produto que o perfil aceita."""
        return PROFILE_RULES[self.investor_profile].maximum_risk_level


class SuitabilityAnswer(Base):
    """A opção escolhida em cada pergunta, para explicar depois por que saiu aquele perfil."""

    __tablename__ = "suitability_answer"

    id = Column(Integer, primary_key=True)
    suitability_assessment_id = Column(Integer, ForeignKey("suitability_assessment.id"), nullable=False)
    suitability_option_id = Column(Integer, ForeignKey("suitability_option.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    suitability_option = relationship(SuitabilityOption)

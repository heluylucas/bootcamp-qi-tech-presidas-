from datetime import datetime

from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.orm import relationship

from models.base import Base
from utils.dates import add_months


# Validade do perfil, em meses (RN-SUI-05).
VALIDITY_MONTHS = 24


class InvestorProfile(Base):
    """Enumerador com dados: cada perfil traz a sua faixa de pontos e o risco máximo que aceita."""

    __tablename__ = "investor_profile"

    id = Column(Integer, primary_key=True)
    code = Column(String(50), nullable=False, unique=True)
    minimum_score = Column(SmallInteger, nullable=False)
    maximum_score = Column(SmallInteger, nullable=False)
    maximum_risk_level = Column(SmallInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


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
    investor_profile_id = Column(Integer, ForeignKey("investor_profile.id"), nullable=False)
    score = Column(SmallInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    investor_profile = relationship(InvestorProfile)
    answers = relationship("SuitabilityAnswer", order_by="SuitabilityAnswer.id")

    # Calculados a partir das colunas, não gravados: guardar seria repetir informação.
    @property
    def valid_until(self) -> datetime:
        """O perfil vale 24 meses a partir da resposta (RN-SUI-05)."""
        return add_months(self.created_at, VALIDITY_MONTHS)

    @property
    def forced_by_rule(self) -> bool:
        """A trava da Q3/Q5 forçou Conservador (RN-SUI-04): o perfil gravado não é o da faixa do score."""
        return not self.investor_profile.minimum_score <= self.score <= self.investor_profile.maximum_score


class SuitabilityAnswer(Base):
    """A opção escolhida em cada pergunta, para explicar depois por que saiu aquele perfil."""

    __tablename__ = "suitability_answer"

    id = Column(Integer, primary_key=True)
    suitability_assessment_id = Column(Integer, ForeignKey("suitability_assessment.id"), nullable=False)
    suitability_option_id = Column(Integer, ForeignKey("suitability_option.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    suitability_option = relationship(SuitabilityOption)

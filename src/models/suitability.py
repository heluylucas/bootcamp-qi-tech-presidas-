from sqlalchemy import Boolean, CHAR, Column, DateTime, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.orm import relationship

from models.base import Base


class InvestorProfile(Base):
    """Enumerador com dados: cada perfil traz a sua faixa de pontos e o risco máximo que aceita."""

    __tablename__ = "investor_profile"

    id = Column(Integer, primary_key=True)
    enumerator = Column(String(50), nullable=False, unique=True)
    min_score = Column(SmallInteger, nullable=False)
    max_score = Column(SmallInteger, nullable=False)
    max_risk_level = Column(SmallInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SuitabilityOption(Base):
    __tablename__ = "suitability_option"

    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("suitability_question.id"), nullable=False)
    code = Column(SmallInteger, nullable=False)
    text = Column(Text, nullable=False)
    # Os pontos nunca saem na API: quem visse os pontos escolheria o perfil.
    points = Column(SmallInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SuitabilityQuestion(Base):
    __tablename__ = "suitability_question"

    id = Column(Integer, primary_key=True)
    code = Column(String(3), nullable=False, unique=True)
    text = Column(Text, nullable=False)
    dimension = Column(String(30), nullable=False)
    position = Column(SmallInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    options = relationship(SuitabilityOption, order_by=SuitabilityOption.code)


class SuitabilityAssessment(Base):
    """Uma linha por vez que o cliente responde. Nunca é editada: refazer cria outra (R4)."""

    __tablename__ = "suitability_assessment"

    id = Column(Integer, primary_key=True)
    assessment_key = Column(CHAR(36), nullable=False, unique=True)
    customer_id = Column(Integer, ForeignKey("customer.id"), nullable=False)
    profile_id = Column(Integer, ForeignKey("investor_profile.id"), nullable=False)
    score = Column(SmallInteger, nullable=False)
    # true quando a trava da Q3/Q5 forçou Conservador (RN-SUI-04).
    forced_by_rule = Column(Boolean, nullable=False, server_default="false")
    # TODO(módulo 4): a RFC da data de movimento muda esta coluna para DATE.
    valid_until = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    profile = relationship(InvestorProfile)
    answers = relationship("SuitabilityAnswer", order_by="SuitabilityAnswer.id")


class SuitabilityAnswer(Base):
    """A opção escolhida em cada pergunta, para explicar depois por que saiu aquele perfil."""

    __tablename__ = "suitability_answer"

    id = Column(Integer, primary_key=True)
    assessment_id = Column(Integer, ForeignKey("suitability_assessment.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("suitability_question.id"), nullable=False)
    option_id = Column(Integer, ForeignKey("suitability_option.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    question = relationship(SuitabilityQuestion)
    option = relationship(SuitabilityOption)

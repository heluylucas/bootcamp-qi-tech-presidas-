import uuid
from typing import List, Optional

from sqlalchemy.orm import selectinload

from database import Context
from models import SuitabilityAnswer, SuitabilityAssessment, SuitabilityQuestion


class SuitabilityRepository:
    @staticmethod
    def list_questions(context: Context) -> List[SuitabilityQuestion]:
        # selectinload: as opções de todas as perguntas vêm numa segunda
        # consulta só, em vez de uma consulta por pergunta.
        return (
            context.db_session.query(SuitabilityQuestion)
            .options(selectinload(SuitabilityQuestion.options))
            .order_by(SuitabilityQuestion.code)
            .all()
        )

    @staticmethod
    def create_assessment(context: Context, customer_id: int, investor_profile: str, score: int) -> SuitabilityAssessment:
        assessment = SuitabilityAssessment(
            assessment_key=str(uuid.uuid4()), customer_id=customer_id, investor_profile=investor_profile, score=score
        )
        context.db_session.add(assessment)
        context.db_session.flush()

        return assessment

    @staticmethod
    def create_answer(context: Context, suitability_assessment_id: int, suitability_option_id: int) -> SuitabilityAnswer:
        answer = SuitabilityAnswer(suitability_assessment_id=suitability_assessment_id, suitability_option_id=suitability_option_id)
        context.db_session.add(answer)
        context.db_session.flush()

        return answer

    @staticmethod
    def get_latest(context: Context, customer_id: int) -> Optional[SuitabilityAssessment]:
        # Pelo id e não pelo created_at: duas respostas no mesmo instante
        # empatariam na hora, mas o id sempre cresce.
        return (
            context.db_session.query(SuitabilityAssessment)
            .filter(SuitabilityAssessment.customer_id == customer_id)
            .order_by(SuitabilityAssessment.id.desc())
            .first()
        )

    @staticmethod
    def list_by_customer(context: Context, customer_id: int) -> List[SuitabilityAssessment]:
        return (
            context.db_session.query(SuitabilityAssessment)
            .filter(SuitabilityAssessment.customer_id == customer_id)
            .order_by(SuitabilityAssessment.id.desc())
            .all()
        )

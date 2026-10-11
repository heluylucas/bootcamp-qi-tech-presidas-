from datetime import datetime, timezone

from controllers.base_controller import BaseController
from dtos.suitability_dto import assessment_to_dict, question_to_dict
from errors import (
    IncompleteAnswers,
    InvalidOption,
    SuitabilityExpired,
    SuitabilityNotFound,
    SuitabilityRequired,
)
from models import SuitabilityAssessment
from models.suitability import profile_for_score
from repositories import SuitabilityRepository


SAFETY_LOCK = {"Q3": 1, "Q5": 1}

SAFE_PROFILE = "CONSERVATIVE"


class SuitabilityController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)

    def list_questions(self) -> dict:
        questions = SuitabilityRepository.list_questions(self.context)
        return {"items": [question_to_dict(question) for question in questions]}

    def submit(self, customer_key: str, payload: dict) -> dict:
        customer = self.get_customer(customer_key)
        questions = {question.code: question for question in SuitabilityRepository.list_questions(self.context)}
        answered_codes = [answer["question_code"] for answer in payload["answers"]]

        if len(answered_codes) != len(set(answered_codes)) or set(answered_codes) != set(questions):
            raise IncompleteAnswers()

        chosen = {}
        for answer in payload["answers"]:
            question = questions[answer["question_code"]]
            option = next((option for option in question.options if option.code == answer["option_code"]), None)

            if option is None:
                raise InvalidOption()

            chosen[question.code] = option

        score = sum(option.code for option in chosen.values())

        lock_triggered = any(chosen[code].code == option_code for code, option_code in SAFETY_LOCK.items())

        profile = SAFE_PROFILE if lock_triggered else profile_for_score(score)

        assessment = SuitabilityRepository.create_assessment(self.context, customer.id, profile, score)

        for code in sorted(chosen):
            SuitabilityRepository.create_answer(self.context, assessment.id, chosen[code].id)

        self.session.commit()
        return assessment_to_dict(assessment)

    def get_current(self, customer_key: str) -> dict:
        customer = self.get_customer(customer_key)
        assessment = SuitabilityRepository.get_latest(self.context, customer.id)

        if assessment is None:
            raise SuitabilityNotFound()

        return assessment_to_dict(assessment)

    def list_history(self, customer_key: str) -> dict:
        customer = self.get_customer(customer_key)
        assessments = SuitabilityRepository.list_by_customer(self.context, customer.id)
        return {"items": [assessment_to_dict(assessment) for assessment in assessments]}

    def get_valid_assessment(self, customer_id: int) -> SuitabilityAssessment:
        assessment = SuitabilityRepository.get_latest(self.context, customer_id)

        if assessment is None:
            raise SuitabilityRequired()

        if self.now() > assessment.valid_until:
            raise SuitabilityExpired()

        return assessment

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

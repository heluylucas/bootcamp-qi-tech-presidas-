from datetime import datetime, timezone

from controllers.base_controller import BaseController
from dtos.suitability_dto import assessment_to_dict, question_to_dict
from errors import (
    CustomerNotFound,
    IncompleteAnswers,
    InvalidOption,
    SuitabilityExpired,
    SuitabilityNotFound,
    SuitabilityRequired,
)
from models import Customer, SuitabilityAssessment
from models.suitability import profile_for_score
from repositories import CustomerRepository, SuitabilityRepository


# A trava de segurança (RN-SUI-04): quem escolhe estas opções é Conservador,
# qualquer que seja a soma. Q3 = "resgataria tudo"; Q5 = "preciso a qualquer momento".
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

        # Exatamente uma resposta por pergunta: nem falta, nem repete, nem
        # pergunta que não existe (RN-SUI-02).
        if len(answered_codes) != len(set(answered_codes)) or set(answered_codes) != set(questions):
            raise IncompleteAnswers()

        chosen = {}
        for answer in payload["answers"]:
            question = questions[answer["question_code"]]
            option = next((option for option in question.options if option.code == answer["option_code"]), None)

            if option is None:
                raise InvalidOption()

            chosen[question.code] = option

        # O código da opção é a sua pontuação (RN-SUI-03).
        score = sum(option.code for option in chosen.values())

        # A trava manda para Conservador, qualquer que seja a soma. Se ela mudou o resultado
        # (perfil fora da faixa do score), a resposta mostra forced_by_rule = true.
        lock_triggered = any(chosen[code].code == option_code for code, option_code in SAFETY_LOCK.items())

        profile = SAFE_PROFILE if lock_triggered else profile_for_score(score)

        assessment = SuitabilityRepository.create_assessment(self.context, customer.id, profile, score)

        # Na ordem do questionário (a do código), e não na ordem em que o cliente mandou.
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
        """O perfil que permite sugerir carteira ou aplicar (RN-SUI-05, RN-CAR-01, RN-ORD-02).

        Nenhuma rota da suitability usa isto: é para a carteira e as ordens.
        """
        assessment = SuitabilityRepository.get_latest(self.context, customer_id)

        if assessment is None:
            raise SuitabilityRequired()

        if self.now() > assessment.valid_until:
            raise SuitabilityExpired()

        return assessment

    def now(self) -> datetime:
        # O relógio real, e não a data de movimento: a validade do perfil é um
        # fato regulatório (RN-SUI-05, RN-GER-13), e a data de movimento pode
        # estar à frente do calendário. Único lugar do módulo que olha o relógio.
        return datetime.now(timezone.utc)

    def get_customer(self, customer_key: str) -> Customer:
        customer = CustomerRepository.get_by_key(self.context, customer_key)

        if customer is None:
            raise CustomerNotFound()

        return customer

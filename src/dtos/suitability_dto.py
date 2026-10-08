from dtos.account_dto import to_utc_text
from models import SuitabilityAssessment, SuitabilityQuestion


def question_to_dict(question: SuitabilityQuestion) -> dict:
    return {
        "code": question.code,
        "text": question.text,
        "dimension": question.dimension,
        # Sem os pontos: quem visse os pontos escolheria o perfil em vez de responder.
        "options": [{"code": option.code, "text": option.text} for option in question.options],
    }


def assessment_to_dict(assessment: SuitabilityAssessment) -> dict:
    return {
        "assessment_key": assessment.assessment_key,
        "profile": assessment.profile.enumerator,
        # Até que risco de produto o perfil aceita (a carteira e as ordens usam).
        "max_risk_level": assessment.profile.max_risk_level,
        "score": assessment.score,
        "forced_by_rule": assessment.forced_by_rule,
        "valid_until": to_utc_text(assessment.valid_until),
        "created_at": to_utc_text(assessment.created_at),
        "answers": [
            {"question_code": answer.option.question.code, "option_code": answer.option.code}
            for answer in assessment.answers
        ],
    }

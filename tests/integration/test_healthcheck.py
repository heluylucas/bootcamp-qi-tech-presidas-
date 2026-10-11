from tests.utils import INTERNAL_TOKEN
from tests.utils.requisition import ClientRequisition


# As frases em português que o cliente lê no campo "translation" das
# respostas de erro. Estão escritas aqui à mão de propósito: o teste
# cobra o contrato pela rede, e importar a constante de src/ faria o
# teste concordar com o código por construção — mudaria a frase lá,
# o teste seguiria verde e ninguém saberia que o cliente passou a ler
# outra coisa.
#
# O que elas defendem é o ACENTO. Até 2026-08-20 o QIException raspava
# todo acento antes de responder ("normalize NFKD" + encode ASCII), e a
# fonte acentuada chegava no cliente sem cedilha nem til. Quem repuser
# aquela linha deixa o teste abaixo vermelho, nomeando o campo.
FORBIDDEN_TRANSLATION = "Requisição precisa ser interna"
NOT_FOUND_TRANSLATION = "O resource solicitado não pode ser encontrado, mas pode estar disponível no futuro. Requests subsequentes do cliente são permitidos."


class TestHealthCheck:
    def test_home(self):
        response = ClientRequisition.send("GET", "/")
        assert response.response_status == 200

    def test_health_check(self):
        response = ClientRequisition.send("GET", "/health_check")
        assert response.response_status == 204

    def test_no_token_keeps_accents(self):
        # O 403 nasce DENTRO do middleware de token, antes da rota.
        response = ClientRequisition.send("PUT", "/sample")
        assert response.response_status == 403
        assert response.response_json["code"] == "PPP000002"
        assert response.response_json["translation"] == FORBIDDEN_TRANSLATION

    def test_sink_keeps_accents(self):
        # O 404 nasce num exception handler, bem mais pra dentro: o outro caminho de erro.
        response = ClientRequisition.send(
            "PUT",
            "/sample",
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        assert response.response_status == 404
        assert response.response_json["code"] == "PPP000404"
        assert response.response_json["translation"] == NOT_FOUND_TRANSLATION

    def test_method_not_allowed(self):
        response = ClientRequisition.send("PUT", "/health_check")
        assert response.response_status == 405
        assert response.response_json["code"] == "PPP000405"

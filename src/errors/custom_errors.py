from errors import QIException


class BusinessDateMismatch(QIException):
    code = "BNK000006"

    def __init__(self) -> None:
        title = "Business Date Mismatch"
        http_status = 409
        description = "The close_date is not the current business date."
        translation = "A data a fechar não é a data de movimento atual."
        super().__init__(title, self.code, http_status, description, translation)


class CustomerNotFound(QIException):
    code = "BNK001001"

    def __init__(self) -> None:
        title = "Customer Not Found"
        http_status = 404
        description = "The customer_key does not exist."
        translation = "Cliente não encontrado."
        super().__init__(title, self.code, http_status, description, translation)


class DocumentAlreadyRegistered(QIException):
    code = "BNK001002"

    def __init__(self) -> None:
        title = "Document Already Registered"
        http_status = 409
        description = "There is already a customer with this document_number."
        translation = "Já existe um cliente cadastrado com este CPF."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidDocumentNumber(QIException):
    code = "BNK001003"

    def __init__(self) -> None:
        title = "Invalid Document Number"
        http_status = 422
        description = "The document_number check digits are invalid."
        translation = "CPF inválido."
        super().__init__(title, self.code, http_status, description, translation)


class UnderageCustomer(QIException):
    code = "BNK001004"

    def __init__(self) -> None:
        title = "Underage Customer"
        http_status = 422
        description = "The customer must be at least 18 years old and born in the past."
        translation = "O cliente precisa ter pelo menos 18 anos."
        super().__init__(title, self.code, http_status, description, translation)


class AccountNotFound(QIException):
    code = "BNK002001"

    def __init__(self) -> None:
        title = "Account Not Found"
        http_status = 404
        description = "The account_key does not exist for this customer."
        translation = "Conta não encontrada."
        super().__init__(title, self.code, http_status, description, translation)


class AccountAlreadyExists(QIException):
    code = "BNK002002"

    def __init__(self) -> None:
        title = "Account Already Exists"
        http_status = 409
        description = "The customer already has an account that is not closed."
        translation = "O cliente já tem uma conta não encerrada."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidStatusTransition(QIException):
    code = "BNK002003"

    def __init__(self) -> None:
        title = "Invalid Status Transition"
        http_status = 409
        description = "The account cannot move from its current status to the requested one."
        translation = "A conta não pode passar do status atual para o status pedido."
        super().__init__(title, self.code, http_status, description, translation)


class AccountNotEmpty(QIException):
    code = "BNK002004"

    def __init__(self) -> None:
        title = "Account Not Empty"
        http_status = 409
        description = "The account must have zero balance and no investment position to be closed."
        translation = "Só é possível encerrar uma conta sem saldo e sem investimentos."
        super().__init__(title, self.code, http_status, description, translation)


class AccountNotActive(QIException):
    code = "BNK002005"

    def __init__(self) -> None:
        title = "Account Not Active"
        http_status = 409
        description = "The account is blocked or closed and cannot move money."
        translation = "A conta está bloqueada ou encerrada e não pode movimentar dinheiro."
        super().__init__(title, self.code, http_status, description, translation)


class StatusReasonRequired(QIException):
    code = "BNK002006"

    def __init__(self) -> None:
        title = "Status Reason Required"
        http_status = 422
        description = "Blocking or closing an account requires a reason."
        translation = "Bloquear ou encerrar a conta exige um motivo."
        super().__init__(title, self.code, http_status, description, translation)


class TransactionNotFound(QIException):
    code = "BNK003001"

    def __init__(self) -> None:
        title = "Transaction Not Found"
        http_status = 404
        description = "The transaction_key does not exist or does not involve this account."
        translation = "Transação não encontrada."
        super().__init__(title, self.code, http_status, description, translation)


class DestinationAccountNotFound(QIException):
    code = "BNK003002"

    def __init__(self) -> None:
        title = "Destination Account Not Found"
        http_status = 404
        description = "The destination_account_key does not exist."
        translation = "Conta de destino não encontrada."
        super().__init__(title, self.code, http_status, description, translation)


class InsufficientBalance(QIException):
    code = "BNK003003"

    def __init__(self) -> None:
        title = "Insufficient Balance"
        http_status = 409
        description = "The account does not have enough balance for amount plus fee."
        translation = "Saldo insuficiente para o valor mais a tarifa."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidAmount(QIException):
    code = "BNK003004"

    def __init__(self) -> None:
        title = "Invalid Amount"
        http_status = 422
        description = "The amount must be an integer greater than zero, in cents."
        translation = "O valor precisa ser maior que zero, em centavos."
        super().__init__(title, self.code, http_status, description, translation)


class AmountAboveLimit(QIException):
    code = "BNK003005"

    def __init__(self) -> None:
        title = "Amount Above Limit"
        http_status = 422
        description = "The amount is above the limit for this type of operation."
        translation = "O valor está acima do limite para este tipo de operação."
        super().__init__(title, self.code, http_status, description, translation)


class SameAccountTransfer(QIException):
    code = "BNK003006"

    def __init__(self) -> None:
        title = "Same Account Transfer"
        http_status = 422
        description = "The destination account must be different from the origin account."
        translation = "A conta de destino precisa ser diferente da conta de origem."
        super().__init__(title, self.code, http_status, description, translation)


class DestinationAccountNotActive(QIException):
    code = "BNK003007"

    def __init__(self) -> None:
        title = "Destination Account Not Active"
        http_status = 409
        description = "The destination account is blocked or closed and cannot receive money."
        translation = "A conta de destino está bloqueada ou encerrada e não pode receber dinheiro."
        super().__init__(title, self.code, http_status, description, translation)


class SuitabilityNotFound(QIException):
    code = "BNK004001"

    def __init__(self) -> None:
        title = "Suitability Not Found"
        http_status = 404
        description = "The customer has never answered the suitability questionnaire."
        translation = "O cliente ainda não respondeu o questionário de perfil de investidor."
        super().__init__(title, self.code, http_status, description, translation)


class IncompleteAnswers(QIException):
    code = "BNK004002"

    def __init__(self) -> None:
        title = "Incomplete Answers"
        http_status = 422
        description = "Every question must be answered exactly once, and only existing questions can be answered."
        translation = "Cada pergunta do questionário precisa de exatamente uma resposta."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidOption(QIException):
    code = "BNK004003"

    def __init__(self) -> None:
        title = "Invalid Option"
        http_status = 422
        description = "The option_code does not belong to the question."
        translation = "A opção escolhida não pertence a esta pergunta."
        super().__init__(title, self.code, http_status, description, translation)


class SuitabilityExpired(QIException):
    code = "BNK004004"

    def __init__(self) -> None:
        title = "Suitability Expired"
        http_status = 409
        description = "The investor profile is more than 24 months old and must be answered again."
        translation = "O perfil de investidor tem mais de 24 meses e precisa ser refeito."
        super().__init__(title, self.code, http_status, description, translation)


class SuitabilityRequired(QIException):
    code = "BNK004005"

    def __init__(self) -> None:
        title = "Suitability Required"
        http_status = 409
        description = "The customer needs an investor profile before this operation."
        translation = "O cliente precisa responder o questionário de perfil de investidor antes desta operação."
class ProductNotFound(QIException):
    code = "BNK005001"

    def __init__(self) -> None:
        title = "Product Not Found"
        http_status = 404
        description = "The product_key does not exist."
        translation = "Produto não encontrado."
        super().__init__(title, self.code, http_status, description, translation)



class PriceSourceUnavailable(QIException):
    code = "BNK005006"

    def __init__(self) -> None:
        title = "Price Source Unavailable"
        http_status = 502
        description = "An external price or rate source is down, timed out or answered an error."
        translation = "Uma fonte externa de preço ou taxa está fora do ar ou respondeu erro. Nada foi gravado."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidPriceSourceResponse(QIException):
    code = "BNK005007"

    def __init__(self) -> None:
        title = "Invalid Price Source Response"
        http_status = 502
        description = "An external price or rate source answered something that makes no sense."
        translation = "Uma fonte externa de preço ou taxa respondeu algo sem sentido. Nada foi gravado."
        super().__init__(title, self.code, http_status, description, translation)

from errors import QIException


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

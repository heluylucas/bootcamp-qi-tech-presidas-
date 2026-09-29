from uuid import uuid4

from database import Context
from models import Author


class AuthorRepository:
    """A camada que fala com o banco. Só aqui existe query.

    Nenhuma regra de negócio mora aqui: esta classe busca e guarda —
    quem decide o que fazer com isso é o controller.

    Repare no que ele recebe: o CONTEXTO do trabalho, e não a sessão
    solta. A sessão é o que ele tira de lá na linha seguinte, e é tudo de
    que precisa hoje — mas a assinatura já fala a língua do que viaja
    entre as camadas. No dia em que o contexto carregar também o
    identificador da requisição, nenhum construtor daqui até o resource
    muda de forma.
    """

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, author_data: dict) -> Author:
        author = Author()

        author.author_key = str(uuid4())
        author.name = author_data["name"]
        author.nationality = author_data["nationality"]
        author.document_number = author_data["document_number"]

        self.session.add(author)
        return author

    def get_by_key(self, author_key: str) -> Author:
        return self.session.query(Author).filter(Author.author_key == author_key).first()

    def get_by_document_number(self, document_number: str) -> Author:
        return self.session.query(Author).filter(Author.document_number == document_number).first()

    def list_page(self, limit: int, offset: int) -> list:
        """A página pedida, do mais novo para o mais antigo.

        Pede UM a mais que o limite: é o jeito barato de o controller
        saber se existe próxima página sem uma segunda consulta. O
        desempate por `id` existe porque dois autores podem nascer no
        mesmo instante, e aí `created_at` sozinho deixaria a ordem em
        aberto — e a página 2 com permissão de repetir uma linha da 1.
        """
        query = self.session.query(Author).order_by(Author.created_at.desc(), Author.id.desc())

        return query.limit(limit + 1).offset(offset).all()

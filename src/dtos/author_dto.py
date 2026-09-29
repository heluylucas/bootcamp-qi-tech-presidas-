from typing import List

from models import Author


class AuthorDTO:
    """Traduz o objeto do banco no JSON que a API devolve.

    O repository entrega um `Author` — o espelho da tabela, com o `id`
    numérico e o `created_at`. Nada disso sai para o cliente: aqui esse
    objeto vira um dicionário simples, e é esse dicionário que o FastAPI
    transforma no JSON da resposta.

    Campo novo na resposta se acrescenta aqui — e só aqui.
    """

    @staticmethod
    def obj_to_dict(author: Author) -> dict:
        dto = dict()
        dto["author_key"] = author.author_key
        dto["name"] = author.name
        dto["nationality"] = author.nationality
        dto["document_number"] = author.document_number

        return dto

    @staticmethod
    def list_obj_to_list_dict(authors_list: List[Author]) -> List[dict]:
        authors_dict_list = []

        for author in authors_list:
            authors_dict_list.append(AuthorDTO.obj_to_dict(author))

        return authors_dict_list

    @staticmethod
    def only_obj_key(author: Author) -> dict:
        dto = dict()
        dto["author_key"] = author.author_key

        return dto

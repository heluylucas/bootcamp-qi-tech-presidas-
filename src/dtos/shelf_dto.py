from typing import List

from models import Shelf


class ShelfDTO:
    """O JSON da estante. Mesma forma do AuthorDTO."""

    @staticmethod
    def obj_to_dict(shelf: Shelf) -> dict:
        dto = dict()
        dto["shelf_key"] = shelf.shelf_key
        dto["code"] = shelf.code
        dto["location"] = shelf.location
        dto["capacity"] = shelf.capacity

        return dto

    @staticmethod
    def list_obj_to_list_dict(shelves_list: List[Shelf]) -> List[dict]:
        shelves_dict_list = []

        for shelf in shelves_list:
            shelves_dict_list.append(ShelfDTO.obj_to_dict(shelf))

        return shelves_dict_list

    @staticmethod
    def only_obj_key(shelf: Shelf) -> dict:
        dto = dict()
        dto["shelf_key"] = shelf.shelf_key

        return dto

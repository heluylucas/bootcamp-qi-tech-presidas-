from typing import List

from models import Member


class MemberDTO:
    """O JSON do leitor. Mesma forma do AuthorDTO."""

    @staticmethod
    def obj_to_dict(member: Member) -> dict:
        dto = dict()
        dto["member_key"] = member.member_key
        dto["name"] = member.name
        dto["email"] = member.email
        dto["document_number"] = member.document_number

        return dto

    @staticmethod
    def list_obj_to_list_dict(members_list: List[Member]) -> List[dict]:
        members_dict_list = []

        for member in members_list:
            members_dict_list.append(MemberDTO.obj_to_dict(member))

        return members_dict_list

    @staticmethod
    def only_obj_key(member: Member) -> dict:
        dto = dict()
        dto["member_key"] = member.member_key

        return dto

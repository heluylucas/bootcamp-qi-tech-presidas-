import random


class RandomGenerator:
    @staticmethod
    def generate_cpf():
        """Um CPF que existe, já com a máscara 000.000.000-00.

        Nove dígitos sorteados e os dois verificadores calculados pela
        mesma conta que a API confere: cada dígito anterior vezes um peso
        que decresce, a soma, o resto por 11; resto menor que 2 vira 0, e
        nos outros casos o dígito é 11 menos o resto. A conta está escrita
        aqui de novo, e não importada: o teste não enxerga o `src/`.

        Nove dígitos iguais são sorteados de novo: a Receita não emite
        CPF de dígitos todos iguais, e a API recusa esses números.
        """
        all_digits_are_equal = True
        while all_digits_are_equal:
            digits = []
            for _position in range(9):
                digits.append(random.randrange(10))

            all_digits_are_equal = True
            for digit in digits:
                if digit != digits[0]:
                    all_digits_are_equal = False
                    break

        for position in [9, 10]:
            total = 0
            first_weight = position + 1

            for index in range(position):
                total = total + digits[index] * (first_weight - index)

            remainder = total % 11

            if remainder < 2:
                digits.append(0)
            else:
                digits.append(11 - remainder)

        cpf_number = ""
        for digit in digits:
            cpf_number = cpf_number + str(digit)

        return f"{cpf_number[0:3]}.{cpf_number[3:6]}.{cpf_number[6:9]}-{cpf_number[9:11]}"

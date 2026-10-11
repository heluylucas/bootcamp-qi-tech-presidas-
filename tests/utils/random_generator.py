import random


class RandomGenerator:
    @staticmethod
    def generate_cpf():
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

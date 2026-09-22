from __future__ import annotations


def digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def luhn_valid(digits_str: str) -> bool:
    if not digits_str.isdigit() or len(digits_str) < 2:
        return False
    total = 0
    reverse = digits_str[::-1]
    for i, ch in enumerate(reverse):
        digit = ord(ch) - 48
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def inn_valid(digits_str: str) -> bool:
    if not digits_str.isdigit():
        return False
    if len(digits_str) == 10:
        weights = (2, 4, 10, 3, 5, 9, 4, 6, 8)
        check = _checksum(digits_str, weights)
        return check == int(digits_str[9])
    if len(digits_str) == 12:
        weights_11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
        weights_12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
        check_11 = _checksum(digits_str, weights_11)
        check_12 = _checksum(digits_str, weights_12)
        return check_11 == int(digits_str[10]) and check_12 == int(digits_str[11])
    return False


def snils_valid(digits_str: str) -> bool:
    if not digits_str.isdigit() or len(digits_str) != 11:
        return False
    if digits_str == digits_str[0] * 11:
        return False
    total = sum(int(ch) * (9 - i) for i, ch in enumerate(digits_str[:9]))
    if total > 101:
        total %= 101
    if total == 100 or total == 101:
        total = 0
    return total == int(digits_str[9:11])


def _checksum(digits_str: str, weights: tuple[int, ...]) -> int:
    total = sum(int(digits_str[i]) * weights[i] for i in range(len(weights)))
    return total % 11 % 10

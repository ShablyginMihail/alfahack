from __future__ import annotations

import re
import secrets

from pii_guard.core.normalize import normalize
from pii_guard.recognizers.validators import luhn_valid

# буквы, с которых может начинаться имя или отчество
_INITIALS = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЭЮЯ"
_CYRILLIC_LOWER = "абвгдежзиклмнопрстуфхцчшщъыьэюя"
_CYRILLIC_UPPER = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
_LATIN_LOWER = "abcdefghijklmnopqrstuvwxyz"
_LATIN_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

_MALE_SURNAMES = [
    "Иванов",
    "Петров",
    "Сидоров",
    "Смирнов",
    "Кузнецов",
    "Попов",
    "Соколов",
    "Лебедев",
    "Козлов",
    "Новиков",
    "Морозов",
    "Волков",
    "Соловьёв",
    "Васильев",
    "Зайцев",
    "Павлов",
    "Семёнов",
    "Голубев",
    "Виноградов",
    "Богданов",
]
_FEMALE_SURNAMES = [
    "Иванова",
    "Петрова",
    "Сидорова",
    "Смирнова",
    "Кузнецова",
    "Попова",
    "Соколова",
    "Лебедева",
    "Козлова",
    "Новикова",
    "Морозова",
    "Волкова",
    "Соловьёва",
    "Васильева",
    "Зайцева",
    "Павлова",
    "Семёнова",
    "Голубева",
    "Виноградова",
    "Богданова",
]
_MALE_NAMES = [
    "Александр",
    "Дмитрий",
    "Сергей",
    "Андрей",
    "Алексей",
    "Максим",
    "Иван",
    "Николай",
    "Михаил",
    "Владимир",
    "Павел",
    "Артём",
    "Игорь",
    "Олег",
    "Роман",
    "Виктор",
    "Юрий",
    "Антон",
    "Денис",
    "Евгений",
]
_FEMALE_NAMES = [
    "Анна",
    "Мария",
    "Ольга",
    "Елена",
    "Наталья",
    "Татьяна",
    "Ирина",
    "Светлана",
    "Екатерина",
    "Надежда",
    "Людмила",
    "Галина",
    "Оксана",
    "Юлия",
    "Вера",
    "Ксения",
    "Дарья",
    "Алина",
    "Полина",
    "Виктория",
]
_MALE_PATRONYMICS = [
    "Иванович",
    "Петрович",
    "Сергеевич",
    "Андреевич",
    "Алексеевич",
    "Дмитриевич",
    "Николаевич",
    "Михайлович",
    "Владимирович",
    "Павлович",
    "Александрович",
    "Викторович",
    "Юрьевич",
    "Антонович",
    "Денисович",
    "Евгеньевич",
    "Максимович",
    "Романович",
    "Олегович",
    "Игоревич",
]
_FEMALE_PATRONYMICS = [
    "Ивановна",
    "Петровна",
    "Сергеевна",
    "Андреевна",
    "Алексеевна",
    "Дмитриевна",
    "Николаевна",
    "Михайловна",
    "Владимировна",
    "Павловна",
    "Александровна",
    "Викторовна",
    "Юрьевна",
    "Антоновна",
    "Денисовна",
    "Евгеньевна",
    "Максимовна",
    "Романовна",
    "Олеговна",
    "Игоревна",
]
_LATIN_NAMES = [
    "SERGEY",
    "DMITRY",
    "ANDREY",
    "ALEXEY",
    "MAXIM",
    "IVAN",
    "NIKOLAY",
    "MIKHAIL",
    "VLADIMIR",
    "PAVEL",
    "ARTEM",
    "IGOR",
    "OLEG",
    "ROMAN",
    "VIKTOR",
    "YURIY",
    "ANTON",
    "DENIS",
    "EVGENIY",
    "ALEXANDER",
]
_LATIN_SURNAMES = [
    "IVANOV",
    "PETROV",
    "SIDOROV",
    "SMIRNOV",
    "KUZNETSOV",
    "POPOV",
    "SOKOLOV",
    "LEBEDEV",
    "KOZLOV",
    "NOVIKOV",
    "MOROZOV",
    "VOLKOV",
    "SOLOVYEV",
    "VASILYEV",
    "ZAYTSEV",
    "PAVLOV",
    "SEMYONOV",
    "GOLUBEV",
    "VINOGRADOV",
    "BOGDANOV",
]
_CITIES = [
    "Москва",
    "Санкт-Петербург",
    "Новосибирск",
    "Екатеринбург",
    "Казань",
    "Нижний Новгород",
    "Челябинск",
    "Самара",
    "Омск",
    "Ростов-на-Дону",
    "Уфа",
    "Красноярск",
    "Воронеж",
    "Пермь",
    "Волгоград",
    "Краснодар",
    "Саратов",
    "Тюмень",
    "Тольятти",
    "Ижевск",
]
_STREETS = [
    "Ленина",
    "Пушкина",
    "Гагарина",
    "Советская",
    "Мира",
    "Центральная",
    "Школьная",
    "Садовая",
    "Молодёжная",
    "Лесная",
    "Новая",
    "Набережная",
    "Заречная",
    "Полевая",
    "Октябрьская",
    "Комсомольская",
    "Первомайская",
    "Юбилейная",
    "Строителей",
    "Победы",
]
_COUNTRIES = ["Россия", "Беларусь", "Казахстан", "Армения", "Узбекистан"]
_EMAIL_DOMAINS = ["mail.ru", "yandex.ru", "gmail.com", "bk.ru"]

_NAME_SET = frozenset(normalize(n) for n in _MALE_NAMES + _FEMALE_NAMES)
_LATIN_NAME_SET = frozenset(n.lower() for n in _LATIN_NAMES)


class SyntheticGenerator:
    def __init__(self) -> None:
        self._rng = secrets.SystemRandom()
        self._cache: dict[tuple[str, str], str] = {}
        self._used: set[tuple[str, str]] = set()
        self._handlers = {
            "PERSON": self._person,
            "CARDHOLDER": self._cardholder,
            "EMAIL": self._email,
            "PHONE": self._phone,
            "CARD_NUMBER": self._card_number,
            "INN": self._inn,
            "SNILS": self._snils,
            "BIRTH_DATE": self._date,
            "PASSPORT_ISSUE_DATE": self._date,
            "ADDRESS": self._address,
            "BIRTH_PLACE": self._birth_place,
            "CITIZENSHIP": self._citizenship,
            "PASSPORT_ISSUER": self._passport_issuer,
        }

    def value(self, pii_type: str, original: str, part: str | None = None) -> str:
        key = (pii_type, "".join(c for c in normalize(original) if c.isalnum()))
        if key in self._cache:
            return self._cache[key]
        handler = self._handlers.get(pii_type, self._generic)
        value = handler(original, part)
        attempts = 0
        while (value == original or (pii_type, value) in self._used) and attempts < 20:
            value = handler(original, part)
            attempts += 1
        self._used.add((pii_type, value))
        self._cache[key] = value
        return value

    @staticmethod
    def _apply_case(generated: str, template: str) -> str:
        if template.isupper():
            return generated.upper()
        if template.islower():
            return generated.lower()
        if template[:1].isupper():
            return generated.capitalize()
        return generated

    @staticmethod
    def _is_cyrillic(ch: str) -> bool:
        return "а" <= ch <= "я" or "А" <= ch <= "Я" or ch in "ёЁ"

    def _is_female(self, words: list[str]) -> bool:
        for word in words:
            w = word.rstrip(".")
            if w.endswith(("ова", "ева", "ина", "ая", "вна")):
                return True
        return False

    def _person(self, original: str, part: str | None) -> str:
        words = original.split()
        female = self._is_female(words)
        return " ".join(self._person_word(w, female) for w in words)

    def _person_word(self, word: str, female: bool) -> str:
        if re.fullmatch(r"[А-Яа-яЁё]\.[А-Яа-яЁё]\.", word):
            a = self._rng.choice(_INITIALS)
            b = self._rng.choice(_INITIALS)
            return self._apply_case(a, word[0]) + "." + self._apply_case(b, word[2]) + "."
        if re.fullmatch(r"[А-Яа-яЁё]\.", word):
            return self._apply_case(self._rng.choice(_INITIALS), word[0]) + "."
        w = word.rstrip(".")
        if w.endswith(("вич", "вна", "ична", "ич")):
            pool = _FEMALE_PATRONYMICS if female else _MALE_PATRONYMICS
            return self._apply_case(self._rng.choice(pool), word)
        if normalize(w) in _NAME_SET:
            pool = _FEMALE_NAMES if female else _MALE_NAMES
            return self._apply_case(self._rng.choice(pool), word)
        pool = _FEMALE_SURNAMES if female else _MALE_SURNAMES
        return self._apply_case(self._rng.choice(pool), word)

    def _cardholder(self, original: str, part: str | None) -> str:
        words = original.split()
        result = []
        for word in words:
            pool = _LATIN_NAMES if word.lower() in _LATIN_NAME_SET else _LATIN_SURNAMES
            result.append(self._apply_case(self._rng.choice(pool), word))
        return " ".join(result)

    def _email(self, original: str, part: str | None) -> str:
        surname = self._rng.choice(_LATIN_SURNAMES).lower()
        digits = "".join(str(self._rng.randint(0, 9)) for _ in range(self._rng.randint(2, 4)))
        return f"{surname}{digits}@{self._rng.choice(_EMAIL_DOMAINS)}"

    def _phone(self, original: str, part: str | None) -> str:
        digits_pos = [i for i, ch in enumerate(original) if ch.isdigit()]
        digits_str = "".join(original[i] for i in digits_pos)
        preserve = 1 if digits_str.startswith(("7", "8")) else 0
        if len(digits_str) > preserve:
            preserve += 1
        chars = list(original)
        for idx, pos in enumerate(digits_pos):
            if idx >= preserve:
                chars[pos] = str(self._rng.randint(0, 9))
        return "".join(chars)

    def _card_number(self, original: str, part: str | None) -> str:
        digits_pos = [i for i, ch in enumerate(original) if ch.isdigit()]
        digits_str = "".join(original[i] for i in digits_pos)
        n = len(digits_str)
        if n < 2:
            return self._generic(original)
        body = [digits_str[0]] + [str(self._rng.randint(0, 9)) for _ in range(n - 2)]
        for last in range(10):
            candidate = "".join(body) + str(last)
            if luhn_valid(candidate):
                break
        chars = list(original)
        for idx, pos in enumerate(digits_pos):
            chars[pos] = candidate[idx]
        return "".join(chars)

    def _inn(self, original: str, part: str | None) -> str:
        digits_pos = [i for i, ch in enumerate(original) if ch.isdigit()]
        digits_str = "".join(original[i] for i in digits_pos)
        n = len(digits_str)
        if n == 10:
            candidate = self._inn_10()
        elif n == 12:
            candidate = self._inn_12()
        else:
            return self._generic(original)
        chars = list(original)
        for idx, pos in enumerate(digits_pos):
            chars[pos] = candidate[idx]
        return "".join(chars)

    def _inn_10(self) -> str:
        base = [str(self._rng.randint(0, 9)) for _ in range(9)]
        weights = (2, 4, 10, 3, 5, 9, 4, 6, 8)
        check = sum(int(base[i]) * weights[i] for i in range(9)) % 11 % 10
        return "".join(base) + str(check)

    def _inn_12(self) -> str:
        base = [str(self._rng.randint(0, 9)) for _ in range(10)]
        w11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
        w12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
        c11 = sum(int(base[i]) * w11[i] for i in range(10)) % 11 % 10
        base.append(str(c11))
        c12 = sum(int(base[i]) * w12[i] for i in range(11)) % 11 % 10
        return "".join(base) + str(c12)

    def _snils(self, original: str, part: str | None) -> str:
        digits_pos = [i for i, ch in enumerate(original) if ch.isdigit()]
        if len(digits_pos) != 11:
            return self._generic(original)
        candidate = self._snils_number()
        chars = list(original)
        for idx, pos in enumerate(digits_pos):
            chars[pos] = candidate[idx]
        return "".join(chars)

    def _snils_number(self) -> str:
        while True:
            base = [str(self._rng.randint(0, 9)) for _ in range(9)]
            if "".join(base) == base[0] * 9:
                continue
            total = sum(int(base[i]) * (9 - i) for i in range(9))
            if total > 101:
                total %= 101
            if total in (100, 101):
                total = 0
            return "".join(base) + f"{total:02d}"

    def _date(self, original: str, part: str | None) -> str:
        groups = list(re.finditer(r"\d+", original))
        roles = self._date_roles(groups)
        if roles is None:
            return self._generic(original)
        chars = list(original)
        for group, role in zip(groups, roles, strict=True):
            value = group.group()
            if role == "day":
                new = f"{self._rng.randint(1, 28):0{len(value)}d}"
            elif role == "month":
                new = f"{self._rng.randint(1, 12):0{len(value)}d}"
            else:
                delta = self._rng.randint(1, 7) * self._rng.choice([-1, 1])
                new = f"{(int(value) + delta) % 10 ** len(value):0{len(value)}d}"
            chars[group.start() : group.end()] = new
        return "".join(chars)

    def _date_roles(self, groups: list[re.Match[str]]) -> list[str] | None:
        values = [g.group() for g in groups]
        if len(values) == 3:
            a, b, c = values
            if self._ok(int(a), int(b)):
                return ["day", "month", "year"]
            if self._ok(int(c), int(b)):
                return ["year", "month", "day"]
        elif len(values) == 2:
            a, b = values
            if self._ok(int(a), 1) and self._is_year(b):
                return ["day", "year"]
            if self._is_year(a) and self._ok(int(b), 1):
                return ["year", "day"]
        elif len(values) == 1 and self._is_year(values[0]):
            return ["year"]
        return None

    @staticmethod
    def _ok(day: int, month: int) -> bool:
        return 1 <= day <= 31 and 1 <= month <= 12

    @staticmethod
    def _is_year(value: str) -> bool:
        return value.isdigit() and len(value) in (2, 4)

    def _address(self, original: str, part: str | None) -> str:
        if part == "city":
            return self._apply_case(self._rng.choice(_CITIES), original)
        if part == "street":
            return self._apply_case(self._rng.choice(_STREETS), original)
        return self._generic(original)

    def _birth_place(self, original: str, part: str | None) -> str:
        return self._apply_case(self._rng.choice(_CITIES), original)

    def _citizenship(self, original: str, part: str | None) -> str:
        return self._apply_case(self._rng.choice(_COUNTRIES), original)

    def _passport_issuer(self, original: str, part: str | None) -> str:
        return f"ОУФМС России по г. {self._rng.choice(_CITIES)}"

    def _generic(self, original: str, part: str | None = None) -> str:
        return "".join(self._random_like(ch) for ch in original)

    def _random_like(self, ch: str) -> str:
        if ch.isdigit():
            return str(self._rng.randint(0, 9))
        if not ch.isalpha():
            return ch
        if self._is_cyrillic(ch):
            pool = _CYRILLIC_LOWER if ch.islower() else _CYRILLIC_UPPER
        else:
            pool = _LATIN_LOWER if ch.islower() else _LATIN_UPPER
        return self._rng.choice(pool)

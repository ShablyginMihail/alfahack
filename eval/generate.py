from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import ClassVar

MALE_NAMES = [
    "иван",
    "петр",
    "сергей",
    "александр",
    "дмитрий",
    "андрей",
    "михаил",
    "николай",
    "владимир",
    "алексей",
]
FEMALE_NAMES = [
    "анна",
    "мария",
    "ольга",
    "елена",
    "наталья",
    "татьяна",
    "ирина",
    "светлана",
    "екатерина",
    "юлия",
]
MALE_PATR = [
    "иванович",
    "петрович",
    "сергеевич",
    "александрович",
    "дмитриевич",
    "андреевич",
    "михайлович",
    "николаевич",
    "владимирович",
    "алексеевич",
]
FEMALE_PATR = [
    "ивановна",
    "петровна",
    "сергеевна",
    "александровна",
    "дмитриевна",
    "андреевна",
    "михайловна",
    "николаевна",
    "владимировна",
    "алексеевна",
]
MALE_SURN = [
    "иванов",
    "петров",
    "сергеев",
    "кузнецов",
    "смирнов",
    "попов",
    "волков",
    "козлов",
    "новиков",
    "морозов",
    "соколов",
    "лебедев",
]
FEMALE_SURN = [
    "иванова",
    "петрова",
    "сергеева",
    "кузнецова",
    "смирнова",
    "попова",
    "волкова",
    "козлова",
    "новикова",
    "морозова",
    "соколова",
    "лебедева",
]

CITIES = [
    "москва",
    "санкт-петербург",
    "новосибирск",
    "екатеринбург",
    "казань",
    "нижний новгород",
    "челябинск",
    "самара",
    "омск",
    "ростов-на-дону",
    "уфа",
    "красноярск",
    "воронеж",
    "пермь",
    "волгоград",
    "краснодар",
    "саратов",
    "тюмень",
    "тольятти",
    "ижевск",
]
STREETS = [
    "ленина",
    "мира",
    "советская",
    "гагарина",
    "пушкина",
    "лермонтова",
    "толстого",
    "чехова",
    "гоголя",
    "есенина",
    "маяковского",
    "кирова",
    "маркса",
    "октябрьская",
    "победы",
    "центральная",
    "молодежная",
    "школьная",
    "садовая",
    "новая",
]
REGIONS = [
    "московской обл.",
    "ленинградской обл.",
    "республике татарстан",
    "краснодарскому краю",
    "свердловской обл.",
    "новосибирской обл.",
]
COUNTRIES = [
    "РФ",
    "Российской Федерации",
    "Республики Беларусь",
    "Казахстана",
    "Украины",
    "Узбекистана",
    "Армении",
    "Грузии",
]
EMAIL_DOMAINS = ["mail.ru", "yandex.ru", "gmail.com", "bk.ru", "inbox.ru", "list.ru"]

MONTHS_GEN = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}
ORDINAL_DAYS_GEN = {
    1: "первого",
    2: "второго",
    3: "третьего",
    4: "четвертого",
    5: "пятого",
    6: "шестого",
    7: "седьмого",
    8: "восьмого",
    9: "девятого",
    10: "десятого",
    11: "одиннадцатого",
    12: "двенадцатого",
    13: "тринадцатого",
    14: "четырнадцатого",
    15: "пятнадцатого",
    16: "шестнадцатого",
    17: "семнадцатого",
    18: "восемнадцатого",
    19: "девятнадцатого",
    20: "двадцатого",
    21: "двадцать первого",
    22: "двадцать второго",
    23: "двадцать третьего",
    24: "двадцать четвертого",
    25: "двадцать пятого",
    26: "двадцать шестого",
    27: "двадцать седьмого",
    28: "двадцать восьмого",
    29: "двадцать девятого",
    30: "тридцатого",
    31: "тридцать первого",
}
YEAR_WORDS = {
    1960: "тысяча девятьсот шестидесятого",
    1975: "тысяча девятьсот семьдесят пятого",
    1985: "тысяча девятьсот восемьдесят пятого",
    1990: "тысяча девятьсот девяностого",
    2000: "двухтысячного",
    2005: "две тысячи пятого",
}

ALL_TYPES = [
    "PERSON",
    "BIRTH_DATE",
    "BIRTH_PLACE",
    "PASSPORT",
    "CITIZENSHIP",
    "PASSPORT_ISSUER",
    "DIVISION_CODE",
    "PASSPORT_ISSUE_DATE",
    "DRIVER_LICENSE",
    "ADDRESS",
    "EMAIL",
    "PHONE",
    "INN",
    "CARD_NUMBER",
    "CVV",
    "PIN",
    "CARDHOLDER",
]

TRAP_TEMPLATES = [
    "поэт Александр Пушкин",
    "Александр Сергеевич Пушкин написал роман",
    "Мы гуляли по улице Льва Толстого с друзьями",
    "Отделение банка находится по адресу: г. Москва, ул. Тверская, д. 10",
    "Банкомат на ул. Ленина, д. 1",
    "Москва — крупный город",
    "Роман о любви",
    "Вера в успех",
    "Надежда умирает последней",
    "Слава труду",
]


BIRTH_REGIONS = (
    "Московская обл.",
    "Краснодарский край",
    "Республика Татарстан",
    "Свердловская область",
)


class Generator:
    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)

    def generate(self, per_type: int) -> list[str]:
        lines: list[str] = []
        for pii_type in ALL_TYPES:
            lines.append(f"# {pii_type}")
            for _ in range(per_type):
                lines.append(self._render(self._phrase_for_type(pii_type)))
        lines.append("# TRAPS")
        for _ in range(per_type):
            lines.append(self._render(self._trap_phrase()))
        lines.append("# COMPLEX")
        for _ in range(per_type):
            lines.append(self._render(self._complex_phrase()))
        return lines

    def _render(self, segments: list[tuple[str, str | None]]) -> str:
        case = self.rng.choice(["as_is", "upper", "lower", "capitalize"])
        parts: list[str] = []
        for text, pii_type in segments:
            cased = self._apply_case(text, case)
            if pii_type is None:
                parts.append(cased)
            else:
                parts.append(f"[[{pii_type}:{cased}]]")
        return "".join(parts)

    @staticmethod
    def _apply_case(text: str, case: str) -> str:
        if case == "upper":
            return text.upper()
        if case == "lower":
            return text.lower()
        if case == "capitalize":
            return text.title()
        return text

    _PHRASE_METHODS: ClassVar[dict[str, str]] = {
        "PERSON": "_person_phrase",
        "BIRTH_DATE": "_birth_date_phrase",
        "BIRTH_PLACE": "_birth_place_phrase",
        "PASSPORT": "_passport_phrase",
        "CITIZENSHIP": "_citizenship_phrase",
        "PASSPORT_ISSUER": "_issuer_phrase",
        "DIVISION_CODE": "_division_code_phrase",
        "PASSPORT_ISSUE_DATE": "_issue_date_phrase",
        "DRIVER_LICENSE": "_driver_phrase",
        "ADDRESS": "_address_phrase",
        "EMAIL": "_email_phrase",
        "PHONE": "_phone_phrase",
        "INN": "_inn_phrase",
        "CARD_NUMBER": "_card_phrase",
        "CVV": "_cvv_phrase",
        "PIN": "_pin_phrase",
        "CARDHOLDER": "_cardholder_phrase",
    }

    def _phrase_for_type(self, pii_type: str) -> list[tuple[str, str | None]]:
        method = self._PHRASE_METHODS.get(pii_type)
        if method is None:
            return []
        return getattr(self, method)()

    def _person_phrase(self) -> list[tuple[str, str | None]]:
        person = self._person()
        templates = [
            [
                ("Клиент ", None),
                (person, "PERSON"),
                (", паспорт ", None),
                (self._passport_value(), "PASSPORT"),
            ],
            [(person, "PERSON"), (" обратился в банк", None)],
            [("Заявление подал ", None), (person, "PERSON")],
            [(person, "PERSON"), (" проживает в ", None), (self.rng.choice(CITIES), "ADDRESS")],
            [("Сотрудник ", None), (self._surname(), "PERSON"), (" позвонил клиенту", None)],
            [("Заемщик ", None), (person, "PERSON"), (", ИНН ", None), (self._inn(), "INN")],
        ]
        return self.rng.choice(templates)

    def _birth_date_phrase(self) -> list[tuple[str, str | None]]:
        date = self._birth_date()
        templates = [
            [("Дата рождения ", None), (date, "BIRTH_DATE")],
            [("Родился ", None), (date, "BIRTH_DATE"), (" года", None)],
            [(date, "BIRTH_DATE"), (" день рождения", None)],
            [("Родилась ", None), (date, "BIRTH_DATE"), (" года", None)],
            [("Дата рождения: ", None), (date, "BIRTH_DATE"), (" года", None)],
        ]
        return self.rng.choice(templates)

    def _birth_place_phrase(self) -> list[tuple[str, str | None]]:
        place = self.rng.choice(CITIES)
        templates = [
            [("Место рождения: г. ", None), (place, "BIRTH_PLACE")],
            [("Уроженец ", None), (place, "BIRTH_PLACE")],
            [("Родился в ", None), (place, "BIRTH_PLACE")],
            [("Место рождения — ", None), (self.rng.choice(BIRTH_REGIONS), "BIRTH_PLACE")],
        ]
        return self.rng.choice(templates)

    def _passport_phrase(self) -> list[tuple[str, str | None]]:
        series = f"{self.rng.randint(10, 99)}{self.rng.randint(10, 99)}"
        number = f"{self.rng.randint(100000, 999999)}"
        templates = [
            [("Паспорт ", None), (f"{series} {number}", "PASSPORT"), (" выдан", None)],
            [("Серия ", None), (series, "PASSPORT"), (" номер ", None), (number, "PASSPORT")],
            [("Паспорт ", None), (f"{series[:2]} {series[2:]} {number}", "PASSPORT")],
            [
                ("Серия паспорта: ", None),
                (f"{series[:2]} {series[2:]}", "PASSPORT"),
                (", номер: ", None),
                (number, "PASSPORT"),
            ],
            [("Паспорт ", None), (f"{series}-{number}", "PASSPORT")],
        ]
        return self.rng.choice(templates)

    def _citizenship_phrase(self) -> list[tuple[str, str | None]]:
        country = self.rng.choice(COUNTRIES)
        templates = [
            [("Гражданство: ", None), (country, "CITIZENSHIP")],
            [("Гражданин ", None), (country, "CITIZENSHIP")],
            [("Гражданка ", None), (country, "CITIZENSHIP")],
            [("Гражданство ", None), (country, "CITIZENSHIP")],
        ]
        return self.rng.choice(templates)

    def _issuer_phrase(self) -> list[tuple[str, str | None]]:
        city = self.rng.choice(CITIES)
        region = self.rng.choice(REGIONS)
        templates = [
            [("Выдан ", None), (f"ОУФМС России по г. {city}", "PASSPORT_ISSUER")],
            [("Паспорт выдан ", None), (f"Отделом УФМС России по {region}", "PASSPORT_ISSUER")],
            [("Кем выдан: ", None), (f"ГУ МВД России по {region}", "PASSPORT_ISSUER")],
            [("Выдан ", None), (f"ТП УФМС России по г. {city}", "PASSPORT_ISSUER")],
        ]
        return self.rng.choice(templates)

    def _division_code_phrase(self) -> list[tuple[str, str | None]]:
        code = f"{self.rng.randint(100, 999)}-{self.rng.randint(100, 999)}"
        templates = [
            [("Код подразделения ", None), (code, "DIVISION_CODE")],
            [("К/п ", None), (code, "DIVISION_CODE")],
            [("Код подразделения: ", None), (code, "DIVISION_CODE")],
        ]
        return self.rng.choice(templates)

    def _issue_date_phrase(self) -> list[tuple[str, str | None]]:
        date = self._birth_date()
        templates = [
            [("Паспорт выдан ", None), (date, "PASSPORT_ISSUE_DATE")],
            [("Дата выдачи ", None), (date, "PASSPORT_ISSUE_DATE")],
            [("Выдан ", None), (date, "PASSPORT_ISSUE_DATE"), (" г.", None)],
        ]
        return self.rng.choice(templates)

    def _driver_phrase(self) -> list[tuple[str, str | None]]:
        series = f"{self.rng.randint(10, 99)} {self.rng.randint(10, 99)}"
        number = f"{self.rng.randint(100000, 999999)}"
        old = (
            f"{self.rng.randint(10, 99)} {self.rng.choice(['ав', 'вс', 'ек', 'мо', 'нн'])} {number}"
        )
        templates = [
            [("Водительское удостоверение ", None), (f"{series} {number}", "DRIVER_LICENSE")],
            [("ВУ ", None), (old, "DRIVER_LICENSE")],
            [
                ("Водительские права ", None),
                (f"{series.replace(' ', '')} {number}", "DRIVER_LICENSE"),
            ],
            [
                ("Водительское удостоверение: серия ", None),
                (series, "DRIVER_LICENSE"),
                (" номер ", None),
                (number, "DRIVER_LICENSE"),
            ],
        ]
        return self.rng.choice(templates)

    def _region_segments(self, pii_type: str = "ADDRESS") -> list[tuple[str, str | None]]:
        kind = self.rng.choice(["obl", "krai", "resp"])
        if kind == "obl":
            name = self.rng.choice(["Московской", "Ленинградской", "Свердловской", "Новосибирской"])
            return [(name, pii_type), (" обл.", None)]
        if kind == "krai":
            name = self.rng.choice(
                ["Краснодарский", "Красноярский", "Приморский", "Ставропольский"]
            )
            return [(name, pii_type), (" край", None)]
        name = self.rng.choice(["Татарстан", "Башкортостан", "Дагестан", "Чувашия"])
        return [("республике ", None), (name, pii_type)]

    def _address_phrase(self) -> list[tuple[str, str | None]]:
        index = f"{self.rng.randint(1, 6)}{self.rng.randint(10000, 99999)}"
        city = self.rng.choice(CITIES)
        street = self.rng.choice(STREETS)
        house = str(self.rng.randint(1, 99))
        apartment = str(self.rng.randint(1, 200))
        templates = [
            [
                ("Адрес регистрации: ", None),
                (index, "ADDRESS"),
                (", г. ", None),
                (city, "ADDRESS"),
                (", ул. ", None),
                (street, "ADDRESS"),
                (", д. ", None),
                (house, "ADDRESS"),
                (", кв. ", None),
                (apartment, "ADDRESS"),
            ],
            [
                ("Проживает по адресу ", None),
                *self._region_segments(),
                (", г. ", None),
                (city, "ADDRESS"),
                (", ул. ", None),
                (street, "ADDRESS"),
                (", д. ", None),
                (house, "ADDRESS"),
                (", кв. ", None),
                (apartment, "ADDRESS"),
            ],
            [
                ("г. ", None),
                (city, "ADDRESS"),
                (", ул. ", None),
                (street, "ADDRESS"),
                (", д. ", None),
                (house, "ADDRESS"),
            ],
            [("Индекс ", None), (index, "ADDRESS")],
        ]
        return self.rng.choice(templates)

    def _email_phrase(self) -> list[tuple[str, str | None]]:
        email = (
            f"{self.rng.choice(MALE_NAMES)}.{self.rng.choice(MALE_SURN)}"
            f"@{self.rng.choice(EMAIL_DOMAINS)}"
        )
        templates = [
            [("Email ", None), (email, "EMAIL")],
            [("Почта ", None), (email, "EMAIL")],
            [("Контакт ", None), (email, "EMAIL")],
            [(email, "EMAIL")],
        ]
        return self.rng.choice(templates)

    def _phone_phrase(self) -> list[tuple[str, str | None]]:
        phone = self._phone()
        templates = [
            [("Телефон ", None), (phone, "PHONE")],
            [("Моб. ", None), (phone, "PHONE")],
            [("Звоните ", None), (phone, "PHONE")],
            [("Контакт ", None), (phone, "PHONE")],
        ]
        return self.rng.choice(templates)

    def _inn_phrase(self) -> list[tuple[str, str | None]]:
        inn = self._inn()
        templates = [
            [("ИНН ", None), (inn, "INN")],
            [("ИНН: ", None), (inn, "INN")],
            [("ИНН ", None), (f"{inn[:4]} {inn[4:7]} {inn[7:]}", "INN")],
        ]
        return self.rng.choice(templates)

    def _card_phrase(self) -> list[tuple[str, str | None]]:
        card = self._card()
        templates = [
            [("Карта ", None), (card, "CARD_NUMBER")],
            [("Номер карты ", None), (card, "CARD_NUMBER")],
            [("Visa ", None), (card, "CARD_NUMBER")],
            [("Карта ", None), (card.replace(" ", "-"), "CARD_NUMBER")],
        ]
        return self.rng.choice(templates)

    def _cvv_phrase(self) -> list[tuple[str, str | None]]:
        cvv = f"{self.rng.randint(100, 999)}"
        templates = [
            [("CVV ", None), (cvv, "CVV")],
            [("CVC2: ", None), (cvv, "CVV")],
            [("Код безопасности ", None), (cvv, "CVV")],
        ]
        return self.rng.choice(templates)

    def _pin_phrase(self) -> list[tuple[str, str | None]]:
        pin = f"{self.rng.randint(1000, 9999)}"
        templates = [
            [("ПИН ", None), (pin, "PIN")],
            [("Пин-код: ", None), (pin, "PIN")],
            [("Пинкод ", None), (pin, "PIN")],
        ]
        return self.rng.choice(templates)

    def _cardholder_phrase(self) -> list[tuple[str, str | None]]:
        latin = (
            f"{self.rng.choice(['IVAN', 'PETR', 'SERGEY', 'ALEXANDER', 'DMITRY'])} "
            f"{self.rng.choice(['IVANOV', 'PETROV', 'SERGEYEV', 'KUZNETSOV', 'SMIRNOV'])}"
        )
        cyrillic = self._person()
        templates = [
            [("Держатель карты ", None), (latin, "CARDHOLDER")],
            [("Имя на карте: ", None), (latin.lower(), "CARDHOLDER")],
            [("Карта ", None), (self._card(), "CARD_NUMBER"), (", ", None), (latin, "CARDHOLDER")],
            [("Держатель карты ", None), (cyrillic, "CARDHOLDER")],
        ]
        return self.rng.choice(templates)

    def _complex_phrase(self) -> list[tuple[str, str | None]]:
        types = self.rng.sample(ALL_TYPES, self.rng.randint(3, 6))
        segments: list[tuple[str, str | None]] = []
        for i, pii_type in enumerate(types):
            if i > 0:
                segments.append((", ", None))
            segments.extend(self._value_segments(pii_type))
        return segments

    _VALUE_METHODS: ClassVar[dict[str, str]] = {
        "PERSON": "_value_person",
        "BIRTH_DATE": "_value_birth_date",
        "BIRTH_PLACE": "_value_birth_place",
        "PASSPORT": "_value_passport",
        "CITIZENSHIP": "_value_citizenship",
        "PASSPORT_ISSUER": "_value_issuer",
        "DIVISION_CODE": "_value_division_code",
        "PASSPORT_ISSUE_DATE": "_value_issue_date",
        "DRIVER_LICENSE": "_value_driver",
        "ADDRESS": "_value_address",
        "EMAIL": "_value_email",
        "PHONE": "_value_phone",
        "INN": "_value_inn",
        "CARD_NUMBER": "_value_card",
        "CVV": "_value_cvv",
        "PIN": "_value_pin",
        "CARDHOLDER": "_value_cardholder",
    }

    def _value_segments(self, pii_type: str) -> list[tuple[str, str | None]]:
        method = self._VALUE_METHODS.get(pii_type)
        if method is None:
            return []
        return getattr(self, method)()

    def _value_person(self) -> list[tuple[str, str | None]]:
        return [("Клиент ", None), (self._person(), "PERSON")]

    def _value_birth_date(self) -> list[tuple[str, str | None]]:
        return [("дата рождения ", None), (self._birth_date(), "BIRTH_DATE")]

    def _value_birth_place(self) -> list[tuple[str, str | None]]:
        return [("место рождения г. ", None), (self.rng.choice(CITIES), "BIRTH_PLACE")]

    def _value_passport(self) -> list[tuple[str, str | None]]:
        return [("паспорт ", None), (self._passport_value(), "PASSPORT")]

    def _value_citizenship(self) -> list[tuple[str, str | None]]:
        return [("гражданство ", None), (self.rng.choice(COUNTRIES), "CITIZENSHIP")]

    def _value_issuer(self) -> list[tuple[str, str | None]]:
        return [
            ("выдан ", None),
            (f"ОУФМС России по г. {self.rng.choice(CITIES)}", "PASSPORT_ISSUER"),
        ]

    def _value_division_code(self) -> list[tuple[str, str | None]]:
        return [
            ("код подразделения ", None),
            (f"{self.rng.randint(100, 999)}-{self.rng.randint(100, 999)}", "DIVISION_CODE"),
        ]

    def _value_issue_date(self) -> list[tuple[str, str | None]]:
        return [("дата выдачи ", None), (self._birth_date(), "PASSPORT_ISSUE_DATE")]

    def _value_driver(self) -> list[tuple[str, str | None]]:
        return [
            ("ВУ ", None),
            (
                f"{self.rng.randint(10, 99)} {self.rng.choice(['ав', 'вс'])} "
                f"{self.rng.randint(100000, 999999)}",
                "DRIVER_LICENSE",
            ),
        ]

    def _value_address(self) -> list[tuple[str, str | None]]:
        return [("адрес г. ", None), (self.rng.choice(CITIES), "ADDRESS")]

    def _value_email(self) -> list[tuple[str, str | None]]:
        return [
            ("email ", None),
            (f"{self.rng.choice(MALE_NAMES)}@{self.rng.choice(EMAIL_DOMAINS)}", "EMAIL"),
        ]

    def _value_phone(self) -> list[tuple[str, str | None]]:
        return [("телефон ", None), (self._phone(), "PHONE")]

    def _value_inn(self) -> list[tuple[str, str | None]]:
        return [("ИНН ", None), (self._inn(), "INN")]

    def _value_card(self) -> list[tuple[str, str | None]]:
        return [("карта ", None), (self._card(), "CARD_NUMBER")]

    def _value_cvv(self) -> list[tuple[str, str | None]]:
        return [("CVV ", None), (f"{self.rng.randint(100, 999)}", "CVV")]

    def _value_pin(self) -> list[tuple[str, str | None]]:
        return [("ПИН ", None), (f"{self.rng.randint(1000, 9999)}", "PIN")]

    def _value_cardholder(self) -> list[tuple[str, str | None]]:
        return [
            ("держатель ", None),
            (
                f"{self.rng.choice(['IVAN', 'PETR'])} {self.rng.choice(['IVANOV', 'PETROV'])}",
                "CARDHOLDER",
            ),
        ]

    def _trap_phrase(self) -> list[tuple[str, str | None]]:
        template = self.rng.choice(TRAP_TEMPLATES)
        if "{order}" in template:
            template = template.format(order=self.rng.randint(10000, 99999))
        return [(template, None)]

    def _person(self) -> str:
        male = self.rng.choice([True, False])
        first = self.rng.choice(MALE_NAMES if male else FEMALE_NAMES)
        patr = self.rng.choice(MALE_PATR if male else FEMALE_PATR)
        surn = self.rng.choice(MALE_SURN if male else FEMALE_SURN)
        return f"{surn} {first} {patr}"

    def _surname(self) -> str:
        return self.rng.choice(MALE_SURN)

    def _birth_date(self) -> str:
        year = self.rng.randint(1940, 2005)
        month = self.rng.randint(1, 12)
        day = self.rng.randint(1, 28)
        fmt = self.rng.choice(
            ["dd.mm.yyyy", "dd/mm/yyyy", "yyyy-mm-dd", "dd.mm.yy", "month", "words"]
        )
        if fmt == "dd.mm.yyyy":
            return f"{day:02d}.{month:02d}.{year}"
        if fmt == "dd/mm/yyyy":
            return f"{day:02d}/{month:02d}/{year}"
        if fmt == "yyyy-mm-dd":
            return f"{year}-{month:02d}-{day:02d}"
        if fmt == "dd.mm.yy":
            return f"{day:02d}.{month:02d}.{year % 100:02d}"
        if fmt == "month":
            return f"{day} {MONTHS_GEN[month]} {year}"
        year_word = YEAR_WORDS.get(year, "тысяча девятьсот восемьдесят пятого")
        return f"{ORDINAL_DAYS_GEN[day]} {MONTHS_GEN[month]} {year_word}"

    def _passport_value(self) -> str:
        series = f"{self.rng.randint(10, 99)}{self.rng.randint(10, 99)}"
        number = f"{self.rng.randint(100000, 999999)}"
        return f"{series} {number}"

    def _phone(self) -> str:
        fmt = self.rng.choice(["plus7", "eight", "compact", "no_code", "intl"])
        code = f"{self.rng.randint(900, 999)}"
        part1 = f"{self.rng.randint(100, 999)}"
        part2 = f"{self.rng.randint(10, 99)}"
        part3 = f"{self.rng.randint(10, 99)}"
        if fmt == "plus7":
            return f"+7 ({code}) {part1}-{part2}-{part3}"
        if fmt == "eight":
            return f"8 {code} {part1} {part2} {part3}"
        if fmt == "compact":
            return f"+7{code}{part1}{part2}{part3}"
        if fmt == "no_code":
            return f"{code} {part1} {part2} {part3}"
        return f"+375 29 {part1}-{part2}-{part3}"

    def _inn(self) -> str:
        if self.rng.random() < 0.5:
            base = [self.rng.randint(0, 9) for _ in range(9)]
            weights = (2, 4, 10, 3, 5, 9, 4, 6, 8)
            check = sum(base[i] * weights[i] for i in range(9)) % 11 % 10
            return "".join(str(d) for d in base) + str(check)
        base = [self.rng.randint(0, 9) for _ in range(10)]
        w11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
        w12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
        c11 = sum(base[i] * w11[i] for i in range(10)) % 11 % 10
        c12 = sum(([*base, c11])[i] * w12[i] for i in range(11)) % 11 % 10
        return "".join(str(d) for d in base) + str(c11) + str(c12)

    def _card(self) -> str:
        base = [self.rng.randint(0, 9) for _ in range(15)]
        total = 0
        for i, d in enumerate(reversed(base)):
            pos = i + 1
            if pos % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        check = (10 - total % 10) % 10
        digits = "".join(str(d) for d in base) + str(check)
        return f"{digits[0:4]} {digits[4:8]} {digits[8:12]} {digits[12:16]}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Генератор синтетического набора")
    parser.add_argument("--per-type", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="eval/generated/dataset.txt")
    args = parser.parse_args()

    lines = Generator(args.seed).generate(args.per_type)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Строк: {len(lines)}")


if __name__ == "__main__":
    main()

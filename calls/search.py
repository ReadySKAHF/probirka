"""Разбор поисковых запросов с масками.

Синтаксис:
    7856*                       — значение начинается с 7856
    *6345                       — значение заканчивается на 6345
    *785*                       — значение содержит 785
    4564566                     — точное совпадение
    "4564566";"*3534543"        — несколько значений через ';' (объединяются по OR),
                                  кавычки вокруг значения необязательны

Звёздочка учитывается только в начале и в конце значения;
внутри значения '*' трактуется как обычный символ.
"""

from django.db.models import Q


def build_search_q(field, raw):
    """Строит Q-объект для поля `field` по строке запроса `raw`.

    Возвращает пустой Q(), если после разбора не осталось ни одного условия.
    """
    q = Q()
    for term in raw.split(';'):
        term = term.strip().strip('"').strip()
        starts = term.startswith('*')
        ends = term.endswith('*')
        value = term.strip('*')
        if not value:
            continue
        if starts and ends:
            lookup = 'icontains'
        elif ends:
            lookup = 'istartswith'
        elif starts:
            lookup = 'iendswith'
        else:
            lookup = 'exact'
        q |= Q(**{f'{field}__{lookup}': value})
    return q

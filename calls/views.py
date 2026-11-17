import csv
from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time

from .models import Call
from .search import build_search_q

SUBSTRING_FILTERS = ('from_ip', 'to_ip')
MASK_FILTERS = ('call_id', 'from_number', 'to_number')
QUICK_SEARCH_FIELDS = ('call_id', 'from_number', 'to_number', 'from_ip', 'to_ip')

DEFAULT_PER_PAGE = 50
PER_PAGE_CHOICES = (25, 50, 100, 200)
EXPORT_LIMIT = 100_000
DISTINCT_STATS_LIMIT = 300_000
RELATED_LIMIT = 50

COLUMNS = {
    'id': ('ID', ('id',)),
    'from_ip': ('From IP', ('from_ip',)),
    'to_ip': ('To IP', ('to_ip',)),
    'call_id': ('Call ID', ('call_id',)),
    'from_number': ('Отправитель', ('from_number',)),
    'to_number': ('Получатель', ('to_number',)),
    'date': ('Дата', ('calling_date', 'calling_time')),
    'time': ('Время', ('calling_time',)),
}
DEFAULT_ORDER = ('-calling_date', '-calling_time', '-id')

FILTER_LABELS = {
    'q': 'Поиск',
    'number': 'Номер',
    'from_number': 'Отправитель',
    'to_number': 'Получатель',
    'call_id': 'Call ID',
    'from_ip': 'From IP',
    'to_ip': 'To IP',
    'date_from': 'Дата с',
    'date_to': 'Дата по',
    'time_from': 'Время с',
    'time_to': 'Время по',
}


def _get(params, key):
    return params.get(key, '').strip()


def _ip_q(field, value):
    if any(ch in value for ch in '*;"'):
        return build_search_q(field, value)
    return Q(**{f'{field}__icontains': value})


def _quick_search_q(value):
    q = Q()
    for field in QUICK_SEARCH_FIELDS:
        if '*' in value or ';' in value:
            q |= build_search_q(field, value)
        else:
            q |= Q(**{f'{field}__icontains': value})
    return q


def _apply_filters(params):
    calls = Call.objects.all()

    for field in SUBSTRING_FILTERS:
        value = _get(params, field)
        if value:
            calls = calls.filter(_ip_q(field, value))

    for field in MASK_FILTERS:
        value = _get(params, field)
        if value:
            calls = calls.filter(build_search_q(field, value))

    number = _get(params, 'number')
    if number:
        calls = calls.filter(
            build_search_q('from_number', number) | build_search_q('to_number', number)
        )

    q = _get(params, 'q')
    if q:
        calls = calls.filter(_quick_search_q(q))

    date_from = parse_date(_get(params, 'date_from'))
    if date_from:
        calls = calls.filter(calling_date__gte=date_from)
    date_to = parse_date(_get(params, 'date_to'))
    if date_to:
        calls = calls.filter(calling_date__lte=date_to)

    time_from = parse_time(_get(params, 'time_from'))
    if time_from:
        calls = calls.filter(calling_time__gte=time_from)
    time_to = parse_time(_get(params, 'time_to'))
    if time_to:
        calls = calls.filter(calling_time__lte=time_to)

    return calls


def _apply_ordering(calls, sort, direction):
    if sort not in COLUMNS:
        return calls.order_by(*DEFAULT_ORDER)
    prefix = '-' if direction == 'desc' else ''
    fields = [f'{prefix}{name}' for name in COLUMNS[sort][1]]
    return calls.order_by(*fields, f'{prefix}id')


def _per_page(params):
    try:
        value = int(params.get('per_page', ''))
    except ValueError:
        return DEFAULT_PER_PAGE
    return value if value in PER_PAGE_CHOICES else DEFAULT_PER_PAGE


def _url(params, **changes):
    """Значение None удаляет параметр из ссылки."""
    data = params.copy()
    data.pop('page', None)
    data.pop('export', None)
    for key, value in changes.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    return '?' + data.urlencode()


def _build_columns(params, sort, direction):
    columns = []
    for key, (label, _) in COLUMNS.items():
        active = key == sort
        next_dir = 'desc' if active and direction == 'asc' else 'asc'
        columns.append({
            'key': key,
            'label': label,
            'url': _url(params, sort=key, dir=next_dir),
            'active': active,
            'arrow': ('↑' if direction == 'asc' else '↓') if active else '',
        })
    return columns


def _build_chips(params):
    chips = []
    for key, label in FILTER_LABELS.items():
        value = _get(params, key)
        if value:
            chips.append({
                'label': label,
                'value': value,
                'remove_url': _url(params, **{key: None}),
            })
    return chips


def _build_periods(params):
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    periods = (
        ('Сегодня', today, today),
        ('Вчера', yesterday, yesterday),
        ('7 дней', today - timedelta(days=6), today),
        ('30 дней', today - timedelta(days=29), today),
    )
    return [
        {
            'label': label,
            'url': _url(params, date_from=start.isoformat(), date_to=end.isoformat()),
            'active': (params.get('date_from') == start.isoformat()
                       and params.get('date_to') == end.isoformat()),
        }
        for label, start, end in periods
    ]


def _build_kpis(calls, total):
    today = timezone.localdate()
    kpis = [
        {'label': 'Записей', 'value': total},
        {'label': 'За сегодня', 'value': calls.filter(calling_date=today).count()},
    ]
    if total <= DISTINCT_STATS_LIMIT:
        # Отдельными запросами: несколько COUNT(DISTINCT) в одном работают в разы медленнее
        for label, field in (('Уникальных Call ID', 'call_id'),
                             ('Отправителей', 'from_number'),
                             ('Получателей', 'to_number')):
            value = calls.order_by().aggregate(n=Count(field, distinct=True))['n']
            kpis.append({'label': label, 'value': value})
    return kpis


class _Echo:
    def write(self, value):
        return value


def _csv_value(call, key):
    if key == 'date':
        return call.calling_date.strftime('%d.%m.%Y') if call.calling_date else ''
    if key == 'time':
        return call.calling_time.strftime('%H:%M:%S') if call.calling_time else ''
    value = getattr(call, key)
    return '' if value is None else value


def _export_csv(calls, params):
    requested = [c for c in params.get('cols', '').split(',') if c in COLUMNS]
    keys = requested or list(COLUMNS)
    writer = csv.writer(_Echo(), delimiter=';')

    def rows():
        yield '﻿' + writer.writerow([COLUMNS[k][0] for k in keys])  # BOM для Excel
        for call in calls[:EXPORT_LIMIT].iterator():
            yield writer.writerow([_csv_value(call, k) for k in keys])

    filename = f'calls_{timezone.localtime():%Y%m%d_%H%M}.csv'
    response = StreamingHttpResponse(rows(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def call_list(request):
    params = request.GET
    sort = params.get('sort', '')
    direction = 'asc' if params.get('dir') == 'asc' else 'desc'

    filtered = _apply_filters(params)
    calls = _apply_ordering(filtered, sort, direction)

    if params.get('export') == 'csv':
        return _export_csv(calls, params)

    paginator = Paginator(calls, _per_page(params))
    page = paginator.get_page(params.get('page'))

    query_params = params.copy()
    query_params.pop('page', None)

    return render(request, 'calls/call_list.html', {
        'page': page,
        'page_range': paginator.get_elided_page_range(page.number, on_each_side=2, on_ends=1),
        'querystring': query_params.urlencode(),
        'columns': _build_columns(params, sort, direction),
        'sort': sort if sort in COLUMNS else '',
        'direction': direction,
        'export_url': _url(params, export='csv'),
        'kpis': _build_kpis(filtered, paginator.count),
        'chips': _build_chips(params),
        'periods': _build_periods(params),
        'filters': {key: params.get(key, '') for key in FILTER_LABELS},
        'per_page': paginator.per_page,
        'per_page_choices': PER_PAGE_CHOICES,
    })


def _call_to_dict(call):
    return {
        'id': call.id,
        'from_ip': call.from_ip or '',
        'to_ip': call.to_ip or '',
        'call_id': call.call_id or '',
        'from_number': call.from_number or '',
        'to_number': call.to_number or '',
        'date': call.calling_date.strftime('%d.%m.%Y') if call.calling_date else '',
        'time': call.calling_time.strftime('%H:%M:%S') if call.calling_time else '',
    }


def call_detail(request, pk):
    call = Call.objects.filter(pk=pk).first()
    if call is None:
        return JsonResponse({'error': 'Запись не найдена'}, status=404)

    same_call = []
    if call.call_id:
        same_call = Call.objects.filter(call_id=call.call_id).order_by(
            'calling_date', 'calling_time', 'id'
        )[:RELATED_LIMIT]

    between = []
    if call.from_number and call.to_number:
        a, b = call.from_number, call.to_number
        between = (
            Call.objects
            .filter(Q(from_number=a, to_number=b) | Q(from_number=b, to_number=a))
            .exclude(pk=call.pk)
            .order_by(*DEFAULT_ORDER)[:RELATED_LIMIT]
        )

    return JsonResponse({
        'call': _call_to_dict(call),
        'same_call': [_call_to_dict(c) for c in same_call],
        'between': [_call_to_dict(c) for c in between],
        'list_url': reverse('calls:call_list'),
    })

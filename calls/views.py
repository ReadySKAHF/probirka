from django.core.paginator import Paginator
from django.shortcuts import render

from .models import Call

TEXT_FILTERS = ('from_ip', 'to_ip', 'call_id', 'from_number', 'to_number')
PER_PAGE = 50


def call_list(request):
    calls = Call.objects.all()

    for field in TEXT_FILTERS:
        value = request.GET.get(field, '').strip()
        if value:
            calls = calls.filter(**{f'{field}__icontains': value})

    date_from = request.GET.get('date_from', '').strip()
    if date_from:
        calls = calls.filter(calling_date__gte=date_from)

    date_to = request.GET.get('date_to', '').strip()
    if date_to:
        calls = calls.filter(calling_date__lte=date_to)

    paginator = Paginator(calls, PER_PAGE)
    page = paginator.get_page(request.GET.get('page'))

    query_params = request.GET.copy()
    query_params.pop('page', None)

    return render(request, 'calls/call_list.html', {
        'page': page,
        'querystring': query_params.urlencode(),
        'filters': {
            'from_ip': request.GET.get('from_ip', ''),
            'to_ip': request.GET.get('to_ip', ''),
            'call_id': request.GET.get('call_id', ''),
            'from_number': request.GET.get('from_number', ''),
            'to_number': request.GET.get('to_number', ''),
            'date_from': date_from,
            'date_to': date_to,
        },
    })

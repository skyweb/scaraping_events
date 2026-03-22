"""
Views server-side per il report (sostituzione del frontend React).
Query dirette ai modelli Django, rendering template con paginazione.
"""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from etl.models import EtlRun, EtlError
from events.models import Event


def _build_query_string(request: HttpRequest, exclude: str = 'page') -> str:
    """Costruisce la query string dai parametri GET, escludendo 'page'."""
    params = request.GET.copy()
    params.pop(exclude, None)
    return params.urlencode()


@login_required
def report_dashboard(request: HttpRequest) -> HttpResponse:
    """Dashboard: statistiche aggregate, top città/sorgenti, ultimi ETL runs."""
    published = Event.objects.filter(status=Event.Status.PUBLISHED)
    counts = published.aggregate(
        total_events=Count('id'),
        active_events=Count('id', filter=Q(is_active=True)),
    )

    events_by_city = dict(
        published
        .values('city')
        .annotate(count=Count('id'))
        .order_by('-count')
        .values_list('city', 'count')[:10]
    )

    events_by_source = dict(
        published
        .values('source')
        .annotate(count=Count('id'))
        .values_list('source', 'count')
    )

    recent_runs = EtlRun.objects.all()[:5]
    staging_count = Event.objects.filter(status=Event.Status.STAGING).count()

    return render(request, 'report/dashboard.html', {
        'active_page': 'dashboard',
        'total_events': counts['total_events'],
        'active_events': counts['active_events'],
        'staging_count': staging_count,
        'cities_count': len(events_by_city),
        'events_by_city': events_by_city,
        'events_by_source': events_by_source,
        'recent_etl_runs': recent_runs,
    })


@login_required
def report_events(request: HttpRequest) -> HttpResponse:
    """Lista eventi pubblicati con filtri e paginazione."""
    qs = Event.objects.filter(status=Event.Status.PUBLISHED).order_by('-date_start')

    search = request.GET.get('search', '')
    selected_city = request.GET.get('city', '')
    selected_source = request.GET.get('source', '')
    selected_is_active = request.GET.get('is_active', '')

    if search:
        qs = qs.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(location_name__icontains=search)
        )
    if selected_city:
        qs = qs.filter(city=selected_city)
    if selected_source:
        qs = qs.filter(source=selected_source)
    if selected_is_active == 'true':
        qs = qs.filter(is_active=True)
    elif selected_is_active == 'false':
        qs = qs.filter(is_active=False)

    cities = (
        Event.objects.filter(status=Event.Status.PUBLISHED)
        .values('city')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    sources = (
        Event.objects.filter(status=Event.Status.PUBLISHED)
        .values('source')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'report/events.html', {
        'active_page': 'events',
        'page_obj': page_obj,
        'search': search,
        'selected_city': selected_city,
        'selected_source': selected_source,
        'selected_is_active': selected_is_active,
        'cities': cities,
        'sources': sources,
        'query_string': _build_query_string(request),
    })


@login_required
def report_etl_runs(request: HttpRequest) -> HttpResponse:
    """Lista ETL runs con filtro stato e paginazione."""
    qs = EtlRun.objects.all()

    selected_status = request.GET.get('status', '')
    if selected_status:
        qs = qs.filter(status=selected_status)

    # Calcola durata per ogni run
    runs = list(qs)
    for run in runs:
        if run.upsert_completed_at and run.started_at:
            run.duration = int((run.upsert_completed_at - run.started_at).total_seconds())
        else:
            run.duration = None

    paginator = Paginator(runs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'report/etl_runs.html', {
        'active_page': 'etl-runs',
        'page_obj': page_obj,
        'selected_status': selected_status,
        'query_string': _build_query_string(request),
    })


@login_required
def report_etl_errors(request: HttpRequest) -> HttpResponse:
    """Lista ETL errors con filtro tipo errore e paginazione."""
    qs = EtlError.objects.all()

    selected_error_type = request.GET.get('error_type', '')
    if selected_error_type:
        qs = qs.filter(error_type=selected_error_type)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'report/etl_errors.html', {
        'active_page': 'etl-errors',
        'page_obj': page_obj,
        'selected_error_type': selected_error_type,
        'query_string': _build_query_string(request),
    })
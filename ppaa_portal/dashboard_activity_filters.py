"""
Dashboard visibility for announcements, events, and todos (activities).

After a deadline (end_date on announcements/events, due_date on todos), items
remain visible through the next whole calendar day in the active Django
timezone, then drop from dashboard aggregates (see InternalPortalDashboardSummary
and PublicPpaaDashboardView).
"""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone


def portal_dashboard_deadline_grace_q(deadline_field: str, *, today=None) -> Q:
    """
    Include rows with no deadline, OR whose deadline *calendar date* is still
    within the grace window (visible through the day after the deadline).

    For a DateTimeField ``deadline_field``, uses the ``__date`` transform.
    """
    d = today if today is not None else timezone.localdate()
    min_deadline_date = d - timedelta(days=1)
    return Q(**{f"{deadline_field}__isnull": True}) | Q(
        **{f"{deadline_field}__date__gte": min_deadline_date}
    )

"""Queue helper functions."""
from django.db import transaction
from django.db.models import F, Max


def next_token_number(branch, token_date):
    """
    Return the next token number for ONE branch on ONE date.

    The running number is stored in the Queue table (branch + date).
    The increment is a single SQL UPDATE (F expression), so two bookings
    made at the same moment can never get the same number.
    """
    from .models import Queue, Token

    with transaction.atomic():
        queue = (
            Queue.objects.select_for_update()
            .filter(branch=branch, date=token_date)
            .order_by("id")
            .first()
        )
        # Never go below tokens that already exist (covers old data)
        existing_max = (
            Token.objects.filter(branch=branch, token_date=token_date)
            .aggregate(m=Max("token_number"))["m"] or 0
        )
        if queue is None:
            queue = Queue.objects.create(
                branch=branch, date=token_date, last_token_number=existing_max
            )
        elif queue.last_token_number < existing_max:
            Queue.objects.filter(pk=queue.pk).update(last_token_number=existing_max)

        Queue.objects.filter(pk=queue.pk).update(
            last_token_number=F("last_token_number") + 1
        )
        queue.refresh_from_db(fields=["last_token_number"])
        return queue.last_token_number


def calculate_service_time(services):
    return sum(service.average_time_minutes for service in services)

from typing import Type
from datetime import datetime

from django.db import models
from django.utils.timezone import make_aware
from django.http import HttpRequest
import pytz


def bulk_sync(ModelType: Type[models.Model], delete: bool = False):
    """Log output for sync, with number of added, updated and deleted models."""

    def outer(syncfunc):
        def inner(cursor):
            ids_to_delete = set(ModelType.objects.values_list("pk", flat=True))
            n_added, n_updated = 0, 0
            for result in syncfunc(cursor):
                create_defaults = None
                if len(result) == 2:
                    update_defaults, kwargs = result
                else:
                    update_defaults, create_defaults, kwargs = result
                model, created = ModelType.objects.update_or_create(
                    defaults=update_defaults, create_defaults=create_defaults, **kwargs
                )
                if created:
                    n_added += 1
                else:
                    n_updated += 1
                ids_to_delete.discard(model.pk)
            n_deleted = 0
            if delete:
                n_deleted, _ = ModelType.objects.filter(pk__in=ids_to_delete).delete()
            print(
                f"Updated {ModelType.__name__:>12} models "
                f"({n_added} created, {n_updated} updated, {n_deleted} deleted)"
            )

        return inner

    return outer


def aware_timestamp(v: int) -> datetime:
    """Generate an aware datetime from epoch timestamp."""
    return make_aware(datetime.fromtimestamp(v / 1e3), pytz.UTC)


def get_src_ip(request: HttpRequest) -> str:
    """Get source IP address."""
    # From https://stackoverflow.com/q/4581789/7337283
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[-1]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def mem_kb_to_bytes(mem: str) -> int:
    """Convert kB memory string to bytes integer."""
    try:
        return int(mem.replace(r"\s*(kb|kB)", "")) * 1024
    except ValueError:
        return -1

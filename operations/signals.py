import json

from django.core.serializers.json import DjangoJSONEncoder
from django.forms.models import model_to_dict
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AIUsageRecord, AuditLog, DailyProgressEntry


def _json_ready_model(instance):
    return json.loads(json.dumps(model_to_dict(instance), cls=DjangoJSONEncoder))


@receiver(post_save, sender=DailyProgressEntry)
def audit_daily_log(sender, instance, created, **kwargs):
    if not created:
        return
    actor = instance.created_by
    if not actor:
        return
    AuditLog.objects.create(
        entity_type="DailyProgressEntry",
        entity_id=instance.id,
        action_type="create",
        actor=actor,
        old_value_json={},
        new_value_json=_json_ready_model(instance),
    )


@receiver(post_save, sender=AIUsageRecord)
def audit_ai_usage(sender, instance, created, **kwargs):
    if not created:
        return
    actor = instance.entry.updated_by
    if not actor:
        return
    AuditLog.objects.create(
        entity_type="AIUsageRecord",
        entity_id=instance.id,
        action_type="create",
        actor=actor,
        old_value_json={},
        new_value_json=_json_ready_model(instance),
    )

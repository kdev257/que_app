"""Automatic processing logs for key events."""
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver

from .services import log_processing


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    log_processing("login", request, actor=user, subject_user=user)


def connect_model_signals():
    from billing.models import Invoice
    from login.models import User
    from queues.models import Token

    @receiver(post_save, sender=User, weak=False, dispatch_uid="privacy_user_created")
    def on_user_created(sender, instance, created, **kwargs):
        if created:
            log_processing("register", subject_user=instance)

    @receiver(post_save, sender=Token, weak=False, dispatch_uid="privacy_token_created")
    def on_token_created(sender, instance, created, **kwargs):
        if created:
            log_processing("booking", subject_user=instance.user, subject_guest=instance.guest, obj=instance)

    @receiver(post_save, sender=Invoice, weak=False, dispatch_uid="privacy_invoice_created")
    def on_invoice_created(sender, instance, created, **kwargs):
        if created:
            log_processing("invoice_created", actor=instance.created_by, subject_user=instance.customer_user,
                           subject_guest=instance.customer_guest, obj=instance)

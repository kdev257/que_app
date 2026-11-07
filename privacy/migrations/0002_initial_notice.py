from django.db import migrations

NOTICE_V1 = """## Who we are
QuickQueue ("we") helps you book services and restaurant orders and skip the queue. We decide how your personal data is used, so we are the Data Fiduciary under India's Digital Personal Data Protection Act, 2023.

## What data we collect
- Your name, email address and mobile number
- Your PIN code, and address (only if you give it in your profile or for home delivery)
- Your profile photo (only if you upload one)
- Your bookings, orders, tokens, invoices and payment status
- Payment reference numbers from Razorpay (we never see or store your card or UPI details)
- Technical details such as IP address and login time, for security

## Why we use it
- To create and manage your bookings, tokens and food orders
- To show nearby branches using your PIN code
- To send booking confirmations, queue updates, order updates and invoices by email
- To take payments through Razorpay
- To keep our service safe and to meet legal duties (for example tax invoices)

## Who we share it with
- The branch or restaurant you book with (your name, phone and booking details)
- Razorpay, for online payments
- Our email service provider, to send emails
We do not sell your data.

## How long we keep it
We keep your data while you use QuickQueue. If you do not use it for 1 year, we email you at least 48 hours before deleting it. Invoices are kept as long as tax law requires. Security logs are kept for at least 1 year, as required by law.

## Your rights
- See a summary of your data and download it
- Correct or update your data
- Withdraw your consent at any time (this is as easy as giving it). After this we stop using your data and delete it as explained above.
- Ask us to delete your data
- Nominate a person to use your rights if you die or cannot act
- Make a complaint to us. We reply within 90 days.
- If you are not happy with our reply, you can complain to the Data Protection Board of India.
Use the "My Data & Privacy" page or contact us (details below).

## Children
QuickQueue is only for people aged 18 and above. Please do not use it if you are under 18."""


def create_notice(apps, schema_editor):
    PrivacyNotice = apps.get_model("privacy", "PrivacyNotice")
    if not PrivacyNotice.objects.exists():
        PrivacyNotice.objects.create(version="1.0", title="Privacy Notice", body=NOTICE_V1, is_current=True)


def remove_notice(apps, schema_editor):
    apps.get_model("privacy", "PrivacyNotice").objects.filter(version="1.0").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('privacy', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_notice, remove_notice),
    ]

"""
restaurants/emails.py
Email notification helpers for the restaurant pre-order flow.

Triggers:
  1. send_order_placed_email       - Customer places a pre-order (pending confirmation)
  2. send_order_accepted_email     - Kitchen accepts the order (redirect to payment)
  3. send_order_rejected_email     - Kitchen rejects the order
  4. send_payment_confirmed_email  - Payment successful, kitchen is cooking
  5. send_order_ready_email        - Food is ready for pickup / dine-in
  6. send_new_order_kitchen_email  - Internal alert to branch/kitchen email on new order
"""

from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_recipient(order):
    """Returns (name, email) tuple for logged-in user or guest, or (None, None)."""
    token = order.token
    if token.user and token.user.email:
        name = token.user.first_name or token.user.username
        return name, token.user.email
    elif token.guest and token.guest.email:
        return token.guest.name, token.guest.email
    return None, None


def _send(subject, text_body, html_body, recipient_email):
    """Send an HTML email with plain-text fallback. Silently ignores errors."""
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.EMAIL_HOST_USER,
            to=[recipient_email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)  # Set to False so exceptions are caught in try-except block
    except Exception as e:
        import sys
        print(f"\n[SMTP ERROR] Failed to send email to {recipient_email}: {e}\n", file=sys.stderr)
        pass  # Never let email failure break the order flow


def _base_html(title, body_html, color="#0d6efd"):
    """Wraps content in a minimal branded HTML email shell."""
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f6f8;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table width="600" cellpadding="0" cellspacing="0"
               style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 16px rgba(0,0,0,0.08);">
          <!-- Header -->
          <tr>
            <td style="background:{color};padding:28px 32px;text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;">🍽️ QuickQueue Restaurant</h1>
              <p style="margin:6px 0 0;color:rgba(255,255,255,0.8);font-size:14px;">{title}</p>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:32px;">
              {body_html}
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background:#f8f9fa;padding:20px 32px;text-align:center;
                       border-top:1px solid #e9ecef;">
              <p style="margin:0;color:#6c757d;font-size:12px;">
                QuickQueue &nbsp;|&nbsp; Skip the wait, enjoy the meal<br>
                This is an automated notification. Please do not reply.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def _order_summary_html(order):
    """Renders the order items as an HTML table snippet."""
    rows = ""
    for item in order.items.all():
        rows += f"""
        <tr>
          <td style="padding:8px 0;border-bottom:1px solid #f0f0f0;color:#333;">{item.menu_item.name}</td>
          <td style="padding:8px 0;border-bottom:1px solid #f0f0f0;color:#666;text-align:center;">x{item.quantity}</td>
          <td style="padding:8px 0;border-bottom:1px solid #f0f0f0;color:#333;text-align:right;">₹{item.price * item.quantity}</td>
        </tr>"""
    total = sum(item.price * item.quantity for item in order.items.all())
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0"
           style="margin:16px 0;border:1px solid #e9ecef;border-radius:8px;overflow:hidden;">
      <thead>
        <tr style="background:#f8f9fa;">
          <th style="padding:10px 12px;text-align:left;font-size:13px;color:#495057;">Item</th>
          <th style="padding:10px 12px;text-align:center;font-size:13px;color:#495057;">Qty</th>
          <th style="padding:10px 12px;text-align:right;font-size:13px;color:#495057;">Price</th>
        </tr>
      </thead>
      <tbody style="padding:0 12px;">
        {rows}
      </tbody>
      <tfoot>
        <tr style="background:#f8f9fa;">
          <td colspan="2" style="padding:10px 12px;font-weight:700;color:#333;">Total</td>
          <td style="padding:10px 12px;font-weight:700;color:#0d6efd;text-align:right;">₹{total}</td>
        </tr>
      </tfoot>
    </table>"""


def _info_row(label, value, color="#495057"):
    return f"""
    <tr>
      <td style="padding:6px 0;font-size:14px;color:#6c757d;width:45%;">{label}</td>
      <td style="padding:6px 0;font-size:14px;font-weight:600;color:{color};">{value}</td>
    </tr>"""


# ---------------------------------------------------------------------------
# 1. Order Placed (pending confirmation)
# ---------------------------------------------------------------------------
def send_order_placed_email(order):
    name, email = _get_recipient(order)
    if not email:
        return

    table_info = f"Table {order.table.table_number}" if order.table else "Auto-assigned"
    arrival_info = f"~{order.minutes_until_arrival} minutes" if order.minutes_until_arrival else "Not specified"

    subject = f"Pre-Order Received – Token #{order.token.token_number} | {order.branch.name}"

    text_body = f"""Hi {name},

Your pre-order at {order.branch.name} has been received!

Token Number : #{order.token.token_number}
Order Type   : {order.get_order_type_display()}
Table        : {table_info}
Arriving In  : {arrival_info}
Status       : Waiting for kitchen confirmation

The kitchen will review your order shortly. You'll receive another email once it's confirmed or if there's an update.

Thank you for using QuickQueue!
"""

    body_html = f"""
    <p style="font-size:16px;color:#333;">Hi <strong>{name}</strong>,</p>
    <p style="color:#555;margin:0 0 16px;">
      Your pre-order at <strong>{order.branch.name}</strong> has been received and is
      <span style="color:#f59e0b;font-weight:600;">waiting for kitchen confirmation</span>.
      You'll be notified as soon as the kitchen responds.
    </p>

    <div style="background:#fff8e1;border:1px solid #ffe082;border-radius:8px;padding:16px;margin:16px 0;">
      <table width="100%">
        {_info_row("Token Number", f"#{order.token.token_number}", "#0d6efd")}
        {_info_row("Restaurant", order.branch.name)}
        {_info_row("Order Type", order.get_order_type_display())}
        {_info_row("Table", table_info)}
        {_info_row("Arriving In", arrival_info)}
      </table>
    </div>

    <p style="font-size:14px;color:#555;margin:16px 0 8px;font-weight:600;">Your Order:</p>
    {_order_summary_html(order)}

    <p style="font-size:13px;color:#6c757d;margin-top:16px;">
      ⚠️ This is a pre-order confirmation. Payment will only be required after kitchen acceptance.
    </p>
"""

    _send(subject, text_body, _base_html("Pre-Order Received", body_html, "#f59e0b"), email)


# ---------------------------------------------------------------------------
# 2. Order Accepted by Kitchen (redirect to payment)
# ---------------------------------------------------------------------------
def send_order_accepted_email(order):
    name, email = _get_recipient(order)
    if not email:
        return

    prep_time = order.estimated_prep_time_minutes or "N/A"
    table_info = f"Table {order.table.table_number}" if order.table else "To be assigned"

    if order.token.payment_status == 'pay_at_home':
        subject = f"Order Accepted & Preparing | {order.branch.name}"
        address_info = order.delivery_address or "—"
        
        text_body = f"""Hi {name},

Great news! The kitchen at {order.branch.name} has accepted your order and started preparing it.

Token Number    : #{order.token.token_number}
Prep Time       : ~{prep_time} minutes
Delivery Address: {address_info}
Payment Status  : Pay at Home (Cash/Card on Delivery)

Thank you for using QuickQueue!
"""

        body_html = f"""
        <p style="font-size:16px;color:#333;">Hi <strong>{name}</strong>, great news! 🎉</p>
        <p style="color:#555;margin:0 0 16px;">
          The kitchen at <strong>{order.branch.name}</strong> has
          <span style="color:#10b981;font-weight:600;">accepted your order</span> and started preparing it.
        </p>

        <div style="background:#e8f5e9;border:1px solid #a5d6a7;border-radius:8px;padding:16px;margin:16px 0;">
          <table width="100%">
            {_info_row("Token Number", f"#{order.token.token_number}", "#0d6efd")}
            {_info_row("Restaurant", order.branch.name)}
            {_info_row("Estimated Prep Time", f"~{prep_time} minutes")}
            {_info_row("Delivery Address", address_info)}
            {_info_row("Payment Method", "Pay at Home (Cash/Card on Delivery)")}
          </table>
        </div>

        <p style="font-size:14px;color:#555;">
          You can track your order status in the QuickQueue app.
        </p>
    """
    else:
        subject = f"Order Accepted – Please Complete Payment | {order.branch.name}"

        text_body = f"""Hi {name},

Great news! The kitchen at {order.branch.name} has accepted your pre-order.

Token Number  : #{order.token.token_number}
Prep Time     : ~{prep_time} minutes
Table         : {table_info}

ACTION REQUIRED: Please complete your payment to confirm the order.
Note: Restaurant orders are non-refundable once payment is made.

Thank you for using QuickQueue!
"""

        body_html = f"""
        <p style="font-size:16px;color:#333;">Hi <strong>{name}</strong>, great news! 🎉</p>
        <p style="color:#555;margin:0 0 16px;">
          The kitchen at <strong>{order.branch.name}</strong> has
          <span style="color:#10b981;font-weight:600;">accepted your pre-order</span>.
          Please complete your payment to lock in your order.
        </p>

        <div style="background:#e8f5e9;border:1px solid #a5d6a7;border-radius:8px;padding:16px;margin:16px 0;">
          <table width="100%">
            {_info_row("Token Number", f"#{order.token.token_number}", "#0d6efd")}
            {_info_row("Restaurant", order.branch.name)}
            {_info_row("Estimated Prep Time", f"~{prep_time} minutes")}
            {_info_row("Table", table_info)}
          </table>
        </div>

        <p style="font-size:13px;color:#dc3545;margin:16px 0;padding:12px;
                  background:#ffeaea;border-radius:8px;border:1px solid #f5c6cb;">
          ⚠️ <strong>Important:</strong> Restaurant pre-orders are <strong>non-refundable</strong>
          once payment is completed. Please ensure your order is correct before paying.
        </p>

        <p style="font-size:14px;color:#555;">
          Please open the QuickQueue app to complete your payment and finalize the order.
        </p>
    """

    _send(subject, text_body, _base_html("Order Accepted ✓", body_html, "#10b981"), email)


# ---------------------------------------------------------------------------
# 3. Order Rejected by Kitchen
# ---------------------------------------------------------------------------
def send_order_rejected_email(order):
    name, email = _get_recipient(order)
    if not email:
        return

    reason = order.rejection_reason or "Kitchen is currently unable to fulfill the order"
    subject = f"Order Update – Unable to Confirm | {order.branch.name}"

    text_body = f"""Hi {name},

We're sorry to inform you that the kitchen at {order.branch.name} was unable to accept your pre-order.

Token Number : #{order.token.token_number}
Reason       : {reason}

No payment has been charged. Please try ordering again or visit another restaurant.

We apologize for the inconvenience.

QuickQueue Team
"""

    body_html = f"""
    <p style="font-size:16px;color:#333;">Hi <strong>{name}</strong>,</p>
    <p style="color:#555;margin:0 0 16px;">
      We're sorry — the kitchen at <strong>{order.branch.name}</strong> was unable to
      confirm your pre-order at this time.
    </p>

    <div style="background:#ffeaea;border:1px solid #f5c6cb;border-radius:8px;padding:16px;margin:16px 0;">
      <table width="100%">
        {_info_row("Token Number", f"#{order.token.token_number}")}
        {_info_row("Restaurant", order.branch.name)}
        {_info_row("Reason", reason, "#dc3545")}
      </table>
    </div>

    <p style="color:#555;margin:16px 0;">
      ✅ <strong>No payment has been charged.</strong> You are free to place a new order
      or try a different restaurant.
    </p>

    <p style="font-size:13px;color:#6c757d;">
      We apologize for the inconvenience. Thank you for your understanding.
    </p>
"""

    _send(subject, text_body, _base_html("Order Declined", body_html, "#dc3545"), email)


# ---------------------------------------------------------------------------
# 4. Payment Confirmed – Kitchen is Cooking
# ---------------------------------------------------------------------------
def send_payment_confirmed_email(order):
    name, email = _get_recipient(order)
    if not email:
        return

    prep_time = order.estimated_prep_time_minutes or "N/A"
    table_info = f"Table {order.table.table_number}" if order.table else "—"
    subject = f"Payment Confirmed – Kitchen is Cooking! | {order.branch.name}"

    text_body = f"""Hi {name},

Your payment has been confirmed and the kitchen is now preparing your order!

Token Number  : #{order.token.token_number}
Restaurant    : {order.branch.name}
Table         : {table_info}
Estimated Prep: ~{prep_time} minutes

You will be notified when your order is ready. No need to stand in line!

Thank you for using QuickQueue!
"""

    body_html = f"""
    <p style="font-size:16px;color:#333;">Hi <strong>{name}</strong>! 🔥</p>
    <p style="color:#555;margin:0 0 16px;">
      Your payment is confirmed and the kitchen at
      <strong>{order.branch.name}</strong> is now
      <span style="color:#3b82f6;font-weight:600;">preparing your order</span>.
    </p>

    <div style="background:#e3f2fd;border:1px solid #90caf9;border-radius:8px;padding:16px;margin:16px 0;">
      <table width="100%">
        {_info_row("Token Number", f"#{order.token.token_number}", "#0d6efd")}
        {_info_row("Restaurant", order.branch.name)}
        {_info_row("Table", table_info)}
        {_info_row("Estimated Prep Time", f"~{prep_time} minutes")}
      </table>
    </div>

    <p style="font-size:14px;color:#555;margin:16px 0;">
      🎉 Sit back and relax — you'll get another notification when your order is ready.
      No need to wait at the counter!
    </p>

    <p style="font-size:14px;color:#555;margin:16px 0;">
      Your Order:
    </p>
    {_order_summary_html(order)}
"""

    _send(subject, text_body, _base_html("Payment Confirmed 🔥", body_html, "#3b82f6"), email)


# ---------------------------------------------------------------------------
# 5. Order Ready for Pickup / Dine-In
# ---------------------------------------------------------------------------
def send_order_ready_email(order):
    name, email = _get_recipient(order)
    if not email:
        return

    if order.order_type == 'dine_in' and order.table:
        pickup_msg = f"Please proceed to Table {order.table.table_number}."
        pickup_html = f"Please proceed to <strong>Table {order.table.table_number}</strong>."
    elif order.order_type == 'dine_in':
        pickup_msg = "Please proceed to your assigned table."
        pickup_html = "Please proceed to your assigned table."
    else:
        pickup_msg = "Please collect your order at the pickup counter."
        pickup_html = "Please collect your order at the <strong>Pickup Counter</strong>."

    subject = f"Your Order is Ready! 🍽️ | {order.branch.name}"

    text_body = f"""Hi {name},

Your order at {order.branch.name} is READY!

Token Number : #{order.token.token_number}
{pickup_msg}

Enjoy your meal!

QuickQueue Team
"""

    body_html = f"""
    <div style="text-align:center;margin-bottom:24px;">
      <div style="font-size:64px;">🍽️</div>
      <h2 style="color:#10b981;margin:8px 0;">Your Order is Ready!</h2>
    </div>

    <p style="font-size:16px;color:#333;text-align:center;">Hi <strong>{name}</strong>!</p>
    <p style="color:#555;margin:0 0 16px;text-align:center;">
      Your order at <strong>{order.branch.name}</strong> is freshly prepared and ready for you.
    </p>

    <div style="background:#e8f5e9;border:1px solid #a5d6a7;border-radius:8px;
                padding:20px;margin:16px 0;text-align:center;">
      <p style="font-size:18px;font-weight:700;color:#10b981;margin:0;">
        Token #{order.token.token_number}
      </p>
      <p style="font-size:15px;color:#555;margin:8px 0 0;">{pickup_html}</p>
    </div>

    <p style="font-size:16px;color:#555;text-align:center;margin-top:24px;">
      😊 Enjoy your meal! Thank you for dining with us.
    </p>
"""

    _send(subject, text_body, _base_html("Order Ready! 🍽️", body_html, "#10b981"), email)


# ---------------------------------------------------------------------------
# 6. New Order Alert to Kitchen / Branch
# ---------------------------------------------------------------------------
def send_new_order_kitchen_email(order):
    """
    Sends an alert to the branch's organisation email when a new pre-order arrives.
    Uses branch.organization.email as the kitchen alert destination.
    """
    try:
        kitchen_email = order.branch.organization.email
    except Exception:
        return

    if not kitchen_email:
        return

    arrival_info = f"~{order.minutes_until_arrival} minutes" if order.minutes_until_arrival else "Not specified"
    table_info = f"Table {order.table.table_number}" if order.table else "Auto-assign"

    subject = f"🆕 New Pre-Order – Token #{order.token.token_number} | {order.branch.name}"

    text_body = f"""New Pre-Order Alert

A new pre-order has been placed at {order.branch.name}.

Customer     : {order.customer_name}
Phone        : {order.customer_phone or 'N/A'}
Token Number : #{order.token.token_number}
Order Type   : {order.get_order_type_display()}
Table        : {table_info}
Arriving In  : {arrival_info}

Items:
{chr(10).join(f"  - {item.quantity}x {item.menu_item.name}" for item in order.items.all())}

Please log in to the Kitchen Dashboard to Accept or Reject this order.
"""

    items_html = "".join(
        f"<li style='padding:4px 0;color:#333;'>{item.quantity}x <strong>{item.menu_item.name}</strong></li>"
        for item in order.items.all()
    )

    body_html = f"""
    <div style="background:#fff3cd;border:1px solid #ffc107;border-radius:8px;
                padding:12px 16px;margin-bottom:20px;">
      <strong style="color:#856404;">🆕 New Pre-Order Received</strong>
    </div>

    <div style="background:#f8f9fa;border-radius:8px;padding:16px;margin:16px 0;">
      <table width="100%">
        {_info_row("Customer", order.customer_name)}
        {_info_row("Phone", order.customer_phone or "N/A")}
        {_info_row("Token Number", f"#{order.token.token_number}", "#0d6efd")}
        {_info_row("Order Type", order.get_order_type_display())}
        {_info_row("Table", table_info)}
        {_info_row("Arriving In", arrival_info, "#f59e0b")}
      </table>
    </div>

    <p style="font-size:14px;color:#555;font-weight:600;margin:16px 0 8px;">Order Items:</p>
    <ul style="margin:0;padding-left:20px;">
      {items_html}
    </ul>

    <p style="font-size:14px;color:#555;margin-top:20px;padding:12px;
              background:#e3f2fd;border-radius:8px;border:1px solid #90caf9;">
      📋 Please log in to the <strong>Kitchen Dashboard</strong> to
      <strong>Accept</strong> or <strong>Reject</strong> this order.
    </p>
"""

    _send(subject, text_body, _base_html("New Pre-Order Alert", body_html, "#f59e0b"), kitchen_email)

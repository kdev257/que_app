from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from queues.models import Token
from queues.views import get_guest
from .forms import ReviewForm
from .models import Review
from .services import can_edit, public_name, token_id_from_key, update_branch_rating


def _owner(request, token):
    """Return (user, guest) if the visitor owns this token (or has the signed email link), else (None, None)."""
    key = request.GET.get("k") or request.POST.get("k")
    if key and token_id_from_key(key) == token.id and (token.user_id or token.guest_id):
        return token.user, token.guest
    if request.user.is_authenticated and token.user_id == request.user.id:
        return request.user, None
    guest = get_guest(request) if not request.user.is_authenticated else None
    if guest is not None and token.guest_id == guest.id:
        return None, guest
    return None, None


def rate_visit(request, token_id):
    token = get_object_or_404(Token.objects.select_related("branch"), id=token_id)
    user, guest = _owner(request, token)
    if user is None and guest is None:
        messages.error(request, "You can only rate your own visits.")
        return redirect("index")
    if token.status != "completed":
        messages.error(request, "You can rate a visit after it is completed.")
        return redirect("index")

    review = Review.objects.filter(token=token).first()
    if review and not can_edit(review):
        messages.info(request, "Reviews can be changed only within 7 days.")
        return render(request, "reviews/rate.html", {"token": token, "review": review, "form": None})

    if request.method == "POST":
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.pk is None:
                obj.token, obj.branch, obj.user, obj.guest = token, token.branch, user, guest
                obj.display_name = public_name(user=user, guest=guest)
            obj.save()
            update_branch_rating(token.branch)
            messages.success(request, "Thank you for your rating!")
            return redirect("index")
    else:
        form = ReviewForm(instance=review)
    return render(request, "reviews/rate.html", {"token": token, "review": review, "form": form})


def branch_reviews(request, branch_id):
    """Public list of reviews for a branch."""
    from organization.models import Branch
    branch = get_object_or_404(Branch, id=branch_id, is_approved=True)
    reviews = Review.objects.filter(branch=branch, is_hidden=False)[:100]
    return render(request, "reviews/branch_reviews.html", {"branch": branch, "reviews": reviews})

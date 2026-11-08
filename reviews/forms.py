from django import forms

from .models import Review


class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=[(i, str(i)) for i in range(5, 0, -1)], coerce=int, widget=forms.RadioSelect,
        error_messages={"required": "Please choose a star rating."},
    )
    tags = forms.MultipleChoiceField(choices=Review.TAG_CHOICES, required=False, widget=forms.CheckboxSelectMultiple,
                                     label="What did you like? (optional)")

    class Meta:
        model = Review
        fields = ["rating", "tags", "comment"]
        labels = {"comment": "Comment (optional)"}
        widgets = {"comment": forms.Textarea(attrs={"rows": 3, "maxlength": 1000,
                                                     "placeholder": "Tell others about your visit"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.tags:
            self.initial["tags"] = self.instance.tags.split(",")

    def clean_tags(self):
        return ",".join(self.cleaned_data.get("tags") or [])


class ReplyForm(forms.Form):
    reply = forms.CharField(widget=forms.Textarea(attrs={"rows": 2, "maxlength": 1000}), max_length=1000,
                            label="Your reply")

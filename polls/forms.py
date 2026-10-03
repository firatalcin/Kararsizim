from django import forms
from django.forms import BaseFormSet, formset_factory

from .models import MAX_OPTIONS, MIN_OPTIONS, Poll


class PollForm(forms.ModelForm):
    class Meta:
        model = Poll
        fields = ("question", "description")
        labels = {"question": "Soru", "description": "Açıklama (isteğe bağlı)"}
        help_texts = {"description": "Kısa bir bağlam: “Hava yağmurlu, bütçem kısıtlı” gibi."}
        widgets = {
            "question": forms.TextInput(attrs={"placeholder": "Bu akşam sinema mı, restoran mı?", "autofocus": True}),
            "description": forms.Textarea(attrs={"rows": 2}),
        }
        error_messages = {"question": {"required": "Bir soru yazmalısın."}}


class OptionForm(forms.Form):
    # Not required: completely empty rows are ignored; the formset enforces the 2–5 count.
    text = forms.CharField(label="Seçenek", max_length=80, required=False)


class BaseOptionFormSet(BaseFormSet):
    default_error_messages = {
        "too_few_forms": "En az %(num)d seçenek yazmalısın.",
        "too_many_forms": "En fazla %(num)d seçenek ekleyebilirsin.",
    }

    def add_fields(self, form, index):
        super().add_fields(form, index)
        if index is not None:
            form.fields["text"].widget.attrs["placeholder"] = f"{index + 1}. seçenek"

    def clean(self):
        if any(self.errors):
            return
        texts = self.option_texts()
        if len(texts) < MIN_OPTIONS:
            raise forms.ValidationError(self.error_messages["too_few_forms"] % {"num": MIN_OPTIONS})
        seen = set()
        for text in texts:
            key = text.casefold()
            if key in seen:
                raise forms.ValidationError("Aynı seçeneği iki kez yazmışsın.")
            seen.add(key)

    def option_texts(self):
        """Filled-in option texts in display order (blank rows dropped)."""
        return [text for form in self.forms if (text := form.cleaned_data.get("text"))]


OptionFormSet = formset_factory(
    OptionForm,
    formset=BaseOptionFormSet,
    extra=0,
    min_num=MIN_OPTIONS,
    max_num=MAX_OPTIONS,
    validate_min=True,
    validate_max=True,
)

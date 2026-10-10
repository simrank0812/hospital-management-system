from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    Appointment,
    ConsultationNote,
    Department,
    Doctor,
    DoctorSchedule,
    Invoice,
    Patient,
    Prescription,
)


class BootstrapFormMixin:
    """Adds Bootstrap 5 CSS classes to every widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            existing = widget.attrs.get("class", "")
            if isinstance(widget, forms.CheckboxInput):
                css = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                css = "form-select"
            elif isinstance(widget, forms.RadioSelect):
                continue
            else:
                css = "form-control"
            widget.attrs["class"] = f"{existing} {css}".strip()


class StyledAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    pass


class PatientRegistrationForm(BootstrapFormMixin, UserCreationForm):
    first_name = forms.CharField(max_length=60)
    last_name = forms.CharField(max_length=60)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20)
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    gender = forms.ChoiceField(choices=Patient.GENDER_CHOICES)
    blood_group = forms.ChoiceField(choices=[("", "Not sure")] + Patient.BLOOD_CHOICES, required=False)
    address = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "username", "email")

    def clean_date_of_birth(self):
        dob = self.cleaned_data["date_of_birth"]
        if dob > timezone.localdate():
            raise ValidationError("Date of birth cannot be in the future.")
        return dob

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.save()
        Patient.objects.create(
            user=user,
            phone=self.cleaned_data["phone"],
            date_of_birth=self.cleaned_data["date_of_birth"],
            gender=self.cleaned_data["gender"],
            blood_group=self.cleaned_data["blood_group"],
            address=self.cleaned_data["address"],
        )
        return user


class UserNameForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]


class PatientProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Patient
        fields = ["phone", "date_of_birth", "gender", "blood_group", "address", "emergency_contact"]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "address": forms.Textarea(attrs={"rows": 2}),
        }


class AppointmentForm(BootstrapFormMixin, forms.ModelForm):
    # The options of this select are filled in by JavaScript (static/js/main.js)
    time = forms.TimeField(
        input_formats=["%H:%M", "%H:%M:%S"],
        widget=forms.Select(choices=[("", "Choose a doctor and date first")]),
    )

    class Meta:
        model = Appointment
        fields = ["doctor", "date", "time", "reason"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "reason": forms.Textarea(attrs={"rows": 3, "placeholder": "For example: chest pain after walking, lasting 3 days"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["doctor"].queryset = Doctor.objects.filter(is_available=True).select_related(
            "user", "department"
        )
        self.fields["doctor"].label_from_instance = lambda d: f"{d.full_name} - {d.department.name}"
        self.fields["doctor"].empty_label = "Select a doctor"

    def clean(self):
        cleaned = super().clean()
        doctor, day, slot = cleaned.get("doctor"), cleaned.get("date"), cleaned.get("time")
        if doctor and day and slot:
            if day < timezone.localdate():
                self.add_error("date", "Pick today or a later date.")
            elif slot not in doctor.available_slots(day):
                self.add_error("time", "That time is not available any more. Please pick another slot.")
        return cleaned


class DoctorScheduleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DoctorSchedule
        fields = ["weekday", "start_time", "end_time", "slot_minutes"]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "end_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def __init__(self, *args, doctor=None, **kwargs):
        self.doctor = doctor
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        start, end, weekday = cleaned.get("start_time"), cleaned.get("end_time"), cleaned.get("weekday")
        if start and end:
            if end <= start:
                raise ValidationError("End time must be after the start time.")
            if self.doctor is not None and weekday is not None:
                overlap = DoctorSchedule.objects.filter(
                    doctor=self.doctor, weekday=weekday, start_time__lt=end, end_time__gt=start
                ).exists()
                if overlap:
                    raise ValidationError("This overlaps with a time block you already have on that day.")
        return cleaned


class ConsultationNoteForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ConsultationNote
        fields = ["diagnosis", "notes", "follow_up_date"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
            "follow_up_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }


class PrescriptionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ["medicine", "dosage", "frequency", "duration", "instructions"]


class DepartmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "description", "icon"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class DoctorForm(BootstrapFormMixin, forms.ModelForm):
    """Creates / edits a doctor together with the login account."""

    first_name = forms.CharField(max_length=60)
    last_name = forms.CharField(max_length=60)
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    password = forms.CharField(widget=forms.PasswordInput(render_value=False), required=False)

    field_order = [
        "first_name", "last_name", "username", "email", "password",
        "department", "specialization", "qualification", "experience_years",
        "consultation_fee", "phone", "bio", "is_available",
    ]

    class Meta:
        model = Doctor
        fields = [
            "department", "specialization", "qualification", "experience_years",
            "consultation_fee", "phone", "bio", "is_available",
        ]
        widgets = {"bio": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            user = self.instance.user
            self.initial.update(
                {
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "username": user.username,
                    "email": user.email,
                }
            )
            self.fields["password"].help_text = "Leave blank to keep the current password."
        else:
            self.fields["password"].required = True
            self.fields["password"].help_text = "The doctor can use this to log in."

    def clean_username(self):
        username = self.cleaned_data["username"]
        existing = User.objects.filter(username__iexact=username)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.user_id)
        if existing.exists():
            raise ValidationError("This username is already taken.")
        return username

    def save(self, commit=True):
        doctor = super().save(commit=False)
        user = doctor.user if doctor.pk else User()
        user.username = self.cleaned_data["username"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)
        user.save()
        doctor.user = user
        doctor.save()
        return doctor


class InvoiceForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["consultation_fee", "medicine_charges", "other_charges", "is_paid"]

    def save(self, commit=True):
        invoice = super().save(commit=False)
        if invoice.is_paid and not invoice.paid_at:
            invoice.paid_at = timezone.now()
        if not invoice.is_paid:
            invoice.paid_at = None
        if commit:
            invoice.save()
        return invoice

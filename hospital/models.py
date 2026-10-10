from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.utils import timezone

WEEKDAYS = [
    (0, "Monday"),
    (1, "Tuesday"),
    (2, "Wednesday"),
    (3, "Thursday"),
    (4, "Friday"),
    (5, "Saturday"),
    (6, "Sunday"),
]


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    icon = models.CharField(
        max_length=50,
        default="bi-heart-pulse",
        help_text="Bootstrap Icons class, for example bi-heart-pulse",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Patient(models.Model):
    GENDER_CHOICES = [("M", "Male"), ("F", "Female"), ("O", "Other")]
    BLOOD_CHOICES = [(b, b) for b in ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="patient_profile")
    phone = models.CharField(max_length=20)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default="M")
    blood_group = models.CharField(max_length=3, choices=BLOOD_CHOICES, blank=True)
    address = models.TextField(blank=True)
    emergency_contact = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["user__first_name", "user__last_name"]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def patient_id(self):
        return f"P{self.pk:05d}"

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = date.today()
        years = today.year - self.date_of_birth.year
        if (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day):
            years -= 1
        return years


class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="doctor_profile")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="doctors")
    specialization = models.CharField(max_length=120)
    qualification = models.CharField(max_length=150)
    experience_years = models.PositiveIntegerField(default=1)
    consultation_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("500.00"))
    phone = models.CharField(max_length=20, blank=True)
    bio = models.TextField(blank=True)
    is_available = models.BooleanField(default=True, help_text="Untick to hide from online booking")

    class Meta:
        ordering = ["user__first_name", "user__last_name"]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"Dr. {self.user.get_full_name() or self.user.username}"

    @property
    def initials(self):
        first = (self.user.first_name or self.user.username)[:1]
        last = self.user.last_name[:1]
        return (first + last).upper()

    def available_slots(self, day):
        """Free appointment start times (datetime.time) for a given date."""
        booked = set(
            self.appointments.filter(date=day, status__in=Appointment.ACTIVE_STATUSES).values_list(
                "time", flat=True
            )
        )
        now = timezone.localtime()
        slots = set()
        for schedule in self.schedules.filter(weekday=day.weekday()):
            current = datetime.combine(day, schedule.start_time)
            end = datetime.combine(day, schedule.end_time)
            step = timedelta(minutes=schedule.slot_minutes)
            while current + step <= end:
                slot = current.time()
                in_past = day == now.date() and slot <= now.time()
                if slot not in booked and not in_past:
                    slots.add(slot)
                current += step
        return sorted(slots)


class DoctorSchedule(models.Model):
    SLOT_CHOICES = [(15, "15 minutes"), (20, "20 minutes"), (30, "30 minutes"), (45, "45 minutes"), (60, "60 minutes")]

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="schedules")
    weekday = models.IntegerField(choices=WEEKDAYS)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_minutes = models.PositiveIntegerField(choices=SLOT_CHOICES, default=30)

    class Meta:
        ordering = ["weekday", "start_time"]

    def __str__(self):
        return f"{self.doctor} - {self.get_weekday_display()} {self.start_time:%H:%M}-{self.end_time:%H:%M}"


class Appointment(models.Model):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (CONFIRMED, "Confirmed"),
        (COMPLETED, "Completed"),
        (CANCELLED, "Cancelled"),
        (REJECTED, "Rejected"),
    ]
    # Statuses that keep a time slot occupied
    ACTIVE_STATUSES = [PENDING, CONFIRMED, COMPLETED]

    BADGES = {
        PENDING: "text-bg-warning",
        CONFIRMED: "text-bg-primary",
        COMPLETED: "text-bg-success",
        CANCELLED: "text-bg-secondary",
        REJECTED: "text-bg-danger",
    }

    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="appointments")
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name="appointments")
    date = models.DateField()
    time = models.TimeField()
    reason = models.TextField(help_text="Briefly describe your symptoms or the reason for the visit")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    admin_note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-time"]
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "date", "time"],
                condition=Q(status__in=["pending", "confirmed", "completed"]),
                name="unique_active_slot",
            )
        ]

    def __str__(self):
        return f"{self.patient} with {self.doctor} on {self.date} {self.time:%H:%M}"

    @property
    def badge_class(self):
        return self.BADGES.get(self.status, "text-bg-secondary")


class ConsultationNote(models.Model):
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name="note")
    diagnosis = models.CharField(max_length=255)
    notes = models.TextField(blank=True, help_text="Findings, advice, tests suggested")
    follow_up_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Note for {self.appointment}"


class Prescription(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name="prescriptions")
    medicine = models.CharField(max_length=150)
    dosage = models.CharField(max_length=100, help_text="For example 500 mg")
    frequency = models.CharField(max_length=100, help_text="For example twice a day, after meals")
    duration = models.CharField(max_length=100, help_text="For example 5 days")
    instructions = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.medicine} ({self.dosage})"


class Invoice(models.Model):
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name="invoice")
    consultation_fee = models.DecimalField(max_digits=9, decimal_places=2, default=Decimal("0.00"))
    medicine_charges = models.DecimalField(max_digits=9, decimal_places=2, default=Decimal("0.00"))
    other_charges = models.DecimalField(max_digits=9, decimal_places=2, default=Decimal("0.00"))
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.number

    @property
    def number(self):
        return f"INV-{self.pk:05d}" if self.pk else "INV-NEW"

    @property
    def total(self):
        return self.consultation_fee + self.medicine_charges + self.other_charges

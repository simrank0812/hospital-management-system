from django.contrib import admin

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


class ScheduleInline(admin.TabularInline):
    model = DoctorSchedule
    extra = 1


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "icon")
    search_fields = ("name",)


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ("full_name", "department", "specialization", "consultation_fee", "is_available")
    list_filter = ("department", "is_available")
    search_fields = ("user__first_name", "user__last_name", "specialization")
    inlines = [ScheduleInline]


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "gender", "blood_group", "created_at")
    search_fields = ("user__first_name", "user__last_name", "phone")


class PrescriptionInline(admin.TabularInline):
    model = Prescription
    extra = 0


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("patient", "doctor", "date", "time", "status")
    list_filter = ("status", "date", "doctor__department")
    search_fields = ("patient__user__first_name", "patient__user__last_name", "doctor__user__last_name")
    inlines = [PrescriptionInline]


@admin.register(ConsultationNote)
class ConsultationNoteAdmin(admin.ModelAdmin):
    list_display = ("appointment", "diagnosis", "follow_up_date")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "appointment", "total", "is_paid", "created_at")
    list_filter = ("is_paid",)

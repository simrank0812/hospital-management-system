import csv
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count, ProtectedError, Q
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .decorators import role_required
from .forms import (
    AppointmentForm,
    ConsultationNoteForm,
    DepartmentForm,
    DoctorForm,
    DoctorScheduleForm,
    InvoiceForm,
    PatientProfileForm,
    PatientRegistrationForm,
    PrescriptionForm,
    UserNameForm,
)
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
from .utils import get_role

APPT_RELATED = ("patient__user", "doctor__user", "doctor__department")


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def paginate(request, queryset, per_page=10):
    paginator = Paginator(queryset, per_page)
    page = paginator.get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return page, params.urlencode()


def check_appointment_access(user, appointment):
    role = get_role(user)
    if role == "admin":
        return
    if role == "doctor" and appointment.doctor.user_id == user.id:
        return
    if role == "patient" and appointment.patient.user_id == user.id:
        return
    raise PermissionDenied


def get_appointment_or_403(request, pk):
    appointment = get_object_or_404(Appointment.objects.select_related(*APPT_RELATED), pk=pk)
    check_appointment_access(request.user, appointment)
    return appointment


def safe_next(request, fallback):
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return target
    return fallback


def last_months(count):
    """List of (year, month) for the last `count` months, oldest first."""
    today = timezone.localdate()
    months = []
    for back in range(count - 1, -1, -1):
        month = today.month - back
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        months.append((year, month))
    return months


# --------------------------------------------------------------------------
# Public pages
# --------------------------------------------------------------------------
def home(request):
    context = {
        "departments": Department.objects.annotate(doctor_total=Count("doctors")).order_by("name")[:8],
        "doctors": Doctor.objects.filter(is_available=True).select_related("user", "department")[:4],
        "all_departments": Department.objects.all(),
    }
    return render(request, "home.html", context)


def departments(request):
    items = Department.objects.annotate(doctor_total=Count("doctors")).order_by("name")
    return render(request, "departments.html", {"departments": items})


def doctor_list(request):
    doctors = Doctor.objects.filter(is_available=True).select_related("user", "department")
    query = request.GET.get("q", "").strip()
    department = request.GET.get("department", "")
    if query:
        doctors = doctors.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(specialization__icontains=query)
        )
    if department.isdigit():
        doctors = doctors.filter(department_id=int(department))
    context = {
        "doctors": doctors,
        "departments": Department.objects.all(),
        "q": query,
        "selected_department": department,
    }
    return render(request, "doctor_list.html", context)


def doctor_detail(request, pk):
    doctor = get_object_or_404(Doctor.objects.select_related("user", "department"), pk=pk)
    return render(
        request,
        "doctor_detail.html",
        {"doctor": doctor, "schedules": doctor.schedules.all()},
    )


def contact(request):
    return render(request, "contact.html")


def slots_api(request, doctor_id):
    """JSON list of free time slots for a doctor on a given date (used by the booking form)."""
    doctor = get_object_or_404(Doctor, pk=doctor_id)
    try:
        day = datetime.strptime(request.GET.get("date", ""), "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"slots": []}, status=400)
    if day < timezone.localdate():
        return JsonResponse({"slots": []})
    return JsonResponse({"slots": [slot.strftime("%H:%M") for slot in doctor.available_slots(day)]})


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------
def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = PatientRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Welcome, {user.first_name}. Your patient account is ready.")
        return redirect("dashboard")
    return render(request, "registration/register.html", {"form": form})


@login_required
def dashboard(request):
    target = {
        "admin": "admin_dashboard",
        "doctor": "doctor_dashboard",
        "patient": "patient_dashboard",
    }.get(get_role(request.user))
    if not target:
        messages.error(request, "Your account has no hospital role yet. Please contact the administrator.")
        return redirect("home")
    return redirect(target)


# --------------------------------------------------------------------------
# Patient
# --------------------------------------------------------------------------
@role_required("patient")
def patient_dashboard(request):
    patient = request.user.patient_profile
    today = timezone.localdate()
    base = patient.appointments.select_related(*APPT_RELATED)
    context = {
        "patient": patient,
        "upcoming": base.filter(
            date__gte=today, status__in=[Appointment.PENDING, Appointment.CONFIRMED]
        ).order_by("date", "time")[:5],
        "recent": base.filter(status=Appointment.COMPLETED).order_by("-date", "-time")[:5],
        "unpaid": Invoice.objects.filter(appointment__patient=patient, is_paid=False).select_related(
            "appointment__doctor__user"
        ),
        "total_visits": patient.appointments.filter(status=Appointment.COMPLETED).count(),
        "pending_count": patient.appointments.filter(status=Appointment.PENDING).count(),
    }
    return render(request, "patient/dashboard.html", context)


@role_required("patient")
def book_appointment(request):
    initial = {}
    doctor_id = request.GET.get("doctor", "")
    if doctor_id.isdigit():
        initial["doctor"] = int(doctor_id)
    form = AppointmentForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        appointment = form.save(commit=False)
        appointment.patient = request.user.patient_profile
        appointment.status = Appointment.PENDING
        try:
            appointment.save()
        except IntegrityError:
            form.add_error("time", "Someone just booked that slot. Please pick another time.")
        else:
            messages.success(
                request, "Appointment requested. You will see it confirmed here once the hospital approves it."
            )
            return redirect("appointment_detail", pk=appointment.pk)
    return render(request, "patient/book.html", {"form": form})


@role_required("patient")
def patient_appointments(request):
    appointments = request.user.patient_profile.appointments.select_related(*APPT_RELATED)
    status = request.GET.get("status", "")
    if status in dict(Appointment.STATUS_CHOICES):
        appointments = appointments.filter(status=status)
    page, qs = paginate(request, appointments)
    return render(
        request,
        "patient/appointments.html",
        {"page": page, "qs": qs, "status": status, "statuses": Appointment.STATUS_CHOICES},
    )


@role_required("patient")
def patient_invoices(request):
    invoices = Invoice.objects.filter(appointment__patient=request.user.patient_profile).select_related(
        "appointment__doctor__user"
    )
    return render(request, "patient/invoices.html", {"invoices": invoices})


@role_required("patient")
def patient_profile(request):
    patient = request.user.patient_profile
    user_form = UserNameForm(request.POST or None, instance=request.user, prefix="user")
    profile_form = PatientProfileForm(request.POST or None, instance=patient, prefix="profile")
    if request.method == "POST" and user_form.is_valid() and profile_form.is_valid():
        user_form.save()
        profile_form.save()
        messages.success(request, "Profile updated.")
        return redirect("patient_profile")
    return render(
        request,
        "patient/profile.html",
        {"user_form": user_form, "profile_form": profile_form, "patient": patient},
    )


# --------------------------------------------------------------------------
# Shared: appointment detail, status changes, notes, prescriptions, invoices
# --------------------------------------------------------------------------
@login_required
def appointment_detail(request, pk):
    appointment = get_appointment_or_403(request, pk)
    role = get_role(request.user)
    note = ConsultationNote.objects.filter(appointment=appointment).first()
    invoice = Invoice.objects.filter(appointment=appointment).first()
    context = {
        "appointment": appointment,
        "note": note,
        "prescriptions": appointment.prescriptions.all(),
        "invoice": invoice,
        "can_treat": role == "doctor" and appointment.status in (Appointment.CONFIRMED, Appointment.COMPLETED),
    }
    if context["can_treat"]:
        context["note_form"] = ConsultationNoteForm(instance=note)
        context["prescription_form"] = PrescriptionForm()
    return render(request, "shared/appointment_detail.html", context)


STATUS_RULES = {
    # action: (allowed roles, allowed current statuses, new status)
    "confirm": ({"admin", "doctor"}, {Appointment.PENDING}, Appointment.CONFIRMED),
    "reject": ({"admin", "doctor"}, {Appointment.PENDING}, Appointment.REJECTED),
    "complete": ({"admin", "doctor"}, {Appointment.CONFIRMED}, Appointment.COMPLETED),
    "cancel": (
        {"admin", "doctor", "patient"},
        {Appointment.PENDING, Appointment.CONFIRMED},
        Appointment.CANCELLED,
    ),
}


@login_required
@require_POST
def appointment_status(request, pk):
    appointment = get_appointment_or_403(request, pk)
    role = get_role(request.user)
    action = request.POST.get("action")
    if action not in STATUS_RULES:
        return HttpResponseBadRequest("Unknown action")
    allowed_roles, allowed_statuses, new_status = STATUS_RULES[action]
    redirect_to = safe_next(request, redirect("appointment_detail", pk=appointment.pk).url)
    if role not in allowed_roles or appointment.status not in allowed_statuses:
        messages.error(request, "That action is not available for this appointment.")
        return redirect(redirect_to)

    appointment.status = new_status
    note = request.POST.get("admin_note", "").strip()
    if note and role in ("admin", "doctor"):
        appointment.admin_note = note[:200]
    appointment.save()

    if new_status == Appointment.COMPLETED:
        Invoice.objects.get_or_create(
            appointment=appointment,
            defaults={"consultation_fee": appointment.doctor.consultation_fee},
        )
    labels = {
        "confirm": "Appointment confirmed.",
        "reject": "Appointment rejected.",
        "complete": "Visit marked as completed and an invoice was created.",
        "cancel": "Appointment cancelled.",
    }
    messages.success(request, labels[action])
    return redirect(redirect_to)


@role_required("doctor")
@require_POST
def save_note(request, pk):
    appointment = get_appointment_or_403(request, pk)
    if appointment.status not in (Appointment.CONFIRMED, Appointment.COMPLETED):
        raise PermissionDenied
    existing = ConsultationNote.objects.filter(appointment=appointment).first()
    form = ConsultationNoteForm(request.POST, instance=existing)
    if form.is_valid():
        note = form.save(commit=False)
        note.appointment = appointment
        note.save()
        messages.success(request, "Consultation note saved.")
    else:
        messages.error(request, "Please enter a diagnosis before saving the note.")
    return redirect("appointment_detail", pk=appointment.pk)


@role_required("doctor")
@require_POST
def add_prescription(request, pk):
    appointment = get_appointment_or_403(request, pk)
    if appointment.status not in (Appointment.CONFIRMED, Appointment.COMPLETED):
        raise PermissionDenied
    form = PrescriptionForm(request.POST)
    if form.is_valid():
        prescription = form.save(commit=False)
        prescription.appointment = appointment
        prescription.save()
        messages.success(request, f"{prescription.medicine} added to the prescription.")
    else:
        messages.error(request, "Medicine, dosage, frequency and duration are required.")
    return redirect("appointment_detail", pk=appointment.pk)


@role_required("doctor")
@require_POST
def delete_prescription(request, pk):
    prescription = get_object_or_404(Prescription.objects.select_related("appointment__doctor"), pk=pk)
    if prescription.appointment.doctor.user_id != request.user.id:
        raise PermissionDenied
    appointment_id = prescription.appointment_id
    prescription.delete()
    messages.success(request, "Medicine removed.")
    return redirect("appointment_detail", pk=appointment_id)


@login_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related(*["appointment__" + r for r in APPT_RELATED]), pk=pk)
    check_appointment_access(request.user, invoice.appointment)
    return render(
        request,
        "shared/invoice_detail.html",
        {
            "invoice": invoice,
            "appointment": invoice.appointment,
            "prescriptions": invoice.appointment.prescriptions.all(),
        },
    )


# --------------------------------------------------------------------------
# Doctor
# --------------------------------------------------------------------------
@role_required("doctor")
def doctor_dashboard(request):
    doctor = request.user.doctor_profile
    today = timezone.localdate()
    base = doctor.appointments.select_related("patient__user", "doctor__user", "doctor__department")
    context = {
        "doctor": doctor,
        "todays": base.filter(date=today)
        .exclude(status__in=[Appointment.CANCELLED, Appointment.REJECTED])
        .order_by("time"),
        "pending": base.filter(status=Appointment.PENDING, date__gte=today).order_by("date", "time"),
        "upcoming": base.filter(
            status=Appointment.CONFIRMED, date__gt=today, date__lte=today + timedelta(days=7)
        ).order_by("date", "time"),
        "completed_count": doctor.appointments.filter(status=Appointment.COMPLETED).count(),
        "patient_count": doctor.appointments.order_by().values("patient").distinct().count(),
        "schedules": doctor.schedules.all(),
    }
    return render(request, "doctor/dashboard.html", context)


@role_required("doctor")
def doctor_appointments(request):
    doctor = request.user.doctor_profile
    appointments = doctor.appointments.select_related(*APPT_RELATED)
    status = request.GET.get("status", "")
    day = request.GET.get("date", "")
    if status in dict(Appointment.STATUS_CHOICES):
        appointments = appointments.filter(status=status)
    if day:
        try:
            appointments = appointments.filter(date=datetime.strptime(day, "%Y-%m-%d").date())
        except ValueError:
            day = ""
    page, qs = paginate(request, appointments)
    return render(
        request,
        "doctor/appointments.html",
        {"page": page, "qs": qs, "status": status, "day": day, "statuses": Appointment.STATUS_CHOICES},
    )


@role_required("doctor")
def doctor_schedule(request):
    doctor = request.user.doctor_profile
    form = DoctorScheduleForm(request.POST or None, doctor=doctor)
    if request.method == "POST" and form.is_valid():
        schedule = form.save(commit=False)
        schedule.doctor = doctor
        schedule.save()
        messages.success(request, "Time block added. Patients can now book it.")
        return redirect("doctor_schedule")
    return render(request, "doctor/schedule.html", {"form": form, "schedules": doctor.schedules.all()})


@role_required("doctor")
@require_POST
def schedule_delete(request, pk):
    schedule = get_object_or_404(DoctorSchedule, pk=pk, doctor=request.user.doctor_profile)
    schedule.delete()
    messages.success(request, "Time block removed. Existing appointments are not affected.")
    return redirect("doctor_schedule")


# --------------------------------------------------------------------------
# Admin dashboard
# --------------------------------------------------------------------------
@role_required("admin")
def admin_dashboard(request):
    today = timezone.localdate()
    appointments = Appointment.objects.select_related(*APPT_RELATED)
    paid_total = sum((i.total for i in Invoice.objects.filter(is_paid=True)), Decimal("0"))
    unpaid_total = sum((i.total for i in Invoice.objects.filter(is_paid=False)), Decimal("0"))
    context = {
        "stats": {
            "doctors": Doctor.objects.count(),
            "patients": Patient.objects.count(),
            "departments": Department.objects.count(),
            "today": appointments.filter(date=today)
            .exclude(status__in=[Appointment.CANCELLED, Appointment.REJECTED])
            .count(),
            "pending": appointments.filter(status=Appointment.PENDING).count(),
        },
        "pending": appointments.filter(status=Appointment.PENDING).order_by("date", "time")[:8],
        "todays": appointments.filter(date=today)
        .exclude(status__in=[Appointment.CANCELLED, Appointment.REJECTED])
        .order_by("time"),
        "paid_total": paid_total,
        "unpaid_total": unpaid_total,
    }
    return render(request, "manage/dashboard.html", context)


@role_required("admin")
def admin_appointments(request):
    appointments = Appointment.objects.select_related(*APPT_RELATED)
    status = request.GET.get("status", "")
    query = request.GET.get("q", "").strip()
    day = request.GET.get("date", "")
    if status in dict(Appointment.STATUS_CHOICES):
        appointments = appointments.filter(status=status)
    if query:
        appointments = appointments.filter(
            Q(patient__user__first_name__icontains=query)
            | Q(patient__user__last_name__icontains=query)
            | Q(doctor__user__first_name__icontains=query)
            | Q(doctor__user__last_name__icontains=query)
        )
    if day:
        try:
            appointments = appointments.filter(date=datetime.strptime(day, "%Y-%m-%d").date())
        except ValueError:
            day = ""
    page, qs = paginate(request, appointments, per_page=12)
    return render(
        request,
        "manage/appointments.html",
        {"page": page, "qs": qs, "status": status, "q": query, "day": day, "statuses": Appointment.STATUS_CHOICES},
    )


@role_required("admin")
def admin_doctors(request):
    doctors = (
        Doctor.objects.select_related("user", "department")
        .annotate(visits=Count("appointments"))
        .order_by("user__first_name", "user__last_name")
    )
    query = request.GET.get("q", "").strip()
    if query:
        doctors = doctors.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(specialization__icontains=query)
            | Q(department__name__icontains=query)
        )
    return render(request, "manage/doctors.html", {"doctors": doctors, "q": query})


@role_required("admin")
def doctor_add(request):
    if not Department.objects.exists():
        messages.warning(request, "Add a department first, then you can add doctors to it.")
        return redirect("department_add")
    form = DoctorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        doctor = form.save()
        messages.success(
            request,
            f"{doctor.full_name} added. Ask them to log in and set their weekly schedule so patients can book.",
        )
        return redirect("admin_doctors")
    return render(
        request,
        "form_page.html",
        {"title": "Add a doctor", "form": form, "submit_label": "Add doctor", "back_url": "admin_doctors"},
    )


@role_required("admin")
def doctor_edit(request, pk):
    doctor = get_object_or_404(Doctor, pk=pk)
    form = DoctorForm(request.POST or None, instance=doctor)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Doctor details saved.")
        return redirect("admin_doctors")
    return render(
        request,
        "form_page.html",
        {"title": f"Edit {doctor.full_name}", "form": form, "submit_label": "Save changes", "back_url": "admin_doctors"},
    )


@role_required("admin")
@require_POST
def doctor_delete(request, pk):
    doctor = get_object_or_404(Doctor, pk=pk)
    name = doctor.full_name
    try:
        doctor.user.delete()
    except ProtectedError:
        messages.error(
            request,
            f"{name} has appointment history and cannot be deleted. Edit the doctor and untick 'Is available' instead.",
        )
    else:
        messages.success(request, f"{name} deleted.")
    return redirect("admin_doctors")


@role_required("admin")
def admin_departments(request):
    items = Department.objects.annotate(doctor_total=Count("doctors")).order_by("name")
    return render(request, "manage/departments.html", {"departments": items})


@role_required("admin")
def department_add(request):
    form = DepartmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Department added.")
        return redirect("admin_departments")
    return render(
        request,
        "form_page.html",
        {"title": "Add a department", "form": form, "submit_label": "Add department", "back_url": "admin_departments"},
    )


@role_required("admin")
def department_edit(request, pk):
    department = get_object_or_404(Department, pk=pk)
    form = DepartmentForm(request.POST or None, instance=department)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Department saved.")
        return redirect("admin_departments")
    return render(
        request,
        "form_page.html",
        {
            "title": f"Edit {department.name}",
            "form": form,
            "submit_label": "Save changes",
            "back_url": "admin_departments",
        },
    )


@role_required("admin")
@require_POST
def department_delete(request, pk):
    department = get_object_or_404(Department, pk=pk)
    try:
        department.delete()
    except ProtectedError:
        messages.error(request, "This department still has doctors. Move or delete them first.")
    else:
        messages.success(request, "Department deleted.")
    return redirect("admin_departments")


@role_required("admin")
def admin_patients(request):
    patients = (
        Patient.objects.select_related("user")
        .annotate(visits=Count("appointments"))
        .order_by("user__first_name", "user__last_name")
    )
    query = request.GET.get("q", "").strip()
    if query:
        patients = patients.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__username__icontains=query)
            | Q(phone__icontains=query)
        )
    page, qs = paginate(request, patients, per_page=12)
    return render(request, "manage/patients.html", {"page": page, "qs": qs, "q": query})


@role_required("admin")
@require_POST
def patient_toggle(request, pk):
    patient = get_object_or_404(Patient.objects.select_related("user"), pk=pk)
    patient.user.is_active = not patient.user.is_active
    patient.user.save(update_fields=["is_active"])
    state = "activated" if patient.user.is_active else "deactivated"
    messages.success(request, f"{patient.full_name}'s account {state}.")
    return redirect(safe_next(request, redirect("admin_patients").url))


@role_required("admin")
def admin_invoices(request):
    invoices = Invoice.objects.select_related("appointment__patient__user", "appointment__doctor__user")
    state = request.GET.get("state", "")
    if state == "paid":
        invoices = invoices.filter(is_paid=True)
    elif state == "unpaid":
        invoices = invoices.filter(is_paid=False)
    page, qs = paginate(request, invoices, per_page=12)
    return render(request, "manage/invoices.html", {"page": page, "qs": qs, "state": state})


@role_required("admin")
def invoice_edit(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    form = InvoiceForm(request.POST or None, instance=invoice)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{invoice.number} saved.")
        return redirect("admin_invoices")
    return render(
        request,
        "form_page.html",
        {"title": f"Edit {invoice.number}", "form": form, "submit_label": "Save invoice", "back_url": "admin_invoices"},
    )


@role_required("admin")
@require_POST
def invoice_toggle_paid(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    invoice.is_paid = not invoice.is_paid
    invoice.paid_at = timezone.now() if invoice.is_paid else None
    invoice.save(update_fields=["is_paid", "paid_at"])
    messages.success(request, f"{invoice.number} marked as {'paid' if invoice.is_paid else 'unpaid'}.")
    return redirect(safe_next(request, redirect("admin_invoices").url))


@role_required("admin")
def admin_reports(request):
    status_counts = {code: 0 for code, _ in Appointment.STATUS_CHOICES}
    for row in Appointment.objects.order_by().values("status").annotate(total=Count("id")):
        status_counts[row["status"]] = row["total"]

    by_department = list(
        Appointment.objects.values("doctor__department__name").annotate(total=Count("id")).order_by("-total")
    )

    months = last_months(6)
    monthly_labels, monthly_appointments, monthly_revenue = [], [], []
    for year, month in months:
        monthly_labels.append(date(year, month, 1).strftime("%b %Y"))
        monthly_appointments.append(Appointment.objects.filter(date__year=year, date__month=month).count())
        paid = Invoice.objects.filter(is_paid=True, paid_at__year=year, paid_at__month=month)
        monthly_revenue.append(float(sum((i.total for i in paid), Decimal("0"))))

    top_doctors = Doctor.objects.select_related("user", "department").annotate(
        total=Count("appointments"),
        done=Count("appointments", filter=Q(appointments__status=Appointment.COMPLETED)),
    ).order_by("-total")[:6]

    invoices = list(Invoice.objects.all())
    paid_total = sum((i.total for i in invoices if i.is_paid), Decimal("0"))
    unpaid_total = sum((i.total for i in invoices if not i.is_paid), Decimal("0"))

    chart_data = {
        "monthLabels": monthly_labels,
        "monthAppointments": monthly_appointments,
        "monthRevenue": monthly_revenue,
        "statusLabels": [label for _, label in Appointment.STATUS_CHOICES],
        "statusValues": [status_counts[code] for code, _ in Appointment.STATUS_CHOICES],
        "deptLabels": [row["doctor__department__name"] for row in by_department],
        "deptValues": [row["total"] for row in by_department],
    }
    context = {
        "chart_data": chart_data,
        "top_doctors": top_doctors,
        "paid_total": paid_total,
        "unpaid_total": unpaid_total,
        "invoice_count": len(invoices),
        "appointment_total": sum(status_counts.values()),
        "completed_total": status_counts[Appointment.COMPLETED],
    }
    return render(request, "manage/reports.html", context)


@role_required("admin")
def export_appointments_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="appointments.csv"'
    writer = csv.writer(response)
    writer.writerow(["Date", "Time", "Patient", "Doctor", "Department", "Status", "Reason"])
    for a in Appointment.objects.select_related(*APPT_RELATED).order_by("-date", "-time"):
        writer.writerow(
            [a.date, a.time.strftime("%H:%M"), a.patient.full_name, a.doctor.full_name,
             a.doctor.department.name, a.get_status_display(), a.reason]
        )
    return response

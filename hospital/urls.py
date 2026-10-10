from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import StyledAuthenticationForm

urlpatterns = [
    # Public pages
    path("", views.home, name="home"),
    path("departments/", views.departments, name="departments"),
    path("doctors/", views.doctor_list, name="doctor_list"),
    path("doctors/<int:pk>/", views.doctor_detail, name="doctor_detail"),
    path("contact/", views.contact, name="contact"),
    path("api/slots/<int:doctor_id>/", views.slots_api, name="slots_api"),
    # Authentication
    path("register/", views.register, name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=StyledAuthenticationForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    # Patient
    path("patient/", views.patient_dashboard, name="patient_dashboard"),
    path("patient/book/", views.book_appointment, name="book_appointment"),
    path("patient/appointments/", views.patient_appointments, name="patient_appointments"),
    path("patient/invoices/", views.patient_invoices, name="patient_invoices"),
    path("patient/profile/", views.patient_profile, name="patient_profile"),
    # Shared appointment / invoice pages
    path("appointments/<int:pk>/", views.appointment_detail, name="appointment_detail"),
    path("appointments/<int:pk>/status/", views.appointment_status, name="appointment_status"),
    path("appointments/<int:pk>/note/", views.save_note, name="save_note"),
    path("appointments/<int:pk>/prescriptions/add/", views.add_prescription, name="add_prescription"),
    path("prescriptions/<int:pk>/delete/", views.delete_prescription, name="delete_prescription"),
    path("invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    # Doctor
    path("doctor/", views.doctor_dashboard, name="doctor_dashboard"),
    path("doctor/appointments/", views.doctor_appointments, name="doctor_appointments"),
    path("doctor/schedule/", views.doctor_schedule, name="doctor_schedule"),
    path("doctor/schedule/<int:pk>/delete/", views.schedule_delete, name="schedule_delete"),
    # Admin dashboard
    path("manage/", views.admin_dashboard, name="admin_dashboard"),
    path("manage/appointments/", views.admin_appointments, name="admin_appointments"),
    path("manage/doctors/", views.admin_doctors, name="admin_doctors"),
    path("manage/doctors/add/", views.doctor_add, name="doctor_add"),
    path("manage/doctors/<int:pk>/edit/", views.doctor_edit, name="doctor_edit"),
    path("manage/doctors/<int:pk>/delete/", views.doctor_delete, name="doctor_delete"),
    path("manage/departments/", views.admin_departments, name="admin_departments"),
    path("manage/departments/add/", views.department_add, name="department_add"),
    path("manage/departments/<int:pk>/edit/", views.department_edit, name="department_edit"),
    path("manage/departments/<int:pk>/delete/", views.department_delete, name="department_delete"),
    path("manage/patients/", views.admin_patients, name="admin_patients"),
    path("manage/patients/<int:pk>/toggle/", views.patient_toggle, name="patient_toggle"),
    path("manage/invoices/", views.admin_invoices, name="admin_invoices"),
    path("manage/invoices/<int:pk>/edit/", views.invoice_edit, name="invoice_edit"),
    path("manage/invoices/<int:pk>/toggle-paid/", views.invoice_toggle_paid, name="invoice_toggle_paid"),
    path("manage/reports/", views.admin_reports, name="admin_reports"),
    path("manage/reports/appointments.csv", views.export_appointments_csv, name="export_appointments_csv"),
]

"""
Fills the database with demo data: departments, doctors with weekly schedules,
a few patients, appointments, consultation notes, prescriptions and invoices.

Usage:  python manage.py seed_demo
Safe to run more than once.
"""
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from hospital.models import (
    Appointment,
    ConsultationNote,
    Department,
    Doctor,
    DoctorSchedule,
    Invoice,
    Patient,
    Prescription,
)

DEPARTMENTS = [
    ("Cardiology", "Heart and blood-vessel care: ECG, echo, stress tests and long-term heart health.", "bi-heart-pulse"),
    ("Neurology", "Headaches, seizures, stroke recovery and nerve conditions.", "bi-lightning-charge"),
    ("Orthopedics", "Bones, joints, sports injuries, fractures and joint replacement.", "bi-bandaid"),
    ("Pediatrics", "Care for newborns, children and teenagers, including vaccinations.", "bi-emoji-smile"),
    ("Gynecology", "Women's health, pregnancy care and family planning.", "bi-gender-female"),
    ("General Medicine", "Fever, infections, diabetes, blood pressure and everyday health concerns.", "bi-clipboard2-pulse"),
    ("Dermatology", "Skin, hair and nail conditions, allergies and cosmetic dermatology.", "bi-droplet"),
    ("Ophthalmology", "Eye check-ups, spectacles, cataract and retina care.", "bi-eye"),
]

# username, first, last, department, specialization, qualification, experience, fee, bio
DOCTORS = [
    ("dr.sen", "Arindam", "Sen", "Cardiology", "Interventional cardiologist", "MD, DM (Cardiology)", 16, 900,
     "Arindam has performed over 4,000 angioplasties and runs the hospital's chest-pain clinic."),
    ("dr.iyer", "Meera", "Iyer", "Neurology", "Epilepsy and headache specialist", "MD, DM (Neurology)", 12, 800,
     "Meera focuses on migraine, epilepsy and long-term neurological care."),
    ("dr.mehta", "Rohan", "Mehta", "Orthopedics", "Sports injury and joint surgeon", "MS (Orthopedics)", 10, 700,
     "Rohan treats athletes and weekend players, and leads the knee replacement programme."),
    ("dr.rao", "Sunita", "Rao", "Pediatrics", "Child health and vaccination", "MD (Pediatrics)", 14, 600,
     "Sunita looks after children from birth to eighteen and runs the vaccination desk."),
    ("dr.nair", "Kavita", "Nair", "Gynecology", "Obstetrician and gynecologist", "MS (OBG), DNB", 11, 800,
     "Kavita guides families through pregnancy, delivery and the months after."),
    ("dr.qureshi", "Imran", "Qureshi", "General Medicine", "Internal medicine and diabetes", "MD (Medicine)", 9, 500,
     "Imran is the first stop for fever, infections, blood pressure and diabetes care."),
    ("dr.banerjee", "Priya", "Banerjee", "Dermatology", "Dermatologist", "MD (Dermatology)", 8, 650,
     "Priya treats acne, eczema, hair loss and skin allergies."),
    ("dr.kapoor", "Anil", "Kapoor", "Ophthalmology", "Cataract and retina surgeon", "MS (Ophthalmology)", 18, 700,
     "Anil has two decades of experience in cataract surgery and diabetic eye care."),
]

PATIENTS = [
    ("rahul", "Rahul", "Das", "9830012345", date(1990, 5, 14), "M", "B+", "12 Park Street, Kolkata"),
    ("ananya", "Ananya", "Ghosh", "9831098765", date(1996, 11, 2), "F", "O+", "45 Lake Road, Kolkata"),
    ("suman", "Suman", "Roy", "9831234567", date(1978, 2, 27), "M", "A+", "8 Salt Lake Sector V, Kolkata"),
]


def workday(day, step):
    """Move `day` by `step` days (+1 or -1) until it is not a Sunday."""
    while day.weekday() == 6:
        day += timedelta(days=step)
    return day


class Command(BaseCommand):
    help = "Create demo departments, doctors, patients and appointments."

    def handle(self, *args, **options):
        # ---- Admin account ------------------------------------------------
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@sanjeevani.example", "admin123", first_name="Hospital", last_name="Admin")

        # ---- Departments --------------------------------------------------
        departments = {}
        for name, description, icon in DEPARTMENTS:
            dept, _ = Department.objects.get_or_create(name=name, defaults={"description": description, "icon": icon})
            departments[name] = dept

        # ---- Doctors + schedules -----------------------------------------
        doctors = []
        for index, (username, first, last, dept, spec, qual, exp, fee, bio) in enumerate(DOCTORS):
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"first_name": first, "last_name": last, "email": f"{username}@sanjeevani.example"},
            )
            if created:
                user.set_password("doctor123")
                user.save()
            doctor, _ = Doctor.objects.get_or_create(
                user=user,
                defaults={
                    "department": departments[dept],
                    "specialization": spec,
                    "qualification": qual,
                    "experience_years": exp,
                    "consultation_fee": Decimal(fee),
                    "phone": f"98300{10000 + index * 111}",
                    "bio": bio,
                },
            )
            if not doctor.schedules.exists():
                for weekday in range(0, 6):  # Monday to Saturday mornings
                    DoctorSchedule.objects.create(
                        doctor=doctor, weekday=weekday, start_time=time(9, 0), end_time=time(13, 0), slot_minutes=30
                    )
                for weekday in ([0, 2, 4] if index % 2 == 0 else [1, 3]):  # some afternoons
                    DoctorSchedule.objects.create(
                        doctor=doctor, weekday=weekday, start_time=time(16, 0), end_time=time(18, 0), slot_minutes=30
                    )
            doctors.append(doctor)

        # ---- Patients -----------------------------------------------------
        patients = []
        for username, first, last, phone, dob, gender, blood, address in PATIENTS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"first_name": first, "last_name": last, "email": f"{username}@example.com"},
            )
            if created:
                user.set_password("patient123")
                user.save()
            patient, _ = Patient.objects.get_or_create(
                user=user,
                defaults={
                    "phone": phone,
                    "date_of_birth": dob,
                    "gender": gender,
                    "blood_group": blood,
                    "address": address,
                },
            )
            patients.append(patient)

        # ---- Appointments -------------------------------------------------
        today = timezone.localdate()
        rahul, ananya, suman = patients
        cardio, neuro, ortho, peds, gyn, general, derm, eye = doctors

        def appointment(patient, doctor, offset, hh, mm, status, reason):
            day = workday(today + timedelta(days=offset), 1 if offset >= 0 else -1)
            obj, _ = Appointment.objects.get_or_create(
                doctor=doctor,
                date=day,
                time=time(hh, mm),
                defaults={"patient": patient, "status": status, "reason": reason},
            )
            return obj

        # Completed visits with notes, prescriptions and invoices
        done = appointment(rahul, cardio, -12, 10, 0, Appointment.COMPLETED, "Chest tightness while climbing stairs.")
        ConsultationNote.objects.get_or_create(
            appointment=done,
            defaults={
                "diagnosis": "Mild hypertension, ECG normal",
                "notes": "Advised to reduce salt, walk 30 minutes daily and monitor blood pressure at home.",
                "follow_up_date": today + timedelta(days=14),
            },
        )
        if not done.prescriptions.exists():
            Prescription.objects.create(appointment=done, medicine="Amlodipine", dosage="5 mg", frequency="Once a day, morning", duration="30 days", instructions="Take after breakfast")
            Prescription.objects.create(appointment=done, medicine="Aspirin", dosage="75 mg", frequency="Once a day, after dinner", duration="30 days")
        invoice, _ = Invoice.objects.get_or_create(appointment=done, defaults={"consultation_fee": cardio.consultation_fee, "medicine_charges": Decimal("640"), "other_charges": Decimal("350")})
        if not invoice.is_paid:
            invoice.is_paid, invoice.paid_at = True, timezone.now() - timedelta(days=12)
            invoice.save()

        done2 = appointment(ananya, derm, -5, 9, 30, Appointment.COMPLETED, "Itchy rash on both arms for a week.")
        ConsultationNote.objects.get_or_create(
            appointment=done2,
            defaults={"diagnosis": "Contact dermatitis", "notes": "Avoid the new detergent. Moisturise twice a day.", "follow_up_date": today + timedelta(days=10)},
        )
        if not done2.prescriptions.exists():
            Prescription.objects.create(appointment=done2, medicine="Cetirizine", dosage="10 mg", frequency="Once at night", duration="7 days")
            Prescription.objects.create(appointment=done2, medicine="Hydrocortisone cream 1%", dosage="Thin layer", frequency="Twice a day", duration="7 days", instructions="Apply on affected skin only")
        Invoice.objects.get_or_create(appointment=done2, defaults={"consultation_fee": derm.consultation_fee, "medicine_charges": Decimal("280")})

        done3 = appointment(suman, ortho, -20, 11, 0, Appointment.COMPLETED, "Right knee pain after running.")
        ConsultationNote.objects.get_or_create(
            appointment=done3,
            defaults={"diagnosis": "Patellar tendinitis", "notes": "Rest for two weeks, physiotherapy three times a week."},
        )
        inv3, _ = Invoice.objects.get_or_create(appointment=done3, defaults={"consultation_fee": ortho.consultation_fee, "other_charges": Decimal("1200")})
        if not inv3.is_paid:
            inv3.is_paid, inv3.paid_at = True, timezone.now() - timedelta(days=20)
            inv3.save()

        # Upcoming / pending
        appointment(rahul, general, 2, 9, 0, Appointment.CONFIRMED, "Routine diabetes check and blood tests.")
        appointment(ananya, gyn, 3, 10, 30, Appointment.CONFIRMED, "Second-trimester check-up.")
        appointment(rahul, neuro, 4, 11, 30, Appointment.PENDING, "Recurring headaches in the evening.")
        appointment(suman, cardio, 1, 9, 30, Appointment.PENDING, "Follow-up ECG and blood pressure review.")
        appointment(ananya, eye, 5, 10, 0, Appointment.PENDING, "Blurred vision while reading.")
        appointment(suman, peds, 6, 12, 0, Appointment.PENDING, "Vaccination for my 4-year-old daughter.")
        appointment(rahul, ortho, -3, 12, 0, Appointment.CANCELLED, "Shoulder stiffness.")

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write("")
        self.stdout.write("  Admin    admin / admin123       ->  /manage/")
        self.stdout.write("  Doctor   dr.sen / doctor123     ->  /doctor/")
        self.stdout.write("  Patient  rahul / patient123     ->  /patient/")

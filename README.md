# Sanjeevani Hospital Management System

Django + Bootstrap 5 + SQLite. Three roles: patient, doctor, admin.

## Quick start

Requires Python 3.10+ and an internet connection (Bootstrap, fonts and Chart.js load from CDNs).

**Windows:** double-click `setup_and_run.bat`
**Mac / Linux:** `bash setup_and_run.sh`

Or manually:

```
python -m venv venv
venv\Scripts\activate          (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python manage.py makemigrations hospital
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open http://127.0.0.1:8000/

## Demo logins (created by `seed_demo`)

| Role    | Username | Password   | Lands on  |
|---------|----------|------------|-----------|
| Admin   | admin    | admin123   | /manage/  |
| Doctor  | dr.sen   | doctor123  | /doctor/  |
| Patient | rahul    | patient123 | /patient/ |

Other doctors: dr.iyer, dr.mehta, dr.rao, dr.nair, dr.qureshi, dr.banerjee, dr.kapoor (all `doctor123`).

## Features

- **Public site:** hero homepage, departments, doctor search, doctor profiles, contact page.
- **Patients:** register, log in, book appointments (live free-slot picker), cancel, view notes, prescriptions, bills, edit profile.
- **Doctors:** weekly schedule, today's list, confirm/reject requests, consultation notes, prescriptions, mark complete (creates invoice).
- **Admin dashboard (/manage/):** approve requests, manage doctors, departments, patients, billing, reports with charts, CSV export. Full  admin at /django-admin/.

## Customising

- Hospital name/address/phone: `templates/base.html`, `templates/contact.html`
- Colours and fonts: top of `static/css/style.css`
- Hero photo: `.hero` rule in `static/css/style.css` (put your image at `static/img/hero.jpg`)

## Structure

```
hms_project/   settings, root urls
hospital/      models, forms, views, urls, seed_demo command
templates/     public, patient/, doctor/, manage/, shared/
static/        css/style.css, js/main.js
```

Demo project: before real use change SECRET_KEY, set DEBUG=False, add password reset email and online payment.

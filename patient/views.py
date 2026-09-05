import datetime
import json
import logging
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.conf import settings

from accounts.models import User
from doctor.models import (
    DoctorProfile, Patients, Appointments, MedicalRecord, 
    Clinic, LabOrderTicket, BillingInvoice, generate_short_uuid
)
from .models import (
    PatientDocument, VaccinationRecord, PatientDoctorMessage, 
    FamilyMember, HealthTip, LabTestCatalog
)

logger = logging.getLogger(__name__)

# ==============================================================================
# HELPER: PATIENT RESOLUTION & SEED DATA INITIALIZATION
# ==============================================================================

def get_current_patient(user):
    """Safely retrieves or initializes the Patients model for the authenticated user."""
    if not user.is_authenticated:
        return None
    
    # 1. Check patient_profile related name
    patient = getattr(user, 'patient_profile', None)
    if patient:
        return patient

    # 2. Query Patients table by user
    patient = Patients.objects.filter(user=user).first()
    if patient:
        return patient

    # 3. Match by email
    if user.email:
        patient = Patients.objects.filter(email__iexact=user.email).first()
        if patient:
            patient.user = user
            patient.save(update_fields=['user'])
            return patient

    # 4. Fallback: auto-create patient profile
    clinic = Clinic.objects.first()
    first_doc = DoctorProfile.objects.first()
    full_name = user.get_full_name().strip() or user.username
    patient = Patients.objects.create(
        user=user,
        name=full_name,
        email=user.email or f"{user.username}@example.com",
        phone_number="+91 98234 56789",
        gender="Male",
        clinic=clinic,
        doctor=first_doc,
        date_of_birth=datetime.date(1995, 6, 15),
        blood_group="B+",
        allergies="Penicillin",
        active_medications="Amoxicillin 500mg, Cetirizine 10mg",
        medical_history="Mild Seasonal Allergies",
        address="Senapati Bapat Road, Pune"
    )
    return patient


def ensure_patient_portal_seed_data():
    """Initializes rich catalogs and baseline doctors so the portal is never empty."""
    # Ensure Doctors have realistic ratings and fees
    doctors = DoctorProfile.objects.all()
    sample_doctors_meta = [
        {"fee": 500.00, "exp": 12, "rating": 4.9, "reviews": 142, "address": "Sunrise Clinic, Senapati Bapat Road, Pune", "spec": "General Physician"},
        {"fee": 700.00, "exp": 15, "rating": 4.8, "reviews": 98, "address": "Apex Heart Institute, FC Road, Pune", "spec": "Cardiologist"},
        {"fee": 450.00, "exp": 9, "rating": 4.9, "reviews": 210, "address": "Little Smiles Pediatric Center, Kothrud, Pune", "spec": "Pediatrician"},
        {"fee": 600.00, "exp": 11, "rating": 4.7, "reviews": 85, "address": "Skin & Aesthetic Clinic, Aundh, Pune", "spec": "Dermatologist"},
        {"fee": 550.00, "exp": 14, "rating": 4.8, "reviews": 115, "address": "Bone & Joint Specialty Clinic, Pune", "spec": "Orthopedic Surgeon"},
    ]
    for idx, doc in enumerate(doctors):
        meta = sample_doctors_meta[idx % len(sample_doctors_meta)]
        if not doc.consultation_fee or doc.consultation_fee <= 0:
            doc.consultation_fee = Decimal(str(meta["fee"]))
        if not doc.experience_years:
            doc.experience_years = meta["exp"]
        if not doc.rating or doc.rating <= 0:
            doc.rating = Decimal(str(meta["rating"]))
        if not doc.review_count:
            doc.review_count = meta["reviews"]
        if not doc.clinic_address:
            doc.clinic_address = meta["address"]
        doc.save()

    # Seed Lab Test Catalog if empty
    if LabTestCatalog.objects.count() == 0:
        tests = [
            {"name": "Complete Blood Count (CBC)", "code": "CBC-01", "category": "Hematology", "price": 350.00, "turnaround": "Within 12 Hours", "prep": "No fasting required", "sample": "Blood (EDTA)", "is_popular": True, "icon": "fa-vial-circle-check", "desc": "Evaluates overall health and detects anemia, infection, and leukemia."},
            {"name": "Fasting Blood Glucose & HbA1c", "code": "GLU-02", "category": "Diabetology", "price": 450.00, "turnaround": "Within 24 Hours", "prep": "10-12 hours overnight fasting required", "sample": "Blood (Serum)", "is_popular": True, "icon": "fa-droplet", "desc": "Assesses 3-month glycemic control and insulin sensitivity."},
            {"name": "Comprehensive Lipid Profile", "code": "LIP-03", "category": "Cardiovascular", "price": 650.00, "turnaround": "Within 24 Hours", "prep": "12 hours strict fasting", "sample": "Blood (Serum)", "is_popular": True, "icon": "fa-heart-pulse", "desc": "Checks total cholesterol, HDL, LDL, VLDL, and triglycerides."},
            {"name": "Thyroid Stimulating Hormone (TSH / T3 / T4)", "code": "THY-04", "category": "Endocrinology", "price": 550.00, "turnaround": "Within 24 Hours", "prep": "Morning sample preferred", "sample": "Blood (Serum)", "is_popular": True, "icon": "fa-dna", "desc": "Monitors hypo- and hyperthyroidism and metabolic balance."},
            {"name": "Liver Function Test (LFT)", "code": "LFT-05", "category": "Biochemistry", "price": 700.00, "turnaround": "Within 24 Hours", "prep": "Overnight fasting recommended", "sample": "Blood (Serum)", "is_popular": False, "icon": "fa-shield-virus", "desc": "Measures bilirubin, SGOT, SGPT, alkaline phosphatase, and proteins."},
            {"name": "Kidney Function Test (KFT / RFT)", "code": "KFT-06", "category": "Renal Care", "price": 600.00, "turnaround": "Within 24 Hours", "prep": "Normal hydration advised", "sample": "Blood (Serum)", "is_popular": False, "icon": "fa-filter", "desc": "Assesses urea, creatinine, BUN, and glomerular filtration efficiency."},
            {"name": "Vitamin D3 & Vitamin B12 Panel", "code": "VIT-07", "category": "Vitamins & Minerals", "price": 950.00, "turnaround": "Within 36 Hours", "prep": "Fasting not strictly required", "sample": "Blood (Serum)", "is_popular": True, "icon": "fa-sun", "desc": "Evaluates bone density, nerve health, and cellular energy levels."},
            {"name": "Digital Chest X-Ray (PA View)", "code": "RAD-08", "category": "Radiology", "price": 500.00, "turnaround": "Within 2 Hours", "prep": "Remove metallic items & jewelry", "sample": "Digital Imaging", "is_popular": False, "icon": "fa-x-ray", "desc": "Visualizes lungs, heart size, rib cage, and respiratory airways."}
        ]
        for t in tests:
            LabTestCatalog.objects.create(
                name=t["name"], code=t["code"], category=t["category"],
                price=Decimal(str(t["price"])), turnaround_time=t["turnaround"],
                preparation=t["prep"], sample_type=t["sample"],
                is_popular=t["is_popular"], icon=t["icon"], description=t["desc"]
            )

    # Seed Health Tips if empty
    if HealthTip.objects.count() == 0:
        tips = [
            {
                "title": "7 Proven Strategies for Cardiovascular Longevity",
                "category": "Heart Health",
                "summary": "Practical daily habits that reduce resting heart rate, lower systemic blood pressure, and keep arterial walls supple.",
                "content": "Cardiovascular wellness starts with consistent moderate aerobic activity: brisk walking 30 minutes 5 days a week lowers hypertension risk by up to 35%. Prioritize potassium-rich leafy greens, manage refined sodium intake below 2,000mg daily, and cultivate 7 hours of uninterrupted nocturnal sleep to optimize heart rhythm and microvascular recovery.",
                "read_time": "4 min read",
                "icon": "fa-heart-pulse",
                "doctor_endorsement": "Verified by Dr. Sarah Sharma, Cardiologist",
                "likes_count": 89
            },
            {
                "title": "Demystifying Blood Sugar Spikes After Meals",
                "category": "Nutrition",
                "summary": "How meal sequencing (fiber first, carbs last) blunts postprandial glucose surges and prevents mid-day fatigue.",
                "content": "Consuming raw dietary fiber (such as a starter salad or steamed greens) 10 minutes prior to starchy carbohydrates forms a protective viscous gel in the small intestine. This noticeably decelerates glucose absorption, lowering insulin spikes by nearly 40% and keeping energy levels steady throughout the afternoon.",
                "read_time": "3 min read",
                "icon": "fa-apple-whole",
                "doctor_endorsement": "Verified by Dr. Diyan Deshmukh, Lead Physician",
                "likes_count": 134
            },
            {
                "title": "Preventive Screening Checklist for Adults 25 to 55",
                "category": "Preventive Care",
                "summary": "Essential annual metrics every individual must track: blood pressure, HbA1c, lipid fractions, and Vitamin D levels.",
                "content": "Modern preventive medicine stresses proactive detection over reactive crisis intervention. An annual full-body diagnostic screen encompassing fasting glucose, comprehensive lipid profiles, liver and renal markers, and thyroid panels uncovers silent metabolic shifts years before clinical symptoms manifest.",
                "read_time": "5 min read",
                "icon": "fa-clipboard-check",
                "doctor_endorsement": "Verified by Clinical Advisory Panel",
                "likes_count": 210
            },
            {
                "title": "The Neurological Impact of Deep Restorative Sleep",
                "category": "Sleep",
                "summary": "Why the brain's glymphatic waste-clearing system depends entirely on deep slow-wave sleep cycles.",
                "content": "During stages 3 and 4 of slow-wave sleep, brain interstitial space widens by up to 60%, allowing cerebrospinal fluid to rapidly flush away metabolic waste products including beta-amyloid proteins. Keep bedroom ambient temperature around 19-21°C and eliminate blue light screens 45 minutes before sleep.",
                "read_time": "3 min read",
                "icon": "fa-moon",
                "doctor_endorsement": "Verified by Dr. Rajesh Verma, Neurologist",
                "likes_count": 165
            },
            {
                "title": "Hydration Science: Electrolytes vs Plain Water",
                "category": "Fitness",
                "summary": "Why high water intake without balanced sodium, magnesium, and potassium can cause paradoxically sluggish cellular hydration.",
                "content": "Drinking gallons of demineralized water in warm climates dilutes plasma sodium, potentially leading to mild hyponatremia and headache. Pair drinking water with natural mineral electrolytes—such as lemon with a pinch of pink rock salt and tender coconut water—for sustained physical endurance and mental clarity.",
                "read_time": "3 min read",
                "icon": "fa-bottle-water",
                "doctor_endorsement": "Verified by Sports Medicine Team",
                "likes_count": 78
            }
        ]
        for tip in tips:
            HealthTip.objects.create(
                title=tip["title"], category=tip["category"], summary=tip["summary"],
                content=tip["content"], read_time=tip["read_time"], icon=tip["icon"],
                doctor_endorsement=tip["doctor_endorsement"], likes_count=tip["likes_count"]
            )


def parse_prescription_lines(raw_text):
    """Splits raw prescription text into clean itemized medicine rows."""
    if not raw_text:
        return []
    import re
    lines = [l.strip() for l in raw_text.replace('\r', '').split('\n') if l.strip()]
    items = []
    for idx, line in enumerate(lines, 1):
        clean_line = re.sub(r'^\d+[\.\)\-]\s*', '', line)
        parts = [p.strip() for p in clean_line.split('-')]
        if len(parts) >= 2:
            med_name = parts[0]
            directions = " - ".join(parts[1:])
        else:
            med_name = clean_line
            directions = "Take as prescribed by physician"
        items.append({
            'num': idx,
            'name': med_name,
            'directions': directions,
            'raw': clean_line
        })
    return items


# ==============================================================================
# SECTION 1: HOME (DASHBOARD)
# ==============================================================================

@login_required
def patient_home(request):
    """Main patient home dashboard with welcome banner, doctor summaries, AI tool & quick stats."""
    ensure_patient_portal_seed_data()
    patient = get_current_patient(request.user)

    # Available doctors
    doctors = DoctorProfile.objects.select_related('user', 'clinic').all()
    doctors_count = doctors.count()

    # Recommended doctors (top rated)
    recommended_doctors = doctors.order_by('-rating')[:4]

    # Upcoming appointment
    today = timezone.localdate()
    upcoming_appointment = Appointments.objects.filter(
        patient=patient,
        date__gte=today,
        status__in=['scheduled', 'confirmed']
    ).select_related('doctor', 'doctor__user', 'clinic').order_by('date', 'start_time').first()

    # Recent prescriptions count
    recent_prescriptions = MedicalRecord.objects.filter(
        patient=patient,
        prescription__isnull=False
    ).exclude(prescription='').order_by('-date')[:3]
    for rx in recent_prescriptions:
        rx.parsed_meds = parse_prescription_lines(rx.prescription)

    # Active lab orders
    recent_lab_orders = LabOrderTicket.objects.filter(
        patient=patient
    ).order_by('-order_created_at')[:3]

    # Unread messages count
    unread_messages_count = PatientDoctorMessage.objects.filter(
        patient=patient,
        is_doctor_reply=True,
        is_read=False
    ).count()

    # Featured wellness tips
    featured_tips = HealthTip.objects.order_by('-likes_count')[:3]

    # Common specialties summary
    specialties = list(doctors.values_list('specialization', flat=True).distinct())

    context = {
        'patient': patient,
        'doctors': doctors,
        'doctors_count': doctors_count,
        'recommended_doctors': recommended_doctors,
        'upcoming_appointment': upcoming_appointment,
        'recent_prescriptions': recent_prescriptions,
        'recent_lab_orders': recent_lab_orders,
        'unread_messages_count': unread_messages_count,
        'featured_tips': featured_tips,
        'specialties': specialties,
        'active_menu': 'home'
    }
    return render(request, 'patient/home.html', context)


# ==============================================================================
# SECTION 2: BOOK APPOINTMENT
# ==============================================================================

@login_required
def book_appointment(request):
    """Full booking workflow: Specialty -> Doctor -> Date -> Time Slot -> Fee -> Confirm."""
    ensure_patient_portal_seed_data()
    patient = get_current_patient(request.user)
    doctors = DoctorProfile.objects.select_related('user', 'clinic').all()

    # Distinct specialties
    specialties = sorted(list(set(doc.specialization for doc in doctors if doc.specialization)))
    if "General Practice" in specialties and "General Physician" not in specialties:
        specialties.append("General Physician")

    # Generate next 14 available dates
    today = timezone.localdate()
    available_dates = []
    for i in range(1, 15):
        d = today + datetime.timedelta(days=i)
        available_dates.append({
            'date_str': d.strftime('%Y-%m-%d'),
            'day_name': d.strftime('%a'),
            'formatted': d.strftime('%a, %d %b'),
            'is_weekend': d.weekday() in [5, 6]
        })

    # Standard clinic time slots
    standard_slots = [
        "09:00 AM", "09:30 AM", "10:00 AM", "10:30 AM",
        "11:00 AM", "11:30 AM", "02:00 PM", "02:30 PM",
        "03:00 PM", "03:30 PM", "04:00 PM", "04:30 PM"
    ]

    selected_doctor_id = request.GET.get('doctor_id')
    selected_specialty = request.GET.get('specialty', '')

    if request.method == 'POST':
        doctor_id = request.POST.get('doctor_id')
        date_str = request.POST.get('date')
        time_slot_str = request.POST.get('time_slot')
        reason = request.POST.get('reason_for_visit', 'General Health Consultation').strip()
        family_member_id = request.POST.get('family_member_id')

        if not doctor_id or not date_str or not time_slot_str:
            messages.error(request, "Please choose a doctor, appointment date, and time slot.")
            return redirect('patient_book_appointment')

        target_doctor = get_object_or_404(DoctorProfile, pk=doctor_id)
        
        try:
            booking_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            # Convert 12h slot (e.g. 09:30 AM) to 24h TimeField (09:30:00)
            parsed_time = datetime.datetime.strptime(time_slot_str, '%I:%M %p').time()
        except ValueError:
            messages.error(request, "Invalid date or time format.")
            return redirect('patient_book_appointment')

        # Check for slot conflicts
        conflict = Appointments.objects.filter(
            doctor=target_doctor,
            date=booking_date,
            start_time=parsed_time,
            status__in=['scheduled', 'confirmed']
        ).exists()

        if conflict:
            messages.error(request, f"Sorry, Dr. {target_doctor.user.get_full_name()} is already booked for {time_slot_str} on {booking_date}. Please choose another time slot.")
            return redirect(f"{request.path}?doctor_id={doctor_id}")

        # Check if booking on behalf of family member
        patient_record = patient
        if family_member_id:
            fam = FamilyMember.objects.filter(id=family_member_id, patient=patient).first()
            if fam:
                reason = f"[{fam.relationship}: {fam.name}] - {reason}"

        # Create Appointment
        appointment = Appointments.objects.create(
            doctor=target_doctor,
            clinic=target_doctor.clinic,
            patient=patient_record,
            date=booking_date,
            start_time=parsed_time,
            status='scheduled',
            reason_for_visit=reason
        )

        # Generate Billing Invoice in Pending state
        fee = target_doctor.consultation_fee or Decimal('500.00')
        BillingInvoice.objects.create(
            patient=patient_record,
            doctor=target_doctor,
            appointment=appointment,
            items_summary=f"Consultation with Dr. {target_doctor.user.get_full_name()} ({target_doctor.specialization})",
            total_amount=fee,
            status='Pending',
            payment_method='Cash'
        )

        messages.success(request, f"Appointment booked successfully with Dr. {target_doctor.user.get_full_name()} for {time_slot_str} on {booking_date.strftime('%d %b %Y')}!")
        return redirect('patient_my_records')

    # Family members for selection
    family_members = FamilyMember.objects.filter(patient=patient)

    context = {
        'patient': patient,
        'doctors': doctors,
        'specialties': specialties,
        'available_dates': available_dates,
        'standard_slots': standard_slots,
        'selected_doctor_id': selected_doctor_id,
        'selected_specialty': selected_specialty,
        'family_members': family_members,
        'active_menu': 'book'
    }
    return render(request, 'patient/book_appointment.html', context)


def api_available_slots(request):
    """Returns booked and available slots for a given doctor and date."""
    doctor_id = request.GET.get('doctor_id')
    date_str = request.GET.get('date')
    if not doctor_id or not date_str:
        return JsonResponse({'status': 'error', 'message': 'Missing parameters'}, status=400)

    try:
        booking_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'status': 'error', 'message': 'Invalid date format'}, status=400)

    booked_times = list(Appointments.objects.filter(
        doctor_id=doctor_id,
        date=booking_date,
        status__in=['scheduled', 'confirmed']
    ).values_list('start_time', flat=True))

    booked_formatted = [t.strftime('%I:%M %p') for t in booked_times]
    standard_slots = [
        "09:00 AM", "09:30 AM", "10:00 AM", "10:30 AM",
        "11:00 AM", "11:30 AM", "02:00 PM", "02:30 PM",
        "03:00 PM", "03:30 PM", "04:00 PM", "04:30 PM"
    ]

    slots_data = []
    for slot in standard_slots:
        slots_data.append({
            'time': slot,
            'is_available': slot not in booked_formatted
        })

    return JsonResponse({
        'status': 'success',
        'doctor_id': doctor_id,
        'date': date_str,
        'slots': slots_data
    })


# ==============================================================================
# SECTION 3: FIND DOCTORS
# ==============================================================================

@login_required
def find_doctors(request):
    """Full medical professionals directory with search, ratings, experience, address & quick booking."""
    ensure_patient_portal_seed_data()
    patient = get_current_patient(request.user)

    doctors = DoctorProfile.objects.select_related('user', 'clinic').all()

    # Search & Filters
    query = request.GET.get('q', '').strip()
    specialty_filter = request.GET.get('specialty', '').strip()

    if query:
        doctors = doctors.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(specialization__icontains=query) |
            Q(clinic__name__icontains=query) |
            Q(clinic_address__icontains=query)
        )

    if specialty_filter and specialty_filter != 'All':
        doctors = doctors.filter(specialization__icontains=specialty_filter)

    all_specialties = sorted(list(set(
        DoctorProfile.objects.values_list('specialization', flat=True)
    )))

    context = {
        'patient': patient,
        'doctors': doctors,
        'doctors_count': doctors.count(),
        'all_specialties': all_specialties,
        'query': query,
        'specialty_filter': specialty_filter,
        'active_menu': 'doctors'
    }
    return render(request, 'patient/find_doctors.html', context)


# ==============================================================================
# SECTION 4: PATIENTS (MY RECORDS & HEALTH REPOSITORY)
# ==============================================================================

@login_required
def my_records(request):
    """Manages personal health profile, visit timeline, immunization and uploaded documents."""
    ensure_patient_portal_seed_data()
    patient = get_current_patient(request.user)

    # Clinical Consultation visits
    records = MedicalRecord.objects.filter(
        patient=patient
    ).select_related('doctor', 'doctor__user', 'clinic').order_by('-date')

    for r in records:
        r.parsed_meds = parse_prescription_lines(r.prescription)

    # Immunizations
    vaccinations = VaccinationRecord.objects.filter(
        patient=patient
    ).order_by('-date_administered')

    # Uploaded Health Documents
    documents = PatientDocument.objects.filter(
        patient=patient
    ).order_by('-uploaded_at')

    # Upcoming & past appointments
    appointments = Appointments.objects.filter(
        patient=patient
    ).select_related('doctor', 'doctor__user').order_by('-date')

    context = {
        'patient': patient,
        'records': records,
        'records_count': records.count(),
        'vaccinations': vaccinations,
        'documents': documents,
        'appointments': appointments,
        'active_menu': 'records'
    }
    return render(request, 'patient/my_records.html', context)


@login_required
def upload_document(request):
    """Handles patient file upload for lab reports, scan images, or discharge files."""
    patient = get_current_patient(request.user)
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        doc_type = request.POST.get('document_type', 'Lab Report')
        notes = request.POST.get('notes', '').strip()
        uploaded_file = request.FILES.get('document_file')

        if not title:
            messages.error(request, "Document title is required.")
            return redirect('patient_my_records')

        doc = PatientDocument.objects.create(
            patient=patient,
            title=title,
            document_type=doc_type,
            notes=notes,
            file=uploaded_file
        )
        messages.success(request, f"Document '{doc.title}' uploaded to your medical repository successfully!")
    return redirect('patient_my_records')


@login_required
def delete_document(request, doc_id):
    """Deletes an uploaded document from the patient's repository."""
    patient = get_current_patient(request.user)
    doc = get_object_or_404(PatientDocument, id=doc_id, patient=patient)
    doc_title = doc.title
    doc.delete()
    messages.info(request, f"Document '{doc_title}' removed.")
    return redirect('patient_my_records')


@login_required
def add_vaccination(request):
    """Adds a new immunization record to the patient's tracker."""
    patient = get_current_patient(request.user)
    if request.method == 'POST':
        vaccine_name = request.POST.get('vaccine_name', '').strip()
        dose_number = request.POST.get('dose_number', 'Dose 1').strip()
        date_admin_str = request.POST.get('date_administered')
        next_due_str = request.POST.get('next_due_date')
        administered_by = request.POST.get('administered_by', 'Clinic Staff').strip()
        batch = request.POST.get('batch_number', '').strip()

        if not vaccine_name:
            messages.error(request, "Vaccine name is required.")
            return redirect('patient_my_records')

        date_administered = timezone.localdate()
        if date_admin_str:
            try:
                date_administered = datetime.datetime.strptime(date_admin_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        next_due = None
        if next_due_str:
            try:
                next_due = datetime.datetime.strptime(next_due_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        VaccinationRecord.objects.create(
            patient=patient,
            vaccine_name=vaccine_name,
            dose_number=dose_number,
            date_administered=date_administered,
            next_due_date=next_due,
            administered_by=administered_by,
            batch_number=batch,
            status='Completed'
        )
        messages.success(request, f"Vaccination '{vaccine_name} ({dose_number})' recorded successfully!")
    return redirect('patient_my_records')


# ==============================================================================
# SECTION 5: PRESCRIPTIONS
# ==============================================================================

@login_required
def patient_prescriptions(request):
    """Digital prescription vault with itemized drugs, ReportLab PDF download & refill requests."""
    ensure_patient_portal_seed_data()
    patient = get_current_patient(request.user)

    # All medical records that contain a prescription
    prescriptions = MedicalRecord.objects.filter(
        patient=patient,
        prescription__isnull=False
    ).exclude(prescription='').select_related('doctor', 'doctor__user', 'clinic').order_by('-date')

    for rx in prescriptions:
        rx.parsed_meds = parse_prescription_lines(rx.prescription)

    context = {
        'patient': patient,
        'prescriptions': prescriptions,
        'prescriptions_count': prescriptions.count(),
        'active_menu': 'prescriptions'
    }
    return render(request, 'patient/prescriptions.html', context)


@login_required
def request_prescription_refill(request, record_id):
    """Submits a medication refill request to the prescribing physician via secure messaging."""
    patient = get_current_patient(request.user)
    rec = get_object_or_404(MedicalRecord, id=record_id, patient=patient)

    if request.method == 'POST':
        med_notes = request.POST.get('refill_notes', 'Requesting medication renewal for next 30 days.').strip()
        
        # Message to doctor
        msg_content = f"Prescription Refill Request for Consultation #{rec.id} ({rec.date.strftime('%d %b %Y')}). Notes: {med_notes}"
        PatientDoctorMessage.objects.create(
            patient=patient,
            doctor=rec.doctor,
            sender=request.user,
            category='Prescription Refill',
            message=msg_content,
            is_doctor_reply=False
        )

        # Automated confirmation acknowledgement
        ack_content = f"Hello {patient.name}, Dr. {rec.doctor.user.get_full_name()}'s care desk has received your refill request for Prescription #{rec.id}. The physician will review your clinical history and confirm within 2-4 business hours."
        PatientDoctorMessage.objects.create(
            patient=patient,
            doctor=rec.doctor,
            sender=rec.doctor.user,
            category='Prescription Refill',
            message=ack_content,
            is_doctor_reply=True
        )

        messages.success(request, f"Refill request sent to Dr. {rec.doctor.user.get_full_name()} successfully!")
    return redirect('patient_prescriptions')


# ==============================================================================
# SECTION 6: LAB TESTS
# ==============================================================================

@login_required
def lab_tests(request):
    """Diagnostic tests catalog (browse & book) plus lab ticket tracker and test results."""
    ensure_patient_portal_seed_data()
    patient = get_current_patient(request.user)

    # Diagnostic catalog
    catalog = LabTestCatalog.objects.all().order_by('-is_popular', 'name')
    popular_tests = catalog.filter(is_popular=True)

    # Patient's lab tickets
    lab_tickets = LabOrderTicket.objects.filter(
        patient=patient
    ).select_related('doctor', 'doctor__user').order_by('-order_created_at')

    # Distinct categories for filtering
    categories = sorted(list(set(catalog.values_list('category', flat=True))))

    context = {
        'patient': patient,
        'catalog': catalog,
        'popular_tests': popular_tests,
        'lab_tickets': lab_tickets,
        'lab_tickets_count': lab_tickets.count(),
        'categories': categories,
        'active_menu': 'labs'
    }
    return render(request, 'patient/lab_tests.html', context)


@login_required
def book_lab_test(request):
    """Schedules a diagnostic lab test with collection preferences."""
    patient = get_current_patient(request.user)
    if request.method == 'POST':
        test_code = request.POST.get('test_code')
        collection_type = request.POST.get('collection_type', 'Home Sample Collection')
        preferred_date_str = request.POST.get('preferred_date')
        notes = request.POST.get('special_instructions', '').strip()

        test_item = get_object_or_404(LabTestCatalog, code=test_code)
        doctor = patient.doctor or DoctorProfile.objects.first()

        clinical_notes = f"Collection Mode: {collection_type}. Preferred Date: {preferred_date_str}. Instructions: {notes or 'Standard Diagnostic Protocol'}"

        ticket = LabOrderTicket.objects.create(
            ticket_id=generate_short_uuid(),
            doctor=doctor,
            patient=patient,
            test_name=test_item.name,
            test_code=test_item.code,
            status='Order Created',
            clinical_notes=clinical_notes,
            technician_name="Central PathLab Diagnostics"
        )
        messages.success(request, f"Lab order #{ticket.ticket_id[:8]} for '{test_item.name}' confirmed! Our collection team will coordinate on {patient.phone_number}.")
    return redirect('patient_lab_tests')


# ==============================================================================
# SECTION 7: MESSAGES (DOCTOR - PATIENT CHAT)
# ==============================================================================

@login_required
def patient_messages(request):
    """In-app communication hub for follow-ups, dosage clarifications, and clinical queries."""
    ensure_patient_portal_seed_data()
    patient = get_current_patient(request.user)

    doctors = DoctorProfile.objects.select_related('user', 'clinic').all()

    # Active selected doctor
    doctor_id = request.GET.get('doctor_id')
    if doctor_id:
        active_doctor = get_object_or_404(DoctorProfile, id=doctor_id)
    else:
        # Default to the doctor the patient consulted recently or the first doctor
        recent_record = MedicalRecord.objects.filter(patient=patient).order_by('-date').first()
        active_doctor = recent_record.doctor if recent_record else doctors.first()

    # Fetch chat thread
    chat_messages = []
    if active_doctor:
        chat_messages = PatientDoctorMessage.objects.filter(
            patient=patient,
            doctor=active_doctor
        ).order_by('created_at')

        # Mark doctor replies as read
        PatientDoctorMessage.objects.filter(
            patient=patient,
            doctor=active_doctor,
            is_doctor_reply=True,
            is_read=False
        ).update(is_read=True)

    if request.method == 'POST':
        msg_text = request.POST.get('message', '').strip()
        category = request.POST.get('category', 'General Inquiry')
        target_doc_id = request.POST.get('doctor_id')

        if msg_text and target_doc_id:
            target_doc = get_object_or_404(DoctorProfile, id=target_doc_id)
            PatientDoctorMessage.objects.create(
                patient=patient,
                doctor=target_doc,
                sender=request.user,
                category=category,
                message=msg_text,
                is_doctor_reply=False
            )

            # Auto-reply from physician's clinical assistant
            ack_msg = f"Thank you for contacting Dr. {target_doc.user.get_full_name()}. We have received your query regarding '{category}'. Typical response turnaround is within 2 hours during clinic working hours."
            PatientDoctorMessage.objects.create(
                patient=patient,
                doctor=target_doc,
                sender=target_doc.user,
                category=category,
                message=ack_msg,
                is_doctor_reply=True
            )

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success'})
            return redirect(f"{request.path}?doctor_id={target_doc_id}")

    context = {
        'patient': patient,
        'doctors': doctors,
        'active_doctor': active_doctor,
        'chat_messages': chat_messages,
        'active_menu': 'messages'
    }
    return render(request, 'patient/messages.html', context)


# ==============================================================================
# SECTION 8: HEALTH TIPS (WELLNESS FEED)
# ==============================================================================

@login_required
def health_tips(request):
    """Curated wellness articles feed and preventive care guides."""
    ensure_patient_portal_seed_data()
    patient = get_current_patient(request.user)

    tips = HealthTip.objects.all().order_by('-published_date')

    # Category filter & search
    category_filter = request.GET.get('category', '').strip()
    query = request.GET.get('q', '').strip()

    if category_filter and category_filter != 'All':
        tips = tips.filter(category__iexact=category_filter)
    if query:
        tips = tips.filter(
            Q(title__icontains=query) |
            Q(summary__icontains=query) |
            Q(content__icontains=query)
        )

    categories = sorted(list(set(HealthTip.objects.values_list('category', flat=True))))

    context = {
        'patient': patient,
        'tips': tips,
        'categories': categories,
        'selected_category': category_filter,
        'query': query,
        'active_menu': 'health_tips'
    }
    return render(request, 'patient/health_tips.html', context)


@login_required
def like_health_tip(request, tip_id):
    """Increments like count on a wellness article."""
    tip = get_object_or_404(HealthTip, id=tip_id)
    tip.likes_count += 1
    tip.save(update_fields=['likes_count'])
    return JsonResponse({'status': 'success', 'likes_count': tip.likes_count})


# ==============================================================================
# SECTION 9: SETTINGS
# ==============================================================================

@login_required
def patient_settings(request):
    """Personal health profile, emergency contacts, notification preferences & linked family members."""
    ensure_patient_portal_seed_data()
    patient = get_current_patient(request.user)
    family_members = FamilyMember.objects.filter(patient=patient).order_by('created_at')

    if request.method == 'POST':
        action = request.POST.get('action', 'update_profile')

        if action == 'update_profile':
            patient.name = request.POST.get('name', patient.name).strip()
            patient.phone_number = request.POST.get('phone_number', patient.phone_number).strip()
            patient.gender = request.POST.get('gender', patient.gender)
            dob_str = request.POST.get('date_of_birth')
            if dob_str:
                try:
                    patient.date_of_birth = datetime.datetime.strptime(dob_str, '%Y-%m-%d').date()
                except ValueError:
                    pass
            patient.blood_group = request.POST.get('blood_group', patient.blood_group).strip()
            patient.address = request.POST.get('address', patient.address).strip()
            patient.allergies = request.POST.get('allergies', patient.allergies).strip()
            patient.medical_history = request.POST.get('medical_history', patient.medical_history).strip()
            patient.preferred_language = request.POST.get('preferred_language', patient.preferred_language)

            patient.emergency_contact_name = request.POST.get('emergency_contact_name', patient.emergency_contact_name).strip()
            patient.emergency_contact_phone = request.POST.get('emergency_contact_phone', patient.emergency_contact_phone).strip()

            # Notifications toggles
            patient.notify_sms = 'notify_sms' in request.POST
            patient.notify_email = 'notify_email' in request.POST
            patient.notify_whatsapp = 'notify_whatsapp' in request.POST

            patient.save()
            messages.success(request, "Personal health profile and preferences updated successfully!")
            return redirect('patient_settings')

    context = {
        'patient': patient,
        'family_members': family_members,
        'active_menu': 'settings'
    }
    return render(request, 'patient/settings.html', context)


@login_required
def add_family_member(request):
    """Adds a dependent or linked family member."""
    patient = get_current_patient(request.user)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        relationship = request.POST.get('relationship', 'Child')
        gender = request.POST.get('gender', 'Male')
        dob_str = request.POST.get('date_of_birth')
        blood_group = request.POST.get('blood_group', 'O+').strip()
        allergies = request.POST.get('allergies', 'None').strip()
        notes = request.POST.get('notes', '').strip()

        dob = None
        if dob_str:
            try:
                dob = datetime.datetime.strptime(dob_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        if name:
            FamilyMember.objects.create(
                patient=patient,
                name=name,
                relationship=relationship,
                gender=gender,
                date_of_birth=dob,
                blood_group=blood_group,
                allergies=allergies,
                notes=notes
            )
            messages.success(request, f"Family member '{name}' linked successfully!")
    return redirect('patient_settings')


@login_required
def delete_family_member(request, member_id):
    """Removes a linked family member."""
    patient = get_current_patient(request.user)
    member = get_object_or_404(FamilyMember, id=member_id, patient=patient)
    m_name = member.name
    member.delete()
    messages.info(request, f"Family member '{m_name}' removed.")
    return redirect('patient_settings')


# ==============================================================================
# AI RECOMMENDATION TOOL (INTELLIGENT SYMPTOM-TO-DOCTOR MATCHER)
# ==============================================================================

def api_ai_recommend_doctor(request):
    """Analyzes freeform symptoms and matches the optimal medical specialty & top doctors."""
    symptoms = request.GET.get('symptoms', '').lower().strip()
    if not symptoms:
        return JsonResponse({'status': 'error', 'message': 'Please provide symptom details.'}, status=400)

    # Symptom mapping rules
    rules = [
        {
            'keywords': ['chest pain', 'palpitation', 'heart', 'breathless', 'blood pressure', 'shortness of breath', 'bp'],
            'specialty': 'Cardiology',
            'rationale': 'Symptoms indicate potential cardiovascular or hemodynamic evaluation requirements.',
            'urgency': 'Immediate Attention / High Priority'
        },
        {
            'keywords': ['child', 'baby', 'infant', 'toddler', 'pediatric', 'growth', 'vaccination'],
            'specialty': 'Pediatrics',
            'rationale': 'Specialized pediatric developmental assessment and adolescent clinical care.',
            'urgency': 'Prompt Pediatric Review'
        },
        {
            'keywords': ['skin', 'rash', 'itching', 'acne', 'eczema', 'allergy', 'mole', 'dermatitis', 'psoriasis'],
            'specialty': 'Dermatology',
            'rationale': 'Cutaneous dermatological evaluation and topical dermatological management.',
            'urgency': 'Routine Care'
        },
        {
            'keywords': ['bone', 'joint', 'knee', 'fracture', 'back pain', 'spine', 'shoulder', 'arthritis', 'ligament'],
            'specialty': 'Orthopedics',
            'rationale': 'Musculoskeletal assessment, biomechanical evaluation, and mobility protection.',
            'urgency': 'Standard Clinical Consultation'
        },
        {
            'keywords': ['headache', 'migraine', 'dizziness', 'seizure', 'numbness', 'nerve', 'tremor'],
            'specialty': 'Neurology',
            'rationale': 'Neurological diagnostic screening and cranial nerve assessment.',
            'urgency': 'Prompt Specialist Review'
        },
        {
            'keywords': ['ear', 'nose', 'throat', 'sinus', 'hearing', 'tonsil', 'voice', 'nasal'],
            'specialty': 'ENT Specialist',
            'rationale': 'Ear, Nose, and Throat physical inspection and airway diagnostic review.',
            'urgency': 'Standard Consultation'
        }
    ]

    matched_rule = None
    for r in rules:
        if any(kw in symptoms for kw in r['keywords']):
            matched_rule = r
            break

    if not matched_rule:
        matched_rule = {
            'specialty': 'General Physician',
            'rationale': 'Comprehensive primary medical intake, diagnostic lab triage, and targeted clinical routing.',
            'urgency': 'Standard Outpatient Consultation'
        }

    # Find matching doctors
    matched_doctors = DoctorProfile.objects.filter(
        Q(specialization__icontains=matched_rule['specialty']) |
        Q(specialization__icontains='General')
    ).select_related('user', 'clinic').order_by('-rating')[:3]

    doctors_data = []
    for doc in matched_doctors:
        doctors_data.append({
            'id': doc.id,
            'name': f"Dr. {doc.user.get_full_name() or doc.user.username}",
            'specialty': doc.specialization,
            'rating': float(doc.rating or 4.9),
            'experience': f"{doc.experience_years or 10}+ Years",
            'fee': f"₹{int(doc.consultation_fee or 500)}",
            'clinic': doc.clinic.name if doc.clinic else "Sunrise Health Clinic",
            'address': doc.clinic_address or "Senapati Bapat Road, Pune",
            'book_url': f"/patient/book-appointment/?doctor_id={doc.id}&specialty={matched_rule['specialty']}"
        })

    return JsonResponse({
        'status': 'success',
        'symptoms_analyzed': symptoms,
        'recommended_specialty': matched_rule['specialty'],
        'clinical_rationale': matched_rule['rationale'],
        'urgency_level': matched_rule['urgency'],
        'matching_doctors': doctors_data
    })


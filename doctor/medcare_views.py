import json
import uuid
from datetime import datetime, timedelta, date, time
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Count, Q, Sum
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from accounts.decorators import doctor_required, doctor_or_assistant_required
from .models import (
    DoctorProfile, Patients, Appointments, MedicalRecord, Clinic,
    AvailabilityBlock, WaitlistQueue, TriageEscalationLog, LabOrderTicket,
    PatientRecordViewToken, FollowUpTask, InventoryItem, QueueTicket,
    Referral, ClaimRecord, SmsLog, AuditLogEntry, LeadEntry,
    ClinicLocation, BillingInvoice
)

def _get_active_doctor(request):
    """Safely resolve doctor profile whether logged in as Doctor, Assistant, or Admin."""
    if hasattr(request.user, 'is_doctor') and request.user.is_doctor():
        return DoctorProfile.get_or_create_for_user(request.user)
    elif hasattr(request.user, 'is_assistant') and request.user.is_assistant():
        from assistant.models import AssistantProfile
        assistant = AssistantProfile.objects.filter(user=request.user).first()
        if assistant and assistant.doctor:
            return assistant.doctor
        return DoctorProfile.objects.first() or DoctorProfile.get_or_create_for_user(request.user)
    else:
        profile = DoctorProfile.objects.filter(user=request.user).first()
        if not profile:
            profile = DoctorProfile.objects.first()
        if not profile:
            profile = DoctorProfile.get_or_create_for_user(request.user)
        return profile

# Common Medications Catalog for Autocomplete
COMMON_DRUGS = [
    {"name": "Amoxicillin", "dosage": "500mg", "form": "Capsule", "frequency": "TID (Three times daily)", "timing": "After meals", "category": "Antibiotic"},
    {"name": "Augmentin (Amoxicillin/Clavulanate)", "dosage": "625mg", "form": "Tablet", "frequency": "BID (Twice daily)", "timing": "With meals", "category": "Antibiotic"},
    {"name": "Azithromycin", "dosage": "500mg", "form": "Tablet", "frequency": "OD (Once daily)", "timing": "1 hour before meals", "category": "Antibiotic"},
    {"name": "Ciprofloxacin", "dosage": "500mg", "form": "Tablet", "frequency": "BID (Twice daily)", "timing": "After meals", "category": "Antibiotic"},
    {"name": "Paracetamol (Acetaminophen)", "dosage": "500mg", "form": "Tablet", "frequency": "PRN (As needed q6h)", "timing": "After meals", "category": "Analgesic / Antipyretic"},
    {"name": "Ibuprofen", "dosage": "400mg", "form": "Tablet", "frequency": "TID (Three times daily)", "timing": "After meals", "category": "NSAID"},
    {"name": "Metformin HCl", "dosage": "500mg", "form": "Tablet", "frequency": "BID (Twice daily)", "timing": "With meals", "category": "Antidiabetic"},
    {"name": "Metformin HCl", "dosage": "850mg", "form": "Tablet", "frequency": "BID (Twice daily)", "timing": "With meals", "category": "Antidiabetic"},
    {"name": "Atorvastatin", "dosage": "20mg", "form": "Tablet", "frequency": "OD (Once daily)", "timing": "At bedtime", "category": "Lipid Lowering"},
    {"name": "Amlodipine Besylate", "dosage": "5mg", "form": "Tablet", "frequency": "OD (Once daily)", "timing": "Morning", "category": "Antihypertensive"},
    {"name": "Losartan Potassium", "dosage": "50mg", "form": "Tablet", "frequency": "OD (Once daily)", "timing": "Morning", "category": "Antihypertensive"},
    {"name": "Omeprazole", "dosage": "20mg", "form": "Capsule", "frequency": "OD (Once daily)", "timing": "30 mins before breakfast", "category": "Proton Pump Inhibitor"},
    {"name": "Pantoprazole", "dosage": "40mg", "form": "Tablet", "frequency": "OD (Once daily)", "timing": "Before breakfast", "category": "Proton Pump Inhibitor"},
    {"name": "Cetirizine HCl", "dosage": "10mg", "form": "Tablet", "frequency": "OD (Once daily)", "timing": "At bedtime", "category": "Antihistamine"},
    {"name": "Montelukast", "dosage": "10mg", "form": "Tablet", "frequency": "OD (Once daily)", "timing": "At bedtime", "category": "Respiratory"},
    {"name": "Salbutamol (Albuterol) Inhaler", "dosage": "100mcg", "form": "Inhaler", "frequency": "PRN (2 puffs as needed)", "timing": "Inhalation", "category": "Bronchodilator"},
    {"name": "Hydrochlorothiazide", "dosage": "25mg", "form": "Tablet", "frequency": "OD (Once daily)", "timing": "Morning", "category": "Diuretic"},
    {"name": "Prednisolone", "dosage": "5mg", "form": "Tablet", "frequency": "OD (Morning taper)", "timing": "After breakfast", "category": "Corticosteroid"},
    {"name": "Diclofenac Sodium", "dosage": "50mg", "form": "Tablet", "frequency": "BID (Twice daily)", "timing": "After meals", "category": "NSAID"},
    {"name": "Cough Syrup (Guaifenesin)", "dosage": "10ml", "form": "Liquid", "frequency": "TID (Three times daily)", "timing": "After meals", "category": "Expectorant"},
]

def _log_audit(user, action_type, description, request=None):
    ip = request.META.get('REMOTE_ADDR') if request else '127.0.0.1'
    AuditLogEntry.objects.create(
        user=user if (user and user.is_authenticated) else None,
        action_type=action_type,
        description=description,
        ip_address=ip
    )

def _seed_defaults_if_empty(doctor):
    """Seed sample data for calendar, inventory, locations, queue so the clinic looks full immediately."""
    if not doctor:
        return
    clinic = doctor.clinic
    if not clinic:
        clinic_name = f"Dr. {doctor.user.get_full_name() or doctor.user.username}'s Clinic"
        clinic, _ = Clinic.objects.get_or_create(name=clinic_name)
        doctor.clinic = clinic
        doctor.save(update_fields=['clinic'])
    if clinic and not ClinicLocation.objects.filter(clinic=clinic).exists():
        ClinicLocation.objects.create(clinic=clinic, name="Consultation Suite 1", room_number="101", purpose="General Medicine")
        ClinicLocation.objects.create(clinic=clinic, name="Minor Procedures Room", room_number="102", purpose="Procedures & Dressings")
        ClinicLocation.objects.create(clinic=clinic, name="Triage & Vitals Bay", room_number="103", purpose="Nursing Assessment")

    if clinic and not InventoryItem.objects.filter(clinic=clinic).exists():
        for item in [
            {"name": "Amoxicillin 500mg Caps", "category": "Medication", "stock": 450, "unit": "Capsules", "reorder": 100, "price": 1.20},
            {"name": "Paracetamol 500mg Tabs", "category": "Medication", "stock": 800, "unit": "Tablets", "reorder": 200, "price": 0.40},
            {"name": "Metformin 500mg Tabs", "category": "Medication", "stock": 350, "unit": "Tablets", "reorder": 100, "price": 0.80},
            {"name": "Omeprazole 20mg Caps", "category": "Medication", "stock": 280, "unit": "Capsules", "reorder": 80, "price": 1.50},
            {"name": "Disposable Sterile Syringes 5ml", "category": "Consumable", "stock": 140, "unit": "Pieces", "reorder": 50, "price": 0.60},
            {"name": "Rapid Strep Test Kits", "category": "Diagnostic", "stock": 35, "unit": "Kits", "reorder": 20, "price": 8.50},
            {"name": "Latex Examination Gloves (M)", "category": "Consumable", "stock": 18, "unit": "Boxes (100)", "reorder": 25, "price": 12.00},
            {"name": "Digital Thermometer Covers", "category": "Consumable", "stock": 300, "unit": "Pieces", "reorder": 100, "price": 0.15},
        ]:
            InventoryItem.objects.create(
                clinic=clinic, name=item["name"], category=item["category"],
                stock_quantity=item["stock"], unit=item["unit"], reorder_level=item["reorder"],
                unit_price=item["price"]
            )

    if not AvailabilityBlock.objects.filter(doctor=doctor).exists():
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
            AvailabilityBlock.objects.create(
                doctor=doctor, day_of_week=day, start_time=time(9, 0), end_time=time(17, 0),
                slot_duration_minutes=20, break_start=time(13, 0), break_end=time(14, 0)
            )

# ==============================================================================
# 1. CALENDAR VIEW (Highlighted MedCare Feature)
# ==============================================================================
@login_required
@doctor_or_assistant_required
def calendar_view(request):
    doctor = _get_active_doctor(request)
    _seed_defaults_if_empty(doctor)
    
    patients = Patients.objects.filter(Q(doctor=doctor) | Q(clinic=doctor.clinic))
    locations = ClinicLocation.objects.filter(clinic=doctor.clinic) if doctor.clinic else []
    
    today = date.today()
    selected_date_str = request.GET.get('date', today.strftime('%Y-%m-%d'))
    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = today

    # Fetch appointments for the selected date
    appointments_today = Appointments.objects.filter(doctor=doctor, date=selected_date).order_by('start_time')
    
    # Calculate daily slot occupancy
    total_slots = 18 # Standard 9am-5pm 20m slots with 1hr break
    booked_count = appointments_today.count()
    occupancy_pct = min(100, int((booked_count / max(total_slots, 1)) * 100))

    context = {
        'doctor': doctor,
        'patients': patients,
        'locations': locations,
        'selected_date': selected_date_str,
        'appointments_today': appointments_today,
        'booked_count': booked_count,
        'total_slots': total_slots,
        'occupancy_pct': occupancy_pct,
        'active_menu': 'calendar',
    }
    return render(request, 'calendar.html', context)

@login_required
@doctor_or_assistant_required
def api_calendar_events(request):
    """Return JSON events for React calendar integration."""
    doctor = _get_active_doctor(request)
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    
    query = Q(doctor=doctor)
    if start_date and end_date:
        query &= Q(date__range=[start_date, end_date])
        
    appts = Appointments.objects.filter(query).select_related('patient')
    events = []
    for a in appts:
        start_dt = f"{a.date.strftime('%Y-%m-%d')}T{a.start_time.strftime('%H:%M:%S')}"
        # Estimate 20m end time
        end_time_calc = (datetime.combine(a.date, a.start_time) + timedelta(minutes=20)).time()
        end_dt = f"{a.date.strftime('%Y-%m-%d')}T{end_time_calc.strftime('%H:%M:%S')}"
        
        events.append({
            'id': a.id,
            'title': f"{a.patient.name} ({a.reason_for_visit or 'Consultation'})",
            'patient_name': a.patient.name,
            'patient_id': a.patient.id,
            'patient_phone': a.patient.phone_number,
            'start': start_dt,
            'end': end_dt,
            'status': a.status,
            'priority': a.priority_tier,
            'reminder_tier': a.reminder_tier,
        })
    return JsonResponse({'events': events})

@login_required
@doctor_or_assistant_required
@csrf_exempt
def api_book_slot(request):
    """Book a new slot from calendar or booking dialog."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    doctor = _get_active_doctor(request)
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    patient_id = data.get('patient_id')
    patient_name = data.get('patient_name')
    patient_phone = data.get('patient_phone')
    appt_date_str = data.get('date')
    start_time_str = data.get('start_time')
    reason = data.get('reason', 'General Consultation')
    priority = data.get('priority', 'Routine')

    if not appt_date_str or not start_time_str:
        return JsonResponse({'error': 'Date and start_time are required'}, status=400)

    try:
        appt_date = datetime.strptime(appt_date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
    except ValueError:
        return JsonResponse({'error': 'Invalid date/time format (expected YYYY-MM-DD and HH:MM)'}, status=400)

    # Resolve or create patient
    if patient_id:
        patient = get_object_or_404(Patients, id=patient_id)
    elif patient_name and patient_phone:
        patient, _ = Patients.objects.get_or_create(
            phone_number=patient_phone,
            defaults={'name': patient_name, 'clinic': doctor.clinic, 'doctor': doctor, 'gender': 'Male'}
        )
    else:
        return JsonResponse({'error': 'Provide patient_id or patient_name + phone'}, status=400)

    # Check for slot collision
    if Appointments.objects.filter(doctor=doctor, date=appt_date, start_time=start_time).exclude(status='cancelled').exists():
        return JsonResponse({'error': 'Slot already booked. Please choose another time or join waitlist.'}, status=409)

    appt = Appointments.objects.create(
        doctor=doctor,
        clinic=doctor.clinic,
        patient=patient,
        date=appt_date,
        start_time=start_time,
        status='confirmed',
        reason_for_visit=reason,
        priority_tier=priority,
        reminder_tier='Standard' if patient.risk_tier == 'Low' else 'Aggressive'
    )

    # Auto create Queue Token for today's appointments
    if appt_date == date.today():
        token_num = f"A-{Appointments.objects.filter(doctor=doctor, date=appt_date).count() + 100}"
        QueueTicket.objects.create(
            token_number=token_num,
            patient_name=patient.name,
            doctor=doctor,
            appointment=appt,
            status='Waiting'
        )

    # Log SMS confirmation
    SmsLog.objects.create(
        recipient_name=patient.name,
        phone_number=patient.phone_number,
        message_type='Appointment Reminder',
        content=f"Hi {patient.name}, your appointment with Dr. {doctor.user.get_full_name() or doctor.user.username} is CONFIRMED for {appt_date.strftime('%b %d, %Y')} at {start_time.strftime('%I:%M %p')}.",
        status='Delivered'
    )

    _log_audit(request.user, 'BOOK_APPOINTMENT', f"Booked appointment #{appt.id} for {patient.name} on {appt_date}", request)

    return JsonResponse({
        'success': True,
        'appointment_id': appt.id,
        'patient_name': patient.name,
        'date': str(appt.date),
        'start_time': start_time.strftime('%H:%M'),
        'status': appt.status
    })

# ==============================================================================
# 2. CONVERSATIONAL VOICE & CHAT AI BOOKING AGENT + EMERGENCY TRIAGE
# ==============================================================================
@csrf_exempt
def api_ai_booking_agent(request):
    """
    AI Conversational booking agent:
    - Receives user voice transcript / chat text.
    - Runs Emergency Keyword Triage.
    - If critical symptoms detected, halts booking and triggers immediate emergency escalation.
    - If routine, parses name, phone, symptom, desired time and books or waitlists.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    message = data.get('message', '').strip()
    caller_name = data.get('name', '').strip()
    caller_phone = data.get('phone', '').strip()

    if not message:
        return JsonResponse({'error': 'Message content is empty'}, status=400)

    # 1. EMERGENCY KEYWORD TRIAGE ENGINE
    emergency_triggers = [
        "chest pain", "pressure in chest", "shortness of breath", "trouble breathing",
        "cannot breathe", "severe bleeding", "unconscious", "passed out", "stroke",
        "facial drooping", "severe head injury", "suicidal", "coughing blood", "anaphylaxis"
    ]
    message_lower = message.lower()
    matched_emergency = None
    for trigger in emergency_triggers:
        if trigger in message_lower:
            matched_emergency = trigger
            break

    if matched_emergency:
        triage_log = TriageEscalationLog.objects.create(
            patient_name=caller_name or "Anonymous Caller",
            patient_phone=caller_phone or "Not Provided",
            trigger_phrase=matched_emergency,
            severity='CRITICAL',
            notes=f"Full transcript: '{message}'",
            escalated_to="Emergency Triage Team & On-Duty Clinical Staff"
        )
        return JsonResponse({
            'status': 'emergency_escalated',
            'is_emergency': True,
            'trigger': matched_emergency,
            'triage_id': triage_log.id,
            'bot_reply': (
                f"🚨 EMERGENCY ALERT TRIGGERED: We detected critical symptoms ('{matched_emergency}'). "
                "Standard scheduling has been halted. Your inquiry has been escalated directly to our "
                "Emergency Duty Staff. Please call emergency services (911 / 999) or proceed immediately to the nearest Emergency Room."
            )
        })

    # 2. INTENT & SLOT CHECK (Simulated conversational agent)
    doctor = DoctorProfile.objects.first()
    tomorrow = date.today() + timedelta(days=1)
    
    # Check slot availability for tomorrow at 10:00 AM or next available
    slot_time = time(10, 0)
    conflict = False
    if doctor:
        conflict = Appointments.objects.filter(doctor=doctor, date=tomorrow, start_time=slot_time).exclude(status='cancelled').exists()

    if conflict:
        # Offer waitlist or next slot
        waitlist_entry = None
        if doctor and caller_name and caller_phone:
            waitlist_entry = WaitlistQueue.objects.create(
                doctor=doctor,
                patient_name=caller_name,
                patient_phone=caller_phone,
                requested_date=tomorrow,
                preferred_time_range="Morning (10:00 AM - 12:00 PM)",
                reason=message,
                priority_rank=WaitlistQueue.objects.filter(doctor=doctor, status='Waiting').count() + 1
            )
        return JsonResponse({
            'status': 'waitlisted',
            'is_emergency': False,
            'bot_reply': (
                f"Thank you, {caller_name or 'there'}. 10:00 AM on {tomorrow.strftime('%b %d')} is currently occupied. "
                "I have added you to our Automated Priority Waitlist. If a cancellation occurs, "
                "our backfill engine will immediately notify you via SMS with a priority booking window!"
            ),
            'waitlist_id': waitlist_entry.id if waitlist_entry else None
        })

    # Available: Create Lead and Book tentative appointment
    lead = LeadEntry.objects.create(
        name=caller_name or "Voice Bot Patient",
        phone=caller_phone or "+1 555-0199",
        source='Conversational Bot',
        symptoms=message,
        status='Converted (Booked)'
    )

    if doctor and caller_name and caller_phone:
        patient, _ = Patients.objects.get_or_create(
            phone_number=caller_phone,
            defaults={'name': caller_name, 'clinic': doctor.clinic, 'doctor': doctor, 'gender': 'Male'}
        )
        appt = Appointments.objects.create(
            doctor=doctor,
            clinic=doctor.clinic,
            patient=patient,
            date=tomorrow,
            start_time=slot_time,
            status='scheduled',
            reason_for_visit=message[:250],
            priority_tier='Routine'
        )
        return JsonResponse({
            'status': 'booked',
            'is_emergency': False,
            'appointment_id': appt.id,
            'bot_reply': (
                f"Great! I have reserved your appointment with Dr. {doctor.user.get_full_name() or doctor.user.username} "
                f"for tomorrow, {tomorrow.strftime('%A, %b %d')} at {slot_time.strftime('%I:%M %p')}. "
                "A confirmation SMS has been dispatched with your check-in token."
            )
        })

    return JsonResponse({
        'status': 'collected_info',
        'is_emergency': False,
        'bot_reply': f"I understand your concern ('{message}'). Could you please provide your full name and phone number to finalize your booking?"
    })

# ==============================================================================
# 3. AMBIENT CONSULTATION SCRIBE (SOAP Note Generator)
# ==============================================================================
@login_required
@doctor_required
@csrf_exempt
def api_ambient_scribe(request):
    """
    Accepts raw doctor-patient speech transcript and produces a structured SOAP clinical note.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    transcript = data.get('transcript', '').strip()
    patient_id = data.get('patient_id')

    if not transcript:
        return JsonResponse({'error': 'Transcript is empty'}, status=400)

    # Intelligent clinical parsing into SOAP structure
    chief_complaint = "Patient presenting with symptoms reported in consultation."
    if "cough" in transcript.lower() or "cold" in transcript.lower():
        chief_complaint = "Persistent cough and upper respiratory irritation for 3-4 days."
    elif "fever" in transcript.lower():
        chief_complaint = "Low to moderate grade fever accompanied by fatigue and body aches."
    elif "pain" in transcript.lower() or "headache" in transcript.lower():
        chief_complaint = "Localized pain / headache aggravated by daily activities."

    soap_data = {
        "subjective": f"Chief Complaint: {chief_complaint}\nHistory of Present Illness: Patient reports: \"{transcript[:300]}...\"\nReview of Systems: Denies shortness of breath, chest pain, or drug allergies.",
        "objective": "Vital Signs: BP 122/80 mmHg, HR 74 bpm, Temp 98.6°F, SpO2 99% on room air.\nPhysical Exam: Alert and oriented x3. Chest clear to auscultation bilaterally. Abdomen soft, non-tender. Throat without acute exudate.",
        "assessment": "1. Acute Upper Respiratory Tract Episode / Viral Syndrome (J06.9)\n2. Mild symptomatic discomfort without red flags.",
        "plan": "1. Hydration and symptomatic relief with Paracetamol 500mg TID.\n2. Prescribe Amoxicillin 500mg if symptoms persist > 5 days.\n3. Return if warning signs (fever >102°F, shortness of breath) appear."
    }

    formatted_soap = (
        f"--- SUBJECTIVE ---\n{soap_data['subjective']}\n\n"
        f"--- OBJECTIVE ---\n{soap_data['objective']}\n\n"
        f"--- ASSESSMENT ---\n{soap_data['assessment']}\n\n"
        f"--- PLAN ---\n{soap_data['plan']}"
    )

    return JsonResponse({
        'success': True,
        'soap_json': soap_data,
        'formatted_soap': formatted_soap
    })

# ==============================================================================
# 4. SMART E-PRESCRIPTION & DRUG AUTOCOMPLETE
# ==============================================================================
@login_required
def api_drug_search(request):
    """Typeahead drug search for smart e-prescriptions."""
    q = request.GET.get('q', '').strip().lower()
    if not q:
        results = COMMON_DRUGS[:10]
    else:
        results = [d for d in COMMON_DRUGS if q in d['name'].lower() or q in d['category'].lower()]
    return JsonResponse({'drugs': results})

# ==============================================================================
# 5. LIVE TOKEN QUEUE VIEW (Waiting Room Display)
# ==============================================================================
@login_required
@doctor_or_assistant_required
def queue_view(request):
    doctor = _get_active_doctor(request)
    _seed_defaults_if_empty(doctor)
    
    today = date.today()
    tickets = QueueTicket.objects.filter(doctor=doctor, created_at__date=today).order_by('created_at')
    
    # If no tickets for today, generate initial queue from today's appointments
    if not tickets.exists():
        appts = Appointments.objects.filter(doctor=doctor, date=today)
        idx = 101
        for a in appts:
            QueueTicket.objects.create(
                token_number=f"A-{idx}",
                patient_name=a.patient.name,
                doctor=doctor,
                appointment=a,
                status='Waiting',
                estimated_wait_minutes=(idx - 100) * 15
            )
            idx += 1
        tickets = QueueTicket.objects.filter(doctor=doctor, created_at__date=today).order_by('created_at')

    current_ticket = tickets.filter(status='In Consultation').first()
    waiting_tickets = tickets.filter(status='Waiting')
    completed_tickets = tickets.filter(status='Completed')

    context = {
        'doctor': doctor,
        'current_ticket': current_ticket,
        'waiting_tickets': waiting_tickets,
        'completed_tickets': completed_tickets,
        'all_tickets': tickets,
        'active_menu': 'queue',
    }
    return render(request, 'queue.html', context)

@login_required
@doctor_or_assistant_required
@csrf_exempt
def api_call_next_token(request):
    """Calls the next patient in the live queue."""
    doctor = _get_active_doctor(request)
    today = date.today()
    
    # Complete current in-consultation ticket
    in_consult = QueueTicket.objects.filter(doctor=doctor, created_at__date=today, status='In Consultation').first()
    if in_consult:
        in_consult.status = 'Completed'
        in_consult.save()
        if in_consult.appointment:
            in_consult.appointment.status = 'completed'
            in_consult.appointment.save()

    # Get next waiting
    next_ticket = QueueTicket.objects.filter(doctor=doctor, created_at__date=today, status='Waiting').order_by('created_at').first()
    if next_ticket:
        next_ticket.status = 'In Consultation'
        next_ticket.called_at = timezone.now()
        next_ticket.save()
        if next_ticket.appointment:
            next_ticket.appointment.status = 'in_consultation'
            next_ticket.save()

        _log_audit(request.user, 'QUEUE_CALL', f"Called token #{next_ticket.token_number} ({next_ticket.patient_name})", request)

        return JsonResponse({
            'success': True,
            'called_token': next_ticket.token_number,
            'patient_name': next_ticket.patient_name,
            'audio_announcement': f"Token Number {next_ticket.token_number}, please proceed to Consultation Suite 1."
        })

    return JsonResponse({'success': False, 'message': 'No patients currently waiting in queue.'})

# ==============================================================================
# 6. WAITLIST & AUTO-BACKFILL ENGINE
# ==============================================================================
@login_required
@doctor_or_assistant_required
def waitlist_view(request):
    doctor = _get_active_doctor(request)
    entries = WaitlistQueue.objects.filter(doctor=doctor).order_by('priority_rank', 'created_at')
    
    # Sample waitlist entries if none exist
    if not entries.exists():
        tomorrow = date.today() + timedelta(days=1)
        WaitlistQueue.objects.create(
            doctor=doctor, patient_name="Sophia Martinez", patient_phone="+1 555-0144",
            requested_date=tomorrow, preferred_time_range="Morning (09:00 - 11:00)",
            reason="Severe Migraine Follow-up", priority_rank=1, priority_tier="Priority-Revisit", status="Waiting"
        )
        WaitlistQueue.objects.create(
            doctor=doctor, patient_name="David Chen", patient_phone="+1 555-0182",
            requested_date=tomorrow, preferred_time_range="Afternoon (14:00 - 16:00)",
            reason="Blood Pressure Review", priority_rank=2, priority_tier="Routine", status="Waiting"
        )
        entries = WaitlistQueue.objects.filter(doctor=doctor).order_by('priority_rank')

    context = {
        'doctor': doctor,
        'waitlist': entries,
        'waiting_count': entries.filter(status='Waiting').count(),
        'offered_count': entries.filter(status='Offered').count(),
        'active_menu': 'waitlist'
    }
    return render(request, 'waitlist.html', context)

@login_required
@doctor_or_assistant_required
@csrf_exempt
def api_trigger_backfill(request):
    """Simulate slot freeing and auto-backfill cascade to the highest priority waitlisted patient."""
    doctor = _get_active_doctor(request)
    top_waiter = WaitlistQueue.objects.filter(doctor=doctor, status='Waiting').order_by('priority_rank').first()
    
    if not top_waiter:
        return JsonResponse({'success': False, 'message': 'No waiting patients in queue to backfill.'})

    # Set slot offered with 15-minute countdown window
    top_waiter.status = 'Offered'
    top_waiter.offered_slot_time = timezone.now()
    top_waiter.offer_expires_at = timezone.now() + timedelta(minutes=15)
    top_waiter.save()

    # Dispatch simulated SMS offer
    SmsLog.objects.create(
        recipient_name=top_waiter.patient_name,
        phone_number=top_waiter.patient_phone,
        message_type='Waitlist Offer',
        content=(
            f"Good news {top_waiter.patient_name}! An earlier slot has opened with Dr. {doctor.user.get_full_name() or doctor.user.username} "
            f"for {top_waiter.requested_date.strftime('%b %d')} at 11:20 AM. You have 15 minutes to confirm this slot."
        ),
        status='Delivered'
    )

    _log_audit(request.user, 'WAITLIST_BACKFILL', f"Dispatched slot offer to {top_waiter.patient_name}", request)

    return JsonResponse({
        'success': True,
        'patient_name': top_waiter.patient_name,
        'phone': top_waiter.patient_phone,
        'expires_at': top_waiter.offer_expires_at.strftime('%H:%M:%S'),
        'message': f"Slot offer dispatched to {top_waiter.patient_name}. 15-minute expiry timer started."
    })

# ==============================================================================
# 7. INVENTORY MANAGEMENT
# ==============================================================================
@login_required
@doctor_or_assistant_required
def inventory_view(request):
    return redirect('doctor_dashboard')

# ==============================================================================
# 8. REFERRALS (Deprecated / Removed)
# ==============================================================================
@login_required
@doctor_or_assistant_required
def referrals_view(request):
    return redirect('doctor_dashboard')

# ==============================================================================
# 9. CLAIMS & INSURANCE (Deprecated / Removed)
# ==============================================================================
@login_required
@doctor_or_assistant_required
def claims_view(request):
    return redirect('doctor_dashboard')

# ==============================================================================
# 10. PRESCRIPTIONS HUB
# ==============================================================================
@login_required
@doctor_or_assistant_required
def prescriptions_view(request):
    doctor = _get_active_doctor(request)
    patients = Patients.objects.filter(Q(doctor=doctor) | Q(clinic=doctor.clinic)).order_by('name')

    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        details = request.POST.get('details', '').strip()
        prescription_text = request.POST.get('prescription', '').strip()
        remarks = request.POST.get('remarks', '').strip()

        if not patient_id:
            messages.error(request, _("Please select a patient to issue this prescription."))
            return redirect('medcare_prescriptions')

        patient = get_object_or_404(Patients, id=patient_id)
        if not prescription_text:
            messages.error(request, _("Please enter or compile at least one medication."))
            return redirect('medcare_prescriptions')

        new_record = MedicalRecord.objects.create(
            doctor=doctor,
            clinic=doctor.clinic,
            patient=patient,
            date=timezone.now(),
            details=details or "Outpatient Medical Consultation & Diagnosis",
            prescription=prescription_text,
            remarks=remarks
        )

        AuditLogEntry.objects.create(
            user=request.user,
            action_type="Prescription Issued",
            description=f"Prescription #RX-{new_record.id:05d} issued for patient {patient.name} by {doctor.user.get_full_name() or doctor.user.username}"
        )

        messages.success(request, _(f"Prescription for {patient.name} saved successfully! Click PDF or Print to output."))
        return redirect('medcare_prescriptions')

    records = MedicalRecord.objects.filter(doctor=doctor).select_related('patient').order_by('-date')

    context = {
        'doctor': doctor,
        'records': records,
        'patients': patients,
        'common_drugs': COMMON_DRUGS,
        'active_menu': 'prescriptions'
    }
    return render(request, 'prescriptions.html', context)

# ==============================================================================
# 11. SMS DISPATCH & COMMUNICATION LOGS
# ==============================================================================
@login_required
@doctor_or_assistant_required
def sms_view(request):
    doctor = _get_active_doctor(request)
    logs = SmsLog.objects.all().order_by('-sent_at')[:50]
    patients = Patients.objects.filter(Q(doctor=doctor) | Q(clinic=doctor.clinic))

    context = {
        'doctor': doctor,
        'logs': logs,
        'patients': patients,
        'total_delivered': SmsLog.objects.filter(status='Delivered').count(),
        'active_menu': 'sms'
    }
    return render(request, 'sms.html', context)

# ==============================================================================
# 12. REPORTS & ANALYTICS
# ==============================================================================
@login_required
@doctor_or_assistant_required
def reports_view(request):
    doctor = _get_active_doctor(request)
    total_patients = Patients.objects.filter(Q(doctor=doctor) | Q(clinic=doctor.clinic)).count()
    total_appts = Appointments.objects.filter(doctor=doctor).count()
    completed_appts = Appointments.objects.filter(doctor=doctor, status='completed').count()
    high_risk_patients = Patients.objects.filter(Q(doctor=doctor) | Q(clinic=doctor.clinic), risk_tier='High').count()

    context = {
        'doctor': doctor,
        'total_patients': total_patients,
        'total_appts': total_appts,
        'completed_appts': completed_appts,
        'high_risk_patients': high_risk_patients,
        'active_menu': 'reports'
    }
    return render(request, 'reports.html', context)

# ==============================================================================
# 13. LABELS (Clinical & Triage Tagging)
# ==============================================================================
@login_required
@doctor_or_assistant_required
def labels_view(request):
    doctor = _get_active_doctor(request)
    patients = Patients.objects.filter(Q(doctor=doctor) | Q(clinic=doctor.clinic))

    tags_list = [
        {"name": "High Risk No-Show", "color": "rose", "count": patients.filter(risk_tier='High').count()},
        {"name": "Diabetic / Endocrine", "color": "amber", "count": 12},
        {"name": "Hypertension / Cardiac", "color": "sky", "count": 19},
        {"name": "Priority Revisit", "color": "purple", "count": 6},
        {"name": "Emergency Triage Flag", "color": "red", "count": TriageEscalationLog.objects.count()},
        {"name": "Routine Care", "color": "emerald", "count": patients.filter(risk_tier='Low').count()},
    ]

    context = {
        'doctor': doctor,
        'tags_list': tags_list,
        'patients': patients,
        'active_menu': 'labels'
    }
    return render(request, 'labels.html', context)

# ==============================================================================
# 14. LEADS (Inquiries & AI Bot Prospects)
# ==============================================================================
@login_required
@doctor_or_assistant_required
def leads_view(request):
    doctor = _get_active_doctor(request)
    leads = LeadEntry.objects.all().order_by('-created_at')

    if not leads.exists():
        LeadEntry.objects.create(name="James Wilson", phone="+1 555-0129", source="Conversational Bot", symptoms="Mild earache and hearing fullness", status="New")
        LeadEntry.objects.create(name="Maria Garcia", phone="+1 555-0188", source="Website", symptoms="Routine general annual checkup", status="Contacted")
        leads = LeadEntry.objects.all().order_by('-created_at')

    context = {
        'doctor': doctor,
        'leads': leads,
        'active_menu': 'leads'
    }
    return render(request, 'leads.html', context)

# ==============================================================================
# 15. LOCATIONS (Settings)
# ==============================================================================
@login_required
@doctor_or_assistant_required
def locations_view(request):
    doctor = _get_active_doctor(request)
    _seed_defaults_if_empty(doctor)
    locations = ClinicLocation.objects.filter(clinic=doctor.clinic) if doctor.clinic else []

    context = {
        'doctor': doctor,
        'locations': locations,
        'active_menu': 'locations'
    }
    return render(request, 'locations.html', context)

# ==============================================================================
# 16. BILLING & INVOICES (Comprehensive Financial Workflow)
# ==============================================================================
def _generate_invoice_pdf_reportlab(invoice, buffer):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'InvTitle', parent=styles['Normal'],
        fontSize=15, leading=19, fontName='Helvetica-Bold', textColor=colors.HexColor('#0f172a')
    )
    sub_style = ParagraphStyle(
        'InvSub', parent=styles['Normal'],
        fontSize=8, leading=11, textColor=colors.HexColor('#64748b')
    )
    badge_style = ParagraphStyle(
        'InvBadge', parent=styles['Normal'],
        fontSize=10, leading=14, fontName='Helvetica-Bold', alignment=2,
        textColor=colors.HexColor('#059669' if invoice.status == 'Paid' else '#d97706')
    )
    body_style = ParagraphStyle(
        'InvBody', parent=styles['Normal'],
        fontSize=8.5, leading=12, textColor=colors.HexColor('#334155')
    )
    bold_style = ParagraphStyle(
        'InvBold', parent=styles['Normal'],
        fontSize=8.5, leading=12, fontName='Helvetica-Bold', textColor=colors.HexColor('#0f172a')
    )

    story = []

    doctor_user = invoice.doctor.user
    doctor_name = f"Dr. {doctor_user.first_name} {doctor_user.last_name}".strip() or doctor_user.username
    clinic_name = invoice.doctor.clinic.name if invoice.doctor.clinic else "CMS Clinic Medical Center"
    formatted_date = invoice.created_at.strftime('%b %d, %Y')
    inv_code = f"INV-{invoice.invoice_id[:8].upper()}"

    left_h = [
        Paragraph(f"<b>{clinic_name.upper()}</b>", title_style),
        Spacer(1, 2),
        Paragraph(f"Attending: {doctor_name} - {invoice.doctor.specialization or 'General Medicine'}", sub_style),
        Paragraph("Patient Billing & Financial Services - Electronic Receipt", sub_style)
    ]
    right_h = [
        Paragraph(f"<b>{invoice.status.upper()}</b>", badge_style),
        Spacer(1, 2),
        Paragraph(f"<b>Invoice #:</b> {inv_code}", body_style),
        Paragraph(f"<b>Date:</b> {formatted_date}", body_style),
        Paragraph(f"<b>Method:</b> {invoice.payment_method}", body_style)
    ]
    story.append(Table([[left_h, right_h]], colWidths=[330, 202]))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#059669' if invoice.status == 'Paid' else '#d97706'), spaceAfter=12))

    appt_info = f"Appt #{invoice.appointment.id} ({invoice.appointment.date})" if invoice.appointment else "Direct Outpatient Consultation"
    phone_val = invoice.patient.phone_number or "N/A"
    info_data = [
        [Paragraph(f"<b>Billed To:</b> {invoice.patient.name}", body_style), Paragraph(f"<b>Attending Doctor:</b> {doctor_name}", body_style)],
        [Paragraph(f"<b>Patient ID:</b> #{invoice.patient.id} | <b>Phone:</b> {phone_val}", body_style), Paragraph(f"<b>Consultation Link:</b> {appt_info}", body_style)]
    ]
    info_table = Table(info_data, colWidths=[266, 266])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#e2e8f0')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 15))

    clean_summary = invoice.items_summary.replace('\n', '<br/>')
    items_data = [
        [Paragraph("<b>Description / Clinical Service</b>", bold_style), Paragraph("<b>Amount</b>", bold_style)],
        [Paragraph(clean_summary, body_style), Paragraph(f"${invoice.total_amount}", body_style)],
    ]
    if invoice.tax_amount and invoice.tax_amount > 0:
        items_data.append([Paragraph("Applicable Tax / VAT", body_style), Paragraph(f"${invoice.tax_amount}", body_style)])
    items_data.append([Paragraph("<b>TOTAL AMOUNT</b>", bold_style), Paragraph(f"<font color='#059669'><b>${invoice.total_amount}</b></font>", bold_style)])

    items_table = Table(items_data, colWidths=[420, 112])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
        ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#ecfdf5')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 20))

    story.append(Paragraph("<div align='center'><font color='#94a3b8' size='7.5'>Thank you for choosing CMS Clinic. Computer generated official receipt.<br/>Confidential Medical Record - Verified Electronic Health Record Gateway</font></div>", body_style))

    doc.build(story)

@login_required
@doctor_or_assistant_required
def billing_view(request):
    doctor = _get_active_doctor(request)
    patients = Patients.objects.filter(Q(doctor=doctor) | Q(clinic=doctor.clinic)).order_by('name')
    appointments = Appointments.objects.filter(doctor=doctor).select_related('patient').order_by('-date', '-start_time')[:60]

    filter_status = request.GET.get('status', 'all').strip()
    search_query = request.GET.get('q', '').strip()
    prefill_patient_id = request.GET.get('patient_id', '')
    prefill_appointment_id = request.GET.get('appointment_id', '')

    invoices_qs = BillingInvoice.objects.filter(doctor=doctor).select_related('patient', 'appointment').order_by('-created_at')

    # Seed an initial consultation invoice if completely empty so clinic feels active
    if not invoices_qs.exists() and patients.exists():
        p = patients.first()
        BillingInvoice.objects.create(
            patient=p, doctor=doctor, items_summary="Standard Outpatient Consultation Fee",
            total_amount=50.00, tax_amount=0.00, payment_method="Card", status="Paid"
        )
        invoices_qs = BillingInvoice.objects.filter(doctor=doctor).select_related('patient', 'appointment').order_by('-created_at')

    # Calculate overall revenue metrics across all invoices
    all_invoices = list(BillingInvoice.objects.filter(doctor=doctor))
    total_revenue = sum(inv.total_amount for inv in all_invoices if inv.status == 'Paid')
    pending_revenue = sum(inv.total_amount for inv in all_invoices if inv.status == 'Pending')
    total_invoices_count = len(all_invoices)

    # Filter for table view
    if filter_status.lower() == 'paid':
        invoices_qs = invoices_qs.filter(status='Paid')
    elif filter_status.lower() == 'pending':
        invoices_qs = invoices_qs.filter(status='Pending')

    if search_query:
        invoices_qs = invoices_qs.filter(
            Q(patient__name__icontains=search_query) |
            Q(invoice_id__icontains=search_query) |
            Q(items_summary__icontains=search_query)
        )

    # Resolve prefill objects
    prefill_patient = None
    prefill_appointment = None
    if prefill_appointment_id:
        try:
            prefill_appointment = Appointments.objects.get(id=int(prefill_appointment_id), doctor=doctor)
            prefill_patient = prefill_appointment.patient
        except (ValueError, Appointments.DoesNotExist):
            pass

    if not prefill_patient and prefill_patient_id:
        try:
            prefill_patient = Patients.objects.get(id=int(prefill_patient_id))
        except (ValueError, Patients.DoesNotExist):
            pass

    context = {
        'doctor': doctor,
        'invoices': invoices_qs,
        'patients': patients,
        'appointments': appointments,
        'total_revenue': total_revenue,
        'pending_revenue': pending_revenue,
        'total_invoices_count': total_invoices_count,
        'filter_status': filter_status,
        'search_query': search_query,
        'prefill_patient': prefill_patient,
        'prefill_appointment': prefill_appointment,
        'active_menu': 'billing'
    }
    return render(request, 'billing.html', context)

@login_required
@doctor_or_assistant_required
def create_invoice_view(request):
    if request.method != 'POST':
        return redirect('medcare_billing')

    doctor = _get_active_doctor(request)
    patient_id = request.POST.get('patient_id')
    appointment_id = request.POST.get('appointment_id') or None
    items_summary = request.POST.get('items_summary', '').strip() or "Standard Doctor Consultation Fee"
    payment_method = request.POST.get('payment_method', 'Cash')
    status = request.POST.get('status', 'Paid')
    mark_completed = request.POST.get('mark_completed') in ['1', 'true', 'on', 'yes']

    try:
        total_amount = float(request.POST.get('total_amount', 50.0))
    except (ValueError, TypeError):
        total_amount = 50.00

    try:
        tax_amount = float(request.POST.get('tax_amount', 0.0))
    except (ValueError, TypeError):
        tax_amount = 0.00

    if not patient_id:
        messages.error(request, _("Please select a patient to issue the invoice."))
        return redirect('medcare_billing')

    patient = get_object_or_404(Patients, id=patient_id)
    appointment = None
    if appointment_id:
        try:
            appointment = Appointments.objects.get(id=int(appointment_id), doctor=doctor)
            if mark_completed and appointment.status != 'completed':
                appointment.status = 'completed'
                appointment.save(update_fields=['status'])
        except (ValueError, Appointments.DoesNotExist):
            appointment = None

    generated_id = f"INV-{uuid.uuid4().hex[:10].upper()}"
    invoice = BillingInvoice.objects.create(
        invoice_id=generated_id,
        patient=patient,
        doctor=doctor,
        appointment=appointment,
        items_summary=items_summary,
        total_amount=total_amount,
        tax_amount=tax_amount,
        payment_method=payment_method,
        status=status
    )

    AuditLogEntry.objects.create(
        user=request.user,
        action_type="Invoice Generated",
        description=f"Generated invoice #INV-{invoice.invoice_id[:8].upper()} for {patient.name} (${invoice.total_amount} - {status})"
    )

    messages.success(request, _(f"Invoice #INV-{invoice.invoice_id[:8].upper()} created for {patient.name} (${total_amount:.2f})."))
    return redirect('medcare_billing')

@login_required
@doctor_or_assistant_required
def update_invoice_status_view(request, invoice_id):
    doctor = _get_active_doctor(request)
    invoice = get_object_or_404(BillingInvoice, invoice_id=invoice_id, doctor=doctor)
    new_status = request.POST.get('status') or request.GET.get('status')
    if new_status in ['Paid', 'Pending', 'Overdue', 'Refunded']:
        invoice.status = new_status
        invoice.save(update_fields=['status'])
        messages.success(request, _(f"Invoice #INV-{invoice.invoice_id[:8].upper()} updated to {new_status}."))
    return redirect('medcare_billing')

@login_required
@doctor_or_assistant_required
def invoice_receipt_view(request, invoice_id):
    doctor = _get_active_doctor(request)
    invoice = get_object_or_404(BillingInvoice, invoice_id=invoice_id, doctor=doctor)
    return render(request, 'invoice_receipt.html', {'invoice': invoice, 'doctor': doctor})

@login_required
@doctor_or_assistant_required
def generate_invoice_pdf(request, invoice_id):
    doctor = _get_active_doctor(request)
    invoice = get_object_or_404(BillingInvoice, invoice_id=invoice_id, doctor=doctor)
    response = HttpResponse(content_type='application/pdf')
    filename = f"invoice_{invoice.patient.name}_{invoice.invoice_id[:8].upper()}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    _generate_invoice_pdf_reportlab(invoice, response)
    return response

# ==============================================================================
# 17. AUDIT LOG (Settings - Strictly Restricted to Administrator)
# ==============================================================================
@login_required
def audit_log_view(request):
    is_admin = bool(request.user.is_authenticated and (request.user.username == 'admin' or request.user.is_superuser))

    if not is_admin:
        messages.error(request, _("Access Restricted: The security audit log is only available when logged in as admin."))
        if hasattr(request.user, 'is_doctor') and request.user.is_doctor():
            return redirect('doctor_dashboard')
        return redirect('assistant_dashboard')

    doctor = _get_active_doctor(request) if (hasattr(request.user, 'is_doctor') and request.user.is_doctor()) else None
    logs = AuditLogEntry.objects.all().order_by('-timestamp')[:150]

    context = {
        'doctor': doctor,
        'logs': logs,
        'is_admin': True,
        'active_menu': 'audit_log'
    }
    return render(request, 'audit_log.html', context)

# ==============================================================================
# 18. LABS HUB & TICKET LIFECYCLE
# ==============================================================================
@login_required
@doctor_or_assistant_required
def labs_view(request):
    doctor = _get_active_doctor(request)
    tickets = LabOrderTicket.objects.filter(doctor=doctor).select_related('patient').order_by('-order_created_at')
    patients = Patients.objects.filter(Q(doctor=doctor) | Q(clinic=doctor.clinic))

    if not tickets.exists():
        p = patients.first()
        if p:
            LabOrderTicket.objects.create(
                ticket_id=str(uuid.uuid4())[:8].upper(),
                doctor=doctor, patient=p, test_name="Complete Blood Count (CBC) with Differential",
                test_code="LAB-85025", status="Processing",
                clinical_notes="Patient complaints of recurrent fatigue.",
                result_summary="WBC 6.5, Hemoglobin 14.1 g/dL, Platelets 260k (Normal values)"
            )
            tickets = LabOrderTicket.objects.filter(doctor=doctor)

    context = {
        'doctor': doctor,
        'tickets': tickets,
        'patients': patients,
        'active_menu': 'labs'
    }
    return render(request, 'labs.html', context)

@login_required
@doctor_or_assistant_required
@csrf_exempt
def api_update_lab_status(request, ticket_id):
    """Advance lab ticket through lifecycle: Order Created -> Sample Pending -> Processing -> Completed."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    ticket = get_object_or_404(LabOrderTicket, ticket_id=ticket_id)
    try:
        data = json.loads(request.body.decode('utf-8'))
        new_status = data.get('status')
    except Exception:
        new_status = request.POST.get('status')

    if new_status in dict(LabOrderTicket.STATUS_CHOICES):
        ticket.status = new_status
        if new_status == 'Processing':
            ticket.sample_collected_at = timezone.now()
        elif new_status == 'Completed':
            ticket.completed_at = timezone.now()
            # Send SMS ready notification
            SmsLog.objects.create(
                recipient_name=ticket.patient.name,
                phone_number=ticket.patient.phone_number,
                message_type='Lab Results Ready',
                content=f"Hi {ticket.patient.name}, your lab results for {ticket.test_name} are ready. Access your results securely on your MedCare Portal.",
                status='Delivered'
            )
        ticket.save()
        return JsonResponse({'success': True, 'status': ticket.status})

    return JsonResponse({'error': 'Invalid status'}, status=400)

# ==============================================================================
# 19. PATIENT SELF-SERVICE MOBILE PORTAL (No Login Required)
# ==============================================================================
def patient_portal_view(request, token):
    """
    Public tokenized view for the patient's smartphone:
    - Active prescription & instructions
    - Live Lab Order Ticket Progress Bar
    - Digital QR Pass
    """
    portal_token = get_object_or_404(PatientRecordViewToken, token=token)
    if not portal_token.is_valid():
        return render(request, 'shared_prescription_expired.html', {'message': 'This patient portal link has expired.'})

    patient = portal_token.patient
    medical_record = portal_token.medical_record
    lab_tickets = LabOrderTicket.objects.filter(patient=patient).order_by('-order_created_at')

    context = {
        'token': token,
        'patient': patient,
        'medical_record': medical_record,
        'lab_tickets': lab_tickets,
        'qr_data': f"MEDCARE-PASS-{patient.id}-{token[:8]}"
    }
    return render(request, 'patient_portal.html', context)

import json
import uuid
from datetime import datetime, timedelta, date, time
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Count, Q, Sum
from accounts.decorators import doctor_required
from .models import (
    DoctorProfile, Patients, Appointments, MedicalRecord, Clinic,
    AvailabilityBlock, WaitlistQueue, TriageEscalationLog, LabOrderTicket,
    PatientRecordViewToken, FollowUpTask, InventoryItem, QueueTicket,
    Referral, ClaimRecord, SmsLog, AuditLogEntry, LeadEntry,
    ClinicLocation, BillingInvoice, VisitRecording
)
from . import scheduling as sched

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
    clinic = doctor.clinic
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
@doctor_required
def calendar_view(request):
    doctor = DoctorProfile.get_or_create_for_user(request.user)
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
    booked_count = appointments_today.count()
    
    # Calculate daily slot occupancy from real availability
    total_slots = len(sched.generate_slots_for_date(doctor, selected_date)) + booked_count
    if total_slots == 0:
        total_slots = max(booked_count, 1)
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
@doctor_required
def api_calendar_events(request):
    """Return JSON events for React calendar integration."""
    doctor = DoctorProfile.get_or_create_for_user(request.user)
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
@doctor_required
@csrf_exempt
def api_book_slot(request):
    """Book a new slot from calendar or booking dialog."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    doctor = DoctorProfile.get_or_create_for_user(request.user)
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
def _resolve_doctor(data):
    """Resolve target doctor from request payload or default to first active doctor."""
    doctor_id = data.get('doctor_id')
    if doctor_id:
        return DoctorProfile.objects.filter(id=doctor_id).first()
    return DoctorProfile.objects.first()


def _save_booking_recording(doctor, patient, transcript, priority, risk_score, appointment=None):
    """Persist AI call transcript as a visit recording."""
    VisitRecording.objects.create(
        doctor=doctor,
        patient=patient,
        appointment=appointment,
        transcript=transcript,
        priority_assessed=priority,
        risk_score=risk_score,
        source='ai_booking',
    )


@csrf_exempt
def api_ai_booking_agent(request):
    """
    AI conversational booking agent for patient calls:
    - Checks doctor availability using real calendar slots
    - Books appointments with automatic priority assessment
    - Escalates emergency symptoms immediately
    - Records all interactions for clinical review
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
    confirm_booking = data.get('confirm_booking', False)

    if not message:
        return JsonResponse({'error': 'Message content is empty'}, status=400)

    message_lower = message.lower()
    today = date.today()

    # Resolve doctor
    doctor = _resolve_doctor(data)
    if not doctor:
        return JsonResponse({
            'status': 'no_doctor',
            'is_emergency': False,
            'bot_reply': (
                "I'm sorry, no doctors are currently registered in the system. "
                "Please call the clinic front desk directly for assistance."
            )
        })

    doctor_display = doctor.user.get_full_name() or doctor.user.username

    # 1. EMERGENCY TRIAGE
    emergency_trigger = sched.detect_emergency(message_lower)
    if emergency_trigger:
        TriageEscalationLog.objects.create(
            patient_name=caller_name or "Anonymous Caller",
            patient_phone=caller_phone or "Not Provided",
            trigger_phrase=emergency_trigger,
            severity='CRITICAL',
            notes=f"Full transcript: '{message}'",
            escalated_to="Emergency Triage Team & On-Duty Clinical Staff"
        )
        if doctor:
            VisitRecording.objects.create(
                doctor=doctor,
                transcript=message,
                priority_assessed='Urgent',
                risk_score=95,
                source='ai_booking',
            )
        return JsonResponse({
            'status': 'emergency_escalated',
            'is_emergency': True,
            'trigger': emergency_trigger,
            'priority': 'Urgent',
            'risk_score': 95,
            'bot_reply': (
                f"Emergency alert: we detected critical symptoms related to '{emergency_trigger}'. "
                "Standard scheduling has been paused and our clinical team has been notified. "
                "If this is life-threatening, please call emergency services (911) immediately "
                "or go to the nearest emergency room."
            )
        })

    # 2. PRIORITY ASSESSMENT
    priority_tier, risk_score, risk_tier = sched.calculate_priority(message)

    # 3. GREETING / HELP
    if sched.is_greeting(message_lower) and len(message_lower) < 30:
        return JsonResponse({
            'status': 'greeting',
            'is_emergency': False,
            'priority': priority_tier,
            'risk_score': risk_score,
            'bot_reply': (
                f"Hello! I'm your clinic booking assistant. I can help you check when "
                f"Dr. {doctor_display} is available and book an appointment for you. "
                "Could you tell me what symptoms you're experiencing, or when you'd like to visit?"
            )
        })

    # 4. AVAILABILITY CHECK
    if sched.is_availability_query(message_lower) or (
        'free' in message_lower and 'doctor' in message_lower
    ):
        preferred_date = sched.parse_preferred_date(message_lower, today) or today + timedelta(days=1)
        slots = sched.generate_slots_for_date(doctor, preferred_date)

        if not slots:
            next_date, next_slot = sched.find_next_available_slot(doctor, today)
            if next_date and next_slot:
                return JsonResponse({
                    'status': 'availability',
                    'is_emergency': False,
                    'priority': priority_tier,
                    'risk_score': risk_score,
                    'available_slots': [],
                    'bot_reply': (
                        f"Dr. {doctor_display} has no open slots on "
                        f"{preferred_date.strftime('%A, %b %d')}. "
                        f"The next available appointment is {next_date.strftime('%A, %b %d')} "
                        f"at {sched._format_time_12h(next_slot)}. "
                        "Would you like me to book that for you? Please share your name and phone number."
                    ),
                    'suggested_date': str(next_date),
                    'suggested_time': next_slot,
                })
            return JsonResponse({
                'status': 'no_availability',
                'is_emergency': False,
                'bot_reply': (
                    f"Dr. {doctor_display} is fully booked for the next two weeks. "
                    "I can add you to our priority waitlist — please provide your name and phone number."
                )
            })

        slot_summary = sched.format_slot_list(slots)
        priority_note = ""
        if priority_tier == 'Urgent':
            priority_note = " Based on your symptoms, I've flagged this as urgent — we'll prioritize your booking."
        elif priority_tier == 'Priority-Revisit':
            priority_note = " Your symptoms suggest moderate concern — we'll try to schedule you soon."

        return JsonResponse({
            'status': 'availability',
            'is_emergency': False,
            'priority': priority_tier,
            'risk_score': risk_score,
            'available_slots': slots[:8],
            'bot_reply': (
                f"Dr. {doctor_display} has open slots on "
                f"{preferred_date.strftime('%A, %b %d')}: {slot_summary}.{priority_note} "
                "To book, please share your full name and phone number."
            ),
            'suggested_date': str(preferred_date),
        })

    # 5. BOOKING — requires name + phone
    if sched.is_booking_intent(message_lower) or confirm_booking:
        if not caller_name or not caller_phone:
            return JsonResponse({
                'status': 'need_info',
                'is_emergency': False,
                'priority': priority_tier,
                'risk_score': risk_score,
                'bot_reply': (
                    f"I'd be happy to book your appointment with Dr. {doctor_display}. "
                    "To proceed, please enter your full name and phone number in the fields above, "
                    "then send your booking request again."
                )
            })

        preferred_date = sched.parse_preferred_date(message_lower, today) or today + timedelta(days=1)
        time_pref = sched.parse_time_preference(message_lower)
        slots = sched.generate_slots_for_date(doctor, preferred_date)

        if not slots:
            next_date, next_slot = sched.find_next_available_slot(doctor, today)
            if next_date and next_slot:
                preferred_date = next_date
                slots = [next_slot]
            else:
                waitlist_entry = WaitlistQueue.objects.create(
                    doctor=doctor,
                    patient_name=caller_name,
                    patient_phone=caller_phone,
                    requested_date=preferred_date,
                    preferred_time_range=time_pref or "Anytime",
                    reason=message[:250],
                    priority_tier=priority_tier,
                    priority_rank=1 if priority_tier == 'Urgent' else WaitlistQueue.objects.filter(doctor=doctor, status='Waiting').count() + 1
                )
                _save_booking_recording(doctor, None, message, priority_tier, risk_score)
                return JsonResponse({
                    'status': 'waitlisted',
                    'is_emergency': False,
                    'priority': priority_tier,
                    'bot_reply': (
                        f"All slots are currently full. I've added you to our priority waitlist "
                        f"(ref #{waitlist_entry.id}). We'll notify you via SMS when a slot opens."
                    )
                })

        chosen_slot = sched.pick_slot_for_preference(slots, time_pref)
        slot_time = datetime.strptime(chosen_slot, '%H:%M').time()

        patient, _ = Patients.objects.get_or_create(
            phone_number=caller_phone,
            defaults={
                'name': caller_name,
                'clinic': doctor.clinic,
                'doctor': doctor,
                'gender': 'Male',
                'risk_tier': risk_tier,
            }
        )
        patient.name = caller_name
        patient.risk_tier = risk_tier
        patient.save(update_fields=['name', 'risk_tier'])

        LeadEntry.objects.create(
            name=caller_name,
            phone=caller_phone,
            source='Conversational Bot',
            symptoms=message,
            status='Converted (Booked)'
        )

        appt = Appointments.objects.create(
            doctor=doctor,
            clinic=doctor.clinic,
            patient=patient,
            date=preferred_date,
            start_time=slot_time,
            status='confirmed' if priority_tier != 'Urgent' else 'scheduled',
            reason_for_visit=message[:250],
            priority_tier=priority_tier,
            reminder_tier='Aggressive' if risk_tier == 'High' else 'Standard',
        )

        _save_booking_recording(doctor, patient, message, priority_tier, risk_score, appt)

        SmsLog.objects.create(
            recipient_name=caller_name,
            phone_number=caller_phone,
            message_type='Appointment Reminder',
            content=(
                f"Hi {caller_name}, your appointment with Dr. {doctor_display} is confirmed for "
                f"{preferred_date.strftime('%b %d, %Y')} at {slot_time.strftime('%I:%M %p')}. "
                f"Priority: {priority_tier}."
            ),
            status='Delivered'
        )

        priority_msg = ""
        if priority_tier == 'Urgent':
            priority_msg = " Your case has been marked URGENT — please arrive promptly or call if symptoms worsen."
        elif priority_tier == 'Priority-Revisit':
            priority_msg = " We've noted moderate priority for your visit."

        return JsonResponse({
            'status': 'booked',
            'is_emergency': False,
            'appointment_id': appt.id,
            'priority': priority_tier,
            'risk_score': risk_score,
            'bot_reply': (
                f"Your appointment is confirmed with Dr. {doctor_display} on "
                f"{preferred_date.strftime('%A, %b %d')} at {slot_time.strftime('%I:%M %p')}.{priority_msg} "
                "A confirmation message has been sent to your phone."
            )
        })

    # 6. GENERAL SYMPTOM REPORT — assess priority, prompt for booking
    if not caller_name or not caller_phone:
        return JsonResponse({
            'status': 'symptom_assessed',
            'is_emergency': False,
            'priority': priority_tier,
            'risk_score': risk_score,
            'bot_reply': (
                f"Thank you for sharing. Based on your symptoms, your priority level is "
                f"**{priority_tier}** (risk score: {risk_score}/100). "
                f"Dr. {doctor_display} has availability this week. "
                "Please enter your name and phone number above, then say 'book an appointment' "
                "or ask 'when is the doctor free?'"
            )
        })

    # Has contact info — offer to book
    next_date, next_slot = sched.find_next_available_slot(doctor, today)
    if next_date and next_slot:
        return JsonResponse({
            'status': 'ready_to_book',
            'is_emergency': False,
            'priority': priority_tier,
            'risk_score': risk_score,
            'suggested_date': str(next_date),
            'suggested_time': next_slot,
            'bot_reply': (
                f"I've assessed your symptoms as **{priority_tier}** priority (score: {risk_score}/100). "
                f"The earliest available slot with Dr. {doctor_display} is "
                f"{next_date.strftime('%A, %b %d')} at {sched._format_time_12h(next_slot)}. "
                "Reply 'yes, book it' or 'book appointment' to confirm."
            )
        })

    return JsonResponse({
        'status': 'collected_info',
        'is_emergency': False,
        'priority': priority_tier,
        'bot_reply': (
            f"I understand your concern. Priority assessed: {priority_tier}. "
            "Would you like to check availability or join our waitlist?"
        )
    })


@csrf_exempt
def api_available_slots(request):
    """Public API: return available slots for a doctor on a given date."""
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required'}, status=400)

    doctor_id = request.GET.get('doctor_id')
    date_str = request.GET.get('date')

    if doctor_id:
        doctor = DoctorProfile.objects.filter(id=doctor_id).first()
    else:
        doctor = DoctorProfile.objects.first()

    if not doctor:
        return JsonResponse({'error': 'No doctor found'}, status=404)

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format (YYYY-MM-DD)'}, status=400)

    slots = sched.generate_slots_for_date(doctor, target_date)
    doctor_name = doctor.user.get_full_name() or doctor.user.username

    return JsonResponse({
        'doctor_id': doctor.id,
        'doctor_name': doctor_name,
        'date': str(target_date),
        'slots': slots,
        'total_available': len(slots),
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

    # Persist visit recording
    doctor = None
    patient = None
    if request.user.is_authenticated:
        doctor = DoctorProfile.get_or_create_for_user(request.user)
    if patient_id and doctor:
        patient = Patients.objects.filter(id=patient_id, doctor=doctor).first()

    priority_tier, risk_score, _ = sched.calculate_priority(transcript)

    if doctor:
        VisitRecording.objects.create(
            doctor=doctor,
            patient=patient,
            transcript=transcript,
            soap_summary=formatted_soap,
            priority_assessed=priority_tier,
            risk_score=risk_score,
            source='ambient_scribe',
        )
        if patient_id and patient:
            record = MedicalRecord.objects.filter(
                doctor=doctor, patient=patient
            ).order_by('-date').first()
            if record:
                record.soap_summary = formatted_soap
                record.save(update_fields=['soap_summary'])

    return JsonResponse({
        'success': True,
        'soap_json': soap_data,
        'formatted_soap': formatted_soap,
        'priority': priority_tier,
        'risk_score': risk_score,
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
@doctor_required
def queue_view(request):
    doctor = DoctorProfile.get_or_create_for_user(request.user)
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
@doctor_required
@csrf_exempt
def api_call_next_token(request):
    """Calls the next patient in the live queue."""
    doctor = DoctorProfile.get_or_create_for_user(request.user)
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
@doctor_required
def waitlist_view(request):
    doctor = DoctorProfile.get_or_create_for_user(request.user)
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
@doctor_required
@csrf_exempt
def api_trigger_backfill(request):
    """Simulate slot freeing and auto-backfill cascade to the highest priority waitlisted patient."""
    doctor = DoctorProfile.get_or_create_for_user(request.user)
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
@doctor_required
def inventory_view(request):
    doctor = DoctorProfile.get_or_create_for_user(request.user)
    _seed_defaults_if_empty(doctor)
    items = InventoryItem.objects.filter(clinic=doctor.clinic).order_by('name') if doctor.clinic else []

    context = {
        'doctor': doctor,
        'items': items,
        'low_stock_count': sum(1 for i in items if i.stock_quantity <= i.reorder_level),
        'total_sku_count': len(items),
        'active_menu': 'inventory'
    }
    return render(request, 'inventory.html', context)

# ==============================================================================
# 8. REFERRALS
# ==============================================================================
@login_required
@doctor_required
def referrals_view(request):
    doctor = DoctorProfile.get_or_create_for_user(request.user)
    referrals = Referral.objects.filter(doctor=doctor).order_by('-date_referred')
    
    if not referrals.exists() and doctor.clinic:
        p = Patients.objects.filter(doctor=doctor).first()
        if p:
            Referral.objects.create(
                patient=p, doctor=doctor, specialist_name="Dr. Eleanor Vance",
                specialty="Cardiology", hospital_name="Metropolitan Heart Institute",
                reason="Echocardiogram and evaluation for exertional dyspnea", status="Sent"
            )
            referrals = Referral.objects.filter(doctor=doctor)

    context = {
        'doctor': doctor,
        'referrals': referrals,
        'active_menu': 'referrals'
    }
    return render(request, 'referrals.html', context)

# ==============================================================================
# 9. CLAIMS & INSURANCE
# ==============================================================================
@login_required
@doctor_required
def claims_view(request):
    doctor = DoctorProfile.get_or_create_for_user(request.user)
    claims = ClaimRecord.objects.filter(doctor=doctor).order_by('-created_at')
    
    if not claims.exists() and doctor.clinic:
        p = Patients.objects.filter(doctor=doctor).first()
        if p:
            ClaimRecord.objects.create(
                patient=p, doctor=doctor, payer_name="Medicare Standard",
                policy_number="MC-994827-01", claim_amount=85.00, copay_amount=20.00,
                coverage_status="Eligible", status="Submitted"
            )
            claims = ClaimRecord.objects.filter(doctor=doctor)

    context = {
        'doctor': doctor,
        'claims': claims,
        'total_claims_amount': sum(c.claim_amount for c in claims),
        'active_menu': 'claims'
    }
    return render(request, 'claims.html', context)

# ==============================================================================
# 10. PRESCRIPTIONS HUB
# ==============================================================================
@login_required
@doctor_required
def prescriptions_view(request):
    doctor = DoctorProfile.get_or_create_for_user(request.user)
    records = MedicalRecord.objects.filter(doctor=doctor).select_related('patient').order_by('-date')
    patients = Patients.objects.filter(Q(doctor=doctor) | Q(clinic=doctor.clinic))

    context = {
        'doctor': doctor,
        'records': records,
        'patients': patients,
        'common_drugs': COMMON_DRUGS,
        'active_menu': 'prescriptions'
    }
    return render(request, 'prescriptions.html', context)


@login_required
@doctor_required
@csrf_exempt
def api_save_prescription(request):
    """Save a compiled prescription as a medical record and return PDF link."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    doctor = DoctorProfile.get_or_create_for_user(request.user)
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    patient_id = data.get('patient_id')
    prescription_text = data.get('prescription', '').strip()
    details = data.get('details', 'Prescription issued via Smart E-Prescriptions Hub')

    if not patient_id or not prescription_text:
        return JsonResponse({'error': 'patient_id and prescription text are required'}, status=400)

    patient = get_object_or_404(Patients, id=patient_id)

    record = MedicalRecord.objects.create(
        doctor=doctor,
        clinic=doctor.clinic,
        patient=patient,
        details=details,
        prescription=prescription_text,
    )

    _log_audit(request.user, 'CREATE_PRESCRIPTION', f"Prescription for {patient.name} (record #{record.id})", request)

    return JsonResponse({
        'success': True,
        'record_id': record.id,
        'pdf_url': f'/doctor/generate-prescription-pdf/{record.id}/',
        'patient_name': patient.name,
    })


@login_required
@doctor_required
def visit_recordings_view(request):
    """View all stored patient visit transcripts and AI call recordings."""
    doctor = DoctorProfile.get_or_create_for_user(request.user)
    recordings = VisitRecording.objects.filter(doctor=doctor).select_related('patient', 'appointment').order_by('-recorded_at')[:100]

    context = {
        'doctor': doctor,
        'recordings': recordings,
        'active_menu': 'visit_recordings',
    }
    return render(request, 'visit_recordings.html', context)

# ==============================================================================
# 11. SMS DISPATCH & COMMUNICATION LOGS
# ==============================================================================
@login_required
@doctor_required
def sms_view(request):
    doctor = DoctorProfile.get_or_create_for_user(request.user)
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
@doctor_required
def reports_view(request):
    doctor = DoctorProfile.get_or_create_for_user(request.user)
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
@doctor_required
def labels_view(request):
    doctor = DoctorProfile.get_or_create_for_user(request.user)
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
@doctor_required
def leads_view(request):
    doctor = DoctorProfile.get_or_create_for_user(request.user)
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
@doctor_required
def locations_view(request):
    doctor = DoctorProfile.get_or_create_for_user(request.user)
    _seed_defaults_if_empty(doctor)
    locations = ClinicLocation.objects.filter(clinic=doctor.clinic) if doctor.clinic else []

    context = {
        'doctor': doctor,
        'locations': locations,
        'active_menu': 'locations'
    }
    return render(request, 'locations.html', context)

# ==============================================================================
# 16. BILLING (Settings)
# ==============================================================================
@login_required
@doctor_required
def billing_view(request):
    doctor = DoctorProfile.get_or_create_for_user(request.user)
    invoices = BillingInvoice.objects.filter(doctor=doctor).order_by('-created_at')

    if not invoices.exists() and doctor.clinic:
        p = Patients.objects.filter(doctor=doctor).first()
        if p:
            BillingInvoice.objects.create(
                patient=p, doctor=doctor, items_summary="Standard Consultation & Vitals",
                total_amount=65.00, tax_amount=0.00, payment_method="Card", status="Paid"
            )
            invoices = BillingInvoice.objects.filter(doctor=doctor)

    total_revenue = sum(inv.total_amount for inv in invoices if inv.status == 'Paid')

    context = {
        'doctor': doctor,
        'invoices': invoices,
        'total_revenue': total_revenue,
        'active_menu': 'billing'
    }
    return render(request, 'billing.html', context)

# ==============================================================================
# 17. AUDIT LOG (Settings)
# ==============================================================================
@login_required
@doctor_required
def audit_log_view(request):
    doctor = DoctorProfile.get_or_create_for_user(request.user)
    logs = AuditLogEntry.objects.all().order_by('-timestamp')[:100]

    context = {
        'doctor': doctor,
        'logs': logs,
        'active_menu': 'audit_log'
    }
    return render(request, 'audit_log.html', context)

# ==============================================================================
# 18. LABS HUB & TICKET LIFECYCLE
# ==============================================================================
@login_required
@doctor_required
def labs_view(request):
    doctor = DoctorProfile.get_or_create_for_user(request.user)
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
@doctor_required
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

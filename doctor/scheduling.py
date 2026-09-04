"""Scheduling helpers: slot generation, availability checks, and clinical priority scoring."""
from datetime import datetime, timedelta, date, time
from django.db.models import Q

DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

EMERGENCY_TRIGGERS = [
    "chest pain", "pressure in chest", "shortness of breath", "trouble breathing",
    "cannot breathe", "severe bleeding", "unconscious", "passed out", "stroke",
    "facial drooping", "severe head injury", "suicidal", "coughing blood", "anaphylaxis",
]

HIGH_RISK_SYMPTOMS = [
    "high fever", "fever over", "103", "104", "severe pain", "intense pain",
    "vomiting blood", "blood in stool", "confusion", "dizzy", "fainting",
    "rapid heartbeat", "swelling face", "allergic reaction", "pregnancy bleeding",
    "severe headache", "vision loss", "numbness", "weakness one side",
]

MODERATE_SYMPTOMS = [
    "fever", "persistent cough", "sore throat", "infection", "uti",
    "ear pain", "rash", "vomiting", "diarrhea", "back pain", "injury",
    "anxiety", "depression", "chronic", "worsening",
]


def get_day_name(target_date):
    return DAY_NAMES[target_date.weekday()]


def generate_slots_for_date(doctor, target_date):
    """Return list of time slot strings (HH:MM) from doctor availability blocks."""
    from .models import AvailabilityBlock, Appointments

    day_name = get_day_name(target_date)
    blocks = AvailabilityBlock.objects.filter(
        doctor=doctor, day_of_week=day_name, is_active=True
    ).order_by('start_time')

    if not blocks.exists():
        blocks = _default_blocks(doctor, day_name)

    booked_times = set(
        Appointments.objects.filter(
            doctor=doctor, date=target_date
        ).exclude(status='cancelled').values_list('start_time', flat=True)
    )

    slots = []
    for block in blocks:
        duration = timedelta(minutes=block.slot_duration_minutes or 20)
        current = datetime.combine(target_date, block.start_time)
        end = datetime.combine(target_date, block.end_time)
        break_start = datetime.combine(target_date, block.break_start) if block.break_start else None
        break_end = datetime.combine(target_date, block.break_end) if block.break_end else None

        while current + duration <= end:
            slot_time = current.time()
            in_break = (
                break_start and break_end
                and break_start <= current < break_end
            )
            if not in_break and slot_time not in booked_times:
                slots.append(slot_time.strftime('%H:%M'))
            current += duration

    return slots


def _default_blocks(doctor, day_name):
    """Fallback when no availability configured."""
    from .models import AvailabilityBlock
    if day_name in ('Saturday', 'Sunday'):
        return AvailabilityBlock.objects.none()
    return AvailabilityBlock.objects.filter(pk=-1)  # empty queryset


def count_total_slots(doctor, target_date):
    return len(generate_slots_for_date(doctor, target_date)) + _booked_count(doctor, target_date)


def _booked_count(doctor, target_date):
    from .models import Appointments
    return Appointments.objects.filter(
        doctor=doctor, date=target_date
    ).exclude(status='cancelled').count()


def find_next_available_slot(doctor, start_date=None, max_days=14):
    """Find the next open appointment slot within max_days."""
    if start_date is None:
        start_date = date.today()

    for offset in range(max_days):
        target = start_date + timedelta(days=offset)
        slots = generate_slots_for_date(doctor, target)
        if slots:
            return target, slots[0]
    return None, None


def parse_preferred_date(message_lower, today=None):
    """Extract preferred date from natural language."""
    if today is None:
        today = date.today()

    if 'today' in message_lower:
        return today
    if 'tomorrow' in message_lower:
        return today + timedelta(days=1)
    if 'next week' in message_lower:
        return today + timedelta(days=7)
    if 'monday' in message_lower:
        return _next_weekday(today, 0)
    if 'tuesday' in message_lower:
        return _next_weekday(today, 1)
    if 'wednesday' in message_lower:
        return _next_weekday(today, 2)
    if 'thursday' in message_lower:
        return _next_weekday(today, 3)
    if 'friday' in message_lower:
        return _next_weekday(today, 4)
    return None


def _next_weekday(from_date, weekday):
    days_ahead = weekday - from_date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return from_date + timedelta(days=days_ahead)


def parse_time_preference(message_lower):
    """Extract preferred time of day from message."""
    if any(w in message_lower for w in ['morning', 'am', 'early']):
        return 'morning'
    if any(w in message_lower for w in ['afternoon', 'midday', 'noon']):
        return 'afternoon'
    if any(w in message_lower for w in ['evening', 'late', 'pm']):
        return 'evening'
    return None


def pick_slot_for_preference(slots, preference):
    """Pick best slot matching time-of-day preference."""
    if not slots:
        return None
    if not preference:
        return slots[0]

    def hour_of(slot_str):
        return int(slot_str.split(':')[0])

    if preference == 'morning':
        morning = [s for s in slots if hour_of(s) < 12]
        return morning[0] if morning else slots[0]
    if preference == 'afternoon':
        afternoon = [s for s in slots if 12 <= hour_of(s) < 17]
        return afternoon[0] if afternoon else slots[0]
    if preference == 'evening':
        evening = [s for s in slots if hour_of(s) >= 17]
        return evening[0] if evening else slots[-1]
    return slots[0]


def detect_emergency(message_lower):
    for trigger in EMERGENCY_TRIGGERS:
        if trigger in message_lower:
            return trigger
    return None


def calculate_priority(message):
    """
    Assess clinical priority from patient symptoms.
    Returns (priority_tier, risk_score, risk_tier) where:
      priority_tier: Routine | Priority-Revisit | Urgent
      risk_score: 0-100
      risk_tier: Low | Medium | High
    """
    message_lower = message.lower()
    score = 10

    if detect_emergency(message_lower):
        return 'Urgent', 95, 'High'

    for symptom in HIGH_RISK_SYMPTOMS:
        if symptom in message_lower:
            score += 25

    for symptom in MODERATE_SYMPTOMS:
        if symptom in message_lower:
            score += 12

    if any(w in message_lower for w in ['routine', 'checkup', 'check-up', 'follow up', 'follow-up', 'annual']):
        score = max(5, score - 10)

    score = min(100, score)

    if score >= 70:
        return 'Urgent', score, 'High'
    if score >= 40:
        return 'Priority-Revisit', score, 'Medium'
    return 'Routine', score, 'Low'


def is_availability_query(message_lower):
    keywords = [
        'when is', 'when are', 'is the doctor free', 'doctor free', 'available',
        'availability', 'open slot', 'next appointment', 'earliest slot',
        'what times', 'schedule', 'book an appointment', 'make an appointment',
        'need to see', 'want to see', 'can i come', 'free today', 'free tomorrow',
    ]
    return any(k in message_lower for k in keywords)


def is_booking_intent(message_lower):
    keywords = [
        'book', 'schedule', 'appointment', 'reserve', 'slot', 'visit',
        'consultation', 'see the doctor', 'need to come in', 'checkup', 'check-up',
    ]
    return any(k in message_lower for k in keywords)


def is_greeting(message_lower):
    greetings = ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening']
    return any(message_lower.strip().startswith(g) or message_lower == g for g in greetings)


def doctor_is_available_on(doctor, target_date):
    """Check if doctor has any open slots on a given date."""
    return len(generate_slots_for_date(doctor, target_date)) > 0


def format_slot_list(slots, limit=5):
    if not slots:
        return "No open slots available."
    shown = slots[:limit]
    formatted = ", ".join(_format_time_12h(s) for s in shown)
    if len(slots) > limit:
        formatted += f" (+{len(slots) - limit} more)"
    return formatted


def _format_time_12h(time_str):
    t = datetime.strptime(time_str, '%H:%M').time()
    return t.strftime('%I:%M %p').lstrip('0')

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

class Clinic(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200, blank=True, default='')
    phone_number = models.CharField(max_length=15, blank=True, default='')
    logo = models.CharField(max_length=200, default='', null=True, blank=True)
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_clinics')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class DoctorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='doctor_profile')
    specialization = models.CharField(max_length=100)
    clinic_photo_path = models.CharField(max_length=100, default='', null=True, blank=True)
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='doctors', null=True, blank=True)

    @property
    def logo_path(self):
        if self.clinic and self.clinic.logo:
            return self.clinic.logo
        return self.clinic_photo_path or ''

    @classmethod
    def get_or_create_for_user(cls, user):
        profile = cls.objects.filter(user=user).first()
        if not profile:
            clinic_name = f"Dr. {user.get_full_name() or user.username}'s Clinic"
            clinic, _ = Clinic.objects.get_or_create(name=clinic_name)
            profile, _ = cls.objects.get_or_create(
                user=user,
                defaults={
                    'specialization': 'General Practice',
                    'clinic': clinic
                }
            )
        elif not profile.clinic:
            clinic_name = f"Dr. {user.get_full_name() or user.username}'s Clinic"
            clinic, _ = Clinic.objects.get_or_create(name=clinic_name)
            profile.clinic = clinic
            profile.save(update_fields=['clinic'])
        return profile

    def __str__(self):
        return f"Dr. {self.user.get_full_name() or self.user.username}"

class Patients(models.Model):
    GENDER_CHOICES = (
        ('Male', 'male'),
        ('Female', 'female')
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='patient_profile')
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='clinic_patients', null=True, blank=True)
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='doctor_patients')
    name = models.CharField(max_length=200)
    date_added = models.DateTimeField(auto_now_add=True)
    phone_number = models.CharField(max_length=15)
    email = models.EmailField(blank=True, default='')
    gender = models.CharField(max_length=6, choices=GENDER_CHOICES)
    date_of_birth = models.DateField(null=True, blank=True)
    
    # AI & Clinical Risk Assessment
    no_show_score = models.IntegerField(default=5, help_text="Calculated risk score 0-100")
    risk_tier = models.CharField(max_length=20, default='Low', choices=(('Low', 'Low'), ('Medium', 'Medium'), ('High', 'High')))
    medical_history = models.TextField(blank=True, default='')
    allergies = models.CharField(max_length=500, blank=True, default='')
    active_medications = models.TextField(blank=True, default='')
    tags = models.CharField(max_length=255, blank=True, default='Routine')

    def __str__(self):
        clinic_str = self.clinic.name if self.clinic else "No Clinic"
        return f"{self.name} ({clinic_str})"

class MedicalRecord(models.Model):
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE)
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, null=True, blank=True)
    patient = models.ForeignKey(Patients, on_delete=models.CASCADE)
    date = models.DateTimeField(default=timezone.now)
    details = models.CharField(max_length=2000, help_text="Clinical notes - visible to doctor and assistant only")
    remarks = models.CharField(max_length=1000, default='', blank=True, help_text="Visible to patient")
    prescription = models.CharField(max_length=1000, default='', null=True, blank=True, help_text="Visible to patient")
    share_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, null=True, blank=True)
    is_shareable = models.BooleanField(default=False)
    share_expires_at = models.DateTimeField(null=True, blank=True)
    soap_summary = models.TextField(blank=True, default='', help_text="AI Ambient Scribe structured SOAP notes")

    def is_share_link_active(self):
        if not self.is_shareable:
            return False
        if self.share_expires_at is not None:
            return timezone.now() < self.share_expires_at
        return True

    def get_share_url(self, request=None):
        from django.urls import reverse
        if not self.share_token:
            self.share_token = uuid.uuid4()
            self.save(update_fields=['share_token'])
        path = reverse('shared_prescription_pdf', kwargs={'token': self.share_token})
        if request:
            return request.build_absolute_uri(path)
        return path

    def __str__(self):
        return f"Medical record for {self.patient} - {self.date.strftime('%Y-%m-%d')}"

class AppointmentTimes(models.Model):
    DAYS_OF_THE_WEEK = (
        ('Monday', 'monday'),
        ('Tuesday', 'tuesday'),
        ('Wednesday', 'wednesday'),
        ('Thursday', 'thursday'),
        ('Friday', 'friday'),
        ('Saturday', 'saturday'),
        ('Sunday', 'sunday')
    )

    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE)
    start_time = models.TimeField()
    end_time = models.TimeField()
    separation_time = models.DurationField(help_text="Duration between appointments (in minutes)")
    day_of_the_week = models.CharField(max_length=10, choices=DAYS_OF_THE_WEEK)
    activated_status = models.BooleanField(default=True, help_text="Whether this appointment slot is currently active")

    def __str__(self):
        status = "active" if self.activated_status else "inactive"
        return f"Appointment times for Dr. {self.doctor.user.get_full_name()} on {self.day_of_the_week} ({status})"

class Appointments(models.Model):
    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('confirmed', 'Confirmed'),
        ('in_consultation', 'In Consultation'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No-Show'),
    )

    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE)
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, null=True, blank=True)
    patient = models.ForeignKey(Patients, on_delete=models.CASCADE)
    start_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    date = models.DateField()
    priority_tier = models.CharField(max_length=20, default='Routine', choices=(('Routine', 'Routine'), ('Waitlist', 'Waitlist'), ('Priority-Revisit', 'Priority-Revisit')))
    reminder_tier = models.CharField(max_length=20, default='Standard', choices=(('Standard', 'Standard'), ('Aggressive', 'Aggressive (High-Risk)')))
    reminder_sent = models.BooleanField(default=False)
    reason_for_visit = models.CharField(max_length=255, blank=True, default='Consultation')
    cancellation_reason = models.CharField(max_length=255, blank=True, default='')

    def __str__(self):
        return f"Appointment for Dr. {self.doctor.user.get_full_name()} and patient {self.patient} on {self.date}"

    class Meta:
        unique_together = ('doctor', 'date', 'start_time')
        verbose_name_plural = "Appointments"

# ==============================================================================
# HACKATHON WORKFLOW & MEDCARE / DESK.CLINIC EXTENDED DATA ENTITIES
# ==============================================================================

class AvailabilityBlock(models.Model):
    """Doctor working blocks, breaks, and auto-slot generation parameters."""
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='availability_blocks')
    day_of_week = models.CharField(max_length=10, choices=AppointmentTimes.DAYS_OF_THE_WEEK)
    start_time = models.TimeField(default='09:00')
    end_time = models.TimeField(default='17:00')
    slot_duration_minutes = models.IntegerField(default=20)
    break_start = models.TimeField(null=True, blank=True)
    break_end = models.TimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.day_of_week}: {self.start_time}-{self.end_time} ({self.slot_duration_minutes}m slots)"

class WaitlistQueue(models.Model):
    """Patients waiting for an earlier slot with auto-backfill cascading."""
    STATUS_CHOICES = (
        ('Waiting', 'Waiting'),
        ('Offered', 'Slot Offered'),
        ('Accepted', 'Accepted'),
        ('Expired', 'Expired'),
        ('Declined', 'Declined')
    )
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='waitlist_entries')
    patient_name = models.CharField(max_length=200)
    patient_phone = models.CharField(max_length=20)
    patient_email = models.CharField(max_length=100, blank=True, default='')
    requested_date = models.DateField()
    preferred_time_range = models.CharField(max_length=50, blank=True, default='Anytime')
    reason = models.CharField(max_length=255, blank=True, default='Doctor Consultation')
    priority_rank = models.IntegerField(default=1, help_text="Lower number = higher priority")
    priority_tier = models.CharField(max_length=20, default='Routine', choices=(('Routine', 'Routine'), ('Priority-Revisit', 'Priority-Revisit'), ('Urgent', 'Urgent')))
    status = models.CharField(max_length=20, default='Waiting', choices=STATUS_CHOICES)
    offered_slot_time = models.DateTimeField(null=True, blank=True)
    offer_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Waitlist: {self.patient_name} for {self.requested_date} ({self.status})"

class TriageEscalationLog(models.Model):
    """Emergency keywords triage log (chest pain, stroke, bleeding, etc.)."""
    patient_name = models.CharField(max_length=200, blank=True, default='Inquiry / Caller')
    patient_phone = models.CharField(max_length=20, blank=True, default='')
    trigger_phrase = models.CharField(max_length=255)
    severity = models.CharField(max_length=20, default='CRITICAL', choices=(('CRITICAL', 'Critical / Emergency'), ('HIGH', 'High Urgency'), ('MEDIUM', 'Medium Urgency')))
    notes = models.TextField(blank=True, default='')
    escalated_to = models.CharField(max_length=100, default='Emergency Duty Staff / Nurse')
    resolved = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.severity}] Triage: {self.trigger_phrase} ({self.timestamp.strftime('%H:%M')})"

class LabOrderTicket(models.Model):
    """Lab test order lifecycle: Order Created -> Sample Pending -> Processing -> Completed."""
    STATUS_CHOICES = (
        ('Order Created', 'Order Created'),
        ('Sample Pending', 'Sample Pending'),
        ('Processing', 'Processing'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled')
    )
    ticket_id = models.CharField(max_length=30, unique=True, default=uuid.uuid4)
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='lab_orders')
    patient = models.ForeignKey(Patients, on_delete=models.CASCADE, related_name='lab_tickets')
    appointment = models.ForeignKey(Appointments, on_delete=models.SET_NULL, null=True, blank=True)
    test_name = models.CharField(max_length=255)
    test_code = models.CharField(max_length=50, blank=True, default='')
    status = models.CharField(max_length=30, default='Order Created', choices=STATUS_CHOICES)
    order_created_at = models.DateTimeField(auto_now_add=True)
    sample_collected_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    technician_name = models.CharField(max_length=100, blank=True, default='Lab Tech Central')
    clinical_notes = models.TextField(blank=True, default='')
    result_summary = models.TextField(blank=True, default='')
    report_file_url = models.CharField(max_length=255, blank=True, default='')

    def __str__(self):
        return f"LabTicket #{self.ticket_id[:8]} - {self.test_name} ({self.status})"

class PatientRecordViewToken(models.Model):
    """Tokenized, no-login mobile patient view for prescriptions, lab status, & QR pass."""
    token = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
    patient = models.ForeignKey(Patients, on_delete=models.CASCADE, related_name='portal_tokens')
    appointment = models.ForeignKey(Appointments, on_delete=models.SET_NULL, null=True, blank=True)
    medical_record = models.ForeignKey(MedicalRecord, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def is_valid(self):
        if not self.is_active:
            return False
        if self.expires_at:
            return timezone.now() < self.expires_at
        return True

    def __str__(self):
        return f"PortalToken for {self.patient.name} ({self.token[:8]}...)"

class FollowUpTask(models.Model):
    """Day+3 automated check-in task. If unwell, flags for priority revisit."""
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Recovered', 'Recovered'),
        ('Unwell', 'Unwell (Priority Revisit)'),
        ('Completed', 'Completed'),
        ('Unreachable', 'Unreachable')
    )
    appointment = models.ForeignKey(Appointments, on_delete=models.CASCADE, related_name='follow_up_tasks')
    patient = models.ForeignKey(Patients, on_delete=models.CASCADE)
    trigger_date = models.DateField()
    status = models.CharField(max_length=20, default='Pending', choices=STATUS_CHOICES)
    revisit_priority = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"T+3 Follow-up: {self.patient.name} on {self.trigger_date} ({self.status})"

class InventoryItem(models.Model):
    """Pharmacy stock and medical supplies inventory."""
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, null=True, blank=True, related_name='inventory_items')
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100, default='Medication', choices=(('Medication', 'Medication'), ('Consumable', 'Consumable'), ('Diagnostic', 'Diagnostic'), ('Surgical', 'Surgical')))
    batch_number = models.CharField(max_length=100, blank=True, default='')
    stock_quantity = models.IntegerField(default=100)
    unit = models.CharField(max_length=50, default='Tablets')
    reorder_level = models.IntegerField(default=20)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=5.00)
    expiry_date = models.DateField(null=True, blank=True)
    supplier = models.CharField(max_length=200, blank=True, default='PharmaDirect Ltd')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.stock_quantity} {self.unit})"

class QueueTicket(models.Model):
    """Waiting room live token queue and caller engine."""
    STATUS_CHOICES = (
        ('Waiting', 'Waiting'),
        ('In Consultation', 'In Consultation'),
        ('Completed', 'Completed'),
        ('No-Show', 'No-Show')
    )
    token_number = models.CharField(max_length=20)
    patient_name = models.CharField(max_length=200)
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='queue_tickets')
    appointment = models.ForeignKey(Appointments, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=30, default='Waiting', choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True)
    estimated_wait_minutes = models.IntegerField(default=15)

    def __str__(self):
        return f"Token #{self.token_number} - {self.patient_name} ({self.status})"

class Referral(models.Model):
    """Specialist & hospital referrals."""
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Sent', 'Sent'),
        ('Accepted', 'Accepted'),
        ('Completed', 'Completed')
    )
    patient = models.ForeignKey(Patients, on_delete=models.CASCADE, related_name='referrals')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE)
    specialist_name = models.CharField(max_length=200)
    specialty = models.CharField(max_length=100)
    hospital_name = models.CharField(max_length=200, blank=True, default='')
    reason = models.TextField()
    status = models.CharField(max_length=30, default='Pending', choices=STATUS_CHOICES)
    date_referred = models.DateField(default=timezone.now)

    def __str__(self):
        return f"Referral: {self.patient.name} to Dr. {self.specialist_name} ({self.specialty})"

class ClaimRecord(models.Model):
    """Insurance coverage verification and claims."""
    STATUS_CHOICES = (
        ('Draft', 'Draft'),
        ('Submitted', 'Submitted'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected')
    )
    patient = models.ForeignKey(Patients, on_delete=models.CASCADE, related_name='claims')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE)
    appointment = models.ForeignKey(Appointments, on_delete=models.SET_NULL, null=True, blank=True)
    payer_name = models.CharField(max_length=150, help_text="Insurance provider")
    policy_number = models.CharField(max_length=100)
    claim_amount = models.DecimalField(max_digits=10, decimal_places=2, default=75.00)
    copay_amount = models.DecimalField(max_digits=10, decimal_places=2, default=15.00)
    coverage_status = models.CharField(max_length=50, default='Eligible')
    status = models.CharField(max_length=30, default='Submitted', choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Claim #{self.id} for {self.patient.name} - ${self.claim_amount} ({self.status})"

class SmsLog(models.Model):
    """Communication dispatch logs for SMS, WhatsApp, and reminders."""
    MESSAGE_TYPES = (
        ('Appointment Reminder', 'Appointment Reminder'),
        ('Digital Prescription', 'Digital Prescription'),
        ('Lab Results Ready', 'Lab Results Ready'),
        ('Waitlist Offer', 'Waitlist Offer'),
        ('T+3 Follow-up', 'T+3 Follow-up')
    )
    recipient_name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=30)
    message_type = models.CharField(max_length=50, choices=MESSAGE_TYPES)
    content = models.TextField()
    status = models.CharField(max_length=20, default='Delivered', choices=(('Delivered', 'Delivered'), ('Pending', 'Pending'), ('Failed', 'Failed')))
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SMS to {self.recipient_name} ({self.message_type}) - {self.status}"

class AuditLogEntry(models.Model):
    """Clinical actions, logins, and prescription access security trail."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action_type = models.CharField(max_length=100)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {self.action_type}"

class LeadEntry(models.Model):
    """Patient inquiries and conversational bot leads."""
    STATUS_CHOICES = (
        ('New', 'New'),
        ('Contacted', 'Contacted'),
        ('Converted', 'Converted (Booked)'),
        ('Dismissed', 'Dismissed')
    )
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30)
    email = models.CharField(max_length=100, blank=True, default='')
    source = models.CharField(max_length=100, default='Conversational Bot', choices=(('Conversational Bot', 'Conversational Bot'), ('Website', 'Website'), ('Phone Inquiry', 'Phone Inquiry'), ('Walk-in', 'Walk-in')))
    symptoms = models.TextField(blank=True, default='')
    status = models.CharField(max_length=30, default='New', choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Lead: {self.name} ({self.source}) - {self.status}"

class ClinicLocation(models.Model):
    """Clinic consultation rooms and clinical suites."""
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='locations')
    name = models.CharField(max_length=150)
    room_number = models.CharField(max_length=50)
    purpose = models.CharField(max_length=150, default='Consultation')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} (Room {self.room_number})"

class BillingInvoice(models.Model):
    """Patient billing, invoices, and payment tracking."""
    STATUS_CHOICES = (
        ('Paid', 'Paid'),
        ('Pending', 'Pending'),
        ('Overdue', 'Overdue'),
        ('Refunded', 'Refunded')
    )
    invoice_id = models.CharField(max_length=30, unique=True, default=uuid.uuid4)
    patient = models.ForeignKey(Patients, on_delete=models.CASCADE, related_name='invoices')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE)
    appointment = models.ForeignKey(Appointments, on_delete=models.SET_NULL, null=True, blank=True)
    items_summary = models.TextField(default='Doctor Consultation Fee')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=50.00)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_method = models.CharField(max_length=50, default='Cash', choices=(('Cash', 'Cash'), ('Card', 'Credit/Debit Card'), ('Insurance', 'Insurance Direct'), ('Online', 'Online / Bank Transfer')))
    status = models.CharField(max_length=20, default='Paid', choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invoice #{self.invoice_id[:8]} - {self.patient.name} (${self.total_amount})"
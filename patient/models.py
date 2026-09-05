from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid

def generate_short_id():
    return uuid.uuid4().hex[:10].upper()

class PatientDocument(models.Model):
    """Personal health documents uploaded by the patient (lab reports, discharge summaries, etc.)."""
    DOCUMENT_TYPES = (
        ('Lab Report', 'Lab Report'),
        ('Prescription', 'Prescription'),
        ('Discharge Summary', 'Discharge Summary'),
        ('Scan / X-Ray', 'Scan / X-Ray'),
        ('Vaccination Card', 'Vaccination Card'),
        ('Insurance Card', 'Insurance Card'),
        ('Other', 'Other')
    )
    patient = models.ForeignKey('doctor.Patients', on_delete=models.CASCADE, related_name='uploaded_documents')
    title = models.CharField(max_length=200)
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES, default='Lab Report')
    file = models.FileField(upload_to='patient_docs/', null=True, blank=True)
    file_url = models.CharField(max_length=500, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.patient.name})"

class VaccinationRecord(models.Model):
    """Personal immunization and vaccination tracker."""
    STATUS_CHOICES = (
        ('Completed', 'Completed'),
        ('Scheduled', 'Scheduled'),
        ('Overdue', 'Overdue')
    )
    patient = models.ForeignKey('doctor.Patients', on_delete=models.CASCADE, related_name='vaccinations')
    vaccine_name = models.CharField(max_length=150)
    dose_number = models.CharField(max_length=50, default='Dose 1')
    date_administered = models.DateField(default=timezone.now)
    next_due_date = models.DateField(null=True, blank=True)
    administered_by = models.CharField(max_length=150, blank=True, default='Primary Health Center')
    batch_number = models.CharField(max_length=100, blank=True, default='')
    status = models.CharField(max_length=30, default='Completed', choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.vaccine_name} - {self.patient.name}"

class PatientDoctorMessage(models.Model):
    """In-app secure messaging between patient and doctor."""
    CATEGORY_CHOICES = (
        ('General Inquiry', 'General Inquiry'),
        ('Prescription Refill', 'Prescription Refill Request'),
        ('Follow-up Question', 'Follow-up Question'),
        ('Lab Results Clarification', 'Lab Results Clarification'),
        ('Appointment Query', 'Appointment Query')
    )
    patient = models.ForeignKey('doctor.Patients', on_delete=models.CASCADE, related_name='chat_messages')
    doctor = models.ForeignKey('doctor.DoctorProfile', on_delete=models.CASCADE, related_name='patient_messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='General Inquiry')
    message = models.TextField()
    is_doctor_reply = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        role = "Doctor" if self.is_doctor_reply else "Patient"
        return f"Msg from {role} ({self.created_at.strftime('%m/%d %H:%M')})"

class FamilyMember(models.Model):
    """Linked family members and dependents."""
    RELATIONSHIP_CHOICES = (
        ('Spouse', 'Spouse'),
        ('Child', 'Child / Dependent'),
        ('Parent', 'Parent (Father/Mother)'),
        ('Sibling', 'Sibling'),
        ('Other', 'Other')
    )
    GENDER_CHOICES = (
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other')
    )
    patient = models.ForeignKey('doctor.Patients', on_delete=models.CASCADE, related_name='family_members')
    name = models.CharField(max_length=150)
    relationship = models.CharField(max_length=50, choices=RELATIONSHIP_CHOICES)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='Male')
    date_of_birth = models.DateField(null=True, blank=True)
    blood_group = models.CharField(max_length=10, blank=True, default='O+')
    allergies = models.CharField(max_length=255, blank=True, default='None')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.relationship} of {self.patient.name})"

class HealthTip(models.Model):
    """Curated wellness articles and health guides."""
    CATEGORY_CHOICES = (
        ('Nutrition', 'Daily Nutrition'),
        ('Heart Health', 'Cardiovascular & Heart'),
        ('Preventive Care', 'Preventive Wellness'),
        ('Mental Health', 'Stress & Mental Wellness'),
        ('Fitness', 'Fitness & Mobility'),
        ('Sleep', 'Sleep Hygiene & Rest'),
        ('Seasonal', 'Seasonal Care & Immunity')
    )
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Preventive Care')
    summary = models.TextField()
    content = models.TextField()
    read_time = models.CharField(max_length=20, default='3 min read')
    icon = models.CharField(max_length=50, default='fa-heart-pulse')
    doctor_endorsement = models.CharField(max_length=150, default='Verified by Clinical Advisory Team')
    likes_count = models.IntegerField(default=24)
    published_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.category}] {self.title}"

class LabTestCatalog(models.Model):
    """Standard diagnostic tests catalog for patient browsing & booking."""
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=100, default='Routine Diagnostic')
    description = models.TextField(blank=True, default='')
    preparation = models.CharField(max_length=255, default='Fasting 10-12 hours recommended')
    turnaround_time = models.CharField(max_length=100, default='Within 24 Hours')
    sample_type = models.CharField(max_length=100, default='Blood (Serum)')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    is_popular = models.BooleanField(default=False)
    icon = models.CharField(max_length=50, default='fa-vial')

    def __str__(self):
        return f"{self.name} (₹{self.price})"

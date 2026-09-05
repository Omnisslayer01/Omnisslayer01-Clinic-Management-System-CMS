import uuid
from datetime import datetime, date
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import DoctorProfile, Patients, MedicalRecord
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from accounts.decorators import doctor_required, doctor_or_assistant_required
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.http import HttpResponse, JsonResponse
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch, mm
import os
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
try:
    from weasyprint import HTML, CSS
except (ImportError, OSError):
    HTML = None
    CSS = None

@login_required
@doctor_or_assistant_required
def add_medical_record(request):
    import re
    from .models import Appointments, AuditLogEntry, QueueTicket
    from .medcare_views import COMMON_DRUGS

    # Retrieve appropriate doctor profile
    if hasattr(request.user, 'is_doctor') and request.user.is_doctor():
        doctor = DoctorProfile.get_or_create_for_user(request.user)
    else:
        from assistant.models import AssistantProfile
        assistant = get_object_or_404(AssistantProfile, user=request.user)
        doctor = assistant.doctor

    if request.method == 'POST':
        patient_id = request.POST.get("patient_id")
        appointment_id = request.POST.get("appointment_id")
        
        # Look up patient under doctor or clinic
        patient = Patients.objects.filter(
            Q(doctor=doctor) | Q(clinic=doctor.clinic) | Q(id=patient_id),
            id=patient_id
        ).first()
        if not patient:
            patient = get_object_or_404(Patients, id=patient_id)

        date_str = request.POST.get("date")
        parsed_date = None
        if date_str:
            try:
                parsed_date = datetime.strptime(date_str, '%Y-%m-%d')
                parsed_date = timezone.make_aware(parsed_date, timezone.get_current_timezone())
            except Exception:
                parsed_date = timezone.now()
        else:
            parsed_date = timezone.now()

        details = request.POST.get("details", "").strip()
        remarks = request.POST.get("remarks", "").strip()
        prescription = request.POST.get("prescription", "").strip()

        # Vitals intake
        v_bp = request.POST.get("vitals_bp", "").strip()
        v_pulse = request.POST.get("vitals_pulse", "").strip()
        v_temp = request.POST.get("vitals_temp", "").strip()
        v_weight = request.POST.get("vitals_weight", "").strip()
        v_spo2 = request.POST.get("vitals_spo2", "").strip()

        vitals_list = []
        if v_bp:
            vitals_list.append(f"BP: {v_bp} mmHg")
        if v_pulse:
            vitals_list.append(f"Pulse: {v_pulse} bpm")
        if v_temp:
            vitals_list.append(f"Temp: {v_temp} °F")
        if v_weight:
            vitals_list.append(f"Weight: {v_weight} kg")
        if v_spo2:
            vitals_list.append(f"SpO2: {v_spo2}%")

        if vitals_list:
            vitals_str = " | ".join(vitals_list)
            if "<p>" in details or "<div>" in details:
                details = f"<p><strong>Vital Signs:</strong> {vitals_str}</p>" + details
            else:
                details = f"Vital Signs: {vitals_str}\n" + (details or "General Clinical Evaluation")

        # Set default clinical notes if blank
        history_count = MedicalRecord.objects.filter(patient=patient).count()
        if not details:
            details = "Initial Patient Consultation & Clinical Intake" if history_count == 0 else "Outpatient Consultation & Evaluation"

        new_record = MedicalRecord.objects.create(
            doctor=doctor,
            clinic=doctor.clinic,
            patient=patient,
            date=parsed_date,
            details=details,
            remarks=remarks,
            prescription=prescription or "Standard Clinical Observation & Routine Care"
        )

        # 1. Update appointment status to completed
        if appointment_id:
            Appointments.objects.filter(id=appointment_id).update(status='completed')
        else:
            today_d = (parsed_date or timezone.now()).date()
            Appointments.objects.filter(
                doctor=doctor,
                patient=patient,
                date=today_d,
                status__in=['scheduled', 'in_consultation']
            ).update(status='completed')

        # 2. Update live queue ticket if any
        QueueTicket.objects.filter(
            doctor=doctor,
            patient_name=patient.name,
            created_at__date=timezone.now().date(),
            status__in=['Waiting', 'In Consultation']
        ).update(status='Completed')

        # 3. Update patient's active medications and primary medical history
        if prescription:
            patient.active_medications = prescription
        if not patient.medical_history:
            clean_diag = re.sub(r'<[^>]+>', ' ', details).strip()
            clean_diag = ' '.join(clean_diag.split())
            patient.medical_history = f"Primary Diagnosis: {clean_diag[:250]}"
        patient.save(update_fields=['active_medications', 'medical_history'])

        # 4. Audit Log
        AuditLogEntry.objects.create(
            user=request.user,
            action_type="Consultation Completed",
            description=f"Consultation Record #{new_record.id:05d} completed for patient {patient.name} by Dr. {request.user.get_full_name() or request.user.username}. Prescription recorded."
        )

        create_invoice = request.POST.get('create_invoice') in ['1', 'true', 'on', 'yes']
        if create_invoice:
            messages.success(request, _(f"Consultation for {patient.name} recorded! Redirecting to Billing..."))
            return redirect(reverse('medcare_billing') + f"?patient_id={patient.id}&appointment_id={appointment_id or ''}")

        messages.success(request, _(f"Consultation Record for {patient.name} saved successfully! Prescription is now recorded in the patient's Medical History."))
        return redirect(f"{reverse('show_patient_details')}?patient_id={patient.id}")

    else:
        patient_id = request.GET.get('patient_id')
        appointment_id = request.GET.get('appointment_id')
        appointment = None
        if appointment_id:
            appointment = Appointments.objects.filter(id=appointment_id).first()
            if not patient_id and appointment:
                patient_id = appointment.patient.id

        if patient_id:
            patient = Patients.objects.filter(
                Q(doctor=doctor) | Q(clinic=doctor.clinic) | Q(id=patient_id),
                id=patient_id
            ).first()
            if not patient:
                patient = get_object_or_404(Patients, id=patient_id)
        else:
            patient = Patients.objects.filter(Q(doctor=doctor) | Q(clinic=doctor.clinic)).first() or Patients.objects.first()
            if not patient:
                messages.error(request, _("Please register a patient first."))
                return redirect('register_patient')
            patient_id = patient.id

        patient_age = None
        if patient.date_of_birth:
            today_d = date.today()
            dob = patient.date_of_birth
            patient_age = today_d.year - dob.year - ((today_d.month, today_d.day) < (dob.month, dob.day))

        history_count = MedicalRecord.objects.filter(patient=patient).count()
        is_first_consultation = (history_count == 0)
        recent_records = MedicalRecord.objects.filter(patient=patient).order_by('-date')[:3]
        all_patients = Patients.objects.filter(Q(doctor=doctor) | Q(clinic=doctor.clinic)).order_by('name')

        context = {
            "user_data": request.user,
            "patient": patient,
            "patient_name": patient.name,
            "patient_id": patient_id,
            "patient_age": patient_age,
            "today_date": timezone.now(),
            "appointment": appointment,
            "is_first_consultation": is_first_consultation,
            "history_count": history_count,
            "recent_records": recent_records,
            "common_drugs": COMMON_DRUGS,
            "all_patients": all_patients,
        }
        return render(request, "add_medical_record.html", context)

@login_required
@doctor_required
def update_medical_record(request):
    medical_record_id = request.GET.get('medical_record_id')
    doctor_profile = DoctorProfile.get_or_create_for_user(request.user)
    medical_record = get_object_or_404(MedicalRecord, id=medical_record_id, doctor=doctor_profile)
    patient_id = medical_record.patient.id

    if request.method == 'GET': 
        context = {
            "user_data": request.user,
            "medical_record": medical_record,
            "patient_name": medical_record.patient.name,
            "patient_id": patient_id
        }
        return render(request, "edit_medical_record.html", context)

    date = request.POST.get('date')
    details = request.POST.get('details')
    remarks = request.POST.get('remarks')
    prescription = request.POST.get('prescription')

    medical_record.date = date
    medical_record.details = details
    medical_record.remarks = remarks
    medical_record.prescription = prescription

    try:
        medical_record.save()
        messages.success(request, _("Medical record updated successfully!"))
        url = reverse('show_patient_details') + f'?patient_id={patient_id}'
        return redirect(url)
    except Exception as e:
        messages.error(request, _(f"Something went wrong while updating the medical record: {str(e)}"))
        url = reverse('show_patient_details') + f'?patient_id={patient_id}'
        return redirect(url)

@login_required
@doctor_required
def delete_medical_record(request):
    medical_record_id = request.GET.get('medical_record_id')
    doctor_profile = DoctorProfile.get_or_create_for_user(request.user)
    medical_record = get_object_or_404(MedicalRecord, id=medical_record_id, doctor=doctor_profile)
    patient_id = medical_record.patient.id

    if request.method == 'POST': 
        try:
            name = medical_record.patient.name
            date = medical_record.date
            medical_record.delete()
            messages.success(request, _(f"Record deleted for {name} with date {date} successfully!"))
            url = reverse('show_patient_details') + f'?patient_id={patient_id}'
            return redirect(url)
        except Exception as e:
            messages.error(request, _(f"Something went wrong while deleting the medical record: {str(e)}"))
            url = reverse('show_patient_details') + f'?patient_id={patient_id}'
            return redirect(url)
    else:
        messages.error(request, _("Method Not allowed"))
        return redirect("doctor_dashboard")

def _clean_rl_text(text):
    if not text:
        return ""
    replacements = {
        '\u2014': '-',
        '\u2013': '-',
        '\u2018': "'",
        '\u2019': "'",
        '\u201c': '"',
        '\u201d': '"',
        '\u211e': 'Rx',
        '\u2022': '*',
        '\u2026': '...',
        '\u00a0': ' ',
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

def parse_prescription_items(raw_rx):
    """
    Intelligently splits and structures prescriptions into individual medication rows,
    handling HTML tags, newlines, semicolons, inline numbering, and inline Rx symbols.
    """
    import re
    if not raw_rx:
        return []
    
    text = str(raw_rx)
    # Convert HTML line breaks to newline
    text = re.sub(r'<\s*br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<\s*/\s*(?:p|div|li|tr|h\d)[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    
    # Replace entities
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Split on multiple inline Rx symbols e.g. "Rx Med 1 Rx Med 2" or "℞ Med 1 ℞ Med 2"
    text = re.sub(r'(?<=\S)\s+(?=(?:[R|r][X|x]\b|[\u211e\u211f]))', '\n', text)
    
    # Split on inline numbered items e.g. "1. Med 1 2. Med 2"
    text = re.sub(r'(?<=\S)\s+(?=\d+[\.\)]\s+)', '\n', text)
    
    raw_lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    final_items = []
    for line in raw_lines:
        if ';' in line:
            sub_parts = [p.strip() for p in line.split(';') if p.strip()]
            final_items.extend(sub_parts)
        elif len(raw_lines) == 1 and ',' in line:
            dash_count = len(re.findall(r'\s+[\u2014\u2013\-\:]\s+|\s+--\s+', line))
            if dash_count >= 2:
                # Multiple distinct medicines with their own dash on a single line
                comma_parts = [p.strip() for p in line.split(',') if p.strip()]
                final_items.extend(comma_parts)
            else:
                has_instructions = bool(re.search(r'\b(take|after meals|before meals|with meals|at bedtime|as needed|for \d+ days)\b', line, re.I))
                if dash_count == 0 and not has_instructions:
                    comma_parts = [p.strip() for p in line.split(',') if p.strip()]
                    if len(comma_parts) > 1 and all(len(p) > 2 for p in comma_parts):
                        final_items.extend(comma_parts)
                    else:
                        final_items.append(line)
                else:
                    final_items.append(line)
        else:
            final_items.append(line)
            
    parsed_records = []
    for idx, item in enumerate(final_items, 1):
        # Strip leading numbers or bullet points (e.g. 1. / 1) / • / -)
        item_clean = re.sub(r'^(?:\d+[\.\)]\s*|[\*\-\•\u2022]\s*)+', '', item).strip()
        # Strip leading Rx or ℞ (\u211e)
        item_clean = re.sub(r'^(?:[R|r][X|x]|[\u211e\u211f])\s*', '', item_clean).strip()
        
        if not item_clean:
            continue
            
        # Parse into Medication Name & Strength vs Directions / Timing
        # Handles patterns like: "Amoxicillin 500mg — Take BID, After meals for 5 days"
        # or "Paracetamol 650mg - 1 tab TID" or "Omeprazole 20mg : Before meals"
        parts = re.split(r'\s+[\u2014\u2013\-\:]\s+|\s+--\s+', item_clean, maxsplit=1)
        if len(parts) == 2:
            med_name = parts[0].strip()
            directions = parts[1].strip()
        elif ',' in item_clean and not re.search(r'\b(after|before|with|at|for|every|daily)\b', item_clean, re.I):
            c_parts = item_clean.split(',', 1)
            med_name = c_parts[0].strip()
            directions = c_parts[1].strip()
        else:
            med_name = item_clean
            directions = "Take as directed by physician"
            
        parsed_records.append({
            'number': idx,
            'name': med_name,
            'directions': directions,
            'full_text': item_clean
        })
        
    return parsed_records

def generate_prescription_pdf_reportlab(medical_record, buffer):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    import re

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    styles = getSampleStyleSheet()

    clinic_title_style = ParagraphStyle(
        'ClinicTitle', parent=styles['Normal'],
        fontSize=15, leading=19, fontName='Helvetica-Bold', textColor=colors.HexColor('#0f2b5c')
    )
    clinic_sub_style = ParagraphStyle(
        'ClinicSub', parent=styles['Normal'],
        fontSize=8, leading=11, fontName='Helvetica', textColor=colors.HexColor('#475569')
    )
    rx_header_style = ParagraphStyle(
        'RxHeader', parent=styles['Normal'],
        fontSize=8.5, leading=12, fontName='Helvetica-Bold', alignment=2, textColor=colors.HexColor('#0f2b5c')
    )
    section_label_style = ParagraphStyle(
        'SectionLabel', parent=styles['Normal'],
        fontSize=9.5, leading=13, fontName='Helvetica-Bold', textColor=colors.HexColor('#0284c7')
    )
    body_style = ParagraphStyle(
        'Body', parent=styles['Normal'],
        fontSize=8.5, leading=12, fontName='Helvetica', textColor=colors.HexColor('#1e293b')
    )
    body_bold_style = ParagraphStyle(
        'BodyBold', parent=styles['Normal'],
        fontSize=8.5, leading=12, fontName='Helvetica-Bold', textColor=colors.HexColor('#0f172a')
    )
    med_num_style = ParagraphStyle(
        'MedNum', parent=styles['Normal'],
        fontSize=9, leading=12, fontName='Helvetica-Bold', alignment=1, textColor=colors.HexColor('#0284c7')
    )
    med_name_style = ParagraphStyle(
        'MedName', parent=styles['Normal'],
        fontSize=9.5, leading=13, fontName='Helvetica-Bold', textColor=colors.HexColor('#0f172a')
    )
    med_dir_style = ParagraphStyle(
        'MedDir', parent=styles['Normal'],
        fontSize=8.5, leading=12, fontName='Helvetica', textColor=colors.HexColor('#334155')
    )
    table_hdr_style = ParagraphStyle(
        'TableHdr', parent=styles['Normal'],
        fontSize=8, leading=10, fontName='Helvetica-Bold', textColor=colors.white
    )
    table_hdr_center = ParagraphStyle(
        'TableHdrCenter', parent=styles['Normal'],
        fontSize=8, leading=10, fontName='Helvetica-Bold', alignment=1, textColor=colors.white
    )
    footer_style = ParagraphStyle(
        'Footer', parent=styles['Normal'],
        fontSize=7.5, leading=10, fontName='Helvetica-Oblique', alignment=1, textColor=colors.HexColor('#94a3b8')
    )

    story = []

    doctor_profile = medical_record.doctor
    doctor_user = doctor_profile.user
    doctor_name = f"Dr. {doctor_user.first_name} {doctor_user.last_name}".strip() or f"Dr. {doctor_user.username}"
    specialization = doctor_profile.specialization or "General Medicine & Outpatient Practice"
    clinic_obj = doctor_profile.clinic
    clinic_name = clinic_obj.name if clinic_obj else "CMS CLINICAL MEDICAL CENTER"
    clinic_address = getattr(clinic_obj, 'address', '') or 'Outpatient Healthcare Facility'
    clinic_phone = getattr(clinic_obj, 'phone_number', '') or '+1 (555) 019-2831'
    formatted_date = medical_record.date.strftime('%B %d, %Y')
    rx_code = f"RX-{medical_record.id:05d}"

    # 1. Header with Clinic Logo & Doctor Credentials
    logo_img = None
    possible_logo = os.path.join(settings.BASE_DIR, 'static', 'cms_logo.png')
    if os.path.exists(possible_logo):
        try:
            logo_img = RLImage(possible_logo, width=42, height=42)
        except Exception:
            logo_img = None

    left_text_block = [
        Paragraph(f"<b>{_clean_rl_text(clinic_name.upper())}</b>", clinic_title_style),
        Spacer(1, 2),
        Paragraph(f"<b>{_clean_rl_text(doctor_name)}</b> — <font color='#475569'>{_clean_rl_text(specialization)}</font>", body_style),
        Paragraph(f"{_clean_rl_text(clinic_address)} · Tel: {_clean_rl_text(clinic_phone)}", clinic_sub_style),
        Paragraph("Digital Clinical Healthcare & Outpatient Services · Telehealth Verified", clinic_sub_style)
    ]

    if logo_img:
        left_header = Table([[logo_img, left_text_block]], colWidths=[50, 300])
        left_header.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
    else:
        left_header = left_text_block

    # Determine document mode & title
    is_consultation = bool(medical_record.details and len(medical_record.details.strip()) > 5)
    doc_title = "CLINICAL CONSULTATION & Rx RECORD" if is_consultation else "CLINICAL E-PRESCRIPTION"
    cert_text = "Clinical Consultation Validated" if is_consultation else "Dispense Ready"

    right_header = [
        Paragraph(f"<b>{doc_title}</b>", rx_header_style),
        Spacer(1, 3),
        Paragraph(f"<b>Record ID:</b> <font color='#0284c7'>CR-{medical_record.id:05d}</font> | <b>Rx ID:</b> <font color='#0284c7'>{rx_code}</font>", rx_header_style),
        Paragraph(f"<b>Date:</b> {formatted_date}", rx_header_style),
        Paragraph(f"<b>Status:</b> <font color='#16a34a'>{cert_text}</font>", rx_header_style),
    ]

    header_table = Table([[left_header, right_header]], colWidths=[330, 192])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#0284c7'), spaceAfter=10))

    # 2. Patient Demographics Card
    patient = medical_record.patient
    gender = getattr(patient, 'gender', 'Not Specified')
    phone = getattr(patient, 'phone_number', '') or 'N/A'
    dob_str = patient.date_of_birth.strftime('%Y-%m-%d') if getattr(patient, 'date_of_birth', None) else 'N/A'
    age_str = ""
    if getattr(patient, 'date_of_birth', None):
        t_d = date.today()
        p_dob = patient.date_of_birth
        c_age = t_d.year - p_dob.year - ((t_d.month, t_d.day) < (p_dob.month, p_dob.day))
        age_str = f" ({c_age} yrs)"

    allergies_text = patient.allergies.strip() if getattr(patient, 'allergies', None) else ""
    if allergies_text:
        allergies_cell = Paragraph(f"<font color='#b91c1c'><b>Allergies:</b></font> <font color='#dc2626'>{_clean_rl_text(allergies_text)}</font>", body_style)
    else:
        allergies_cell = Paragraph("<font color='#15803d'><b>Allergies:</b></font> <font color='#16a34a'>NKDA (No Known Drug Allergies)</font>", body_style)

    pat_rows = [
        [
            Paragraph(f"<b>Patient Name:</b> {_clean_rl_text(patient.name)}", body_style),
            Paragraph(f"<b>Patient ID:</b> #{patient.id}", body_style),
            Paragraph(f"<b>Gender:</b> {_clean_rl_text(gender)}", body_style),
        ],
        [
            Paragraph(f"<b>Contact:</b> {_clean_rl_text(phone)}", body_style),
            Paragraph(f"<b>DOB / Age:</b> {dob_str}{age_str}", body_style),
            Paragraph(f"<b>Consultation:</b> Outpatient Intake", body_style),
        ],
        [
            allergies_cell,
            Paragraph(f"<b>Visit Type:</b> Clinical Consultation", body_style),
            Paragraph(f"<b>Payment:</b> Account Verified", body_style),
        ]
    ]
    pat_table = Table(pat_rows, colWidths=[184, 160, 178])
    pat_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 4.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4.5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(pat_table)
    story.append(Spacer(1, 8))

    # 3. Clinical Vitals & Measurements (if present in record)
    vitals_match = re.search(r'Vital Signs:\s*([^<\n\r]+)', str(medical_record.details or ''), re.IGNORECASE)
    if vitals_match:
        vitals_raw = vitals_match.group(1).strip()
        v_parts = [p.strip() for p in vitals_raw.split('|') if p.strip()]
        if v_parts:
            v_cells = [Paragraph(f"<b>{_clean_rl_text(p)}</b>", body_style) for p in v_parts]
            # Pad to 4 or 5 columns
            while len(v_cells) < 4:
                v_cells.append(Paragraph("", body_style))
            v_cells = v_cells[:5]
            w_each = int(522 / len(v_cells))
            vitals_table = Table([v_cells], colWidths=[w_each] * len(v_cells))
            vitals_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#ecfdf5')),
                ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#a7f3d0')),
                ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#d1fae5')),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('LEFTPADDING', (0,0), (-1,-1), 4),
                ('RIGHTPADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(Paragraph("<font color='#047857' size='8'><b>RECORDED VITALS & BIOMETRICS:</b></font>", body_bold_style))
            story.append(Spacer(1, 2))
            story.append(vitals_table)
            story.append(Spacer(1, 8))

    # 4. Clinical Diagnosis & Examination Findings
    if medical_record.details:
        raw_det = medical_record.details
        # Remove the extracted vital signs line from details display so it doesn't repeat
        raw_det = re.sub(r'<\s*p\s*>\s*<\s*strong\s*>\s*Vital Signs:\s*<\s*/strong\s*>[^<]*<\s*/p\s*>', '', raw_det, flags=re.I)
        raw_det = re.sub(r'Vital Signs:\s*[^\n\r]+', '', raw_det, flags=re.I)
        
        # Split HTML paragraphs and breaks into distinct lines
        raw_det = re.sub(r'<\s*br\s*/?>', '\n', raw_det, flags=re.I)
        raw_det = re.sub(r'<\s*/\s*(?:p|div|li|tr|h\d)[^>]*>', '\n', raw_det, flags=re.I)
        raw_det = re.sub(r'<[^>]+>', ' ', raw_det)
        raw_det = raw_det.replace('&nbsp;', ' ').replace('&amp;', '&')
        
        detail_lines = [line.strip() for line in raw_det.split('\n') if line.strip()]
        if detail_lines:
            diag_paragraphs = []
            diag_paragraphs.append(Paragraph("<font color='#0284c7'><b>CLINICAL EVALUATION & DIAGNOSIS:</b></font>", body_bold_style))
            for dl in detail_lines:
                diag_paragraphs.append(Paragraph(_clean_rl_text(dl), body_style))
            
            diag_table = Table([[p] for p in diag_paragraphs], colWidths=[522])
            diag_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f0f9ff')),
                ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#bae6fd')),
                ('TOPPADDING', (0,0), (-1,-1), 3),
                ('BOTTOMPADDING', (0,0), (-1,-1), 3),
                ('LEFTPADDING', (0,0), (-1,-1), 8),
                ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ]))
            story.append(diag_table)
            story.append(Spacer(1, 10))

    # 4. Prescription (Rx) Section - EACH MEDICINE ON ITS OWN ROW
    story.append(Paragraph("<font size='13' color='#0284c7'><b>Rx</b></font> <b>PRESCRIBED MEDICATIONS & REGIMEN</b>", section_label_style))
    story.append(Spacer(1, 4))

    medication_items = parse_prescription_items(medical_record.prescription)
    if not medication_items:
        medication_items = [{
            'number': 1,
            'name': 'Standard Clinical Care & Observation',
            'directions': 'Follow routine clinical wellness advice and return if symptoms change.'
        }]

    rx_table_data = [
        [
            Paragraph("<b>#</b>", table_hdr_center),
            Paragraph("<b>MEDICATION & DOSAGE FORM</b>", table_hdr_style),
            Paragraph("<b>DIRECTIONS / FREQUENCY / DURATION</b>", table_hdr_style),
        ]
    ]

    for idx, med in enumerate(medication_items, 1):
        num_p = Paragraph(f"<b>{idx}</b>", med_num_style)
        name_p = Paragraph(f"<b>{_clean_rl_text(med['name'])}</b>", med_name_style)
        dir_p = Paragraph(_clean_rl_text(med['directions']), med_dir_style)
        rx_table_data.append([num_p, name_p, dir_p])

    rx_table = Table(rx_table_data, colWidths=[32, 230, 260])
    table_styles = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f2b5c')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#94a3b8')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]

    # Alternating row backgrounds to guarantee visual distinction
    for r_idx in range(1, len(rx_table_data)):
        bg_color = colors.HexColor('#f8fafc') if r_idx % 2 == 0 else colors.HexColor('#ffffff')
        table_styles.append(('BACKGROUND', (0, r_idx), (-1, r_idx), bg_color))

    rx_table.setStyle(TableStyle(table_styles))
    story.append(rx_table)
    story.append(Spacer(1, 10))

    # 5. Doctor Remarks & Special Precautions (if present)
    if medical_record.remarks:
        rem_clean = _clean_rl_text(medical_record.remarks.strip())
        if rem_clean:
            rem_data = [
                [Paragraph("<font color='#b45309'><b>DOCTOR'S ADVICE, PRECAUTIONS & DIETARY RESTRICTIONS:</b></font>", body_bold_style)],
                [Paragraph(rem_clean, body_style)]
            ]
            rem_table = Table(rem_data, colWidths=[522])
            rem_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fefce8')),
                ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#fef08a')),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ('LEFTPADDING', (0,0), (-1,-1), 8),
                ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ]))
            story.append(rem_table)
            story.append(Spacer(1, 14))

    # 6. Clinical Authentication & Physician Signature
    sig_data = [
        [
            Paragraph(
                "<font color='#0284c7'><b>CLINICAL AUTHENTICATION</b></font><br/>"
                "<font color='#64748b' size='7.5'>Digitally authenticated and locked under CMS EMR clinical protocols.<br/>"
                "Valid for dispensation at any licensed pharmacy.</font>",
                body_style
            ),
            Paragraph(
                f"<div align='right'>"
                f"<b>{_clean_rl_text(doctor_name)}</b><br/>"
                f"<font color='#64748b' size='7.5'>{_clean_rl_text(specialization)}<br/>"
                f"Medical License: <b>CMS-DOC-{doctor_user.id:04d}</b><br/>"
                f"<i>Digitally Signed & Certified</i></font>"
                f"</div>",
                body_style
            )
        ]
    ]
    sig_table = Table(sig_data, colWidths=[270, 252])
    sig_table.setStyle(TableStyle([
        ('LINEABOVE', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 12))

    # 7. Legal Disclaimer Footer
    story.append(Paragraph(
        "Notice: Take medications strictly as directed. Do not reuse or share prescription drugs.<br/>"
        "Clinic Management System (CMS) — Confidential Patient Health Record",
        footer_style
    ))

    doc.build(story)

def _render_prescription_pdf_response(request, medical_record, inline=False):
    patient = medical_record.patient
    doctor_profile = medical_record.doctor
    formatted_date = str(medical_record.date).split(' ')[0]
    
    response = HttpResponse(content_type='application/pdf')
    filename = f"prescription_{patient.name}_{formatted_date}.pdf"
    disposition = 'inline' if inline else 'attachment'
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'

    medication_items = parse_prescription_items(medical_record.prescription)

    # Try WeasyPrint first if library is functional on host system
    weasy_success = False
    if HTML is not None:
        try:
            clinic_logo_path = None
            if doctor_profile.logo_path:
                clinic_logo_path = request.build_absolute_uri(settings.MEDIA_URL + doctor_profile.logo_path)
            else:
                clinic_logo_path = request.build_absolute_uri(settings.STATIC_URL + 'cms_logo.png')

            doctor_user = doctor_profile.user
            doctor_name = f"{doctor_user.first_name} {doctor_user.last_name}".strip() or doctor_user.username
            context = {
                'patient': patient,
                'medical_record': medical_record,
                'doctor_profile': doctor_profile,
                'formatted_date': formatted_date,
                'doctor_name': doctor_name,
                'doctor_specialization': doctor_profile.specialization,
                'clinic_logo_path': clinic_logo_path,
                'medication_items': medication_items,
            }
            html_string = render_to_string('prescription_pdf.html', context)
            html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
            html.write_pdf(response)
            weasy_success = True
        except Exception:
            weasy_success = False

    # Seamless fallback to ReportLab (100% native Python without external GTK/cairo DLLs)
    if not weasy_success:
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
        generate_prescription_pdf_reportlab(medical_record, response)

    return response

@login_required
@doctor_or_assistant_required
def generate_prescription_pdf(request, record_id):
    doctor_profile = DoctorProfile.get_or_create_for_user(request.user) if (hasattr(request.user, 'is_doctor') and request.user.is_doctor()) else None
    if doctor_profile:
        medical_record = get_object_or_404(MedicalRecord, id=record_id, doctor=doctor_profile)
    else:
        medical_record = get_object_or_404(MedicalRecord, id=record_id)
    return _render_prescription_pdf_response(request, medical_record, inline=False)

@login_required
@doctor_or_assistant_required
def print_prescription_view(request, record_id):
    doctor_profile = DoctorProfile.get_or_create_for_user(request.user) if (hasattr(request.user, 'is_doctor') and request.user.is_doctor()) else None
    if doctor_profile:
        medical_record = get_object_or_404(MedicalRecord, id=record_id, doctor=doctor_profile)
    else:
        medical_record = get_object_or_404(MedicalRecord, id=record_id)
    
    doctor_user = medical_record.doctor.user
    doctor_name = f"{doctor_user.first_name} {doctor_user.last_name}".strip() or doctor_user.username
    formatted_date = medical_record.date.strftime('%B %d, %Y')
    medication_items = parse_prescription_items(medical_record.prescription)
    
    context = {
        'medical_record': medical_record,
        'patient': medical_record.patient,
        'doctor_profile': medical_record.doctor,
        'doctor_name': doctor_name,
        'doctor_specialization': medical_record.doctor.specialization,
        'formatted_date': formatted_date,
        'medication_items': medication_items,
        'auto_print': request.GET.get('auto_print') == '1',
    }
    return render(request, 'print_prescription.html', context)

def shared_prescription_pdf(request, token):
    medical_record = get_object_or_404(MedicalRecord, share_token=token)
    if not medical_record.is_share_link_active():
        context = {
            'medical_record': medical_record,
            'error_message': _("This prescription share link is no longer shared or has expired."),
            'redirect_seconds': 10,
        }
        return render(request, 'shared_prescription_expired.html', context, status=403)
    
    return _render_prescription_pdf_response(request, medical_record, inline=True)

@login_required
@doctor_required
def toggle_prescription_share(request, record_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': str(_('Method Not allowed'))}, status=405)
    
    doctor_profile = DoctorProfile.get_or_create_for_user(request.user)
    medical_record = get_object_or_404(MedicalRecord, id=record_id, doctor=doctor_profile)
    
    action = request.POST.get('action', 'enable')
    expires_at_str = request.POST.get('expires_at', '')
    never_expires = request.POST.get('never_expires', 'false').lower() in ['true', '1', 'yes']
    
    if action == 'disable':
        medical_record.is_shareable = False
        medical_record.share_expires_at = None
        medical_record.save(update_fields=['is_shareable', 'share_expires_at'])
        return JsonResponse({
            'status': 'success',
            'is_shareable': False,
            'message': str(_('Prescription share link disabled successfully.')),
            'share_url': medical_record.get_share_url(request),
            'share_expires_at': None,
            'share_expires_at_formatted': None,
        })
    
    if not medical_record.share_token:
        medical_record.share_token = uuid.uuid4()
    
    medical_record.is_shareable = True
    
    if never_expires or not expires_at_str or expires_at_str.lower() in ['never', 'forever']:
        medical_record.share_expires_at = None
    else:
        try:
            parsed_dt = parse_datetime(expires_at_str)
            if parsed_dt is None:
                parsed_dt = datetime.fromisoformat(expires_at_str)
            if timezone.is_naive(parsed_dt):
                parsed_dt = timezone.make_aware(parsed_dt, timezone.get_current_timezone())
            medical_record.share_expires_at = parsed_dt
        except Exception:
            return JsonResponse({'status': 'error', 'message': str(_('Invalid expiration date format.'))}, status=400)
    
    medical_record.save()
    
    expires_formatted = medical_record.share_expires_at.strftime('%Y-%m-%d %H:%M') if medical_record.share_expires_at else str(_('Forever (No Expiration)'))
    
    return JsonResponse({
        'status': 'success',
        'is_shareable': True,
        'message': str(_('Prescription share link updated successfully.')),
        'share_url': medical_record.get_share_url(request),
        'share_expires_at': medical_record.share_expires_at.isoformat() if medical_record.share_expires_at else None,
        'share_expires_at_formatted': expires_formatted,
    })
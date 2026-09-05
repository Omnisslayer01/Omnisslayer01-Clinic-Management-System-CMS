from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import DoctorProfile, MedicalRecord, Appointments
from assistant.models import AssistantProfile
from accounts.models import User
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from accounts.decorators import doctor_required
from datetime import datetime, date, timedelta
from django.contrib import messages
from django.utils.translation import gettext_lazy as _

@login_required
@doctor_required
def dashboard(request):
    doctor_profile = DoctorProfile.get_or_create_for_user(request.user)

    number_of_patients = doctor_profile.doctor_patients.count()

    patients_records = MedicalRecord.objects.filter(doctor=doctor_profile).order_by('-date')
    
    # to get the daily average
    today = date.today()

    latest_record = patients_records.first()
    latest_update = latest_record.date if latest_record else None

    if latest_update and hasattr(latest_update, 'date'):
        latest_update = latest_update.date()

    if latest_update == today:
        latest_update = "today"
    elif latest_update == (today - timedelta(days=1)):
        latest_update = "yesterday"

    number_of_patients_records = patients_records.count()
    
    thirty_days_ago = today - timedelta(days=30)
    patients_last_30_days = doctor_profile.doctor_patients.filter(
        date_added__gte=thirty_days_ago
    ).count()

    if patients_last_30_days > 0:
        avg_patients_per_day = round(patients_last_30_days / 30, 1)
    else:
        avg_patients_per_day = 0

    todays_appointments_today = Appointments.objects.filter(doctor=doctor_profile, date=date.today()).count()

    completed = Appointments.objects.filter(doctor=doctor_profile, date=date.today(), status='completed').count()

    todays_appointments = {
        'total': todays_appointments_today,
        'completed': completed
    }

    # Get appointments and implement pagination
    appointments_list = Appointments.objects.filter(doctor=doctor_profile, date=date.today()).order_by('-date', 'start_time')
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(appointments_list, 5)  # Show 5 appointments per page
    
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    context = {
        "user_data": request.user,
        "today_date": datetime.now(),
        "number_of_patients": number_of_patients,
        "number_of_patients_records": number_of_patients_records,
        "todays_appointments": todays_appointments,
        "avg_patients_per_day": avg_patients_per_day,
        "appointments": appointments_list,
        "page_obj": page_obj,
        "latest_update":latest_update
    }
    return render(request, "doctor_dashboard.html", context)

def add_assistant(request):
    messages.info(request, _("Members and assistant management is disabled for this clinic deployment."))
    return redirect('doctor_dashboard')


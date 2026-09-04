from django.urls import path
from . import views, medical_records, patients, doctor_settings, appointments, medcare_views

urlpatterns = [
    # Dashboard & Base
    path('dashboard/', views.dashboard, name='doctor_dashboard'),
    
    # Patients Hub
    path('add-patient/', patients.add_patient, name='add_patient'),
    path('show-patients/', patients.show_patients, name='show_patients'),
    path('show-patient-details/', patients.show_patient_details, name='show_patient_details'),
    path('update-patient/', patients.update_patient, name='update_patient'),
    path('delete-patient/', patients.delete_patient, name='delete_patient'),
    path('search-patient/', patients.search_patient, name='search_patient'),
    
    # Medical Records & Prescriptions
    path('add-medical-record/', medical_records.add_medical_record, name='add_medical_record'),
    path('update-medical-record/', medical_records.update_medical_record, name='update_medical_record'),
    path('delete-medical-record/', medical_records.delete_medical_record, name='delete_medical_record'),
    path('generate-prescription-pdf/<int:record_id>/', medical_records.generate_prescription_pdf, name='generate_prescription_pdf'),
    path('prescription/share/<uuid:token>/', medical_records.shared_prescription_pdf, name='shared_prescription_pdf'),
    path('prescription/toggle-share/<int:record_id>/', medical_records.toggle_prescription_share, name='toggle_prescription_share'),

    # Profile & Settings
    path('update-doctor-profile/', doctor_settings.update_doctor_profile, name='update_doctor_profile'),
    path('upload-clinic-logo/', doctor_settings.upload_clinic_logo, name='upload_clinic_logo'),
    path('remove-clinic-logo/', doctor_settings.remove_clinic_logo, name='remove_clinic_logo'),
    path('set-appointment-times/', doctor_settings.set_appointment_times, name='set_appointment_times'),
    path('update-appointment-times/', doctor_settings.update_appointment_times, name='update_appointment_times'),
    path('deactivate-appointment-times/', doctor_settings.deactivate_appointment_times, name='deactivate_appointment_times'),
    path('add-assistant/', views.add_assistant, name='add_assistant'),

    # Legacy Appointments
    path('appointments/', appointments.appointment_list, name='appointment_list'),
    path('appointment-detail/', appointments.appointment_detail, name='appointment_detail'),
    path('schedule-appointment/', appointments.schedule_appointment, name='schedule_appointment'),
    path('get_available_times/', appointments.get_available_times, name='get_available_times'),
    path('mark-appointment-completed/', appointments.mark_appointment, name='mark_appointment'),
    path('update-appointment/', appointments.update_appointment_doctor, name='update_appointment_doctor'),
    path('delete-appointment/', appointments.delete_appointment_doctor, name='delete_appointment_doctor'),

    # =========================================================================
    # MEDCARE CLINIC / DESK.CLINIC APPLICATION FEATURES & AI WORKFLOW
    # =========================================================================
    # 1. Interactive Calendar
    path('calendar/', medcare_views.calendar_view, name='medcare_calendar'),
    path('api/calendar-events/', medcare_views.api_calendar_events, name='api_calendar_events'),
    path('api/book-slot/', medcare_views.api_book_slot, name='api_book_slot'),
    
    # 2. AI Conversational Booking & Emergency Triage
    path('api/ai-booking-agent/', medcare_views.api_ai_booking_agent, name='api_ai_booking_agent'),
    path('api/available-slots/', medcare_views.api_available_slots, name='api_available_slots'),
    
    # 3. Ambient Consultation Scribe
    path('api/ambient-scribe/', medcare_views.api_ambient_scribe, name='api_ambient_scribe'),
    
    # 4. Smart Drug Search & Prescription Save
    path('api/drug-search/', medcare_views.api_drug_search, name='api_drug_search'),
    path('api/save-prescription/', medcare_views.api_save_prescription, name='api_save_prescription'),
    
    # 5. Live Token Queue
    path('queue/', medcare_views.queue_view, name='medcare_queue'),
    path('api/call-next-token/', medcare_views.api_call_next_token, name='api_call_next_token'),
    
    # 6. Waitlist & Auto-Backfill
    path('waitlist/', medcare_views.waitlist_view, name='medcare_waitlist'),
    path('api/trigger-backfill/', medcare_views.api_trigger_backfill, name='api_trigger_backfill'),
    
    # 7. Inventory
    path('inventory/', medcare_views.inventory_view, name='medcare_inventory'),
    
    # 8. Referrals
    path('referrals/', medcare_views.referrals_view, name='medcare_referrals'),
    
    # 9. Claims
    path('claims/', medcare_views.claims_view, name='medcare_claims'),
    
    # 10. Prescriptions Hub
    path('prescriptions/', medcare_views.prescriptions_view, name='medcare_prescriptions'),
    
    # 10b. Visit Recordings
    path('visit-recordings/', medcare_views.visit_recordings_view, name='medcare_visit_recordings'),
    
    # 11. SMS Dispatch & Logs
    path('sms/', medcare_views.sms_view, name='medcare_sms'),
    
    # 12. Reports & Analytics
    path('reports/', medcare_views.reports_view, name='medcare_reports'),
    
    # 13. Labels
    path('labels/', medcare_views.labels_view, name='medcare_labels'),
    
    # 14. Leads
    path('leads/', medcare_views.leads_view, name='medcare_leads'),
    
    # 15. Settings: Locations
    path('locations/', medcare_views.locations_view, name='medcare_locations'),
    
    # 16. Settings: Billing
    path('billing/', medcare_views.billing_view, name='medcare_billing'),
    
    # 17. Settings: Audit Log
    path('audit-log/', medcare_views.audit_log_view, name='medcare_audit_log'),

    # 18. Labs Hub & Ticket Lifecycle
    path('labs/', medcare_views.labs_view, name='medcare_labs'),
    path('api/lab-status/<str:ticket_id>/', medcare_views.api_update_lab_status, name='api_update_lab_status'),

    # 19. Patient Self-Service Mobile Portal
    path('portal/<str:token>/', medcare_views.patient_portal_view, name='patient_portal_view'),
]

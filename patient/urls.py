from django.urls import path
from . import views

urlpatterns = [
    # 1. Home Dashboard
    path('', views.patient_home, name='patient_home'),

    # 2. Book Appointment
    path('book-appointment/', views.book_appointment, name='patient_book_appointment'),
    path('api/available-slots/', views.api_available_slots, name='patient_api_available_slots'),

    # 3. Find Doctors
    path('find-doctors/', views.find_doctors, name='patient_find_doctors'),

    # 4. Patients (My Records)
    path('records/', views.my_records, name='patient_my_records'),
    path('records/upload-document/', views.upload_document, name='patient_upload_document'),
    path('records/delete-document/<int:doc_id>/', views.delete_document, name='patient_delete_document'),
    path('records/add-vaccination/', views.add_vaccination, name='patient_add_vaccination'),

    # 5. Prescriptions
    path('prescriptions/', views.patient_prescriptions, name='patient_prescriptions'),
    path('prescriptions/refill/<int:record_id>/', views.request_prescription_refill, name='patient_request_refill'),

    # 6. Lab Tests
    path('lab-tests/', views.lab_tests, name='patient_lab_tests'),
    path('lab-tests/book/', views.book_lab_test, name='patient_book_lab_test'),

    # 7. Messages
    path('messages/', views.patient_messages, name='patient_messages'),

    # 8. Health Tips
    path('health-tips/', views.health_tips, name='patient_health_tips'),
    path('health-tips/like/<int:tip_id>/', views.like_health_tip, name='patient_like_health_tip'),

    # 9. Settings
    path('settings/', views.patient_settings, name='patient_settings'),
    path('settings/add-family/', views.add_family_member, name='patient_add_family_member'),
    path('settings/delete-family/<int:member_id>/', views.delete_family_member, name='patient_delete_family_member'),

    # AI Recommendation Tool Endpoint
    path('api/ai-recommend/', views.api_ai_recommend_doctor, name='patient_ai_recommend'),
]



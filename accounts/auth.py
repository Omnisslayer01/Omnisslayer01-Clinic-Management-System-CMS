#all of the auth related function
import logging
import urllib.parse
import requests
from django.shortcuts import render, redirect
from .models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_backends
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.template.loader import render_to_string
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth.tokens import default_token_generator
from django.http import HttpResponse
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.utils.translation import gettext_lazy as _
from doctor.models import DoctorProfile, Clinic

logger = logging.getLogger(__name__)

def _redirect_after_login(request, user):
    """Safely redirects an authenticated user based on their role."""
    if hasattr(user, 'is_doctor') and user.is_doctor():
        return redirect("doctor_dashboard")
    if hasattr(user, 'is_assistant') and user.is_assistant():
        return redirect("assistant_dashboard")
    if hasattr(user, 'is_clinic_admin') and (user.is_clinic_admin() or user.is_super_admin() or user.is_staff or user.is_superuser):
        return redirect("/admin/")
    if getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False):
        return redirect("/admin/")
    return redirect("landing_page")

def _send_verification_email(user, email_address=None):
    """Safely send verification email without crashing on SMTP failures."""
    recipient = email_address or getattr(user, 'email', None)
    if not recipient:
        return False
    try:
        mail_subject = 'Activate your account.'
        site_domain = getattr(settings, 'SITE_DOMAIN', 'http://localhost:8000').rstrip('/')
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        activation_path = reverse('activate', kwargs={'uidb64': uid, 'token': token})
        full_activation_url = f"{site_domain}{activation_path}"
        logger.info(f"Generated activation link for {user.username} ({recipient}): {full_activation_url}")

        message = render_to_string('activate_mail_send.html', {
            'user': user,
            'domain': site_domain,
            'uid': uid,
            'token': token,
        })
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', None) or 'webmaster@localhost'
        send_mail(mail_subject, message, from_email, [recipient], html_message=message)
        return True
    except Exception as e:
        logger.warning(f"SMTP dispatch failed for {recipient}: {e}")
        return False

#the register route
def register(request):
    if request.user.is_authenticated:
        return _redirect_after_login(request, request.user)

    if request.method == "POST":
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        user_type = request.POST.get('user_type', 'doctor')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        specialization = request.POST.get('specialization', '').strip()

        if user_type not in ['doctor', 'patient']:
            user_type = 'doctor'

        # Check if username contains '@'
        if not username:
            messages.error(request, _("Username is required."))
            return render(request, "register.html")

        if '@' in username:
            messages.error(request, _("Username cannot include @"))
            return render(request, "register.html")

        # Check if email contains '@'
        if not email or '@' not in email:
            messages.error(request, _("Please provide a valid email address."))
            return render(request, "register.html")

        if len(password) < 8:
            messages.error(request, _("Password must be at least 8 characters long."))
            return render(request, "register.html")

        # Check if username already exists (case-insensitive)
        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, _('Username already taken, please choose another one!'))
            return render(request, "register.html")

        # Check if email already exists (case-insensitive)
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, _('Email already registered, please choose another one or login!'))
            return render(request, "register.html")

        require_verification = getattr(settings, 'REQUIRE_EMAIL_VERIFICATION', False)

        # Create a new user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            email_verify=not require_verification,
            user_type=user_type,
            first_name=first_name,
            last_name=last_name
        )
        user.save()

        if user_type == 'doctor':
            if not specialization:
                specialization = 'General Practice'
            clinic_name = f"Dr. {user.get_full_name() or user.username}'s Clinic"
            clinic, _created = Clinic.objects.get_or_create(name=clinic_name)
            DoctorProfile.objects.create(
                user=user,
                specialization=specialization,
                clinic=clinic
            )

        # Send verification email
        email_sent = _send_verification_email(user, email)

        if require_verification:
            if email_sent:
                messages.success(request, _("Account created successfully! Please check your email to verify your account."))
            else:
                messages.warning(request, _("Account created! (Verification email could not be delivered; please verify via admin or contact support)."))
            return redirect("login")
        else:
            backend = get_backends()[0]
            user.backend = f'{backend.__module__}.{backend.__class__.__name__}'
            login(request, user)
            messages.success(request, _("Welcome to CMS! Your account has been created successfully."))
            return _redirect_after_login(request, user)

    return render(request, "register.html")

#the activate route
def activate(request, uidb64, token):
    try:
        # Decode the user ID
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    # Check if the token is valid
    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.email_verify = True
        user.save(update_fields=['is_active', 'email_verify'])

        # Set the backend attribute on the user
        backend = get_backends()[0]
        user.backend = f'{backend.__module__}.{backend.__class__.__name__}'

        # Log the user in
        login(request, user)
        messages.success(request, _("Thank you! Your email has been confirmed and your account is active."))
        return _redirect_after_login(request, user)
    else:
        messages.error(request, _("Activation link is invalid or has expired!"))
        return redirect('login')

#the login route
def user_login(request):
    if request.user.is_authenticated:
        return _redirect_after_login(request, request.user)

    if request.method == "POST":
        user_username_mail = request.POST.get('user_username_mail', '').strip()
        password = request.POST.get('password', '')

        if not user_username_mail or not password:
            messages.error(request, _("Please enter your username/email and password."))
            return render(request, "login.html")

        # Resolve user by username or email
        user = None
        if '@' in user_username_mail:
            existing_user = User.objects.filter(email__iexact=user_username_mail).first()
            if existing_user:
                user = authenticate(request, username=existing_user.username, password=password)
        else:
            user = authenticate(request, username=user_username_mail, password=password)

        if user is not None:
            require_verification = getattr(settings, 'REQUIRE_EMAIL_VERIFICATION', False)
            if user.email_verify or not require_verification or user.is_staff or user.is_superuser:
                if not user.email_verify:
                    user.email_verify = True
                    user.save(update_fields=['email_verify'])
                login(request, user)
                messages.success(request, _("Login successful!"))
                return _redirect_after_login(request, user)
            else:
                email_sent = _send_verification_email(user)
                messages.error(request, _("E-mail not verified!"))
                if email_sent:
                    messages.info(request, _("Please check your email to verify your account."))
                else:
                    messages.warning(request, _("Unable to send verification email via SMTP. Please contact clinic admin."))
                return redirect("login")
        else:
            messages.error(request, _("Invalid username/email or password!"))

    return render(request, "login.html")

#the logout route
@login_required
def user_logout(request):
    logout(request)
    messages.success(request, _("You have been logged out."))
    return redirect("login")

def demo_login(request):
    """Login as demo doctor account"""
    # Get or create demo account
    demo_username = "demo_doctor"
    demo_user = User.objects.filter(username=demo_username, is_demo=True).first()
    
    if not demo_user:
        
        demo_user = User.objects.create_user(
            username=demo_username,
            email="demo@clinicmanagementsystem.com",
            password="demo123456",
            first_name="Demo",
            last_name="Doctor",
            email_verify=True,
            user_type='doctor',
            is_demo=True
        )
        
        from doctor.models import Clinic, DoctorProfile
        clinic, _created = Clinic.objects.get_or_create(
            name="Demo Doctor's Clinic"
        )
        DoctorProfile.objects.create(
            user=demo_user,
            specialization="General Practice",
            clinic=clinic
        )
    
    # Log in the demo user
    backend = get_backends()[0]
    demo_user.backend = f'{backend.__module__}.{backend.__class__.__name__}'
    login(request, demo_user)
    
    messages.success(request, _("Logged in as Demo Doctor. Some features are restricted."))
    messages.info(request, _("Note: You cannot change password, email, username, or name in demo mode."))
    return redirect("doctor_dashboard")

class CustomPasswordResetView(PasswordResetView):
    template_name = 'password_reset.html'
    form_class = PasswordResetForm
    email_template_name = 'password_reset_email.html'
    html_email_template_name = 'password_reset_email.html'
    
    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, error)
        return super().form_invalid(form)

    def get_extra_email_context(self):
        context = {}
        context['domain'] = SITE_DOMAIN.replace('http://', '').replace('https://', '')
        context['site_name'] = 'CMS'
        context['protocol'] = 'https' if 'https://' in SITE_DOMAIN else 'http'
        return context

    def form_valid(self, form):
        """
        Override form_valid to handle email sending ourselves rather than 
        letting Django's built-in functionality handle it.
        """
        # Get user email
        email = form.cleaned_data["email"]
        # Get associated users
        active_users = form.get_users(email)
        
        for user in active_users:
            # Generate token and context
            context = {
                'email': email,
                'domain': SITE_DOMAIN.replace('http://', '').replace('https://', ''),
                'site_name': 'CMS',
                'protocol': 'https' if 'https://' in SITE_DOMAIN else 'http',
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'user': user,
                'token': self.token_generator.make_token(user),
            }
            
            # Render email
            subject = "Reset your CMS password"
            email_message = render_to_string(self.email_template_name, context)
            html_email = render_to_string(self.html_email_template_name, context)
            
            # Send email
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', None) or 'webmaster@localhost'
            try:
                send_mail(
                    subject,
                    email_message,
                    self.from_email or from_email,
                    [user.email],
                    html_message=html_email,
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to send password reset email to {user.email}: {e}")
            
        # Return success response
        return super().form_valid(form)
    
class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'password_reset_done.html'

class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'password_reset_confirm.html'
    form_class = SetPasswordForm

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, error)
        return super().form_invalid(form)

class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'password_reset_complete.html'


def _get_google_oauth_credentials(request=None):
    """Retrieve Google OAuth client credentials and proper redirect URI."""
    provider_config = settings.SOCIALACCOUNT_PROVIDERS.get('google', {})
    app_config = provider_config.get('APP', {})
    client_id = app_config.get('client_id') or getattr(settings, 'GOOGLE_CLIENT_ID', '')
    client_secret = app_config.get('secret') or getattr(settings, 'GOOGLE_CLIENT_SECRET', '')
    site_domain = getattr(settings, 'SITE_DOMAIN', 'http://localhost:8000').rstrip('/')
    configured_redirect_uri = provider_config.get('REDIRECT_URI') or f"{site_domain}/google/callback/"
    
    if request:
        current_host = request.get_host()
        scheme = 'https' if request.is_secure() else 'http'
        request_redirect_uri = f"{scheme}://{current_host}/google/callback/"
        # Use configured redirect URI if domain matches or if explicitly specified in settings
        return client_id, client_secret, configured_redirect_uri, request_redirect_uri
    return client_id, client_secret, configured_redirect_uri, configured_redirect_uri

def google_login(request):
    """Initiates the Google OAuth2 login flow"""
    client_id, client_secret, configured_redirect_uri, request_redirect_uri = _get_google_oauth_credentials(request)
    if not client_id:
        messages.error(request, _("Google login is not configured. Missing GOOGLE_CLIENT_ID in settings."))
        return redirect('login')

    # Prefer configured redirect URI; fallback to current request host
    redirect_uri = configured_redirect_uri or request_redirect_uri
    request.session['google_oauth_redirect_uri'] = redirect_uri

    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'access_type': 'online',
        'prompt': 'select_account',
    }
    oauth2_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return redirect(oauth2_url)

def google_callback(request):
    """Handles the callback from Google OAuth2"""
    error = request.GET.get('error')
    if error:
        error_desc = request.GET.get('error_description', error)
        messages.error(request, _(f"Google login was not completed: {error_desc}"))
        return redirect('login')

    code = request.GET.get('code')
    if not code:
        messages.error(request, _("Google login was canceled. Please try again."))
        return redirect('login')

    client_id, client_secret, configured_redirect_uri, request_redirect_uri = _get_google_oauth_credentials(request)
    redirect_uri = request.session.get('google_oauth_redirect_uri') or configured_redirect_uri or request_redirect_uri

    # Exchange code for access token
    token_url = 'https://oauth2.googleapis.com/token'
    token_payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }

    try:
        token_response = requests.post(token_url, data=token_payload, timeout=10)
        token_data = token_response.json()

        if token_response.status_code != 200 or 'access_token' not in token_data:
            err_msg = token_data.get('error_description') or token_data.get('error', 'Token exchange failed')
            logger.error(f"Google OAuth token error: {err_msg} | payload redirect_uri: {redirect_uri}")
            messages.error(request, _(f"Google authentication error: {err_msg}"))
            return redirect('login')

        # Get user info using access token
        userinfo_url = 'https://www.googleapis.com/oauth2/v3/userinfo'
        headers = {'Authorization': f'Bearer {token_data["access_token"]}'}
        userinfo_response = requests.get(userinfo_url, headers=headers, timeout=10)
        user_info = userinfo_response.json()

        email = user_info.get('email')
        if not email:
            messages.error(request, _("Unable to retrieve email from your Google account."))
            return redirect('login')

        email = email.lower().strip()
        first_name = user_info.get('given_name', '')
        last_name = user_info.get('family_name', '')
        username_candidate = email.split('@')[0]

        # Check if user already exists
        user = User.objects.filter(email__iexact=email).first()

        if user:
            # Google accounts have verified email
            if not user.email_verify:
                user.email_verify = True
                user.save(update_fields=['email_verify'])

            backend = get_backends()[0]
            user.backend = f'{backend.__module__}.{backend.__class__.__name__}'
            login(request, user)
            messages.success(request, _("Login successful!"))
            return _redirect_after_login(request, user)

        # User does not exist, prepare session data
        google_user_data = {
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
        }

        # Check if username is taken
        if User.objects.filter(username__iexact=username_candidate).exists():
            google_user_data['need_username'] = True
            request.session['google_user_info'] = google_user_data
            return render(request, 'add_username_google.html')

        google_user_data['username'] = username_candidate
        request.session['google_user_info'] = google_user_data
        return redirect('add_details_google_login')

    except requests.RequestException as e:
        logger.error(f"Google OAuth network error: {e}", exc_info=True)
        messages.error(request, _("Network error connecting to Google. Please check your internet connection and try again."))
        return redirect('login')
    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}", exc_info=True)
        messages.error(request, _(f"An unexpected error occurred during Google login: {e}"))
        return redirect('login')

def add_username_google_login(request):
    if request.method != "POST":
        return redirect('login')

    user_info = request.session.get('google_user_info')
    if not user_info:
        messages.error(request, _("Session expired. Please sign in with Google again."))
        return redirect('login')

    new_username = request.POST.get('username', '').strip()
    if not new_username:
        messages.error(request, _("Please choose a valid username."))
        return render(request, 'add_username_google.html')

    if '@' in new_username:
        messages.error(request, _("Username cannot contain '@'."))
        return render(request, 'add_username_google.html')

    # Validate username
    if User.objects.filter(username__iexact=new_username).exists():
        messages.error(request, _("Username already taken. Please choose another."))
        return render(request, 'add_username_google.html')

    # Update username in session
    user_info['username'] = new_username
    request.session['google_user_info'] = user_info
    return redirect('add_details_google_login')

def add_details_google_login(request):
    """Collects user type and role-specific details after Google login"""
    user_info = request.session.get('google_user_info')

    if not user_info:
        messages.error(request, _("Session expired. Please sign in with Google again."))
        return redirect('login')

    if request.method == "POST":
        user_type = request.POST.get('user_type', 'doctor')
        if user_type not in ['doctor', 'patient']:
            user_type = 'doctor'

        username = user_info.get('username')
        email = user_info.get('email')

        # Double check username
        if not username or User.objects.filter(username__iexact=username).exists():
            messages.error(request, _("Username already taken. Please choose another."))
            return render(request, 'add_username_google.html')

        # Double check email
        if User.objects.filter(email__iexact=email).exists():
            existing = User.objects.filter(email__iexact=email).first()
            backend = get_backends()[0]
            existing.backend = f'{backend.__module__}.{backend.__class__.__name__}'
            login(request, existing)
            request.session.pop('google_user_info', None)
            messages.success(request, _("Logged into your existing account."))
            return _redirect_after_login(request, existing)

        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=None,
            first_name=user_info.get('first_name', ''),
            last_name=user_info.get('last_name', ''),
            email_verify=True,
            user_type=user_type
        )
        user.set_unusable_password()
        user.save()

        # Create profile
        if user_type == 'doctor':
            specialization = request.POST.get('specialization', '').strip()
            if not specialization:
                specialization = 'General Practice'

            clinic_name = f"Dr. {user.get_full_name() or user.username}'s Clinic"
            clinic, _created = Clinic.objects.get_or_create(name=clinic_name)

            DoctorProfile.objects.create(
                user=user,
                specialization=specialization,
                clinic=clinic
            )

        # Clean up session
        request.session.pop('google_user_info', None)

        # Log user in
        backend = get_backends()[0]
        user.backend = f'{backend.__module__}.{backend.__class__.__name__}'
        login(request, user)

        messages.success(request, _("Account created successfully! Welcome to CMS."))
        return _redirect_after_login(request, user)

    return render(request, 'add_details_google.html', {'user_info': user_info})
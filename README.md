# Clinic Management System (CMS)

<p align="center">
  <img src="static/cms_logo.png" alt="Clinic Management System (CMS) Logo" width="220">
</p>

<p align="center">
  <strong>A Modern, Self-Hostable Medical Clinic Management System</strong>
</p>

<p align="center">
  Built with Django, TailwindCSS, React, and Docker for medical practices and healthcare providers.
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#docker-deployment">Docker</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#license">License</a>
</p>

---

## 🏥 About Clinic Management System (CMS)

**Clinic Management System (CMS)** is a comprehensive, self-hostable medical management platform designed for doctors, clinics, and healthcare practices who prioritize data privacy, operational efficiency, and complete ownership of their clinical records.

### Why Self-Host CMS?
- **Complete Data Ownership**: Keep sensitive patient health records securely on your own infrastructure.
- **Regulatory Compliance**: Retain control over medical data storage to comply with HIPAA, GDPR, and local medical data protection laws.
- **Zero Subscription Overhead**: Eliminate recurring per-seat SaaS costs.
- **Modern Clinical Experience**: Responsive, accessible interface with real-time queues, interactive dashboards, and smart prescription tooling.

---

## ✨ Features

### 👨‍⚕️ Doctor Portal (`/doctor/`)
- **Clinical Dashboard**: Real-time patient volume metrics, growth trends, appointment schedules, and quick actions.
- **Patient Explorer**: Advanced searchable registry with comprehensive medical history, consultation records, and vital trends.
- **Prescription System**: Fast medication prescribing with bilingual support (English & Arabic), dosage instructions, and duration presets.
- **Smart Queue & Token Management**: Live clinic token progression, call-in updates, and automated notifications.
- **Appointment Scheduler & Waitlist**: Dynamic slot booking, doctor availability calendar, and automated waitlist backfill triggers.
- **Medical Records & File Attachments**: Encrypted diagnostic attachments, lab requisitions, and historical case sheets.

### 👩‍💼 Assistant Portal (`/assistant/`)
- **Fast Patient Intake**: Streamlined patient registration, demographic capture, and token generation.
- **Appointment Coordination**: Booking, rescheduling, and status tracking for incoming visits.
- **Doctor Availability Tracking**: View real-time shift hours and clinician schedules.

### ⚡ Interactive UI & Frontend Engine
- **Modern React Components**: Client-side interactive islands for top header navigation, patient explorer, and dashboard widgets.
- **Dynamic Toast Engine**: Unobtrusive status alerts for appointment events, token updates, and clinical actions.
- **Theme Switcher**: Instant light/dark mode toggling with system preference detection.
- **Progressive Web App (PWA)**: Offline fallbacks and mobile-friendly layouts.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+ or Docker & Docker Compose
- Git

---

### Option 1: Docker Deployment (Recommended)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Omnisslayer01/Clinic-Management-System-CMS.git
   cd Clinic-Management-System-CMS
   ```

2. **Launch with Docker Compose**:
   ```bash
   docker compose up --build
   ```

3. **Access the application**:
   - Open your browser to `http://localhost:8000`
   - Default administrator account:
     - **Username**: `admin`
     - **Password**: `admin123`

---

### Option 2: Local Python Setup

1. **Create and activate a virtual environment**:
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\activate

   # macOS / Linux
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   ```bash
   # Copy example configuration
   copy .env.example .env     # Windows
   cp .env.example .env        # macOS / Linux
   ```

4. **Run migrations and start the server**:
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

5. **Visit** `http://127.0.0.1:8000` in your browser.

---

## 🏗️ Architecture

```text
Clinic Management System (CMS)
├── accounts/               # Authentication, user roles (Doctor, Assistant, Patient), profiles
├── doctor/                 # Clinical records, appointments, queues, prescriptions, inventory
├── assistant/              # Front-desk intake, receptionist workflows
├── cms/                    # Core Django project settings, WSGI/ASGI configuration, routing
├── static/                 # Styles, logo assets, React frontend components, icons
├── templates/              # Base layouts, landing page, error handlers, legal policies
├── docker-compose.yml      # Multi-container orchestration (Django Backend + PostgreSQL)
├── Dockerfile              # Containerized production-ready image definition
└── entrypoint.sh           # Database readiness check and automated migration runner
```

---

## ⚙️ Environment Configuration

Configuration is managed via `.env`. Key options include:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `DEBUG` | Enable debug mode for development | `True` |
| `SECRET_KEY` | Django cryptographic signing key | Configured in `.env` |
| `database_type` | Database engine (`sqlite` or `postgresql`) | `sqlite` |
| `POSTGRES_DB` | PostgreSQL database name (Docker) | `cms_db` |
| `POSTGRES_USER` | PostgreSQL username (Docker) | `cms_user` |
| `POSTGRES_PASSWORD` | PostgreSQL password (Docker) | `cms_password` |
| `SITE_DOMAIN` | Base URL used for email links and callbacks | `http://localhost:8000` |

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

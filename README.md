# Clinic Management System (CMS)

<p align="center">
  <img src="static/cms_logo.png" alt="Clinic Management System (CMS) Logo" width="180">
</p>

<p align="center">
  <strong>A Modern, Self-Hostable Medical Clinic Management System</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Django-5.2-092E20?style=flat-square&logo=django&logoColor=white" alt="Django">
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-blue?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/PostgreSQL-15-336791?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/SQLite-Supported-003B57?style=flat-square&logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/TailwindCSS-v3-38B2AC?style=flat-square&logo=tailwind-css&logoColor=white" alt="Tailwind CSS">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
</p>

<p align="center">
  <a href="#-quick-launch-options">Quick Launch</a> •
  <a href="#option-1-local-python--sqlite-fastest">Python & SQLite</a> •
  <a href="#option-2-docker-compose-full-stack-with-postgresql">Docker Compose</a> •
  <a href="#-pre-configured-accounts">Accounts & Logins</a> •
  <a href="#-google-oauth-20-setup">Google OAuth</a> •
  <a href="#-environment-configuration">Configuration</a> •
  <a href="#-troubleshooting">Troubleshooting</a>
</p>

---

## 🏥 About CMS

**Clinic Management System (CMS)** is an open-source, HIPAA/GDPR-compliant clinical practice management system designed for independent doctors, polyclinics, and healthcare providers. It provides clinical records, prescription writing, appointment scheduling, patient intake, queue token tracking, and role-based permissions.

---

## 🚀 Quick Launch Options

Choose whichever launch option fits your environment:

| Method | Database | Setup Time | Best For |
| :--- | :--- | :--- | :--- |
| **[Option 1: Local Python & SQLite](#option-1-local-python--sqlite-fastest)** | SQLite | ~2 minutes | Quick evaluation, local development, zero database installation |
| **[Option 2: Docker Compose](#option-2-docker-compose-full-stack-with-postgresql)** | PostgreSQL | ~3 minutes | Production-like environment, multi-container orchestration |
| **[Option 3: Local Python & PostgreSQL](#option-3-local-python--postgresql)** | PostgreSQL | ~4 minutes | Local development with PostgreSQL |

---

### Option 1: Local Python & SQLite (Fastest)

No external database server is required. SQLite creates a single `db.sqlite3` file automatically.

#### 1. Clone the repository:
```bash
git clone https://github.com/Omnisslayer01/Clinic-Management-System-CMS.git
cd Clinic-Management-System-CMS
```

#### 2. Create and activate a Python virtual environment:
```bash
# Windows (PowerShell / Command Prompt)
python -m venv .venv
.\.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

#### 3. Install dependencies:
```bash
pip install -r requirements.txt
```

#### 4. Create your `.env` file:
```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` and verify database type is set to `sqlite`:
```ini
database_type='sqlite'
DEBUG=True
REQUIRE_EMAIL_VERIFICATION=False
SITE_DOMAIN='http://localhost:8000'
```

#### 5. Run database migrations:
```bash
python manage.py migrate
```

#### 6. Create an administrator account:
```bash
python manage.py createsuperuser
```
*(Follow the prompts to enter a username, email, and password)*

#### 7. Start the development server:
```bash
python manage.py runserver
```

Open your browser and visit: **[http://127.0.0.1:8000](http://127.0.0.1:8000)** (or **[http://localhost:8000](http://localhost:8000)**).

---

### Option 2: Docker Compose (Full Stack with PostgreSQL)

Runs the Django application and a PostgreSQL 15 database in isolated containers with auto-migrations and healthchecks.

#### 1. Ensure Docker and Docker Compose are installed and running:
```bash
docker --version
docker compose version
```

#### 2. Clone the repository and configure `.env`:
```bash
git clone https://github.com/Omnisslayer01/Clinic-Management-System-CMS.git
cd Clinic-Management-System-CMS

# Copy the configuration
cp .env.example .env   # macOS/Linux
copy .env.example .env # Windows
```

Make sure `.env` contains:
```ini
DEBUG=True
database_type='postgresql'
DATABASE_HOST='db'
DATABASE_PORT='5432'
DATABASE_NAME='cms_db'
DATABASE_USER='cms_user'
DATABASE_PASSWORD='cms_password'
SITE_DOMAIN='http://localhost:8000'
```

#### 3. Launch the complete system:
Launch Docker in the background and in VS code terminal type: 
```bash
docker compose up --build
```
*(Add `-d` to run in background mode: `docker compose up -d --build`)*

#### 4. Access the application:
- **Web Application**: [http://localhost:8000](http://localhost:8000)
- **Django Admin**: [http://localhost:8000/admin/](http://localhost:8000/admin/)
- The container's startup script automatically sets up the default admin:
  - **Username**: `admin`
  - **Password**: `admin123`

#### 5. Stop the containers:
```bash
docker compose down
```

---

### Option 3: Local Python & PostgreSQL

If you already run a local PostgreSQL instance or have started the Postgres container:

1. **Activate virtual environment and install packages**:
   ```bash
   .\.venv\Scripts\activate      # Windows
   source .venv/bin/activate    # macOS/Linux
   pip install -r requirements.txt
   ```

2. **Configure `.env` for PostgreSQL**:
   ```ini
   database_type='postgresql'
   DATABASE_NAME='cms_db'
   DATABASE_USER='cms_user'
   DATABASE_PASSWORD='cms_password'
   DATABASE_HOST='localhost'
   DATABASE_PORT='5432'         # Or '5433' if connecting to docker postgres from host
   DEBUG=True
   REQUIRE_EMAIL_VERIFICATION=False
   ```

3. **Run migrations and launch**:
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

---

## 🔑 Pre-Configured Accounts

| Account Type | Username / Email | Password | Access URL | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Live Demo Doctor** | `demo_doctor` | `demo123456` | `/login/` | Instant login button on login page |
| **System Admin** | `admin` | `admin123` | `/admin/` | Superuser generated by entrypoint or `createsuperuser` |
| **Doctor Self-Registration** | *(Your Choice)* | *(Your Choice)* | `/register/` | Register practice name and specialization |

---

## 🌐 Google OAuth 2.0 Setup

To enable one-click "Sign in with Google":

1. Visit the **[Google Cloud Console](https://console.cloud.google.com/)**.
2. Navigate to **APIs & Services** > **Credentials**.
3. Click **Create Credentials** > **OAuth client ID** (Application Type: *Web application*).
4. Configure the following URIs:
   - **Authorized JavaScript origins**:
     - `http://localhost:8000`
     - `http://127.0.0.1:8000`
   - **Authorized redirect URIs**:
     - `http://localhost:8000/google/callback/`
     - `http://127.0.0.1:8000/google/callback/`
5. Copy your **Client ID** and **Client Secret** into `.env`:
   ```ini
   GOOGLE_CLIENT_ID='your-client-id.apps.googleusercontent.com'
   GOOGLE_CLIENT_SECRET='your-client-secret'
   ```
6. Restart the server. The "Sign in with Google" button on `/login/` and `/register/` will be active.

---

## ⚙️ Environment Configuration

All settings are configured through `.env`:

| Key | Description | Recommended (Dev) | Production |
| :--- | :--- | :--- | :--- |
| `DEBUG` | Django debug mode | `True` | `False` |
| `SECRET_KEY` | Cryptographic signing key | Any string for dev | Cryptographically secure random key |
| `SITE_DOMAIN` | Canonical domain for redirects & emails | `http://localhost:8000` | `https://yourdomain.com` |
| `REQUIRE_EMAIL_VERIFICATION` | Require email link before allowing login | `False` *(Instant login)* | `True` *(Production)* |
| `database_type` | Database engine selection | `sqlite` or `postgresql` | `postgresql` |
| `DATABASE_NAME` | Database name | `cms_db` | `cms_db` |
| `DATABASE_USER` | Database username | `cms_user` | `cms_user` |
| `DATABASE_PASSWORD` | Database password | `cms_password` | Strong password |
| `DATABASE_HOST` | Database host address | `localhost` or `db` | Database host |
| `DATABASE_PORT` | Database connection port | `5432` / `5433` | `5432` |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | Optional | Production Client ID |
| `GOOGLE_CLIENT_SECRET`| Google OAuth Client Secret | Optional | Production Client Secret |
| `MAIL_USER` | SMTP username / Gmail address | Optional | Notification email address |
| `MAIL_PASSWORD` | SMTP password / Gmail App Password | Optional | App-specific password |

---

## 🛠️ Useful Management Commands

```bash
# Verify system configuration and detect potential errors
python manage.py check

# Apply database migrations
python manage.py migrate

# Create a new superuser account
python manage.py createsuperuser

# Collect static files for production
python manage.py collectstatic --noinput

# Run automated tests
python manage.py test
```

---

## 🏗️ Architecture & Directory Structure

```text
Clinic Management System (CMS)
├── accounts/               # Auth, registration, password reset, user types & Google OAuth
├── doctor/                 # Clinical records, appointments, queues, prescriptions, settings
├── assistant/              # Receptionist & front-desk patient intake workflows
├── cms/                    # Project routing, WSGI/ASGI handlers, settings configuration
├── static/                 # CSS styles, branding assets, React islands, PWA worker
├── templates/              # Base layouts, landing page, policies, error templates
├── docker-compose.yml      # Orchestration for Django backend + PostgreSQL 15
├── Dockerfile              # Container image definition
├── entrypoint.sh           # Container entrypoint with healthcheck, migrations & auto-admin
└── requirements.txt        # Python package dependencies
```

---

## ❓ Troubleshooting

### 1. `E-mail not verified!` error upon login
- Set `REQUIRE_EMAIL_VERIFICATION=False` in your `.env` file to enable immediate login without requiring email activation during local testing.
- If you have an existing unverified user, activate it via the admin panel (`/admin/` > Users > check `Email verify`) or through the Django shell:
  ```bash
  python manage.py shell -c "from accounts.models import User; u = User.objects.get(username='YOUR_USERNAME'); u.email_verify=True; u.save()"
  ```

### 2. Google Login returns `redirect_uri_mismatch`
- Ensure the exact URL in your browser matches what is registered in the [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
- Add both `http://localhost:8000/google/callback/` and `http://127.0.0.1:8000/google/callback/` to **Authorized redirect URIs**.

### 3. Port 8000 is already in use
- Run on an alternative port:
  ```bash
  python manage.py runserver 8080
  ```
  *(Remember to update `SITE_DOMAIN='http://localhost:8080'` in `.env` if changing ports)*

### 4. PostgreSQL Connection Refused (Non-Docker)
- If you don't have PostgreSQL installed locally, switch to SQLite by setting `database_type='sqlite'` in `.env` and run `python manage.py migrate`.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

"""Flask API application."""
from src.jobs.worker import start_worker
import uuid
import json
import logging
import copy
import secrets
from functools import wraps
from src import config
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from datetime import datetime, timedelta, timezone
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from src import db
from src import crypto_utils
from src import wp_client
from src.mailer import build_reset_password_url, send_password_reset_email
from src.models import ConnectSiteRequest, GeneratePostRequest, PublishPostRequest
from src.generator.draft_builder import build_draft, build_multilang_drafts
from src.generator.text_openai import regenerate_section, REGENERATABLE_SECTIONS, regenerate_inline_selection
from src.jobs.queue import enqueue_job
from src.auth import User
from src import offline_auth

# Configure logging
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get the project root directory (parent of src/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOTSTRAP_ON_IMPORT = os.getenv(
    "APP_BOOTSTRAP_ON_IMPORT", "true").strip().lower() == "true"

app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))
app.secret_key = config.MASTER_KEY  # Use master key from config for sessions

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Log alsjeblieft in om deze pagina te bekijken.'

# Initialize Bcrypt
bcrypt = Bcrypt(app)

# Initialize offline auth fallback store
if config.OFFLINE_AUTH_REGENERATE_ON_START:
    offline_auth.regenerate_offline_auth_store(bcrypt)
else:
    offline_auth.init_offline_auth_store(bcrypt)


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    return User.get(int(user_id))


# Initialize database
if BOOTSTRAP_ON_IMPORT:
    db_ready = db.init_db()
    if db_ready and config.ADMIN_EMAILS:
        promoted_count = db.bootstrap_admin_users(config.ADMIN_EMAILS)
        if promoted_count:
            logger.info(
                f"Promoted {promoted_count} configured admin account(s) from ADMIN_EMAILS")

    # Start background worker
    if db_ready:
        start_worker()
    else:
        logger.info("Background worker not started because SQL is unavailable.")


# Helper functions
def strip_base64_from_draft(draft):
    """
    Remove base64 image data from draft to avoid MySQL packet size issues.
    Recursively removes all 'bytes_base64' keys from the draft structure.
    Keeps only image metadata (imageId, mime_type, filename).
    """
    def strip_recursive(obj):
        """Recursively remove bytes_base64 from any nested structure."""
        if isinstance(obj, dict):
            # Create new dict without bytes_base64
            result = {}
            for key, value in obj.items():
                if key == 'bytes_base64':
                    # Skip this key entirely
                    continue
                elif key in ('image', 'images', '_image'):
                    # For image fields, strip recursively and keep only metadata
                    if isinstance(value, dict):
                        result[key] = {
                            'imageId': value.get('imageId'),
                            'mime_type': value.get('mime_type'),
                            # Some use 'mime' instead of 'mime_type'
                            'mime': value.get('mime'),
                            'filename': value.get('filename'),
                            'feedbackChain': value.get('feedbackChain', []),
                            'generationNumber': value.get('generationNumber', 1)
                        }
                        # Remove None values
                        result[key] = {
                            k: v for k, v in result[key].items() if v is not None}
                    elif isinstance(value, list):
                        result[key] = [strip_recursive(item) for item in value]
                    else:
                        result[key] = value
                else:
                    result[key] = strip_recursive(value)
            return result
        elif isinstance(obj, list):
            return [strip_recursive(item) for item in obj]
        else:
            return obj

    draft_copy = copy.deepcopy(draft)
    return strip_recursive(draft_copy)


def validate_publish_draft_scheduling(draft: dict) -> None:
    """Validate and normalize scheduling fields for publish draft payloads."""
    status = draft.get("status", "publish")
    schedule_date_gmt = draft.get("scheduleDateGmt")

    if status not in ("draft", "publish", "future"):
        raise ValueError(
            "Invalid draft status. Allowed values: draft, publish, future")

    if status == "future":
        if not schedule_date_gmt:
            raise ValueError(
                "scheduleDateGmt is required when status is 'future'")

        try:
            normalized_input = schedule_date_gmt.replace("Z", "+00:00")
            parsed_datetime = datetime.fromisoformat(normalized_input)
        except ValueError:
            raise ValueError(
                "scheduleDateGmt must be a valid ISO datetime (e.g. 2026-03-09T15:30:00)")

        if parsed_datetime.tzinfo is not None:
            parsed_datetime = parsed_datetime.astimezone(
                timezone.utc).replace(tzinfo=None)

        if parsed_datetime <= datetime.utcnow():
            raise ValueError("scheduleDateGmt must be in the future")

        draft["scheduleDateGmt"] = parsed_datetime.strftime(
            "%Y-%m-%dT%H:%M:%S")
    elif schedule_date_gmt:
        draft.pop("scheduleDateGmt", None)


def admin_required(func):
    """Ensure route access is restricted to admin users."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not getattr(current_user, "is_admin", False):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Admin access required"}), 403
            flash("Je hebt geen toegang tot het admin paneel.", "error")
            return redirect(url_for('home_page'))
        return func(*args, **kwargs)
    return wrapper


def build_dashboard_quota(quota: dict) -> dict:
    """Normalize quota data for dashboard templates."""
    return {
        "blogs_limit": quota.get("blogs_monthly_limit", 0),
        "blogs_used": quota.get("blogs_used", 0),
        "blogs_remaining": max(0, quota.get("blogs_monthly_limit", 0) - quota.get("blogs_used", 0)),
        "text_regen_limit": quota.get("text_regen_monthly_limit", 0),
        "text_regen_used": quota.get("text_regen_used", 0),
        "text_regen_remaining": max(0, quota.get("text_regen_monthly_limit", 0) - quota.get("text_regen_used", 0)),
        "image_regen_limit": quota.get("image_regen_limit", 0),
        "usage_month": quota.get("usage_month"),
    }


def build_app_page_context(*, current_page: str) -> dict:
    """Build shared render context for authenticated app pages."""
    stats = db.get_user_stats(current_user.id)
    sites = db.get_user_sites(current_user.id)
    quota = db.get_user_quota(current_user.id)

    if not db.is_database_configured():
        stats = None
        sites = None
        quota = None

    context = {
        "user": current_user,
        "stats": stats,
        "sites": sites,
        "quota": build_dashboard_quota(quota) if quota else None,
        "current_page": current_page,
    }

    return context


# Authentication routes
@app.route("/")
def index():
    """Landing route that redirects to login or the authenticated home page."""
    if current_user.is_authenticated:
        return redirect(url_for('home_page'))
    return redirect(url_for('login'))


@app.route("/register", methods=["GET", "POST"])
def register():
    """User registration page."""
    if current_user.is_authenticated:
        return redirect(url_for('home_page'))

    if request.method == "POST":
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Validation
        if not username or not email or not password:
            flash('Alle velden zijn verplicht.', 'error')
            return render_template('register.html')

        if password != confirm_password:
            flash('Wachtwoorden komen niet overeen.', 'error')
            return render_template('register.html')

        if len(password) < 8:
            flash('Wachtwoord moet minimaal 8 karakters lang zijn.', 'error')
            return render_template('register.html')

        # Check if user already exists
        if db.get_user_by_username(username):
            flash('Gebruikersnaam is al in gebruik.', 'error')
            return render_template('register.html')

        if db.get_user_by_email(email):
            flash('Email is al geregistreerd.', 'error')
            return render_template('register.html')

        # Create user
        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        user_id = db.create_user(username, email, password_hash)

        flash('Account succesvol aangemaakt! Je kunt nu inloggen.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route("/login", methods=["GET", "POST"])
def login():
    """User login page."""
    if current_user.is_authenticated:
        return redirect(url_for('home_page'))

    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False) == 'on'

        if not username or not password:
            flash('Gebruikersnaam en wachtwoord zijn verplicht.', 'error')
            return render_template('login.html')

        # db helpers fall back to sqlite auth store when MySQL is unavailable.
        user_data = db.get_user_by_username(username)

        if not user_data:
            flash('Ongeldige gebruikersnaam of wachtwoord.', 'error')
            return render_template('login.html')

        # Verify password
        if not bcrypt.check_password_hash(user_data['password_hash'], password):
            flash('Ongeldige gebruikersnaam of wachtwoord.', 'error')
            return render_template('login.html')

        # Check if active
        if not user_data.get('is_active', 1):
            flash('Account is gedeactiveerd.', 'error')
            return render_template('login.html')

        # Login user
        user = User(
            id=user_data['id'],
            username=user_data['username'],
            email=user_data['email'],
            is_active=bool(user_data.get('is_active', 1)),
            is_admin=bool(user_data.get('is_admin', 0))
        )
        login_user(user, remember=remember)
        db.update_user_last_login(user.id)

        flash(f'Welkom terug, {user.username}!', 'success')

        # Redirect to next page or home page
        next_page = request.args.get('next')
        return redirect(next_page) if next_page else redirect(url_for('home_page'))

    return render_template('login.html')


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Request a password reset link by email."""
    if current_user.is_authenticated:
        return redirect(url_for("home_page"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()

        if not email:
            flash("Vul je e-mailadres in om een resetlink aan te vragen.", "error")
            return render_template("forgot_password.html", email=email)

        user = db.get_user_by_email(email)
        if user and user.get("is_active", 1):
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
                seconds=config.PASSWORD_RESET_TOKEN_TTL_SECONDS)

            try:
                created = db.create_password_reset_token(
                    user["id"], token, expires_at)
                if created:
                    reset_url = build_reset_password_url(
                        token, request.url_root)
                    mail_sent, mail_error = send_password_reset_email(
                        user["email"], reset_url)
                    if not mail_sent:
                        logger.error(
                            "Password reset mail kon niet worden verstuurd voor user_id=%s: %s",
                            user["id"],
                            mail_error,
                        )
                        db.delete_password_reset_token(token)
            except Exception as exc:
                logger.exception(
                    "Password reset aanvraag mislukt voor user_id=%s", user["id"])

        flash(
            "Als dit e-mailadres bekend is, ontvang je een reset link.",
            "info",
        )
        return redirect(url_for("login"))

    return render_template("forgot_password.html", email="")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    """Validate reset token and store a new password."""
    if current_user.is_authenticated:
        return redirect(url_for("home_page"))

    token_data = db.validate_password_reset_token(token)
    if not token_data:
        flash("Deze reset link is ongeldig of verlopen.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not new_password or not confirm_password:
            flash("Vul beide wachtwoordvelden in.", "error")
            return render_template("reset_password.html", token=token)

        if new_password != confirm_password:
            flash("Wachtwoorden komen niet overeen.", "error")
            return render_template("reset_password.html", token=token)

        if len(new_password) < 8:
            flash("Wachtwoord moet minimaal 8 karakters lang zijn.", "error")
            return render_template("reset_password.html", token=token)

        password_hash = bcrypt.generate_password_hash(
            new_password).decode("utf-8")
        updated = db.update_user_password_hash(
            token_data["user_id"], password_hash)

        if not updated:
            flash("Wachtwoord kon niet worden aangepast.", "error")
            return render_template("reset_password.html", token=token)

        db.delete_password_reset_token(token)
        flash("Je wachtwoord is aangepast. Je kunt nu inloggen.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token)


@app.route("/logout")
@login_required
def logout():
    """Logout user."""
    logout_user()
    flash('Je bent uitgelogd.', 'info')
    return redirect(url_for('login'))


@app.route("/home")
@login_required
def home_page():
    """Home page for authenticated users."""
    return render_template(
        'home.html',
        **build_app_page_context(current_page='home'),
    )


@app.route("/connect")
@login_required
def connect_page():
    """WordPress connection page."""
    return render_template(
        'connect.html',
        **build_app_page_context(current_page='connect'),
    )


@app.route("/generate")
@login_required
def generate_page():
    """Content generation page."""
    return render_template(
        'generate.html',
        **build_app_page_context(current_page='generate'),
    )


@app.route("/publish")
@login_required
def publish_page():
    """Publishing page."""
    quota = db.get_user_quota(current_user.id)
    translation_enabled = bool(
        quota.get("translation_enabled", 0)) if quota else False
    return render_template(
        'publish.html',
        translation_enabled=translation_enabled,
        **build_app_page_context(current_page='publish'),
    )


@app.route("/archive")
@login_required
def archive_page():
    """Jobs archive page."""
    return render_template(
        'archive.html',
        **build_app_page_context(current_page='archive'),
    )


@app.route("/admin", methods=["GET"])
@login_required
@admin_required
def admin_panel():
    """Admin panel for account and quota management."""
    try:
        users = db.get_admin_user_list()
        logger.info(f"Admin panel loaded: {len(users)} users found")
    except Exception as e:
        logger.error(f"Error loading admin user list: {e}", exc_info=True)
        users = []
    return render_template("admin.html", user=current_user, users=users, current_page="admin")


@app.route("/admin/users/create", methods=["POST"])
@login_required
@admin_required
def admin_create_user():
    """Create account from admin panel."""
    username = (request.form.get("username") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    is_admin = request.form.get("is_admin") == "on"

    blogs_monthly_limit = request.form.get("blogs_monthly_limit", "20")
    text_regen_monthly_limit = request.form.get(
        "text_regen_monthly_limit", "20")
    image_regen_limit = request.form.get("image_regen_limit", "3")

    if not username or not email or not password:
        flash("Gebruikersnaam, e-mail en wachtwoord zijn verplicht.", "error")
        return redirect(url_for("admin_panel"))

    if len(password) < 8:
        flash("Wachtwoord moet minimaal 8 karakters lang zijn.", "error")
        return redirect(url_for("admin_panel"))

    if db.get_user_by_username(username):
        flash("Gebruikersnaam is al in gebruik.", "error")
        return redirect(url_for("admin_panel"))

    if db.get_user_by_email(email):
        flash("E-mail is al geregistreerd.", "error")
        return redirect(url_for("admin_panel"))

    try:
        blogs_monthly_limit = max(1, int(blogs_monthly_limit))
        text_regen_monthly_limit = max(0, int(text_regen_monthly_limit))
        image_regen_limit = max(1, int(image_regen_limit))
    except ValueError:
        flash("Limieten moeten numeriek zijn.", "error")
        return redirect(url_for("admin_panel"))

    password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    user_id = db.create_user(username, email, password_hash, is_admin=is_admin)
    translation_enabled = request.form.get("translation_enabled") == "on"
    db.update_user_quota(
        user_id,
        blogs_monthly_limit=blogs_monthly_limit,
        text_regen_monthly_limit=text_regen_monthly_limit,
        image_regen_limit=image_regen_limit,
        translation_enabled=translation_enabled,
    )

    flash(f"Account {username} succesvol aangemaakt.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/users/<int:user_id>/quota", methods=["POST"])
@login_required
@admin_required
def admin_update_user_quota(user_id: int):
    """Update per-account limits from admin panel."""
    user = db.get_user_by_id(user_id)
    if not user:
        flash("Gebruiker niet gevonden.", "error")
        return redirect(url_for("admin_panel"))

    try:
        blogs_monthly_limit = max(
            1, int(request.form.get("blogs_monthly_limit", "20")))
        text_regen_monthly_limit = max(
            0, int(request.form.get("text_regen_monthly_limit", "20")))
        image_regen_limit = max(
            1, int(request.form.get("image_regen_limit", "3")))
    except ValueError:
        flash("Limieten moeten numeriek zijn.", "error")
        return redirect(url_for("admin_panel"))

    translation_enabled = request.form.get("translation_enabled") == "on"

    db.update_user_quota(
        user_id,
        blogs_monthly_limit=blogs_monthly_limit,
        text_regen_monthly_limit=text_regen_monthly_limit,
        image_regen_limit=image_regen_limit,
        translation_enabled=translation_enabled,
    )

    flash(f"Limieten bijgewerkt voor {user['username']}.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/users/<int:user_id>/password", methods=["POST"])
@login_required
@admin_required
def admin_update_user_password(user_id: int):
    """Update a user's password from the admin panel."""
    user = db.get_user_by_id(user_id)
    if not user:
        flash("Gebruiker niet gevonden.", "error")
        return redirect(url_for("admin_panel"))

    new_password = request.form.get("new_password") or ""

    if len(new_password) < 8:
        flash("Wachtwoord moet minimaal 8 karakters lang zijn.", "error")
        return redirect(url_for("admin_panel"))

    password_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
    updated = db.update_user_password_hash(user_id, password_hash)

    if not updated:
        flash("Wachtwoord kon niet worden aangepast.", "error")
        return redirect(url_for("admin_panel"))

    flash(f"Wachtwoord aangepast voor {user['username']}.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/api/admin/users", methods=["GET"])
@login_required
@admin_required
def admin_get_users_api():
    """Return user list for admin integrations."""
    return jsonify({"users": db.get_admin_user_list()}), 200


@app.route("/api/admin/users", methods=["POST"])
@login_required
@admin_required
def admin_create_user_api():
    """Create account through API."""
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    is_admin = bool(data.get("isAdmin", False))

    if not username or not email or not password:
        return jsonify({"error": "username, email en password zijn verplicht"}), 400

    if len(password) < 8:
        return jsonify({"error": "password moet minimaal 8 karakters lang zijn"}), 400

    if db.get_user_by_username(username):
        return jsonify({"error": "Gebruikersnaam is al in gebruik"}), 409

    if db.get_user_by_email(email):
        return jsonify({"error": "E-mail is al geregistreerd"}), 409

    try:
        blogs_monthly_limit = max(1, int(data.get("blogsMonthlyLimit", 20)))
        text_regen_monthly_limit = max(
            0, int(data.get("textRegenMonthlyLimit", 20)))
        image_regen_limit = max(1, int(data.get("imageRegenLimit", 3)))
    except (ValueError, TypeError):
        return jsonify({"error": "Limieten moeten numeriek zijn"}), 400

    password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    user_id = db.create_user(username, email, password_hash, is_admin=is_admin)
    translation_enabled = bool(data.get("translationEnabled", False))
    db.update_user_quota(
        user_id,
        blogs_monthly_limit=blogs_monthly_limit,
        text_regen_monthly_limit=text_regen_monthly_limit,
        image_regen_limit=image_regen_limit,
        translation_enabled=translation_enabled,
    )

    return jsonify({"ok": True, "userId": user_id}), 201


@app.route("/api/admin/users/<int:user_id>/quota", methods=["PUT"])
@login_required
@admin_required
def admin_update_user_quota_api(user_id: int):
    """Update per-account limits through API."""
    if not db.get_user_by_id(user_id):
        return jsonify({"error": "Gebruiker niet gevonden"}), 404

    data = request.get_json() or {}
    try:
        blogs_monthly_limit = max(1, int(data.get("blogsMonthlyLimit", 20)))
        text_regen_monthly_limit = max(
            0, int(data.get("textRegenMonthlyLimit", 20)))
        image_regen_limit = max(1, int(data.get("imageRegenLimit", 3)))
    except (ValueError, TypeError):
        return jsonify({"error": "Limieten moeten numeriek zijn"}), 400

    translation_enabled = bool(data.get("translationEnabled", False))

    db.update_user_quota(
        user_id,
        blogs_monthly_limit=blogs_monthly_limit,
        text_regen_monthly_limit=text_regen_monthly_limit,
        image_regen_limit=image_regen_limit,
        translation_enabled=translation_enabled,
    )
    return jsonify({"ok": True}), 200


@app.route("/api/sites", methods=["GET"])
@login_required
def get_user_sites_api():
    """Get all WordPress sites for the logged-in user."""
    try:
        if not db.is_database_configured():
            return jsonify([]), 200

        sites = db.get_user_sites(current_user.id)
        return jsonify(sites), 200
    except Exception as e:
        logger.error(f"Error fetching user sites: {e}", exc_info=True)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/sites/connect", methods=["POST"])
@login_required
def connect_site():
    """Connect to a WordPress site - MULTI-TENANT. Replaces existing site if user already has one."""
    try:
        data = request.get_json()
        req = ConnectSiteRequest(**data)

        # Check if user already has a site (limit: 1 site per account)
        existing_sites = db.get_user_sites(current_user.id)
        # Filter out temporary context sites
        real_sites = [site for site in existing_sites if site.get(
            'wp_username') != '__context_temp__']

        replaced_site = None
        if real_sites:
            # Delete all existing real sites (should be only 1, but delete all to be safe)
            deleted_count = db.delete_user_sites(current_user.id)
            replaced_site = real_sites[0]
            logger.info(
                f"User {current_user.id} replacing existing site: {replaced_site.get('wp_base_url')} - Deleted {deleted_count} site(s)")

        # Test connection
        try:
            user_info = wp_client.test_connection(
                req.wpBaseUrl,
                req.wpUsername,
                req.wpApplicationPassword
            )
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return jsonify({"ok": False, "error": f"Connection failed: {str(e)}"}), 400

        # Store site with user_id
        site_id = str(uuid.uuid4())
        encrypted_password = crypto_utils.encrypt(req.wpApplicationPassword)

        db.create_site(
            site_id=site_id,
            user_id=current_user.id,  # MULTI-TENANT: link to current user
            wp_base_url=req.wpBaseUrl,
            wp_username=req.wpUsername,
            wp_app_password_enc=encrypted_password,
            default_author_id=user_info.get("id")
        )

        response_data = {
            "siteId": site_id,
            "ok": True,
            "wpUser": {
                "id": user_info.get("id"),
                "name": user_info.get("name")
            }
        }

        if replaced_site:
            response_data["replaced"] = True
            response_data["oldSiteUrl"] = replaced_site.get("wp_base_url")

        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Error connecting site: {e}", exc_info=True)
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/posts/generate", methods=["POST"])
@login_required
def generate_post():
    """Generate blog post content - MULTI-TENANT."""
    try:
        can_generate, blog_limit_msg = db.can_generate_post(current_user.id)
        if not can_generate:
            return jsonify({"error": blog_limit_msg}), 429

        can_text_regen, text_regen_msg = db.can_regenerate_text(
            current_user.id)
        if not can_text_regen:
            return jsonify({"error": text_regen_msg}), 429

        data = request.get_json()
        req = GeneratePostRequest(**data)

        # Verify site exists AND belongs to current user
        # Note: siteId can be either a WordPress site (for publishing) or context site (for context retrieval)
        site = None
        if req.siteId:
            # Try WordPress site first
            site = db.get_site(req.siteId, user_id=current_user.id)

            # If not found, check if it's a context site (used for context retrieval only)
            if not site:
                context_site = db.get_context_site(
                    req.siteId, user_id=current_user.id)
                if not context_site:
                    return jsonify({"error": f"Site {req.siteId} not found or access denied"}), 404
                # Context site is OK for generation (used for context retrieval)
                # We'll use siteId for context bundle but not for publishing

        # Build draft(s)
        if req.multilang.enabled and len(req.multilang.languages) > 1:
            # Multi-language
            drafts = build_multilang_drafts(
                topic=req.topic,
                audience=req.audience.model_dump(),
                tone_of_voice=req.toneOfVoice.model_dump(),
                seo=req.seo.model_dump(),
                brand=req.brand.model_dump(),
                languages=req.multilang.languages,
                strategy=req.multilang.strategy,
                generate_image=req.generateImage,
                site_id=req.siteId
            )

            # Add status and schedule to each draft
            for lang, draft in drafts.items():
                draft["status"] = req.status
                if req.scheduleDateGmt:
                    draft["scheduleDateGmt"] = req.scheduleDateGmt

            db.increment_user_usage(
                current_user.id, blogs_delta=1, text_regen_delta=1)

            return jsonify({"drafts": drafts}), 200
        else:
            # Single language
            draft = build_draft(
                topic=req.topic,
                audience=req.audience.model_dump(),
                tone_of_voice=req.toneOfVoice.model_dump(),
                seo=req.seo.model_dump(),
                brand=req.brand.model_dump(),
                language=req.language,
                generate_image=req.generateImage,
                site_id=req.siteId,
                image_settings=req.imageSettings,
                user_id=current_user.id
            )

            draft["status"] = req.status
            if req.scheduleDateGmt:
                draft["scheduleDateGmt"] = req.scheduleDateGmt

            # Save draft to database for persistence (without base64 image data to avoid MySQL packet size issues)
            draft_for_db = strip_base64_from_draft(draft)
            draft_id = db.create_draft(
                user_id=current_user.id,
                site_id=req.siteId,
                draft_data=draft_for_db
            )
            logger.info(f"Draft saved to database with ID: {draft_id}")

            db.increment_user_usage(
                current_user.id, blogs_delta=1, text_regen_delta=1)

            return jsonify({"draft": draft, "draftId": draft_id}), 200

    except Exception as e:
        logger.error(f"Error generating post: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@app.route("/api/posts/text/regenerate", methods=["POST"])
@login_required
def regenerate_text_section():
    """Regenerate one section (or the full text) of an existing draft."""
    try:
        can_regen, regen_msg = db.can_regenerate_text(current_user.id)
        if not can_regen:
            return jsonify({"error": regen_msg}), 429

        data = request.get_json() or {}
        section = (data.get("section") or "").strip()
        instruction = (data.get("instruction") or "").strip()
        current_draft = data.get("currentDraft") or {}
        draft_id = data.get("draftId")
        language = (data.get("language") or "nl").strip()

        if section not in REGENERATABLE_SECTIONS:
            return jsonify({"error": f"Onbekend onderdeel '{section}'"}), 400

        if not instruction:
            return jsonify({"error": "Aanpasinstructie is verplicht"}), 400

        if not current_draft:
            # Try to load from database if draftId provided
            if draft_id:
                db_draft = db.get_draft(int(draft_id), current_user.id)
                if not db_draft:
                    return jsonify({"error": "Draft niet gevonden"}), 404
                current_draft = db_draft.get("draft_data", {})
            else:
                return jsonify({"error": "currentDraft of draftId is verplicht"}), 400

        updated = regenerate_section(
            section=section,
            instruction=instruction,
            current_draft=current_draft,
            language=language,
        )

        # Optionally persist updated fields back to the draft in the database
        if draft_id:
            try:
                db_draft = db.get_draft(int(draft_id), current_user.id)
                if db_draft:
                    merged = {**db_draft.get("draft_data", {}), **updated}
                    db.update_draft(int(draft_id), current_user.id, merged)
            except Exception as merge_err:
                logger.warning(
                    f"Could not auto-save regenerated section: {merge_err}")

        db.increment_user_usage(current_user.id, text_regen_delta=1)

        return jsonify({"ok": True, "updated": updated}), 200

    except Exception as e:
        logger.error(f"Error regenerating text section: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@app.route("/api/posts/text/regenerate-inline", methods=["POST"])
@login_required
def regenerate_text_inline():
    """Regenerate a selected text fragment based on a user instruction."""
    try:
        can_regen, regen_msg = db.can_regenerate_text(current_user.id)
        if not can_regen:
            return jsonify({"error": regen_msg}), 429

        data = request.get_json() or {}
        selected_text = (data.get("selectedText") or "").strip()
        instruction = (data.get("instruction") or "").strip()
        context_before = (data.get("contextBefore") or "")[:400]
        context_after = (data.get("contextAfter") or "")[:400]
        language = (data.get("language") or "nl").strip()

        if not selected_text:
            return jsonify({"error": "selectedText is verplicht"}), 400
        if not instruction:
            return jsonify({"error": "instruction is verplicht"}), 400

        replacement = regenerate_inline_selection(
            selected_text=selected_text,
            instruction=instruction,
            context_before=context_before,
            context_after=context_after,
            language=language,
        )

        db.increment_user_usage(current_user.id, text_regen_delta=1)
        return jsonify({"ok": True, "replacementText": replacement}), 200

    except Exception as e:
        logger.error(f"Error regenerating inline text: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@app.route("/api/image/regenerate", methods=["POST"])
@login_required
def regenerate_image():
    """Regenerate image with cumulative feedback."""
    try:
        data = request.get_json()
        parent_id = data.get('parentId')
        user_feedback = data.get('feedback', '').strip()

        if not parent_id:
            return jsonify({"error": "parentId is required"}), 400

        if not user_feedback:
            return jsonify({"error": "feedback is required"}), 400

        # Validate regeneration limit
        user_quota = db.get_user_quota(current_user.id)
        is_valid, error_msg = db.validate_regeneration_limit(
            parent_id,
            current_user.id,
            limit=user_quota.get('image_regen_limit', 3)
        )
        if not is_valid:
            return jsonify({"error": error_msg}), 400

        # Get parent generation
        parent = db.get_image_generation(parent_id, current_user.id)
        if not parent:
            return jsonify({"error": "Parent image generation not found"}), 404

        # Build cumulative feedback chain
        import json

        try:
            previous_feedback = json.loads(parent['all_feedback_json']) if parent.get(
                'all_feedback_json') else []
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(
                f"Failed to parse all_feedback_json: {e}, using empty list")
            previous_feedback = []

        all_feedback = previous_feedback + [user_feedback]

        # Parse parent settings with error handling
        topic = parent['topic']

        try:
            brand = json.loads(parent['brand_json']
                               ) if parent['brand_json'] else {}
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse brand_json: {e}")
            brand = {}

        try:
            image_settings = json.loads(
                parent['image_settings_json']) if parent['image_settings_json'] else {}
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to parse image_settings_json: {e}")
            return jsonify({"error": "Invalid image settings in parent generation"}), 500

        # Generate new image with cumulative feedback
        from src.generator.image_gemini import generate_featured_image

        logger.info(f"Regenerating image with feedback: {all_feedback}")

        image_bytes, mime_type, filename, error_msg = generate_featured_image(
            topic=topic,
            brand=brand,
            image_settings=image_settings,
            variation_index=0,
            feedback_chain=all_feedback,
            reference_image_bytes=parent.get('image_data'),
            reference_image_mime_type=parent.get('mime_type'),
        )

        if not image_bytes:
            logger.error(
                f"Image generation failed for regeneration. Topic: {topic}, Feedback: {all_feedback}")
            logger.error(f"Error from Gemini: {error_msg}")

            # Return the specific error from Gemini API
            user_error_msg = error_msg if error_msg else "Image generation failed. The prompt may be too complex or contain invalid content. Try simpler feedback."
            return jsonify({"error": user_error_msg}), 500

        # Build prompt for storage
        prompt = f"Topic: {topic}, Settings: {json.dumps(image_settings)}, Feedback: {all_feedback}"

        # Save new generation
        new_image_id = db.save_image_generation(
            user_id=current_user.id,
            topic=topic,
            image_settings=image_settings,
            prompt_used=prompt,
            image_data=image_bytes,
            mime_type=mime_type,
            filename=filename,
            brand=brand,
            parent_id=parent_id,
            user_feedback=user_feedback,
            all_feedback=all_feedback
        )

        # Get updated generation info
        new_generation = db.get_image_generation(new_image_id, current_user.id)

        # Return response
        import base64
        return jsonify({
            "imageId": new_image_id,
            "generationNumber": new_generation['generation_number'],
            "feedbackChain": all_feedback,
            "image": {
                "imageId": new_image_id,
                "bytes_base64": base64.b64encode(image_bytes).decode('utf-8'),
                "mime_type": mime_type,
                "filename": filename
            }
        }), 200

    except Exception as e:
        logger.error(f"Error regenerating image: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/sites/<site_id>/crawl", methods=["POST"])
def crawl_site(site_id: str):
    """Crawl website and generate Site DNA."""
    try:
        from context.ingest import ingest_website

        # Verify site exists
        site = db.get_site(site_id)
        if not site:
            return jsonify({"error": f"Site {site_id} not found"}), 404

        data = request.get_json() or {}
        seed_urls = data.get("seedUrls")
        max_depth = data.get("maxDepth", 3)
        max_pages = data.get("maxPages", 50)

        # Run ingest
        logger.info(f"Starting crawl for site {site_id}")
        result = ingest_website(
            site_id=site_id,
            seed_urls=seed_urls,
            max_depth=max_depth,
            max_pages=max_pages,
            user_id=site.get("user_id")  # Pass user_id from site
        )

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error crawling site: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/sites/crawl-for-context", methods=["POST"])
@login_required
def crawl_for_context():
    """Crawl a website for context without WordPress credentials - MULTI-TENANT.

    Note: Creates a context site entry. Old context sites are automatically cleaned up.
    """
    try:
        from context.ingest import ingest_website

        data = request.get_json()
        website_url = data.get("websiteUrl")

        if not website_url:
            return jsonify({"error": "websiteUrl is required"}), 400

        # Clean up old context sites (older than 30 days / 1 month)
        cleaned = db.cleanup_old_context_sites(current_user.id, days_old=30)
        if cleaned > 0:
            logger.info(
                f"Cleaned up {cleaned} old context site(s) for user {current_user.id}")

        # Normalize URL - add trailing slash if not present
        if not website_url.endswith('/'):
            website_url = website_url + '/'

        # Create a context site entry in separate table
        site_id = str(uuid.uuid4())

        # Store context site (separate from WordPress sites)
        db.create_context_site(
            site_id=site_id,
            user_id=current_user.id,
            base_url=website_url.rstrip('/')
        )

        # Run ingest with site_type='context'
        logger.info(
            f"Starting context crawl for {website_url} (context site)")
        result = ingest_website(
            site_id=site_id,
            seed_urls=[website_url],
            max_depth=data.get("maxDepth", 2),
            max_pages=data.get("maxPages", 30),
            site_type='context',  # Pass site_type to ingest
            user_id=current_user.id  # Pass user_id for multi-tenant
        )

        result["siteId"] = site_id

        # Detect JavaScript-rendered sites more accurately
        # A JS site has pages that return 200 but yield no extractable content
        # BUT: if we got SOME content from SOME pages, it's not purely JS
        pages_crawled = result.get("pages_crawled", 0)
        pages_stored = result.get("pages_stored", 0)

        # Consider it a JS site only if:
        # 1. We crawled multiple pages (at least 3)
        # 2. NONE of them had extractable content
        # 3. HTTP responses were successful (not blocked)
        is_js_site = pages_crawled >= 3 and pages_stored == 0
        result["is_js_site"] = is_js_site

        # Add warning if no pages were crawled or stored
        if pages_stored == 0:
            if is_js_site:
                result["warning"] = "JavaScript-website gedetecteerd. Deze site laadt content via JavaScript en kan niet worden gecrawld."
            elif pages_crawled == 0:
                result["warning"] = "Geen pagina's konden worden gecrawld. Controleer of de URL correct is en de website bereikbaar is."
            else:
                result["warning"] = f"Website gecrawld ({pages_crawled} pagina's), maar geen content kon worden geëxtraheerd. Mogelijk gebruikt de site ongebruikelijke HTML structuur."

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error crawling for context: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/context-sites", methods=["GET"])
@login_required
def list_context_sites():
    """Get all context sites for the current user with DNA info - MULTI-TENANT."""
    try:
        sites = db.get_user_context_sites(current_user.id)

        # Enrich with site DNA info and include legacy sites without DNA.
        result = []
        for site in sites:
            from context.site_dna import get_site_dna
            dna = get_site_dna(site["id"], user_id=current_user.id)

            result.append({
                "id": site["id"],
                "baseUrl": site["base_url"],
                "createdAt": site["created_at"].isoformat() if site["created_at"] else None,
                "brandName": dna.get("brand_name", "") if dna else "",
                "hasDna": dna is not None
            })

        return jsonify({"sites": result}), 200

    except Exception as e:
        logger.error(f"Error listing context sites: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/context-sites/<site_id>/details", methods=["GET"])
@login_required
def get_context_site_details(site_id: str):
    """Get detailed information about a context site - MULTI-TENANT."""
    try:
        # Verify site belongs to user
        site = db.get_context_site(site_id, user_id=current_user.id)
        if not site:
            return jsonify({"error": "Site not found"}), 404

        # Get page and chunk counts
        conn = db.get_db_connection()
        if conn is None:
            return jsonify({"error": "MySQL is momenteel niet beschikbaar"}), 503
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM scraped_pages 
            WHERE site_id = %s AND site_type = 'context'
        """, (site_id,))
        pages_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM page_chunks 
            WHERE site_id = %s AND site_type = 'context'
        """, (site_id,))
        chunks_count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        # Get Site DNA
        from context.site_dna import get_site_dna
        dna = get_site_dna(site_id, user_id=current_user.id)

        return jsonify({
            "id": site["id"],
            "baseUrl": site["base_url"],
            "createdAt": site["created_at"].isoformat() if site["created_at"] else None,
            "pagesCount": pages_count,
            "chunksCount": chunks_count,
            "hasDna": dna is not None,
            "brandName": dna.get("brand_name", "") if dna else ""
        }), 200

    except Exception as e:
        logger.error(f"Error getting context site details: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/debug/test-url", methods=["POST"])
def test_url():
    """Test if a URL is accessible before crawling."""
    try:
        import httpx

        data = request.get_json()
        url = data.get("url")

        if not url:
            return jsonify({"error": "url is required"}), 400

        # Try to fetch the URL
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            response = client.get(url, headers={
                "User-Agent": "BlogGenerator/1.0",
                "Accept": "text/html"
            })

        return jsonify({
            "accessible": True,
            "status_code": response.status_code,
            "final_url": str(response.url),
            "content_type": response.headers.get("content-type", ""),
            "content_length": len(response.text)
        }), 200

    except Exception as e:
        return jsonify({
            "accessible": False,
            "error": str(e)
        }), 200  # Return 200 but with accessible=false


@app.route("/api/sites/<site_id>/site-dna", methods=["GET"])
def get_site_dna_endpoint(site_id: str):
    """Get Site DNA for a site."""
    try:
        from context.site_dna import get_site_dna

        # Verify site exists
        site = db.get_site(site_id)
        if not site:
            return jsonify({"error": f"Site {site_id} not found"}), 404

        dna = get_site_dna(site_id)
        if not dna:
            return jsonify({"error": "No Site DNA found. Run /crawl first."}), 404

        return jsonify(dna), 200

    except Exception as e:
        logger.error(f"Error getting Site DNA: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/sites/<site_id>/ingest-stats", methods=["GET"])
def get_ingest_stats_endpoint(site_id: str):
    """Get ingest statistics for a site."""
    try:
        from context.ingest import get_ingest_stats

        # Verify site exists
        site = db.get_site(site_id)
        if not site:
            return jsonify({"error": f"Site {site_id} not found"}), 404

        stats = get_ingest_stats(site_id)
        return jsonify(stats), 200

    except Exception as e:
        logger.error(f"Error getting ingest stats: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/images/<int:image_id>", methods=["GET"])
@login_required
def get_image(image_id: int):
    """Get a specific image by ID with full data - MULTI-TENANT."""
    try:
        image = db.get_image_generation(image_id, current_user.id)
        if not image:
            return jsonify({"error": "Image not found or access denied"}), 404

        # Build response with base64 data
        import base64
        response_data = {
            "imageId": image['id'],
            "mime_type": image['mime_type'],
            "filename": image['filename'],
            "feedbackChain": json.loads(image['all_feedback_json']) if image.get('all_feedback_json') else [],
            "generationNumber": image['generation_number']
        }

        # Add base64 data if available
        if image.get('image_data'):
            response_data['bytes_base64'] = base64.b64encode(
                image['image_data']).decode('utf-8')

        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Error getting image: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@app.route("/api/drafts", methods=["GET"])
@login_required
def get_drafts():
    """Get all drafts for the current user - MULTI-TENANT."""
    try:
        drafts = db.get_user_drafts(current_user.id)
        return jsonify({"drafts": drafts}), 200

    except Exception as e:
        logger.error(f"Error getting drafts: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@app.route("/api/drafts/<int:draft_id>", methods=["GET"])
@login_required
def get_draft(draft_id: int):
    """Get a specific draft - MULTI-TENANT."""
    try:
        draft = db.get_draft(draft_id, current_user.id)
        if not draft:
            return jsonify({"error": "Draft not found or access denied"}), 404

        return jsonify(draft), 200

    except Exception as e:
        logger.error(f"Error getting draft: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@app.route("/api/drafts/<int:draft_id>", methods=["PUT"])
@login_required
def update_draft(draft_id: int):
    """Update a specific draft - MULTI-TENANT."""
    try:
        data = request.get_json() or {}
        draft_payload = data.get("draft", data)

        if not isinstance(draft_payload, dict):
            return jsonify({"error": "Invalid draft payload"}), 400

        draft_for_db = strip_base64_from_draft(draft_payload)
        updated = db.update_draft(draft_id, current_user.id, draft_for_db)
        if not updated:
            return jsonify({"error": "Draft not found or access denied"}), 404

        draft = db.get_draft(draft_id, current_user.id)
        return jsonify({"ok": True, "draft": draft}), 200

    except Exception as e:
        logger.error(f"Error updating draft: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@app.route("/api/drafts/<int:draft_id>", methods=["DELETE"])
@login_required
def delete_draft(draft_id: int):
    """Delete a draft - MULTI-TENANT."""
    try:
        deleted = db.delete_draft(draft_id, current_user.id)
        if not deleted:
            return jsonify({"error": "Draft not found or access denied"}), 404

        return jsonify({"ok": True, "message": "Draft deleted successfully"}), 200

    except Exception as e:
        logger.error(f"Error deleting draft: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@app.route("/api/posts/publish", methods=["POST"])
@login_required
def publish_post():
    """Publish a blog post - MULTI-TENANT."""
    try:
        data = request.get_json()
        req = PublishPostRequest(**data)

        # Verify site exists AND belongs to current user
        site = db.get_site(req.siteId, user_id=current_user.id)
        if not site:
            return jsonify({"error": f"Site {req.siteId} not found or access denied"}), 404

        # Create job for current user
        job_id = str(uuid.uuid4())
        payload = {
            "siteId": req.siteId
        }

        if req.draftId:
            payload["draftId"] = req.draftId

        if req.draft:
            validate_publish_draft_scheduling(req.draft)
            payload["draft"] = req.draft
        elif req.drafts:
            for lang_draft in req.drafts.values():
                validate_publish_draft_scheduling(lang_draft)
            payload["drafts"] = req.drafts

        # Auto-include translations when publishing a single draft
        if req.draftId and "draft" in payload and "drafts" not in payload:
            translations = db.get_draft_translations(
                req.draftId, current_user.id)
            if translations:
                # Convert single draft to multilang drafts dict
                original_lang = payload["draft"].get("language", "nl")
                drafts_dict = {original_lang: payload["draft"]}
                for t in translations:
                    t_draft = dict(t["translated"])
                    # Copy scheduling/status from original
                    t_draft["status"] = payload["draft"].get("status", "draft")
                    if payload["draft"].get("scheduleDateGmt"):
                        t_draft["scheduleDateGmt"] = payload["draft"]["scheduleDateGmt"]
                    # Attach translated image if available
                    if t.get("imageId"):
                        t_draft["image"] = {"imageId": t["imageId"]}
                    elif payload["draft"].get("image"):
                        # Fall back to original image
                        t_draft["image"] = payload["draft"]["image"]
                    drafts_dict[t["language"]] = t_draft
                # Replace single draft with multilang drafts
                del payload["draft"]
                payload["drafts"] = drafts_dict

        db.create_job(job_id, current_user.id, "publish", payload)

        if req.draftId:
            draft = db.get_draft(req.draftId, current_user.id)
            if not draft:
                return jsonify({"error": "Draft not found or access denied"}), 404

            db.mark_draft_sent_for_publish(
                req.draftId, current_user.id, job_id, req.siteId)

        enqueue_job(job_id, "publish", payload)

        return jsonify({
            "jobId": job_id,
            "status": "queued"
        }), 200

    except Exception as e:
        logger.error(f"Error creating publish job: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@app.route("/api/jobs", methods=["GET"])
@login_required
def get_jobs():
    """Get recent jobs for the current user."""
    try:
        limit = request.args.get("limit", default=50, type=int)
        limit = max(1, min(limit or 50, 200))

        jobs = db.get_user_jobs(current_user.id, limit=limit)

        # Build site name lookup for all referenced sites
        site_name_cache = {}

        response_jobs = []

        for row in jobs:
            payload = json.loads(row["payload_json"]) if row.get(
                "payload_json") else {}
            result = json.loads(row["result_json"]) if row.get(
                "result_json") else None
            error = json.loads(row["error_json"]) if row.get(
                "error_json") else None

            # Resolve site name
            site_id = payload.get("siteId")
            site_name = None
            if site_id:
                if site_id not in site_name_cache:
                    site = db.get_site(str(site_id), user_id=current_user.id)
                    site_name_cache[site_id] = site.get(
                        "wp_base_url", "") if site else None
                site_name = site_name_cache[site_id]

            # Resolve title from draft payload
            title = None
            draft_payload = payload.get("draft")
            if isinstance(draft_payload, dict):
                title = draft_payload.get("title")

            response_jobs.append({
                "jobId": row["id"],
                "type": row["type"],
                "status": row["status"],
                "payload": payload,
                "result": result,
                "error": error,
                "title": title,
                "siteName": site_name,
                "createdAt": row["created_at"].isoformat() if row.get("created_at") else None,
                "updatedAt": row["updated_at"].isoformat() if row.get("updated_at") else None,
            })

        return jsonify({"jobs": response_jobs}), 200

    except Exception as e:
        logger.error(f"Error getting jobs list: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job(job_id: str):
    """Get job status."""
    try:
        job = db.get_job(job_id)
        if not job:
            return jsonify({"error": f"Job {job_id} not found"}), 404

        steps = db.get_job_steps(job_id)

        response = {
            "jobId": job_id,
            "status": job["status"],
            "result": job.get("result"),
            "error": job.get("error"),
            "steps": [
                {
                    "step": step["step"],
                    "status": step["status"],
                    "detail": json.loads(step["detail_json"]) if step.get("detail_json") else None,
                    "ts": step["ts"]
                }
                for step in steps
            ]
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error getting job: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@app.route("/api/sites/<site_id>/dna", methods=["GET"])
@login_required
def get_site_dna_api(site_id):
    """Get Site DNA for a site - MULTI-TENANT."""
    try:
        # Check if it's a WordPress site
        site = db.get_site(site_id, user_id=current_user.id)

        if not site:
            # Check if it's a context site
            context_site = db.get_context_site(
                site_id, user_id=current_user.id)
            if not context_site:
                return jsonify({"error": f"Site {site_id} not found or access denied"}), 404

        # Get Site DNA (works for both WP and context sites)
        from src.context.site_dna import get_site_dna
        # Pass user_id for filtering
        dna = get_site_dna(site_id, user_id=current_user.id)

        if not dna:
            return jsonify({"error": "No Site DNA found for this site"}), 404

        return jsonify(dna), 200

    except Exception as e:
        logger.error(f"Error fetching Site DNA: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200


# ============================================
# TRANSLATION API ENDPOINTS
# ============================================

@app.route("/api/drafts/<int:draft_id>/translate", methods=["POST"])
@login_required
def translate_draft(draft_id: int):
    """Translate a draft to a target language."""
    try:
        # Check translation feature is enabled for this user
        quota = db.get_user_quota(current_user.id)
        if not quota.get("translation_enabled"):
            return jsonify({"error": "Vertaalfunctie is niet ingeschakeld voor dit account."}), 403

        data = request.get_json()
        language = data.get("language", "").strip().lower()
        translate_image = data.get("translateImage", True)

        supported_languages = ("en", "de", "fr", "es")
        if language not in supported_languages:
            return jsonify({"error": f"Taal '{language}' wordt momenteel niet ondersteund. Beschikbaar: {', '.join(supported_languages)}"}), 400

        # Get the original draft
        draft_record = db.get_draft(draft_id, current_user.id)
        if not draft_record:
            return jsonify({"error": "Concept niet gevonden."}), 404

        draft_data = draft_record.get("draft", {})
        if not draft_data.get("title"):
            return jsonify({"error": "Concept bevat geen titel."}), 400

        # Translate the text content
        from src.generator.translator import translate_blog
        translated = translate_blog(draft_data, language)

        # Optionally translate the image
        translated_image_id = None
        translated_image_base64 = None
        if translate_image:
            # Find the selected image from the draft
            image_data = draft_data.get("image") or draft_data.get("_image")
            if image_data and image_data.get("imageId"):
                image_gen = db.get_image_generation(
                    image_data["imageId"], current_user.id)
                if image_gen and image_gen.get("image_data"):
                    from src.generator.image_gemini import translate_image as gemini_translate_image
                    import base64

                    img_bytes, img_mime, img_filename, img_error = gemini_translate_image(
                        image_bytes=image_gen["image_data"],
                        mime_type=image_gen.get("mime_type", "image/jpeg"),
                        target_language=language,
                    )

                    if img_bytes and not img_error:
                        # Save translated image to DB
                        translated_image_id = db.save_image_generation(
                            user_id=current_user.id,
                            topic=f"translation-{language}-{draft_data.get('title', '')[:100]}",
                            image_settings={
                                "translation": True, "language": language, "source_image_id": image_data["imageId"]},
                            prompt_used=f"Translate image text to {language}",
                            image_data=img_bytes,
                            mime_type=img_mime,
                            filename=img_filename or f"translated-{language}.jpg",
                            parent_id=image_data["imageId"],
                        )
                        translated_image_base64 = base64.b64encode(
                            img_bytes).decode("utf-8")
                    elif img_error:
                        logger.warning(
                            f"Image translation failed: {img_error}")

        # Save translation to DB
        translation_id = db.create_or_update_draft_translation(
            user_id=current_user.id,
            original_draft_id=draft_id,
            language=language,
            translated_data=translated,
            image_id=translated_image_id,
        )

        response = {
            "translationId": translation_id,
            "language": language,
            "translated": translated,
        }

        if translated_image_id and translated_image_base64:
            response["translatedImage"] = {
                "imageId": translated_image_id,
                "bytes_base64": translated_image_base64,
            }

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error translating draft: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/drafts/<int:draft_id>/translations", methods=["GET"])
@login_required
def get_draft_translations(draft_id: int):
    """Get all translations for a draft."""
    try:
        translations = db.get_draft_translations(draft_id, current_user.id)
        return jsonify({"translations": translations}), 200
    except Exception as e:
        logger.error(f"Error getting translations: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/drafts/<int:draft_id>/translations/<language>", methods=["GET"])
@login_required
def get_draft_translation_api(draft_id: int, language: str):
    """Get a specific translation for a draft."""
    try:
        translation = db.get_draft_translation(
            draft_id, language, current_user.id)
        if not translation:
            return jsonify({"error": "Vertaling niet gevonden."}), 404
        return jsonify(translation), 200
    except Exception as e:
        logger.error(f"Error getting translation: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/drafts/<int:draft_id>/translations/<language>", methods=["PUT"])
@login_required
def update_draft_translation_api(draft_id: int, language: str):
    """Update a translation after user edits."""
    try:
        data = request.get_json()
        translated_data = data.get("translated")
        if not translated_data:
            return jsonify({"error": "Geen vertaaldata meegegeven."}), 400

        updated = db.update_draft_translation(
            draft_id, language, current_user.id, translated_data)
        if not updated:
            return jsonify({"error": "Vertaling niet gevonden."}), 404

        return jsonify({"ok": True}), 200
    except Exception as e:
        logger.error(f"Error updating translation: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    from src import config
    logger.info(f"Starting Flask app on {config.APP_HOST}:{config.APP_PORT}")
    app.run(host=config.APP_HOST, port=config.APP_PORT, debug=False)

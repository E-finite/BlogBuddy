"""Flask API application."""
from src.jobs.worker import start_worker
import uuid
import json
import logging
from src import config
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from datetime import datetime
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from src import db
from src import crypto_utils
from src import wp_client
from src.models import ConnectSiteRequest, GeneratePostRequest, PublishPostRequest
from src.generator.draft_builder import build_draft, build_multilang_drafts
from src.jobs.queue import enqueue_job
from src.auth import User

# Configure logging
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get the project root directory (parent of src/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    return User.get(int(user_id))


# Initialize database
db.init_db()

# Start background worker
start_worker()


# Authentication routes
@app.route("/")
def home():
    """Home page - redirect to login or dashboard."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route("/register", methods=["GET", "POST"])
def register():
    """User registration page."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

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
        return redirect(url_for('dashboard'))

    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False) == 'on'

        if not username or not password:
            flash('Gebruikersnaam en wachtwoord zijn verplicht.', 'error')
            return render_template('login.html')

        # Check user
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
            is_active=bool(user_data.get('is_active', 1))
        )
        login_user(user, remember=remember)
        db.update_user_last_login(user.id)

        flash(f'Welkom terug, {user.username}!', 'success')

        # Redirect to next page or dashboard
        next_page = request.args.get('next')
        return redirect(next_page) if next_page else redirect(url_for('dashboard'))

    return render_template('login.html')


@app.route("/logout")
@login_required
def logout():
    """Logout user."""
    logout_user()
    flash('Je bent uitgelogd.', 'info')
    return redirect(url_for('login'))


@app.route("/dashboard")
@login_required
def dashboard():
    """Dashboard page for authenticated users."""
    # Get user statistics
    stats = db.get_user_stats(current_user.id)
    sites = db.get_user_sites(current_user.id)
    recent_jobs = db.get_user_jobs(current_user.id, limit=5)

    return render_template('dashboard.html',
                           user=current_user,
                           stats=stats,
                           sites=sites,
                           recent_jobs=recent_jobs)


@app.route("/api/sites", methods=["GET"])
@login_required
def get_user_sites_api():
    """Get all WordPress sites for the logged-in user."""
    try:
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
        data = request.get_json()
        req = GeneratePostRequest(**data)

        # Verify site exists AND belongs to current user
        site = db.get_site(req.siteId, user_id=current_user.id)
        if not site:
            return jsonify({"error": f"Site {req.siteId} not found or access denied"}), 404

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
                image_settings=req.imageSettings
            )

            draft["status"] = req.status
            if req.scheduleDateGmt:
                draft["scheduleDateGmt"] = req.scheduleDateGmt

            return jsonify({"draft": draft}), 200

    except Exception as e:
        logger.error(f"Error generating post: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 400


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
            max_pages=max_pages
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
            logger.info(f"Cleaned up {cleaned} old context site(s) for user {current_user.id}")

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
            site_type='context'  # Pass site_type to ingest
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

        if req.draft:
            payload["draft"] = req.draft
        elif req.drafts:
            payload["drafts"] = req.drafts

        db.create_job(job_id, current_user.id, "publish", payload)
        enqueue_job(job_id, "publish", payload)

        return jsonify({
            "jobId": job_id,
            "status": "queued"
        }), 200

    except Exception as e:
        logger.error(f"Error creating publish job: {e}", exc_info=True)
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
            context_site = db.get_context_site(site_id, user_id=current_user.id)
            if not context_site:
                return jsonify({"error": f"Site {site_id} not found or access denied"}), 404
        
        # Get Site DNA (works for both WP and context sites)
        from src.context.site_dna import get_site_dna
        dna = get_site_dna(site_id)
        
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


@app.route("/", methods=["GET"])
def index():
    """Serve the main frontend page."""
    return render_template("index.html")


if __name__ == "__main__":
    from src import config
    logger.info(f"Starting Flask app on {config.APP_HOST}:{config.APP_PORT}")
    app.run(host=config.APP_HOST, port=config.APP_PORT, debug=False)

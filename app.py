"""Flask API application."""
from jobs.worker import start_worker
import uuid
import json
import logging
from flask import Flask, request, jsonify, render_template
from datetime import datetime
import db
import crypto_utils
import wp_client
from models import ConnectSiteRequest, GeneratePostRequest, PublishPostRequest
from generator.draft_builder import build_draft, build_multilang_drafts
from jobs.queue import enqueue_job

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize database
db.init_db()

# Start background worker
start_worker()


@app.route("/api/sites/connect", methods=["POST"])
def connect_site():
    """Connect to a WordPress site."""
    try:
        data = request.get_json()
        req = ConnectSiteRequest(**data)

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

        # Store site
        site_id = str(uuid.uuid4())
        encrypted_password = crypto_utils.encrypt(req.wpApplicationPassword)

        db.create_site(
            site_id=site_id,
            wp_base_url=req.wpBaseUrl,
            wp_username=req.wpUsername,
            wp_app_password_enc=encrypted_password,
            default_author_id=user_info.get("id")
        )

        return jsonify({
            "siteId": site_id,
            "ok": True,
            "wpUser": {
                "id": user_info.get("id"),
                "name": user_info.get("name")
            }
        }), 200

    except Exception as e:
        logger.error(f"Error connecting site: {e}", exc_info=True)
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/posts/generate", methods=["POST"])
def generate_post():
    """Generate blog post content."""
    try:
        data = request.get_json()
        req = GeneratePostRequest(**data)

        # Verify site exists
        site = db.get_site(req.siteId)
        if not site:
            return jsonify({"error": f"Site {req.siteId} not found"}), 404

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
                strategy=req.multilang.strategy
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
                language=req.language
            )

            draft["status"] = req.status
            if req.scheduleDateGmt:
                draft["scheduleDateGmt"] = req.scheduleDateGmt

            return jsonify({"draft": draft}), 200

    except Exception as e:
        logger.error(f"Error generating post: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@app.route("/api/posts/publish", methods=["POST"])
def publish_post():
    """Publish a blog post (creates a job)."""
    try:
        data = request.get_json()
        req = PublishPostRequest(**data)

        # Verify site exists
        site = db.get_site(req.siteId)
        if not site:
            return jsonify({"error": f"Site {req.siteId} not found"}), 404

        # Create job
        job_id = str(uuid.uuid4())
        payload = {
            "siteId": req.siteId
        }

        if req.draft:
            payload["draft"] = req.draft
        elif req.drafts:
            payload["drafts"] = req.drafts

        db.create_job(job_id, "publish", payload)
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


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def index():
    """Serve the main frontend page."""
    return render_template("index.html")


if __name__ == "__main__":
    import config
    logger.info(f"Starting Flask app on {config.APP_HOST}:{config.APP_PORT}")
    app.run(host=config.APP_HOST, port=config.APP_PORT, debug=False)

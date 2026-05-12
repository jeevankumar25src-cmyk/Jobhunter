"""
JobHunter AI - REST API Server
Serves job data to your website and mobile app.
Run: python api.py
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from database import init_db, get_jobs, Job

app = Flask(__name__)
CORS(app)  # Allow your website/app to call this API


@app.route("/api/jobs", methods=["GET"])
def search_jobs():
    """
    GET /api/jobs
    Query params:
      keyword     - job title or keyword
      location    - city or state
      remote      - Remote / Hybrid / On-site
      sponsorship - true / false
      category    - Big Tech / Startups / Healthcare / Finance
      page        - page number (default 1)
      per_page    - results per page (default 20)
    """
    keyword     = request.args.get("keyword", "")
    location    = request.args.get("location", "")
    remote      = request.args.get("remote", "")
    category    = request.args.get("category", "")
    page        = int(request.args.get("page", 1))
    per_page    = int(request.args.get("per_page", 20))
    sponsorship_param = request.args.get("sponsorship", "")
    sponsorship = None
    if sponsorship_param.lower() == "true":
        sponsorship = True
    elif sponsorship_param.lower() == "false":
        sponsorship = False

    result = get_jobs(
        keyword=keyword,
        location=location,
        remote=remote,
        sponsorship=sponsorship,
        category=category,
        page=page,
        per_page=per_page,
    )
    return jsonify(result)


@app.route("/api/jobs/<int:job_id>", methods=["GET"])
def get_job(job_id):
    """GET /api/jobs/123 — get full detail of one job."""
    job = Job.get_or_none(Job.id == job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    data = job.to_dict()
    data["description"] = job.description
    return jsonify(data)


@app.route("/api/stats", methods=["GET"])
def stats():
    """GET /api/stats — dashboard numbers."""
    total      = Job.select().count()
    remote     = Job.select().where(Job.remote_type.contains("Remote")).count()
    sponsored  = Job.select().where(Job.sponsorship == True).count()
    categories = {}
    for cat in ["Big Tech", "Startups", "Healthcare", "Finance"]:
        categories[cat] = Job.select().where(Job.category == cat).count()
    return jsonify({
        "total_jobs":        total,
        "remote_jobs":       remote,
        "sponsorship_jobs":  sponsored,
        "by_category":       categories,
    })


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    init_db()
    print("JobHunter AI API running on http://localhost:5000")
    print("Endpoints:")
    print("  GET /api/jobs?keyword=engineer&location=NYC&remote=Remote&sponsorship=true")
    print("  GET /api/jobs/123")
    print("  GET /api/stats")
    app.run(debug=True, host="0.0.0.0", port=5000)

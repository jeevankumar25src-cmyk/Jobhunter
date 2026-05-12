"""
JobHunter AI - REST API Server
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
from database import init_db, get_jobs, Job

app = Flask(__name__)
CORS(app)

# Initialize DB when app starts (works with gunicorn too)
init_db()

@app.route("/api/jobs", methods=["GET"])
def search_jobs():
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
        keyword=keyword, location=location, remote=remote,
        sponsorship=sponsorship, category=category,
        page=page, per_page=per_page,
    )
    return jsonify(result)

@app.route("/api/jobs/<int:job_id>", methods=["GET"])
def get_job(job_id):
    job = Job.get_or_none(Job.id == job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    data = job.to_dict()
    data["description"] = job.description
    return jsonify(data)

@app.route("/api/stats", methods=["GET"])
def stats():
    try:
        total     = Job.select().count()
        remote    = Job.select().where(Job.remote_type.contains("Remote")).count()
        sponsored = Job.select().where(Job.sponsorship == True).count()
        categories = {}
        for cat in ["Big Tech", "Startups", "Healthcare", "Finance", "Tech"]:
            categories[cat] = Job.select().where(Job.category == cat).count()
        return jsonify({
            "total_jobs": total,
            "remote_jobs": remote,
            "sponsorship_jobs": sponsored,
            "by_category": categories,
        })
    except Exception as e:
        return jsonify({"total_jobs":0,"remote_jobs":0,"sponsorship_jobs":0,"by_category":{},"error":str(e)})

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "JobHunter AI API is running!", "endpoints": ["/api/stats", "/api/jobs", "/api/health"]})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

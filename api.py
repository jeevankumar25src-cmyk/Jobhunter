"""
JobHunter AI - API v11
Instant JSearch on demand. No background threads. No timeouts.
"""
import requests, hashlib, time, os
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, request
from flask_cors import CORS
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0",
    "Accept": "application/json",
}

JSEARCH_KEY = os.getenv("JSEARCH_KEY", "8acef9867emshf21b10c7e42b5acp1cc495jsn8a75d9eeeda7")

# Separate caches
_company_cache = {"jobs": [], "time": 0}
_jsearch_cache = {}  # keyword -> {jobs, time}
COMPANY_TTL = 300
JSEARCH_TTL = 600

NON_USA = [
    "canada","ontario","toronto","vancouver","montreal","british columbia","alberta",
    "uk","united kingdom","england","london","manchester","birmingham",
    "india","bangalore","bengaluru","delhi","mumbai","hyderabad","pune","chennai","kolkata","noida","gurgaon",
    "germany","berlin","munich","frankfurt","hamburg",
    "france","paris","lyon",
    "australia","sydney","melbourne","brisbane",
    "singapore","japan","tokyo","china","beijing","shanghai",
    "brazil","mexico","ireland","dublin","netherlands","amsterdam",
    "sweden","spain","israel","poland","switzerland","denmark","finland",
    "south korea","korea","seoul","philippines","pakistan","bangladesh",
    "nigeria","kenya","south africa","egypt","uae","dubai","saudi arabia",
    "iran","iraq","russia","ukraine","vietnam","indonesia","malaysia","thailand",
    "europe","emea","apac","latam","worldwide","global",
]

def is_usa(loc):
    if not loc: return True
    l = loc.lower()
    return not any(c in l for c in NON_USA)

def detect_sponsorship(text):
    t = text.lower()
    return any(k in t for k in [
        "h1b","h-1b","sponsorship","visa sponsor","will sponsor",
        "work authorization","ead","opt","green card sponsor",
        "authorize to work","immigration"
    ])

def detect_remote(text, loc=""):
    t = (text+" "+loc).lower()
    if any(x in t for x in ["fully remote","100% remote","work from home","remote first"]): return "Remote"
    if "hybrid" in t: return "Hybrid"
    if "remote" in t: return "Remote"
    return "On-site"

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

GH = [
    ("airbnb","Airbnb","Big Tech"),("stripe","Stripe","Big Tech"),
    ("databricks","Databricks","Big Tech"),("figma","Figma","Big Tech"),
    ("reddit","Reddit","Big Tech"),("cloudflare","Cloudflare","Big Tech"),
    ("hubspot","HubSpot","Big Tech"),("datadog","Datadog","Big Tech"),
    ("mongodb","MongoDB","Big Tech"),("zoom","Zoom","Big Tech"),
    ("toast","Toast","Big Tech"),("twilio","Twilio","Big Tech"),
    ("okta","Okta","Big Tech"),("squarespace","Squarespace","Big Tech"),
    ("zendesk","Zendesk","Big Tech"),("pagerduty","PagerDuty","Big Tech"),
    ("anthropic","Anthropic","Startups"),("gusto","Gusto","Startups"),
    ("airtable","Airtable","Startups"),("webflow","Webflow","Startups"),
    ("miro","Miro","Startups"),("lattice","Lattice","Startups"),
    ("chime","Chime","Finance"),("affirm","Affirm","Finance"),
    ("robinhood","Robinhood","Finance"),("coinbase","Coinbase","Finance"),
    ("marqeta","Marqeta","Finance"),
    ("oscar","Oscar Health","Healthcare"),("springhealth","Spring Health","Healthcare"),
]

LV = [
    ("openai","OpenAI","Startups"),("notion","Notion","Startups"),
    ("rippling","Rippling","Startups"),("scale-ai","Scale AI","Startups"),
    ("mercury","Mercury","Finance"),("ramp","Ramp","Finance"),
    ("brex","Brex","Finance"),("sentry","Sentry","Big Tech"),
    ("drata","Drata","Startups"),("deel","Deel","Startups"),
]

def fetch_gh(cid, name, cat):
    jobs = []
    try:
        r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{cid}/jobs",
            params={"content":"true"}, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            for item in r.json().get("jobs",[])[:15]:
                loc = item.get("location",{}).get("name","United States")
                if not is_usa(loc): continue
                desc = BeautifulSoup(item.get("content",""),"html.parser").get_text(separator=" ")
                desc = " ".join(desc.split())[:600]
                updated = (item.get("updated_at") or now_iso())[:19]
                jobs.append({
                    "id": hashlib.md5(f"{item.get('id','')}{cid}".encode()).hexdigest()[:12],
                    "title": item.get("title",""), "company": name, "location": loc,
                    "salary": "Not listed", "job_type": "Full-time",
                    "remote_type": detect_remote(desc, loc),
                    "sponsorship": detect_sponsorship(desc),
                    "description": desc, "apply_url": item.get("absolute_url",""),
                    "category": cat, "posted_at": updated,
                })
    except: pass
    return jobs

def fetch_lv(cid, name, cat):
    jobs = []
    try:
        r = requests.get(f"https://api.lever.co/v0/postings/{cid}",
            params={"mode":"json","limit":15}, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            for item in r.json()[:15]:
                loc = item.get("categories",{}).get("location","United States")
                if not is_usa(loc): continue
                desc = " ".join(item.get("descriptionPlain","").split())[:600]
                created = item.get("createdAt",0)
                posted = datetime.fromtimestamp(created/1000,tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") if created else now_iso()
                jobs.append({
                    "id": hashlib.md5(f"{item.get('id','')}{cid}".encode()).hexdigest()[:12],
                    "title": item.get("text",""), "company": name, "location": loc,
                    "salary": "Not listed", "job_type": "Full-time",
                    "remote_type": detect_remote(desc, loc),
                    "sponsorship": detect_sponsorship(desc),
                    "description": desc, "apply_url": item.get("hostedUrl",""),
                    "category": cat, "posted_at": posted,
                })
    except: pass
    return jobs

def jsearch(keyword, category, num=10):
    """Search JSearch API for a keyword. Cached per keyword."""
    now = time.time()
    if keyword in _jsearch_cache and (now - _jsearch_cache[keyword]["time"]) < JSEARCH_TTL:
        return _jsearch_cache[keyword]["jobs"]
    jobs = []
    try:
        r = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            headers={"X-RapidAPI-Key": JSEARCH_KEY, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"},
            params={"query": f"{keyword} USA", "page":"1", "num_results":str(num),
                    "date_posted":"week", "country":"us"},
            timeout=12
        )
        if r.status_code == 200:
            for item in r.json().get("data",[]):
                if item.get("job_country","").upper() not in ["US","USA",""]: continue
                city = item.get("job_city","")
                state = item.get("job_state","")
                loc = f"{city}, {state}".strip(", ") or "United States"
                if not is_usa(loc): continue
                desc = " ".join(item.get("job_description","").split())[:600]
                mn = item.get("job_min_salary")
                mx = item.get("job_max_salary", mn)
                period = item.get("job_salary_period","YEAR")
                if mn:
                    salary = f"${mn:.0f} - ${mx:.0f}/{'hr' if period=='HOUR' else 'yr'}"
                else:
                    salary = "Not listed"
                ts = item.get("job_posted_at_timestamp")
                posted = datetime.fromtimestamp(ts,tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") if ts else now_iso()
                jobs.append({
                    "id": hashlib.md5(f"{item.get('job_id','')}{keyword}".encode()).hexdigest()[:12],
                    "title": item.get("job_title",""),
                    "company": item.get("employer_name",""),
                    "location": loc,
                    "salary": salary,
                    "job_type": item.get("job_employment_type","Full-time"),
                    "remote_type": "Remote" if item.get("job_is_remote") else detect_remote(desc, loc),
                    "sponsorship": detect_sponsorship(desc),
                    "description": desc,
                    "apply_url": item.get("job_apply_link",""),
                    "category": category,
                    "posted_at": posted,
                })
        elif r.status_code == 429:
            print("JSearch rate limit")
    except Exception as e:
        print(f"JSearch error: {e}")
    _jsearch_cache[keyword] = {"jobs": jobs, "time": now}
    return jobs

def get_company_jobs():
    now = time.time()
    if _company_cache["jobs"] and (now - _company_cache["time"]) < COMPANY_TTL:
        return _company_cache["jobs"]
    jobs = []
    companies = [("gh",)+c for c in GH] + [("lv",)+c for c in LV]
    with ThreadPoolExecutor(max_workers=10) as ex:
        def fetch(c):
            return fetch_gh(c[1],c[2],c[3]) if c[0]=="gh" else fetch_lv(c[1],c[2],c[3])
        for r in ex.map(fetch, companies):
            jobs.extend(r)
    jobs.sort(key=lambda j: j.get("posted_at",""), reverse=True)
    _company_cache["jobs"] = jobs
    _company_cache["time"] = now
    return jobs

# Map keywords to JSearch queries
KEYWORD_MAP = {
    "data analyst": ("Data Analyst", "Enterprise"),
    "business analyst": ("Business Analyst", "Enterprise"),
    ".net": (".NET Developer", "Enterprise"),
    "c#": ("C# Developer", "Enterprise"),
    "java": ("Java Developer", "Enterprise"),
    "servicenow": ("ServiceNow Developer", "Enterprise"),
    "sap": ("SAP Consultant", "Enterprise"),
    "salesforce": ("Salesforce Developer", "Enterprise"),
    "power bi": ("Power BI Developer", "Enterprise"),
    "powerbi": ("Power BI Developer", "Enterprise"),
    "sql": ("SQL Developer", "Enterprise"),
    "oracle": ("Oracle Developer", "Enterprise"),
    "etl": ("ETL Developer", "Enterprise"),
    "python": ("Python Developer", "Big Tech"),
    "react": ("React Developer", "Big Tech"),
    "angular": ("Angular Developer", "Big Tech"),
    "devops": ("DevOps Engineer", "Big Tech"),
    "cloud": ("Cloud Engineer", "Big Tech"),
    "aws": ("AWS Engineer", "Big Tech"),
    "azure": ("Azure Developer", "Big Tech"),
    "machine learning": ("Machine Learning Engineer", "Big Tech"),
    "ml": ("Machine Learning Engineer", "Big Tech"),
    "data engineer": ("Data Engineer", "Big Tech"),
    "full stack": ("Full Stack Developer", "Big Tech"),
    "node": ("Node.js Developer", "Big Tech"),
    "cybersecurity": ("Cybersecurity Analyst", "Enterprise"),
    "security": ("Security Engineer", "Enterprise"),
    "product manager": ("Product Manager", "Big Tech"),
    "ux": ("UX Designer", "Big Tech"),
    "jpmorgan": ("Software Engineer JPMorgan", "Finance"),
    "bank of america": ("Data Analyst Bank of America", "Finance"),
    "amazon": ("Software Engineer Amazon", "Big Tech"),
    "microsoft": ("Software Engineer Microsoft", "Big Tech"),
    "google": ("Software Engineer Google", "Big Tech"),
}

@app.route("/api/jobs", methods=["GET"])
def search_jobs():
    keyword  = request.args.get("keyword","").lower().strip()
    location = request.args.get("location","").lower()
    remote   = request.args.get("remote","").lower()
    category = request.args.get("category","")
    sponsor  = request.args.get("sponsorship","")
    hours    = request.args.get("hours","")
    page     = int(request.args.get("page",1))
    per_page = int(request.args.get("per_page",20))

    # Get company jobs (fast, cached)
    jobs = get_company_jobs().copy()

    # If keyword matches a JSearch query, fetch those too
    jsearch_jobs = []
    if keyword and JSEARCH_KEY:
        # Find best matching JSearch query
        for kw, (query, cat) in KEYWORD_MAP.items():
            if kw in keyword or keyword in kw:
                print(f"JSearch triggered for: {query}")
                jsearch_jobs = jsearch(query, cat, num=15)
                break
        # If no exact match, search JSearch directly with the keyword
        if not jsearch_jobs:
            jsearch_jobs = jsearch(keyword, "Enterprise", num=10)

    # Merge and dedupe
    all_jobs = jobs + jsearch_jobs
    seen, unique = set(), []
    for j in all_jobs:
        key = f"{j['title'].lower()[:25]}{j['company'].lower()[:15]}"
        if key not in seen:
            seen.add(key)
            unique.append(j)
    jobs = unique

    # Apply filters
    if keyword:
        jobs = [j for j in jobs if
                keyword in j["title"].lower() or
                keyword in j["company"].lower() or
                keyword in j["description"].lower()]
    if location:
        jobs = [j for j in jobs if location in j["location"].lower()]
    if remote:
        jobs = [j for j in jobs if remote in j["remote_type"].lower()]
    if category:
        jobs = [j for j in jobs if j["category"]==category]
    if sponsor=="true":
        jobs = [j for j in jobs if j["sponsorship"]]
    if hours:
        try:
            cutoff = time.time()-(int(hours)*3600)
            jobs = [j for j in jobs if
                    datetime.fromisoformat(j["posted_at"])
                    .replace(tzinfo=timezone.utc).timestamp()>=cutoff]
        except: pass

    jobs.sort(key=lambda j: j.get("posted_at",""), reverse=True)
    total = len(jobs)
    start = (page-1)*per_page
    return jsonify({"total":total,"page":page,"per_page":per_page,"jobs":jobs[start:start+per_page]})

@app.route("/api/stats", methods=["GET"])
def stats():
    try:
        jobs = get_company_jobs()
        cats = {c: len([j for j in jobs if j["category"]==c])
                for c in ["Big Tech","Startups","Healthcare","Finance","Enterprise"]}
        return jsonify({
            "total_jobs": len(jobs),
            "remote_jobs": len([j for j in jobs if "Remote" in j["remote_type"]]),
            "sponsorship_jobs": len([j for j in jobs if j["sponsorship"]]),
            "by_category": cats,
        })
    except Exception as e:
        return jsonify({"total_jobs":0,"remote_jobs":0,"sponsorship_jobs":0,"by_category":{},"error":str(e)})

@app.route("/api/health",methods=["GET"])
def health():
    return jsonify({"status":"ok","company_jobs":len(_company_cache["jobs"]),"jsearch":bool(JSEARCH_KEY)})

@app.route("/",methods=["GET"])
def home():
    return jsonify({"message":"JobHunter AI USA","company_jobs":len(_company_cache["jobs"])})

if __name__ == "__main__":
    app.run(debug=True,host="0.0.0.0",port=5000)

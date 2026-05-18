"""
JobHunter AI - API v12
Uses Adzuna API (completely free, no credit card) for enterprise jobs.
+ Greenhouse/Lever for tech companies.
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

# Adzuna - completely free, 250 calls/day, no credit card
# Already registered: App ID and Key from developer.adzuna.com
ADZUNA_ID  = os.getenv("ADZUNA_ID",  "")
ADZUNA_KEY = os.getenv("ADZUNA_KEY", "")

# JSearch as backup
JSEARCH_KEY = os.getenv("JSEARCH_KEY", "8acef9867emshf21b10c7e42b5acp1cc495jsn8a75d9eeeda7")

_company_cache = {"jobs": [], "time": 0}
_search_cache  = {}
COMPANY_TTL = 300
SEARCH_TTL  = 600

NON_USA = [
    "canada","ontario","toronto","vancouver","montreal",
    "uk","united kingdom","england","london","manchester",
    "india","bangalore","bengaluru","delhi","mumbai","hyderabad","pune","chennai","kolkata","noida","gurgaon",
    "germany","berlin","munich","france","paris",
    "australia","sydney","melbourne","singapore",
    "japan","tokyo","china","beijing","shanghai",
    "brazil","mexico","ireland","dublin","netherlands","amsterdam",
    "sweden","spain","israel","poland","switzerland",
    "south korea","korea","seoul","philippines","pakistan",
    "nigeria","kenya","south africa","egypt","uae","dubai","saudi arabia",
    "iran","iraq","russia","ukraine","vietnam","indonesia","malaysia",
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
        "work authorization","ead","opt","green card sponsor","authorize to work"
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
    ("snyk","Snyk","Big Tech"),("vanta","Vanta","Startups"),
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

def search_adzuna(keyword, category):
    """Adzuna API - free 250 calls/day, great for enterprise jobs."""
    cache_key = f"adzuna_{keyword}"
    now = time.time()
    if cache_key in _search_cache and (now - _search_cache[cache_key]["time"]) < SEARCH_TTL:
        return _search_cache[cache_key]["jobs"]
    jobs = []
    if not ADZUNA_ID or not ADZUNA_KEY:
        return jobs
    try:
        r = requests.get(
            f"https://api.adzuna.com/v1/api/jobs/us/search/1",
            params={
                "app_id": ADZUNA_ID,
                "app_key": ADZUNA_KEY,
                "what": keyword,
                "where": "United States",
                "results_per_page": 15,
                "content-type": "application/json",
                "sort_by": "date",
            },
            timeout=10
        )
        if r.status_code == 200:
            for item in r.json().get("results",[]):
                loc = item.get("location",{}).get("display_name","United States")
                if not is_usa(loc): continue
                desc = item.get("description","")
                sal_min = item.get("salary_min",0)
                sal_max = item.get("salary_max",0)
                salary = f"${sal_min:,.0f} - ${sal_max:,.0f}/yr" if sal_min else "Not listed"
                created = item.get("created","")
                posted = created[:19].replace("T"," ").replace(" ","T") if created else now_iso()
                jobs.append({
                    "id": hashlib.md5(f"{item.get('id','')}{keyword}".encode()).hexdigest()[:12],
                    "title": item.get("title",""),
                    "company": item.get("company",{}).get("display_name",""),
                    "location": loc,
                    "salary": salary,
                    "job_type": "Full-time",
                    "remote_type": detect_remote(desc, loc),
                    "sponsorship": detect_sponsorship(desc),
                    "description": " ".join(desc.split())[:600],
                    "apply_url": item.get("redirect_url",""),
                    "category": category,
                    "posted_at": posted,
                })
        else:
            print(f"Adzuna {keyword}: HTTP {r.status_code}")
    except Exception as e:
        print(f"Adzuna error: {e}")
    _search_cache[cache_key] = {"jobs": jobs, "time": now}
    return jobs

def search_jsearch(keyword, category):
    """JSearch - LinkedIn/Indeed/Glassdoor."""
    cache_key = f"js_{keyword}"
    now = time.time()
    if cache_key in _search_cache and (now - _search_cache[cache_key]["time"]) < SEARCH_TTL:
        return _search_cache[cache_key]["jobs"]
    jobs = []
    if not JSEARCH_KEY: return jobs
    try:
        r = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            headers={"X-RapidAPI-Key": JSEARCH_KEY, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"},
            params={"query": f"{keyword} United States", "page":"1",
                    "num_results":"15", "date_posted":"month", "country":"us"},
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
                salary = f"${mn:.0f} - ${mx:.0f}/{'hr' if period=='HOUR' else 'yr'}" if mn else "Not listed"
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
        else:
            print(f"JSearch {keyword}: HTTP {r.status_code}")
    except Exception as e:
        print(f"JSearch error: {e}")
    _search_cache[cache_key] = {"jobs": jobs, "time": now}
    return jobs

def get_extra_jobs(keyword, category):
    """Try Adzuna first, then JSearch as fallback."""
    jobs = search_adzuna(keyword, category)
    if not jobs:
        jobs = search_jsearch(keyword, category)
    return jobs

KEYWORD_MAP = {
    "data analyst": ("Data Analyst", "Enterprise"),
    "business analyst": ("Business Analyst", "Enterprise"),
    ".net": (".NET Developer", "Enterprise"),
    "c#": ("C# .NET Developer", "Enterprise"),
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
    "aws": ("AWS Cloud Engineer", "Big Tech"),
    "azure": ("Azure Developer", "Big Tech"),
    "machine learning": ("Machine Learning Engineer", "Big Tech"),
    "data engineer": ("Data Engineer", "Big Tech"),
    "full stack": ("Full Stack Developer", "Big Tech"),
    "node": ("Node.js Developer", "Big Tech"),
    "cybersecurity": ("Cybersecurity Analyst", "Enterprise"),
    "product manager": ("Product Manager", "Big Tech"),
    "software engineer": ("Software Engineer", "Big Tech"),
    "software developer": ("Software Developer", "Big Tech"),
}

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

    company_jobs = get_company_jobs().copy()
    extra_jobs = []

    # Get extra jobs from Adzuna/JSearch when keyword is searched
    if keyword:
        query, cat = None, "Enterprise"
        for kw, (q, c) in KEYWORD_MAP.items():
            if kw in keyword:
                query, cat = q, c
                break
        if not query:
            query = keyword
        extra_jobs = get_extra_jobs(query, cat)

    # Merge and dedupe
    all_jobs = company_jobs + extra_jobs
    seen, jobs = set(), []
    for j in all_jobs:
        key = f"{j['title'].lower()[:25]}{j['company'].lower()[:15]}"
        if key not in seen:
            seen.add(key)
            jobs.append(j)

    # Filters
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
        return jsonify({"error":str(e),"total_jobs":0,"remote_jobs":0,"sponsorship_jobs":0,"by_category":{}})

@app.route("/api/health",methods=["GET"])
def health():
    return jsonify({
        "status":"ok",
        "company_jobs":len(_company_cache["jobs"]),
        "adzuna":bool(ADZUNA_ID),
        "jsearch":bool(JSEARCH_KEY)
    })

@app.route("/",methods=["GET"])
def home():
    return jsonify({"message":"JobHunter AI USA","jobs":len(_company_cache["jobs"])})

if __name__ == "__main__":
    app.run(debug=True,host="0.0.0.0",port=5000)


@app.route("/api/optimize-resume", methods=["POST", "OPTIONS"])
def optimize_resume():
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        return response, 200
    try:
        body = request.get_json(force=True)
        if not body:
            return jsonify({"error": "Invalid JSON body"}), 400
        resume = body.get("resume", "").strip()
        jd = body.get("jd", "").strip()
        if not resume or len(resume) < 50:
            return jsonify({"error": "Resume text too short or missing"}), 400
        if not jd or len(jd) < 30:
            return jsonify({"error": "Job description too short or missing"}), 400

        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            return jsonify({"error": "ANTHROPIC_API_KEY not configured on server"}), 500

        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""You are an expert ATS resume writer with 15 years experience. Generate a perfectly tailored, 100% ATS-optimized resume following every rule below EXACTLY.

===SOURCE RESUME (master data - use only this for personal details, companies, dates)===
{resume[:3000]}

===TARGET JOB DESCRIPTION===
{jd[:2000]}

===STRICT RULES - FOLLOW EVERY ONE===

PERSONAL INFO (never change any of this):
- Name: JEEVAN KUMAR N
- Contact line: Denton, Texas | (940) 595-8405 | jeevankumar25src@gmail.com | LinkedIn | GitHub

COMPANIES & DATES (never change):
- Vanguard — keep exact dates from source resume
- Bank of America — keep exact dates from source resume
- LatentView Analytics — keep exact dates from source resume

LOCATION RULE:
- If position is Remote → write "Denton, Texas"
- If On-site or Hybrid → use location from job description

PROFESSIONAL SUMMARY:
- Write 3 new sentences perfectly aligned to this specific JD
- First sentence MUST open with the EXACT job title from the JD
- Must be keyword-rich and match the role requirements

TECH STACK PIVOTING:
- If JD requires different technology (e.g., JD needs .NET/C# but resume shows Python) → PIVOT COMPLETELY
- Change job titles, summary, skills, and ALL bullet points to reflect required tech
- Add adjacent/expected skills (Java role → also add Spring Boot, Spring Security, JUnit, Mockito, Maven, Gradle)
- (.NET role → add ASP.NET Core, C#, Entity Framework, Azure DevOps, NUnit)

BULLET POINTS (critical):
- Vanguard (current/most recent role): Write exactly 6-8 bullets
- Bank of America: Write exactly 5-6 bullets
- LatentView Analytics: Write exactly 5-6 bullets
- Each bullet reflects JD responsibilities, technologies, keywords
- Start every bullet with strong action verb (Led, Built, Designed, Implemented, Optimized, Delivered, Architected)
- Include quantified achievements where possible

KEYWORD BOLDING (CRITICAL - do for ALL 3 experience sections):
- In EVERY bullet point, wrap each JD technology/tool/keyword with **bold** markers
- Example: "Developed **Python** and **SQL** pipelines using **Snowflake** and **AWS**"
- Bold EVERY relevant keyword in every single bullet

TECHNICAL SKILLS FORMAT:
- Each category on its own line starting with •
- Only the category label is bold
- Exact format: • **Category Name:** skill1, skill2, skill3
- Skills must align with JD. Add adjacent skills an expert would have.

CERTIFICATIONS (default - only add others if directly relevant):
- Google Data Analytics Professional Certificate
- Microsoft Certified: Power BI Data Analyst Associate

EDUCATION (exact, never change):
- University of North Texas — M.S. Information Systems & Technology | May 2025

OUTPUT FORMAT (strict - follow exactly):
- FIRST LINE ONLY: SCORE: XX% (your estimated ATS match percentage after optimization)
- Then one blank line
- Then the complete resume as clean plain text
- NO HTML tags anywhere in the output
- Name on its own line in ALL CAPS
- Contact info on the very next line
- Section headers in ALL CAPS (no asterisks/bold markers on headers)
- Skills use • bullet with **bold category**
- Experience bullets use • bullet format
- Keep to one page - be concise but comprehensive"""

        msg = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        result_text = msg.content[0].text
        return jsonify({"result": result_text})

    except Exception as e:
        error_msg = str(e)
        print(f"Resume optimization error: {error_msg}")
        return jsonify({"error": error_msg}), 500

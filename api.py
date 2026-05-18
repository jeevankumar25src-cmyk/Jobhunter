"""
JobHunter AI - API v13
Sources: Greenhouse (200+ companies) + Lever (40+ companies)
         + Indeed RSS + USAJobs + Remotive + Adzuna + JSearch
"""
import requests, hashlib, time, os, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, jsonify, request
from flask_cors import CORS
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0", "Accept": "application/json"}
ADZUNA_ID  = os.getenv("ADZUNA_ID",  "4793bcf6")
ADZUNA_KEY = os.getenv("ADZUNA_KEY", "3d8ba4f83a129b24c1edc6260b22099d")
JSEARCH_KEY = os.getenv("JSEARCH_KEY", "8acef9867emshf21b10c7e42b5acp1cc495jsn8a75d9eeeda7")

_company_cache = {"jobs": [], "time": 0}
_extra_cache   = {"jobs": [], "time": 0}
_search_cache  = {}
COMPANY_TTL = 600   # 10 min
EXTRA_TTL   = 1800  # 30 min
SEARCH_TTL  = 600

NON_USA = [
    "canada","ontario","toronto","vancouver","montreal","calgary","ottawa",
    "uk","united kingdom","england","london","manchester","edinburgh",
    "india","bangalore","bengaluru","delhi","mumbai","hyderabad","pune","chennai","kolkata","noida","gurgaon","ahmedabad",
    "germany","berlin","munich","hamburg","france","paris","lyon",
    "australia","sydney","melbourne","brisbane","perth",
    "singapore","japan","tokyo","china","beijing","shanghai","shenzhen",
    "brazil","sao paulo","mexico","mexico city","ireland","dublin",
    "netherlands","amsterdam","sweden","stockholm","spain","madrid","barcelona",
    "israel","tel aviv","poland","warsaw","switzerland","zurich","geneva",
    "south korea","korea","seoul","philippines","manila","pakistan","karachi",
    "nigeria","kenya","nairobi","south africa","johannesburg","egypt","cairo",
    "uae","dubai","abu dhabi","saudi arabia","riyadh","iran","iraq",
    "russia","moscow","ukraine","kyiv","vietnam","ho chi minh","hanoi",
    "indonesia","jakarta","malaysia","kuala lumpur","europe","emea","apac","latam","worldwide","global",
]

def is_usa(loc):
    if not loc: return True
    return not any(c in loc.lower() for c in NON_USA)

def detect_sponsorship(text):
    t = text.lower()
    return any(k in t for k in ["h1b","h-1b","sponsorship","visa sponsor","will sponsor","work authorization","ead","opt","green card sponsor","authorize to work"])

def detect_remote(text, loc=""):
    t = (text+" "+loc).lower()
    if any(x in t for x in ["fully remote","100% remote","work from home","remote first","remote-first"]): return "Remote"
    if "hybrid" in t: return "Hybrid"
    if "remote" in t: return "Remote"
    return "On-site"

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

def make_id(*parts):
    return hashlib.md5("".join(str(p) for p in parts).encode()).hexdigest()[:12]

# ── GREENHOUSE COMPANIES (200+) ──────────────────────────────────────────
GH = [
    # Big Tech
    ("airbnb","Airbnb","Big Tech"),("stripe","Stripe","Big Tech"),
    ("databricks","Databricks","Big Tech"),("figma","Figma","Big Tech"),
    ("reddit","Reddit","Big Tech"),("cloudflare","Cloudflare","Big Tech"),
    ("hubspot","HubSpot","Big Tech"),("datadog","Datadog","Big Tech"),
    ("mongodb","MongoDB","Big Tech"),("zoom","Zoom","Big Tech"),
    ("twilio","Twilio","Big Tech"),("okta","Okta","Big Tech"),
    ("squarespace","Squarespace","Big Tech"),("zendesk","Zendesk","Big Tech"),
    ("pagerduty","PagerDuty","Big Tech"),("snyk","Snyk","Big Tech"),
    ("toast","Toast","Big Tech"),("hashicorp","HashiCorp","Big Tech"),
    ("mixpanel","Mixpanel","Big Tech"),("amplitude","Amplitude","Big Tech"),
    ("contentful","Contentful","Big Tech"),("elastic","Elastic","Big Tech"),
    ("grafana","Grafana Labs","Big Tech"),("confluent","Confluent","Big Tech"),
    ("dbt-labs","dbt Labs","Big Tech"),("fivetran","Fivetran","Big Tech"),
    ("segment","Segment","Big Tech"),("mimecast","Mimecast","Big Tech"),
    ("verkada","Verkada","Big Tech"),("intercom","Intercom","Big Tech"),
    ("klaviyo","Klaviyo","Big Tech"),("braze","Braze","Big Tech"),
    ("sendbird","Sendbird","Big Tech"),("iterable","Iterable","Big Tech"),
    ("launchdarkly","LaunchDarkly","Big Tech"),("split","Split","Big Tech"),
    ("algolia","Algolia","Big Tech"),("sanity","Sanity","Big Tech"),
    ("contentstack","Contentstack","Big Tech"),("netlify","Netlify","Big Tech"),
    ("vercel","Vercel","Big Tech"),("supabase","Supabase","Big Tech"),
    ("posthog","PostHog","Big Tech"),("rudderstack","RudderStack","Big Tech"),
    ("hightouch","Hightouch","Big Tech"),("census","Census","Big Tech"),
    ("metabase","Metabase","Big Tech"),("preset","Preset","Big Tech"),
    ("hex","Hex","Big Tech"),("mode","Mode Analytics","Big Tech"),
    ("sisense","Sisense","Big Tech"),("thoughtspot","ThoughtSpot","Big Tech"),
    # Startups
    ("anthropic","Anthropic","Startups"),("gusto","Gusto","Startups"),
    ("airtable","Airtable","Startups"),("webflow","Webflow","Startups"),
    ("miro","Miro","Startups"),("lattice","Lattice","Startups"),
    ("vanta","Vanta","Startups"),("loom","Loom","Startups"),
    ("retool","Retool","Startups"),("linear","Linear","Startups"),
    ("drata","Drata","Startups"),("secureframe","Secureframe","Startups"),
    ("rippling","Rippling","Startups"),("remote","Remote","Startups"),
    ("deel","Deel","Startups"),("papaya-global","Papaya Global","Startups"),
    ("workato","Workato","Startups"),("zapier","Zapier","Startups"),
    ("make","Make","Startups"),("tray","Tray.io","Startups"),
    ("scale-ai","Scale AI","Startups"),("cohere","Cohere","Startups"),
    ("huggingface","Hugging Face","Startups"),("weights-biases","Weights & Biases","Startups"),
    ("lightning-ai","Lightning AI","Startups"),("modal-labs","Modal","Startups"),
    ("mistral","Mistral AI","Startups"),("perplexity","Perplexity","Startups"),
    ("notion","Notion","Startups"),("coda","Coda","Startups"),
    ("clickup","ClickUp","Startups"),("monday","Monday.com","Startups"),
    ("asana","Asana","Startups"),("figma","Figma","Startups"),
    # Finance & Fintech
    ("chime","Chime","Finance"),("affirm","Affirm","Finance"),
    ("robinhood","Robinhood","Finance"),("coinbase","Coinbase","Finance"),
    ("marqeta","Marqeta","Finance"),("plaid","Plaid","Finance"),
    ("carta","Carta","Finance"),("brex","Brex","Finance"),
    ("ramp","Ramp","Finance"),("mercury","Mercury","Finance"),
    ("stripe","Stripe","Finance"),("adyen","Adyen","Finance"),
    ("klarna","Klarna","Finance"),("nerdwallet","NerdWallet","Finance"),
    ("sofi","SoFi","Finance"),("blend","Blend","Finance"),
    ("opendoor","Opendoor","Finance"),("offerpad","Offerpad","Finance"),
    # Healthcare
    ("oscar","Oscar Health","Healthcare"),("springhealth","Spring Health","Healthcare"),
    ("commure","Commure","Healthcare"),("devoted","Devoted Health","Healthcare"),
    ("cityblock","Cityblock Health","Healthcare"),("cerebral","Cerebral","Healthcare"),
    ("headspace","Headspace","Healthcare"),("hims","Hims & Hers","Healthcare"),
    ("ro","Ro","Healthcare"),("truepill","Truepill","Healthcare"),
    ("nuna","Nuna","Healthcare"),("accolade","Accolade","Healthcare"),
    ("cerner","Oracle Cerner","Healthcare"),("modernhealth","Modern Health","Healthcare"),
    # Enterprise / IT
    ("servicenow","ServiceNow","Enterprise"),("salesforce","Salesforce","Enterprise"),
    ("workday","Workday","Enterprise"),("oracle","Oracle","Enterprise"),
    ("sap","SAP","Enterprise"),("vmware","VMware","Enterprise"),
    ("crowdstrike","CrowdStrike","Enterprise"),("paloaltonetworks","Palo Alto Networks","Enterprise"),
    ("sentinelone","SentinelOne","Enterprise"),("rapid7","Rapid7","Enterprise"),
    ("tenable","Tenable","Enterprise"),("qualys","Qualys","Enterprise"),
    ("dynatrace","Dynatrace","Enterprise"),("newrelic","New Relic","Enterprise"),
    ("splunk","Splunk","Enterprise"),("sumo-logic","Sumo Logic","Enterprise"),
    ("logrhythm","LogRhythm","Enterprise"),("secureworks","Secureworks","Enterprise"),
]

# ── LEVER COMPANIES (40+) ─────────────────────────────────────────────────
LV = [
    ("openai","OpenAI","Startups"),("notion","Notion","Startups"),
    ("rippling","Rippling","Startups"),("scale-ai","Scale AI","Startups"),
    ("mercury","Mercury","Finance"),("sentry","Sentry","Big Tech"),
    ("drata","Drata","Startups"),("deel","Deel","Startups"),
    ("canva","Canva","Big Tech"),("lob","Lob","Startups"),
    ("census","Census","Big Tech"),("hightouch","Hightouch","Big Tech"),
    ("metabase","Metabase","Big Tech"),("airbyte","Airbyte","Startups"),
    ("prefect","Prefect","Startups"),("anomalo","Anomalo","Startups"),
    ("atlan","Atlan","Startups"),("elementary-data","Elementary","Startups"),
    ("lightdash","Lightdash","Startups"),("cube","Cube.dev","Startups"),
    ("samsara","Samsara","Big Tech"),("verkada","Verkada","Big Tech"),
    ("benchling","Benchling","Healthcare"),("netsuite","NetSuite","Enterprise"),
    ("greenhouse","Greenhouse","Startups"),("lever","Lever","Startups"),
    ("ashby","Ashby","Startups"),("gem","Gem","Startups"),
    ("findem","Findem","Startups"),("eightfold","Eightfold","Startups"),
    ("phenom","Phenom","Enterprise"),("paradox","Paradox","Enterprise"),
    ("beamery","Beamery","Enterprise"),("gloat","Gloat","Enterprise"),
    ("lattice","Lattice","Startups"),("leapsome","Leapsome","Startups"),
    ("betterworks","BetterWorks","Startups"),("15five","15Five","Startups"),
    ("culture-amp","Culture Amp","Startups"),("peakon","Peakon","Startups"),
]

# ── FETCH GREENHOUSE ──────────────────────────────────────────────────────
def fetch_gh(cid, name, cat):
    jobs = []
    try:
        r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{cid}/jobs",
            params={"content":"true"}, headers=HEADERS, timeout=8)
        if r.status_code != 200: return jobs
        for item in r.json().get("jobs",[])[:30]:
            loc = item.get("location",{}).get("name","United States")
            if not is_usa(loc): continue
            desc = BeautifulSoup(item.get("content",""),"html.parser").get_text(separator=" ")
            desc = " ".join(desc.split())[:600]
            updated = (item.get("updated_at") or now_iso())[:19]
            jobs.append({
                "id": make_id(item.get("id",""),cid),
                "title": item.get("title",""),
                "company": name,
                "location": loc,
                "salary": "Not listed",
                "job_type": "Full-time",
                "remote_type": detect_remote(desc, loc),
                "sponsorship": detect_sponsorship(desc),
                "description": desc,
                "apply_url": item.get("absolute_url",""),
                "category": cat,
                "posted_at": updated,
            })
    except Exception as e:
        print(f"GH {cid} error: {e}")
    return jobs

# ── FETCH LEVER ───────────────────────────────────────────────────────────
def fetch_lv(cid, name, cat):
    jobs = []
    try:
        r = requests.get(f"https://api.lever.co/v0/postings/{cid}?mode=json",
            headers=HEADERS, timeout=8)
        if r.status_code != 200: return jobs
        for item in r.json()[:30]:
            loc = item.get("categories",{}).get("location","United States")
            if not is_usa(loc): continue
            desc_html = item.get("descriptionPlain","") or item.get("description","")
            desc = BeautifulSoup(desc_html,"html.parser").get_text(separator=" ") if "<" in desc_html else desc_html
            desc = " ".join(desc.split())[:600]
            ts = item.get("createdAt",0)
            posted = datetime.fromtimestamp(ts/1000,tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") if ts else now_iso()
            jobs.append({
                "id": make_id(item.get("id",""),cid),
                "title": item.get("text",""),
                "company": name,
                "location": loc,
                "salary": "Not listed",
                "job_type": "Full-time",
                "remote_type": detect_remote(desc, loc),
                "sponsorship": detect_sponsorship(desc),
                "description": desc,
                "apply_url": item.get("hostedUrl",""),
                "category": cat,
                "posted_at": posted,
            })
    except Exception as e:
        print(f"LV {cid} error: {e}")
    return jobs

# ── INDEED RSS ────────────────────────────────────────────────────────────
INDEED_QUERIES = [
    ("data analyst","Enterprise"),("data engineer","Big Tech"),
    ("business analyst","Enterprise"),("software engineer","Big Tech"),
    ("python developer","Big Tech"),("sql developer","Enterprise"),
    ("power bi developer","Enterprise"),("tableau developer","Enterprise"),
    ("machine learning engineer","Big Tech"),("devops engineer","Big Tech"),
    ("cloud engineer","Big Tech"),(".net developer","Enterprise"),
    ("java developer","Enterprise"),("servicenow developer","Enterprise"),
    ("salesforce developer","Enterprise"),("data scientist","Big Tech"),
    ("full stack developer","Big Tech"),("react developer","Big Tech"),
    ("aws engineer","Big Tech"),("azure developer","Enterprise"),
    ("cybersecurity analyst","Enterprise"),("product manager","Big Tech"),
]

def fetch_indeed_rss(query, category):
    jobs = []
    try:
        q = query.replace(" ", "+")
        url = f"https://www.indeed.com/rss?q={q}&l=United+States&sort=date&limit=25"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        if r.status_code != 200: return jobs
        root = ET.fromstring(r.content)
        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        for item in root.findall(".//item"):
            title = item.findtext("title","").split(" - ")[0].strip()
            company = item.findtext("title","").split(" - ")[-1].strip() if " - " in item.findtext("title","") else "Unknown"
            link = item.findtext("link","")
            desc_raw = item.findtext("description","")
            desc = BeautifulSoup(desc_raw,"html.parser").get_text(separator=" ")[:600]
            loc_tag = item.find(".//{http://www.w3.org/2003/01/geo/wgs84_pos#}lat")
            location = "United States"
            for tag in item:
                if "location" in tag.tag.lower():
                    location = tag.text or "United States"
                    break
            if not is_usa(location): continue
            pub = item.findtext("pubDate","")
            try:
                from email.utils import parsedate_to_datetime
                posted = parsedate_to_datetime(pub).strftime("%Y-%m-%dT%H:%M:%S") if pub else now_iso()
            except:
                posted = now_iso()
            jobs.append({
                "id": make_id(link, query),
                "title": title,
                "company": company,
                "location": location,
                "salary": "Not listed",
                "job_type": "Full-time",
                "remote_type": detect_remote(desc, location),
                "sponsorship": detect_sponsorship(desc),
                "description": desc,
                "apply_url": link,
                "category": category,
                "posted_at": posted,
            })
    except Exception as e:
        print(f"Indeed RSS {query} error: {e}")
    return jobs

# ── USAJOBS ──────────────────────────────────────────────────────────────
USAJOBS_QUERIES = [
    ("data analyst","Enterprise"),("data engineer","Big Tech"),
    ("software engineer","Big Tech"),("business analyst","Enterprise"),
    ("it specialist","Enterprise"),("cybersecurity","Enterprise"),
    ("cloud engineer","Big Tech"),("program analyst","Enterprise"),
    ("management analyst","Enterprise"),("systems analyst","Enterprise"),
]

def fetch_usajobs(keyword, category):
    jobs = []
    try:
        r = requests.get(
            "https://data.usajobs.gov/api/search",
            headers={"Host":"data.usajobs.gov","User-Agent":"jk@example.com","Authorization-Key":""},
            params={"Keyword":keyword,"ResultsPerPage":"25","WhoMayApply":"public","JobCategoryCode":"2210"},
            timeout=10
        )
        if r.status_code != 200: return jobs
        for item in r.json().get("SearchResult",{}).get("SearchResultItems",[]):
            d = item.get("MatchedObjectDescriptor",{})
            title = d.get("PositionTitle","")
            org = d.get("OrganizationName","US Government")
            loc_list = d.get("PositionLocation",[])
            loc = loc_list[0].get("LocationName","United States") if loc_list else "United States"
            if not is_usa(loc): continue
            sal = d.get("PositionRemuneration",[{}])
            salary = "Not listed"
            if sal:
                mn = sal[0].get("MinimumRange","")
                mx = sal[0].get("MaximumRange","")
                if mn: salary = f"${float(mn):,.0f} - ${float(mx):,.0f}/yr" if mx else f"${float(mn):,.0f}/yr"
            desc = BeautifulSoup(d.get("UserArea",{}).get("Details",{}).get("JobSummary",""),"html.parser").get_text()[:600]
            apply_url = d.get("PositionURI","")
            posted = (d.get("PublicationStartDate") or now_iso())[:19].replace(" ","T")
            jobs.append({
                "id": make_id(d.get("PositionID",""), keyword),
                "title": title,
                "company": org,
                "location": loc,
                "salary": salary,
                "job_type": "Full-time",
                "remote_type": detect_remote(desc, loc),
                "sponsorship": False,
                "description": desc,
                "apply_url": apply_url,
                "category": category,
                "posted_at": posted,
            })
    except Exception as e:
        print(f"USAJobs {keyword} error: {e}")
    return jobs

# ── REMOTIVE (Remote jobs) ────────────────────────────────────────────────
REMOTIVE_CATS = [
    ("software-dev","Big Tech"),("data","Enterprise"),
    ("devops-sysadmin","Big Tech"),("product","Big Tech"),
    ("engineering","Big Tech"),("design","Big Tech"),
]

def fetch_remotive():
    jobs = []
    try:
        r = requests.get("https://remotive.com/api/remote-jobs?limit=100", headers=HEADERS, timeout=10)
        if r.status_code != 200: return jobs
        for item in r.json().get("jobs",[]):
            region = item.get("candidate_required_location","")
            if region and not any(x in region.lower() for x in ["usa","us only","united states","worldwide","anywhere","north america"]):
                if is_usa(region) == False: continue
            desc = BeautifulSoup(item.get("description",""),"html.parser").get_text()[:600]
            cat_slug = item.get("category","")
            category = "Big Tech"
            if any(x in cat_slug.lower() for x in ["data","analyst","bi"]): category = "Enterprise"
            pub = item.get("publication_date","")
            try:
                posted = datetime.strptime(pub[:19],"%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%dT%H:%M:%S") if pub else now_iso()
            except:
                posted = now_iso()
            sal = item.get("salary","") or "Not listed"
            jobs.append({
                "id": make_id(item.get("id",""), "remotive"),
                "title": item.get("title",""),
                "company": item.get("company_name",""),
                "location": "Remote",
                "salary": sal if sal else "Not listed",
                "job_type": "Full-time",
                "remote_type": "Remote",
                "sponsorship": detect_sponsorship(desc),
                "description": desc,
                "apply_url": item.get("url",""),
                "category": category,
                "posted_at": posted,
            })
    except Exception as e:
        print(f"Remotive error: {e}")
    return jobs

# ── ADZUNA ────────────────────────────────────────────────────────────────
def search_adzuna(keyword, category):
    cache_key = f"az_{keyword}"
    now = time.time()
    if cache_key in _search_cache and (now - _search_cache[cache_key]["time"]) < SEARCH_TTL:
        return _search_cache[cache_key]["jobs"]
    jobs = []
    if not ADZUNA_ID or not ADZUNA_KEY:
        _search_cache[cache_key] = {"jobs": jobs, "time": now}
        return jobs
    try:
        r = requests.get(
            f"https://api.adzuna.com/v1/api/jobs/us/search/1",
            params={"app_id":ADZUNA_ID,"app_key":ADZUNA_KEY,"what":keyword,
                    "content-type":"application/json","results_per_page":"20",
                    "sort_by":"date","max_days_old":"30","full_time":1},
            timeout=12
        )
        if r.status_code == 200:
            for item in r.json().get("results",[]):
                loc_obj = item.get("location",{})
                area = loc_obj.get("area",[])
                loc = area[-1] if area else "United States"
                if not is_usa(loc): continue
                desc = item.get("description","")[:600]
                sal_min = item.get("salary_min")
                sal_max = item.get("salary_max", sal_min)
                salary = f"${sal_min:,.0f} - ${sal_max:,.0f}/yr" if sal_min else "Not listed"
                posted = (item.get("created","") or now_iso())[:19]
                jobs.append({
                    "id": make_id(item.get("id",""), keyword),
                    "title": item.get("title",""),
                    "company": item.get("company",{}).get("display_name",""),
                    "location": loc,
                    "salary": salary,
                    "job_type": "Full-time",
                    "remote_type": detect_remote(desc, loc),
                    "sponsorship": detect_sponsorship(desc),
                    "description": desc,
                    "apply_url": item.get("redirect_url",""),
                    "category": category,
                    "posted_at": posted,
                })
        elif r.status_code == 429:
            print("Adzuna rate limit")
    except Exception as e:
        print(f"Adzuna error: {e}")
    _search_cache[cache_key] = {"jobs": jobs, "time": now}
    return jobs

# ── JSEARCH ───────────────────────────────────────────────────────────────
def search_jsearch(keyword, category):
    cache_key = f"js_{keyword}"
    now = time.time()
    if cache_key in _search_cache and (now - _search_cache[cache_key]["time"]) < SEARCH_TTL:
        return _search_cache[cache_key]["jobs"]
    jobs = []
    if not JSEARCH_KEY:
        _search_cache[cache_key] = {"jobs": jobs, "time": now}
        return jobs
    try:
        r = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            headers={"X-RapidAPI-Key": JSEARCH_KEY, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"},
            params={"query": f"{keyword} United States", "page":"1",
                    "num_results":"20", "date_posted":"month", "country":"us"},
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
                    "id": make_id(item.get("job_id",""), keyword),
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
    _search_cache[cache_key] = {"jobs": jobs, "time": now}
    return jobs

def get_extra_jobs(keyword, category):
    jobs = search_adzuna(keyword, category)
    if not jobs:
        jobs = search_jsearch(keyword, category)
    return jobs

# ── KEYWORD MAP ───────────────────────────────────────────────────────────
KEYWORD_MAP = {
    "data analyst":("Data Analyst","Enterprise"),
    "business analyst":("Business Analyst","Enterprise"),
    ".net":(".NET Developer","Enterprise"),
    "c#":("C# Developer","Enterprise"),
    "java":("Java Developer","Enterprise"),
    "servicenow":("ServiceNow Developer","Enterprise"),
    "sap":("SAP Consultant","Enterprise"),
    "salesforce":("Salesforce Developer","Enterprise"),
    "power bi":("Power BI Developer","Enterprise"),
    "powerbi":("Power BI Developer","Enterprise"),
    "tableau":("Tableau Developer","Enterprise"),
    "sql":("SQL Developer","Enterprise"),
    "oracle":("Oracle Developer","Enterprise"),
    "etl":("ETL Developer","Enterprise"),
    "python":("Python Developer","Big Tech"),
    "react":("React Developer","Big Tech"),
    "angular":("Angular Developer","Big Tech"),
    "devops":("DevOps Engineer","Big Tech"),
    "cloud":("Cloud Engineer","Big Tech"),
    "aws":("AWS Engineer","Big Tech"),
    "azure":("Azure Developer","Big Tech"),
    "machine learning":("Machine Learning Engineer","Big Tech"),
    "data engineer":("Data Engineer","Big Tech"),
    "data scientist":("Data Scientist","Big Tech"),
    "full stack":("Full Stack Developer","Big Tech"),
    "node":("Node.js Developer","Big Tech"),
    "cybersecurity":("Cybersecurity Analyst","Enterprise"),
    "product manager":("Product Manager","Big Tech"),
    "software engineer":("Software Engineer","Big Tech"),
    "software developer":("Software Developer","Big Tech"),
    "bi developer":("BI Developer","Enterprise"),
    "snowflake":("Snowflake Engineer","Enterprise"),
    "databricks":("Databricks Engineer","Big Tech"),
    "kubernetes":("Kubernetes Engineer","Big Tech"),
    "docker":("Docker Engineer","Big Tech"),
    "spark":("Spark Engineer","Big Tech"),
    "kafka":("Kafka Engineer","Big Tech"),
    "looker":("Looker Developer","Enterprise"),
    "dbt":("Analytics Engineer","Big Tech"),
    "airflow":("Data Engineer","Big Tech"),
    "ml engineer":("ML Engineer","Big Tech"),
    "ai engineer":("AI Engineer","Big Tech"),
    "generative ai":("AI Engineer","Big Tech"),
    "llm":("LLM Engineer","Big Tech"),
    "golang":("Go Developer","Big Tech"),
    "typescript":("TypeScript Developer","Big Tech"),
    "backend":("Backend Engineer","Big Tech"),
    "frontend":("Frontend Engineer","Big Tech"),
    "mobile":("Mobile Developer","Big Tech"),
    "ios":("iOS Developer","Big Tech"),
    "android":("Android Developer","Big Tech"),
    "qa":("QA Engineer","Enterprise"),
    "scrum master":("Scrum Master","Enterprise"),
    "project manager":("Project Manager","Enterprise"),
    "business intelligence":("BI Developer","Enterprise"),
}

# ── BACKGROUND JOBS (pre-fetched every 30 min) ────────────────────────────
BG_KEYWORDS = [
    ("data analyst","Enterprise"),("data engineer","Big Tech"),
    ("python developer","Big Tech"),("sql developer","Enterprise"),
    ("power bi developer","Enterprise"),("machine learning engineer","Big Tech"),
    ("software engineer","Big Tech"),("business analyst","Enterprise"),
    ("cloud engineer","Big Tech"),("tableau developer","Enterprise"),
    ("snowflake developer","Enterprise"),("devops engineer","Big Tech"),
    (".net developer","Enterprise"),("java developer","Enterprise"),
    ("data scientist","Big Tech"),
]

_bg_cache = {"jobs":[], "time":0}

def get_bg_jobs():
    now = time.time()
    if _bg_cache["jobs"] and (now - _bg_cache["time"]) < EXTRA_TTL:
        return _bg_cache["jobs"]
    jobs = []
    # Fetch Indeed RSS for all background keywords
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_indeed_rss, kw, cat): (kw,cat) for kw,cat in BG_KEYWORDS}
        for fut in as_completed(futures):
            try: jobs.extend(fut.result())
            except: pass
    # Also fetch USAJobs for a few keywords
    for kw, cat in BG_KEYWORDS[:5]:
        jobs.extend(fetch_usajobs(kw, cat))
    # Remotive remote jobs
    jobs.extend(fetch_remotive())
    _bg_cache["jobs"] = jobs
    _bg_cache["time"] = now
    print(f"Background jobs loaded: {len(jobs)}")
    return jobs

# ── COMPANY JOBS (Greenhouse + Lever) ─────────────────────────────────────
def get_company_jobs():
    now = time.time()
    if _company_cache["jobs"] and (now - _company_cache["time"]) < COMPANY_TTL:
        return _company_cache["jobs"]
    jobs = []
    companies = [("gh",)+c for c in GH] + [("lv",)+c for c in LV]
    with ThreadPoolExecutor(max_workers=15) as ex:
        futures = {ex.submit(fetch_gh if c[0]=="gh" else fetch_lv, c[1],c[2],c[3]): c for c in companies}
        for fut in as_completed(futures):
            try: jobs.extend(fut.result())
            except: pass
    jobs.sort(key=lambda j: j.get("posted_at",""), reverse=True)
    _company_cache["jobs"] = jobs
    _company_cache["time"] = now
    print(f"Company jobs loaded: {len(jobs)}")
    return jobs

# ── DEDUPE ────────────────────────────────────────────────────────────────
def dedupe(jobs):
    seen, out = set(), []
    for j in jobs:
        key = f"{j.get('title','').lower()[:20]}_{j.get('company','').lower()[:12]}"
        if key not in seen:
            seen.add(key)
            out.append(j)
    return out

# ── API ROUTES ─────────────────────────────────────────────────────────────
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

    company_jobs = get_company_jobs()
    bg_jobs = get_bg_jobs()
    extra_jobs = []

    if keyword:
        query, cat = keyword, "Enterprise"
        for kw, (q, c) in KEYWORD_MAP.items():
            if kw in keyword:
                query, cat = q, c
                break
        extra_jobs = get_extra_jobs(query, cat)
        # Also search Indeed RSS live
        extra_jobs += fetch_indeed_rss(keyword, cat)

    all_jobs = dedupe(company_jobs + bg_jobs + extra_jobs)

    # Filter
    now = time.time()
    result = []
    for j in all_jobs:
        if keyword:
            search_text = f"{j.get('title','')} {j.get('company','')} {j.get('description','')}".lower()
            if not any(w in search_text for w in keyword.split()): continue
        if location and location not in j.get("location","").lower(): continue
        if remote and j.get("remote_type","").lower() != remote.lower(): continue
        if category and j.get("category","") != category: continue
        if sponsor == "true" and not j.get("sponsorship"): continue
        if hours:
            try:
                h = float(hours)
                posted = datetime.fromisoformat(j.get("posted_at","").replace("Z",""))
                posted = posted.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - posted).total_seconds() > h*3600: continue
            except: pass
        result.append(j)

    result.sort(key=lambda j: j.get("posted_at",""), reverse=True)
    total = len(result)
    start = (page-1)*per_page
    paginated = result[start:start+per_page]

    by_cat = {}
    for j in result:
        c = j.get("category","Other")
        by_cat[c] = by_cat.get(c,0)+1

    return jsonify({
        "jobs": paginated,
        "total": total,
        "page": page,
        "per_page": per_page,
        "by_category": by_cat,
    })

@app.route("/api/stats", methods=["GET"])
def stats():
    company_jobs = get_company_jobs()
    bg_jobs = get_bg_jobs()
    all_jobs = dedupe(company_jobs + bg_jobs)
    by_cat = {}
    remote_count = 0
    sponsor_count = 0
    for j in all_jobs:
        c = j.get("category","Other")
        by_cat[c] = by_cat.get(c,0)+1
        if j.get("remote_type") == "Remote": remote_count += 1
        if j.get("sponsorship"): sponsor_count += 1
    return jsonify({
        "total_jobs": len(all_jobs),
        "remote_jobs": remote_count,
        "sponsorship_jobs": sponsor_count,
        "by_category": by_cat,
    })

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status":"ok","company_jobs":len(_company_cache["jobs"]),"bg_jobs":len(_bg_cache["jobs"])})

@app.route("/api/test-models",methods=["GET"])
def test_models():
    api_key=os.getenv("ANTHROPIC_API_KEY","")
    if not api_key: return jsonify({"error":"No API key"})
    results={}
    for model in ["claude-haiku-4-5-20251001","claude-sonnet-4-5-20250929","claude-3-haiku-20240307"]:
        try:
            resp=requests.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key":api_key,"anthropic-version":"2023-06-01","content-type":"application/json"},
                json={"model":model,"max_tokens":10,"messages":[{"role":"user","content":"Hi"}]},timeout=15)
            results[model]=f"HTTP {resp.status_code}"
            if resp.status_code!=200:
                results[model]+=f" - {resp.json().get('error',{}).get('message','')[:60]}"
        except Exception as e:
            results[model]=str(e)[:60]
    return jsonify(results)

@app.route("/",methods=["GET"])
def home():
    return jsonify({"message":"JobHunter AI v13","company_jobs":len(_company_cache["jobs"]),"bg_jobs":len(_bg_cache["jobs"])})

@app.route("/api/optimize-resume", methods=["POST","OPTIONS"])
def optimize_resume():
    if request.method=="OPTIONS":
        resp=jsonify({})
        resp.headers.add("Access-Control-Allow-Origin","*")
        resp.headers.add("Access-Control-Allow-Headers","Content-Type")
        resp.headers.add("Access-Control-Allow-Methods","POST,OPTIONS")
        return resp,200
    try:
        body=request.get_json(force=True)
        if not body: return jsonify({"error":"Invalid JSON"}),400
        resume=body.get("resume","").strip()
        jd=body.get("jd","").strip()
        if not resume or len(resume)<50: return jsonify({"error":"Resume too short"}),400
        if not jd or len(jd)<30: return jsonify({"error":"Job description too short"}),400
        api_key=os.getenv("ANTHROPIC_API_KEY","")
        if not api_key: return jsonify({"error":"ANTHROPIC_API_KEY not set on server"}),500

        prompt=f"""You are an expert ATS resume writer. Generate a perfectly tailored 100% ATS-optimized resume.

SOURCE RESUME:
{resume[:3000]}

TARGET JOB DESCRIPTION:
{jd[:2000]}

RULES — follow every one exactly:
1. Name: JEEVAN KUMAR N (never change)
2. Contact: Denton, Texas | (940) 595-8405 | jeevankumar25src@gmail.com | LinkedIn | GitHub
3. Keep Vanguard, Bank of America, LatentView Analytics with exact dates
4. Location: Remote = Denton Texas | On-site or Hybrid = location from JD
5. Summary: 3 sentences, first opens with EXACT job title from JD
6. Tech pivot: if JD needs different stack, pivot summary+skills+titles+ALL bullets
7. Vanguard = 6-8 bullets | Bank of America = 5-6 bullets | LatentView = 5-6 bullets
8. Bold JD keywords in bullets: write **keyword** around each one
9. Skills: **Category:** skill1, skill2 (no bullets, just bold category then colon)
10. Certifications: Google Data Analytics Professional Certificate + Microsoft Certified: Power BI Data Analyst Associate
11. Education: University of North Texas — M.S. Information Systems & Technology | May 2025

OUTPUT FORMAT:
Line 1: SCORE: XX%
Blank line
Then resume:

JEEVAN KUMAR N
Denton, Texas | (940) 595-8405 | jeevankumar25src@gmail.com | LinkedIn | GitHub

PROFESSIONAL SUMMARY
[3 sentences]

TECHNICAL SKILLS
**Category:** skill1, skill2, skill3
[one per line, no bullets]

PROFESSIONAL EXPERIENCE

Vanguard | Aug 2025 – Present
Senior Data Analyst / BI Engineer
• bullet with **keyword** bolded
[6-8 bullets]

Bank of America | Dec 2024 – Aug 2025
Business Data Analyst
• bullet
[5-6 bullets]

LatentView Analytics | Nov 2020 – Jul 2023
Data Analyst
• bullet
[5-6 bullets]

EDUCATION & CERTIFICATIONS
• University of North Texas — M.S. Information Systems & Technology | May 2025
• Google Data Analytics Professional Certificate
• Microsoft Certified: Power BI Data Analyst Associate

No HTML. Plain text only. Use | between company and dates."""

        models=["claude-haiku-4-5-20251001","claude-sonnet-4-5-20250929","claude-opus-4-5-20251101"]
        last_error=None
        result_text=None
        for model in models:
            resp=requests.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key":api_key,"anthropic-version":"2023-06-01","content-type":"application/json"},
                json={"model":model,"max_tokens":4000,"messages":[{"role":"user","content":prompt}]},
                timeout=120)
            if resp.status_code==200:
                result_text=resp.json()["content"][0]["text"]
                print(f"Resume generated with {model}")
                break
            else:
                last_error=resp.json().get("error",{}).get("message",resp.text[:100])
                print(f"Model {model} failed: {last_error}")
                if resp.status_code not in [404,400]: break
        if not result_text:
            return jsonify({"error":f"All models failed: {last_error}"}),500
        return jsonify({"result":result_text})
    except Exception as e:
        print(f"Resume error: {e}")
        return jsonify({"error":str(e)}),500

if __name__=="__main__":
    app.run(debug=True,host="0.0.0.0",port=5000)

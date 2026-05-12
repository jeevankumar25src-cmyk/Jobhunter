"""
JobHunter AI - Database
Auto-detects PostgreSQL or SQLite based on DATABASE_URL env var.
"""
import os
from datetime import datetime
from peewee import Model, CharField, TextField, BooleanField, DateTimeField, AutoField, SqliteDatabase, PostgresqlDatabase
from urllib.parse import urlparse

DATABASE_URL = os.getenv("DATABASE_URL", "")

if DATABASE_URL:
    url = urlparse(DATABASE_URL)
    db = PostgresqlDatabase(
        url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port or 5432,
    )
    print(f"Using PostgreSQL at {url.hostname}")
else:
    db = SqliteDatabase("jobs.db")
    print("Using SQLite locally")

class BaseModel(Model):
    class Meta:
        database = db

class Job(BaseModel):
    id          = AutoField()
    job_id      = CharField(unique=True, max_length=64)
    title       = CharField(max_length=255)
    company     = CharField(max_length=255)
    location    = CharField(max_length=255, default="United States")
    salary      = CharField(max_length=128, default="Not listed")
    job_type    = CharField(max_length=64, default="Full-time")
    remote_type = CharField(max_length=64, default="On-site")
    sponsorship = BooleanField(default=False)
    description = TextField(default="")
    apply_url   = TextField(default="")
    category    = CharField(max_length=64, default="General")
    company_size= CharField(max_length=64, default="Unknown")
    posted_at   = DateTimeField(default=datetime.utcnow)

    class Meta:
        table_name = "jobs"

    def to_dict(self):
        return {
            "id": self.id, "title": self.title, "company": self.company,
            "location": self.location, "salary": self.salary,
            "job_type": self.job_type, "remote_type": self.remote_type,
            "sponsorship": self.sponsorship, "category": self.category,
            "company_size": self.company_size, "apply_url": self.apply_url,
            "posted_at": self.posted_at.isoformat(),
            "description": getattr(self, '_description', ''),
        }

def init_db():
    with db:
        db.create_tables([Job], safe=True)
    print("Database ready!")

def get_jobs(keyword="", location="", remote="", sponsorship=None, category="", page=1, per_page=20):
    query = Job.select().order_by(Job.posted_at.desc())
    if keyword:
        query = query.where((Job.title.contains(keyword))|(Job.company.contains(keyword))|(Job.description.contains(keyword)))
    if location:
        query = query.where(Job.location.contains(location))
    if remote:
        query = query.where(Job.remote_type.contains(remote))
    if sponsorship is not None:
        query = query.where(Job.sponsorship == sponsorship)
    if category:
        query = query.where(Job.category == category)
    total = query.count()
    jobs = list(query.offset((page-1)*per_page).limit(per_page))
    return {"total": total, "page": page, "per_page": per_page, "jobs": [j.to_dict() for j in jobs]}

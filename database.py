"""
JobHunter AI - Database
Uses PostgreSQL (Supabase) in production, SQLite locally.
"""
import os
from datetime import datetime
from peewee import Model, CharField, TextField, BooleanField, DateTimeField, AutoField
from playhouse.db_url import connect

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///jobs.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

db = connect(DATABASE_URL)

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
        }

def init_db():
    with db:
        db.create_tables([Job], safe=True)
    print(f"Database ready!")

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

"""
JobHunter AI - Database
Uses SQLite locally (free, zero setup).
Change DATABASE_URL in .env to switch to PostgreSQL for production.
"""

import os
from datetime import datetime
from peewee import (
    SqliteDatabase, Model,
    CharField, TextField, BooleanField,
    DateTimeField, AutoField
)

DB_PATH = os.getenv("DATABASE_PATH", "jobs.db")
db = SqliteDatabase(DB_PATH)


class BaseModel(Model):
    class Meta:
        database = db


class Job(BaseModel):
    id          = AutoField()
    job_id      = CharField(unique=True, max_length=64)   # MD5 dedup key
    title       = CharField(max_length=255)
    company     = CharField(max_length=255)
    location    = CharField(max_length=255, default="United States")
    salary      = CharField(max_length=128, default="Not listed")
    job_type    = CharField(max_length=64,  default="Full-time")   # Full-time / Part-time / Contract
    remote_type = CharField(max_length=64,  default="On-site")     # Remote / Hybrid / On-site
    sponsorship = BooleanField(default=False)                       # H1B / visa mention
    description = TextField(default="")
    apply_url   = TextField(default="")
    category    = CharField(max_length=64,  default="General")     # Big Tech / Startup / Healthcare / Finance
    company_size= CharField(max_length=64,  default="Unknown")
    posted_at   = DateTimeField(default=datetime.utcnow)

    class Meta:
        table_name = "jobs"
        indexes = (
            (("title", "company", "location"), False),
            (("category",), False),
            (("remote_type",), False),
            (("sponsorship",), False),
            (("posted_at",), False),
        )

    def to_dict(self):
        return {
            "id":           self.id,
            "title":        self.title,
            "company":      self.company,
            "location":     self.location,
            "salary":       self.salary,
            "job_type":     self.job_type,
            "remote_type":  self.remote_type,
            "sponsorship":  self.sponsorship,
            "category":     self.category,
            "company_size": self.company_size,
            "apply_url":    self.apply_url,
            "posted_at":    self.posted_at.isoformat(),
        }


def init_db():
    """Create tables if they don't exist."""
    with db:
        db.create_tables([Job], safe=True)
    print(f"Database ready: {DB_PATH}")


def get_jobs(
    keyword:     str  = "",
    location:    str  = "",
    remote:      str  = "",
    sponsorship: bool = None,
    category:    str  = "",
    salary_min:  int  = 0,
    page:        int  = 1,
    per_page:    int  = 20,
):
    """Query jobs with filters — used by the API."""
    query = Job.select().order_by(Job.posted_at.desc())

    if keyword:
        query = query.where(
            (Job.title.contains(keyword)) |
            (Job.company.contains(keyword)) |
            (Job.description.contains(keyword))
        )
    if location:
        query = query.where(Job.location.contains(location))
    if remote:
        query = query.where(Job.remote_type.contains(remote))
    if sponsorship is not None:
        query = query.where(Job.sponsorship == sponsorship)
    if category:
        query = query.where(Job.category == category)

    total = query.count()
    offset = (page - 1) * per_page
    jobs = list(query.offset(offset).limit(per_page))
    return {
        "total":    total,
        "page":     page,
        "per_page": per_page,
        "jobs":     [j.to_dict() for j in jobs],
    }

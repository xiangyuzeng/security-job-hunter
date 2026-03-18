import os
from pathlib import Path

# Project paths
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "jobs.db"

# Turso / libsql settings (set env vars for cloud deployment)
TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

# Detect serverless environment (Vercel sets VERCEL=1)
IS_SERVERLESS = bool(TURSO_DATABASE_URL) or bool(os.environ.get("VERCEL", ""))

# Job search settings
SEARCH_TERMS = [
    "Cybersecurity Analyst",
    "Security Engineer",
    "Information Security",
    "SOC Analyst",
    "Security Operations",
    "Cloud Security Engineer",
    "Application Security",
    "GRC Analyst",
    "Penetration Tester",
    "Security Architect",
    "Threat Intelligence Analyst",
    "Incident Response",
    "Vulnerability Management",
]
SITES = ["indeed", "linkedin", "glassdoor", "google", "zip_recruiter"]
IS_REMOTE = True
HOURS_OLD = 336  # 14 days
RESULTS_WANTED = 50  # per search term per site
COUNTRY_INDEED = "USA"
LOCATION = "USA"

# Title filtering — reject jobs that are clearly irrelevant
TITLE_EXCLUDE_PATTERNS = [
    r"software\s+engineer",
    r"frontend",
    r"backend",
    r"full[\s\-]?stack",
    r"data\s+scientist",
    r"marketing",
    r"sales",
    r"dba",
    r"database\s+admin",
    r"network\s+admin",
    r"help\s+desk",
    r"graphic\s+design",
    r"product\s+manager",
    r"scrum\s+master",
    r"recruiter",
    r"ui/?ux",
    r"web\s+developer",
]

# Title keywords that always indicate a relevant job
TITLE_INCLUDE_KEYWORDS = [
    "security", "cybersecurity", "infosec", "soc", "siem",
    "threat", "vulnerability", "penetration", "pentest",
    "incident response", "compliance", "grc", "risk", "audit",
    "forensics", "malware", "firewall", "ids", "ips",
    "zero trust", "devsecops", "ciso", "iso 27001", "nist",
    "encryption", "identity", "access management", "iam",
    "cloud security", "appsec", "red team", "blue team",
    "threat intelligence", "endpoint",
]

# Scheduler settings
REFRESH_INTERVAL_HOURS = 4

# Email notification settings (optional — set env vars to enable)
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "")

# Dashboard URL (for email notifications)
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")

# Server settings
HOST = "0.0.0.0"
PORT = 8890

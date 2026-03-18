import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config

logger = logging.getLogger(__name__)


def is_configured():
    return bool(config.GMAIL_ADDRESS and config.GMAIL_APP_PASSWORD and config.NOTIFY_EMAIL)


def send_notification(new_jobs):
    """Send email notification about new job listings.
    new_jobs: list of job dicts from database."""
    if not is_configured():
        logger.debug("Email notifications not configured, skipping.")
        return

    if not new_jobs:
        return

    subject = f"Security Job Alert: {len(new_jobs)} new listing(s) found"

    rows = ""
    for job in new_jobs[:20]:  # cap at 20 in email
        salary = ""
        if job.get("salary_min"):
            salary = f"${job['salary_min']:,.0f}"
            if job.get("salary_max"):
                salary += f" - ${job['salary_max']:,.0f}"
            if job.get("salary_interval"):
                salary += f" / {job['salary_interval']}"

        rows += f"""
        <tr>
            <td><a href="{job.get('job_url', '#')}">{job.get('title', 'N/A')}</a></td>
            <td>{job.get('company', 'N/A')}</td>
            <td>{salary or 'N/A'}</td>
            <td>{job.get('source', 'N/A')}</td>
            <td>{job.get('date_posted', 'N/A')}</td>
        </tr>"""

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2>New Security Job Listings Found</h2>
        <p>{len(new_jobs)} new remote security job(s) matched your search.</p>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse;">
            <tr style="background: #6d28d9; color: white;">
                <th>Title</th><th>Company</th><th>Salary</th><th>Source</th><th>Posted</th>
            </tr>
            {rows}
        </table>
        <p style="margin-top: 16px;">
            <a href="{config.DASHBOARD_URL or f'http://localhost:{config.PORT}'}">Open Dashboard</a> to view all jobs and apply.
        </p>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.GMAIL_ADDRESS
    msg["To"] = config.NOTIFY_EMAIL
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
            server.sendmail(config.GMAIL_ADDRESS, config.NOTIFY_EMAIL, msg.as_string())
        logger.info(f"Email notification sent to {config.NOTIFY_EMAIL}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

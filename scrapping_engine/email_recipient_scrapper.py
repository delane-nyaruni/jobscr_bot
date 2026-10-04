"""
Replaces email_recipient_scrapper.py.

Scrapes the active JobBoard URLs for recruiter/hiring-manager emails on
individual job postings, filters out anything on the IgnoredDomain list,
and stores new finds as JobLead rows instead of writing two CSV files.

Run with: python manage.py scrape_leads
"""
import re
import time

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils import timezone

from leads.models import IgnoredDomain, JobBoard, JobLead

EMAIL_REGEX = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
LINKS_PER_BOARD = 15


class Command(BaseCommand):
    help = "Scrape configured job boards for recruiter emails and store new leads."

    def handle(self, *args, **options):
        boards = list(JobBoard.objects.filter(is_active=True).values_list("url", flat=True))
        ignored_domains = list(IgnoredDomain.objects.values_list("domain", flat=True))
        self.stdout.write(f"Monitoring {len(boards)} boards...")

        new_leads = []

        for board_url in boards:
            self.stdout.write(f"Scanning: {board_url}")
            try:
                response = requests.get(board_url, headers=HEADERS, timeout=15)
                soup = BeautifulSoup(response.text, "html.parser")

                job_links = set()
                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    full_url = href if href.startswith("http") else f"{board_url.rstrip('/')}/{href.lstrip('/')}"
                    if any(x in full_url.lower() for x in ["/job", "/post", "detail", "vacancy"]):
                        job_links.add(full_url)

                for url in list(job_links)[:LINKS_PER_BOARD]:
                    data = self._get_job_details(url, ignored_domains)
                    for email in data["emails"]:
                        lead, created = JobLead.objects.get_or_create(
                            email=email,
                            job_board=board_url,
                            defaults={"job_title": data["title"], "job_type": "Remote/Full-time"},
                        )
                        if created:
                            new_leads.append(lead)
                            self.stdout.write(f"    [+] New lead: {email}")
                    time.sleep(1)
            except Exception as exc:
                self.stderr.write(f"Error on {board_url}: {exc}")

        self._send_email_report(len(new_leads))

    def _get_job_details(self, url, ignored_domains):
        details = {"emails": [], "title": "N/A"}
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")
            found = re.findall(EMAIL_REGEX, response.text)
            details["emails"] = list({
                e.lower() for e in found if not any(d in e.lower() for d in ignored_domains)
            })
            title_tag = soup.find("h1") or soup.find("h2")
            if title_tag:
                details["title"] = title_tag.get_text(strip=True)
        except Exception:
            pass
        return details

    def _send_email_report(self, found_count):
        receiver = getattr(settings, "RECEIVER_EMAIL", None)
        if not receiver:
            self.stdout.write("RECEIVER_EMAIL not configured, skipping report.")
            return
        subject = f"Job Leads: {found_count} New Found - {timezone.now():%Y-%m-%d}"
        body = f"Scraper finished. Found {found_count} new email leads today."
        EmailMessage(subject, body, to=[receiver]).send(fail_silently=True)
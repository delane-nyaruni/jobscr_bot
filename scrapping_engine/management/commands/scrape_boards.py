# scrapping_engine/management/commands/scrape_boards.py
import os
import requests
from bs4 import BeautifulSoup
import re
import time
from django.conf import settings
from django.core.management.base import BaseCommand
from scrapping_engine.models import JobBoard, JobLead, CandidateCV
from scrapping_engine.utils import parse_cv_filename

EMAIL_REGEX = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
BLACKLIST = ["example.com", "sentry.io"]

class Command(BaseCommand):
    help = 'Scrapes job boards for emails based on CV career parameters'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting job scraper...")

        # 1. SYNC CVs FROM FOLDER FIRST
        self.sync_cvs_from_folder()

        # 2. Get the CVs and extract their roles
        cvs = CandidateCV.objects.all()
        search_roles = [cv.target_role for cv in cvs]
        
        if not search_roles:
            self.stdout.write(self.style.WARNING("No CVs found. Please add a PDF to media/docs/cv/ and try again."))
            return

        self.stdout.write(f"Target Roles to search: {search_roles}")

        # 3. Get active job boards (LIMIT TO 4)
        boards = JobBoard.objects.filter(is_active=True)[:4]
        
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

        for board in boards:
            self.stdout.write(f"Scanning Board: {board.name} ({board.url})")
            
            for role in search_roles:
                self.stdout.write(f"  Searching for role: {role}")
                
                try:
                    response = requests.get(board.url, headers=headers, timeout=15)
                    soup = BeautifulSoup(response.text, 'html.parser')
                    links = soup.find_all('a', href=True)
                    
                    job_links = []
                    for link in links:
                        href = link['href']
                        full_url = href if href.startswith('http') else f"{board.url.rstrip('/')}/{href.lstrip('/')}"
                        if any(x in full_url.lower() for x in ["/job", "/post", "detail", "vacancy"]):
                            job_links.append(full_url)
                    
                    # LIMIT TO 4 JOBS PER ROLE
                    for url in list(set(job_links))[:4]:
                        self.stdout.write(f"    Checking: {url}")
                        self.process_job_url(url, board, role, headers)
                        time.sleep(1) 
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error on {board.url}: {e}"))

    def sync_cvs_from_folder(self):
        """Scans media/docs/cv/ for PDFs, extracts roles, and saves to DB."""
        cv_folder = os.path.join(settings.BASE_DIR, 'media', 'docs', 'cv')
        
        if not os.path.exists(cv_folder):
            self.stdout.write(self.style.WARNING(f"CV folder not found at {cv_folder}. Creating it..."))
            os.makedirs(cv_folder)
            return

        self.stdout.write(f"Checking for new CVs in: {cv_folder}")
        found_new = False

        for filename in os.listdir(cv_folder):
            # Ignore non-PDF files
            if not filename.lower().endswith('.pdf'):
                continue

            # Check if this file is already in the database
            if not CandidateCV.objects.filter(filename=filename).exists():
                name, role = parse_cv_filename(filename)
                
                if name and role:
                    CandidateCV.objects.create(
                        filename=filename,
                        full_name=name,
                        target_role=role
                    )
                    self.stdout.write(self.style.SUCCESS(f"  [+] Added CV to DB: {name} - Role: {role}"))
                    found_new = True
                else:
                    self.stdout.write(self.style.WARNING(f"  [!] Could not parse filename: {filename}. Ensure format is Name_Surname_Role_CV.pdf"))

        if not found_new:
            self.stdout.write("  [-] No new CVs found in folder.")

    def process_job_url(self, url, board, role, headers):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            emails = re.findall(EMAIL_REGEX, response.text)
            valid_emails = list(set([e.lower() for e in emails if not any(d in e.lower() for d in BLACKLIST)]))
            
            title_tag = soup.find('h1') or soup.find('h2')
            job_title = title_tag.get_text(strip=True) if title_tag else "N/A"
            
            for email in valid_emails[:4]:
                job_lead, created = JobLead.objects.get_or_create(
                    job_board=board,
                    job_url=url,
                    email_link=email,
                    defaults={
                        'cv_career': role,
                        'job_title': job_title,
                        'country': board.country
                    }
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f"      [+] Saved Lead: {email} for {role}"))
                else:
                    self.stdout.write(f"      [-] Duplicate: {email}")
                    
        except Exception as e:
            pass
import os
import sys
import django

# 1. SETUP DJANGO ENVIRONMENT
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from django.conf import settings
from django.core.management import call_command
from scrapping_engine.models import JobBoard, CandidateCV
from scrapping_engine.utils import parse_cv_filename

def sync_cvs_from_folder():
    """Reads media/docs/cv/ and adds new CVs to the database."""
    print("\n--- STEP 1: Syncing CVs ---")
    cv_folder = os.path.join(settings.BASE_DIR, 'media', 'docs', 'cv')
    
    if not os.path.exists(cv_folder):
        print(f"Creating CV folder at {cv_folder}")
        os.makedirs(cv_folder)
        return

    found_new = False
    for filename in os.listdir(cv_folder):
        if not filename.lower().endswith('.pdf'):
            continue
            
        if not CandidateCV.objects.filter(filename=filename).exists():
            name, role = parse_cv_filename(filename)
            if name and role:
                CandidateCV.objects.create(filename=filename, full_name=name, target_role=role)
                print(f"  [+] Added CV: {name} - Role: {role}")
                found_new = True
                
    if not found_new:
        print("  [-] No new CVs to add.")

def seed_job_boards():
    """Adds default job boards if the database is empty."""
    print("\n--- STEP 2: Seeding Job Boards ---")
    
    # EDIT THIS LIST WITH YOUR ACTUAL TARGET BOARDS
    default_boards = [
        {"name": "ZimbaJob", "url": "https://www.zimbajob.com/", "country": "Zimbabwe"},
        {"name": "VacancyMail", "url": "https://vacancymail.co.zw/", "country": "Zimbabwe"},
        {"name": "Classifieds", "url": "https://www.classifieds.co.zw/jobs", "country": "Zimbabwe"},
        {"name": "MyJobboard", "url": "https://example.com/jobs", "country": "Zimbabwe"},
    ]

    for board in default_boards:
        obj, created = JobBoard.objects.get_or_create(
            url=board['url'],
            defaults={'name': board['name'], 'country': board['country']}
        )
        if created:
            print(f"  [+] Added Board: {board['name']}")
        else:
            print(f"  [-] Board already exists: {board['name']}")

if __name__ == "__main__":
    print("🚀 Initializing Jobser Engine...")
    
    # 1. Get CVs
    sync_cvs_from_folder()
    
    # 2. Add Job Boards
    seed_job_boards()
    
    # 3. Trigger the Scraper
    print("\n--- STEP 3: Starting Scraper ---")
    try:
        call_command('scrape_boards')
    except Exception as e:
        print(f"[!] Scraper error: {e}")

    print("\n✅ Engine run complete.")
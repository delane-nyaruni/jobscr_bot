import os
import sys
import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dfms_backend.settings')
django.setup()

from scrapping_engine.models import JobBoard, IgnoredDomain, CandidateCV
from utilities.seed_utils import load_json
from utilities.cv_utils import parse_cv_filename
from django.conf import settings


def seed_boards():
    print("\n--- SEEDING JOB BOARDS ---")
    boards = load_json('jobboards.json')
    if not boards:
        print("  [-] No boards found in jobboards.json")
        return

    added = 0
    for board in boards:
        obj, created = JobBoard.objects.get_or_create(
            url=board['url'],
            defaults={
                'name': board.get('name', 'Unknown'),
                'country': board.get('country', 'Zimbabwe'),
                'is_active': True,
            }
        )
        if created:
            print(f"  [+] Added Board: {board['name']}")
            added += 1
        else:
            print(f"  [-] Already exists: {board['name']}")

    print(f"  [*] Total added: {added}")


def seed_blacklist():
    print("\n--- SEEDING BLACKLIST ---")
    domains = load_json('blacklist.json')
    if not domains:
        print("  [-] No domains found in blacklist.json")
        return

    added = 0
    for domain in domains:
        obj, created = IgnoredDomain.objects.get_or_create(domain=domain)
        if created:
            print(f"  [+] Added Domain: {domain}")
            added += 1

    print(f"  [*] Total added: {added}")


def sync_cvs_from_folder():
    print("\n--- SYNCING CVs FROM FOLDER ---")
    cv_folder = os.path.join(settings.BASE_DIR, 'media', 'docs', 'cv')

    if not os.path.exists(cv_folder):
        print(f"  [!] CV folder does not exist: {cv_folder}")
        return

    found_new = False
    for filename in os.listdir(cv_folder):
        if not filename.lower().endswith('.pdf'):
            continue

        if CandidateCV.objects.filter(filename=filename).exists():
            continue

        name, role = parse_cv_filename(filename)
        if name and role:
            CandidateCV.objects.create(filename=filename, full_name=name, target_role=role)
            print(f"  [+] Added CV: {name} - Role: {role}")
            found_new = True
        else:
            print(f"  [!] Could not parse filename: {filename}")

    if not found_new:
        print("  [-] No new CVs to add.")


if __name__ == "__main__":
    print("Initializing Seed Engine...")
    seed_boards()
    seed_blacklist()
    sync_cvs_from_folder()
    print("\nSeed run complete.")
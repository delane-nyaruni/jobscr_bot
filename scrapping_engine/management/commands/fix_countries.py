from django.core.management.base import BaseCommand
from scrapping_engine.models import JobBoard
from utilities.location_utils import infer_country_from_url

class Command(BaseCommand):
    help = 'Updates all JobBoards currently labeled as Zimbabwe to their correct country based on URL'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting country inference for job boards...")
        
        # Filter only boards that are currently mislabeled as Zimbabwe
        boards = JobBoard.objects.filter(country="Zimbabwe")
        count = 0
        
        for board in boards:
            new_country = infer_country_from_url(board.url)
            
            # If the inferred country is different (or even if it's still Zimbabwe but we want to be sure)
            if board.country != new_country:
                board.country = new_country
                board.save()
                count += 1
                self.stdout.write(f"  [+] Updated {board.name} -> {new_country}")
            else:
                self.stdout.write(f"  [-] {board.name} remains {new_country}")
                
        self.stdout.write(self.style.SUCCESS(f"Successfully updated {count} boards to their correct countries!"))
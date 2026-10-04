import subprocess
import sys
from django.core.management.base import BaseCommand
class Command(BaseCommand):
    class Colors:
        """ANSI escape sequences for terminal colors"""
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        RED = '\033[91m'
        RESET = '\033[0m'
        BOLD = '\033[1m'

    def run_check(settings_module=None):
        """
        Executes the Django deployment check command with color-coded results.
        """
        command = [sys.executable, "manage.py", "check", "--deploy"]
        
        if settings_module:
            command.append(f"--settings={settings_module}")
            print(f"{Colors.BOLD}--- Running Deployment Check with: {settings_module} ---{Colors.RESET}")
        else:
            print(f"{Colors.BOLD}--- Running Default Deployment Check ---{Colors.RESET}")

        try:
            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode == 0:
                # Success in Green
                print(f"{Colors.GREEN}PASSED: No critical deployment issues found.{Colors.RESET}")
                
                output = result.stdout if result.stdout else result.stderr
                if output:
                    # Warnings in Yellow (Django checks often include non-critical warnings here)
                    if "Warning" in output or "System check identified" in output:
                        print(f"{Colors.YELLOW}{output.strip()}{Colors.RESET}")
                    else:
                        print(output.strip())
            else:
                # Errors/Failure in Red
                print(f"{Colors.RED}FAILED: Deployment checks found issues.{Colors.RESET}")
                error_output = result.stderr if result.stderr else result.stdout
                print(f"{Colors.RED}{error_output}{Colors.RESET}")
                sys.exit(1)
                
        except FileNotFoundError:
            print(f"{Colors.RED}ERROR: manage.py not found.{Colors.RESET}")
            sys.exit(1)

    if __name__ == "__main__":
        # 1. Check with production settings
        run_check("dfms_backend.settings")
        
        print("-" * 40)
        
        # 2. Check with default settings
        run_check()

        print(f"\n{Colors.GREEN}{Colors.BOLD}All deployment checks made. See results above!{Colors.RESET}")
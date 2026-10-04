import subprocess
import os
import time

def open_cmd(command:str, cwd=None, title=None):
    """Open a new Windows CMD window and run a command."""
    cmd = f'start "{title or ""}" cmd /k "{command}"'
    subprocess.Popen(cmd, cwd=cwd, shell=True)

if __name__ == "__main__":
    print("Launching services on Windows...")

    project_root = os.path.dirname(os.path.abspath(__file__))

    # 1. Start Django Backend
    django_path = os.path.join(project_root, "") 
    django_cmd = " .venv/Scripts/activates "
    django_cmd = "  py manage.py runserver"

    print("starting backend server...")
    open_cmd(django_cmd, cwd=django_path, title="backend server")

    # 2. Wait a moment for the DB/Backend to initialize
    time.sleep(5)
    print("\nbackend server started")

   
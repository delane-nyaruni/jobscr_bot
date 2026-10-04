import subprocess
import sys

def run_command(command):
    """Run a shell command and print its output."""
    try:
        result = subprocess.run(command, shell=True, check=True, text=True, capture_output=True)
        print(result.stdout)
        if result.stderr:
            print("Errors:", result.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {command}")
        print(e.stderr)
        sys.exit(1)

def git_workflow(commit_message: str):
    print("adding changes locally...")
    run_command("git add .")

    print(f"committing changes with message: '{commit_message}'")
    run_command(f'git commit -m "{commit_message}"')
    print("commited to local repository successfully")
    print("staging for cloud repository...")

    print("pushing to remote github repository...")
    run_command("git push origin main")
    print("pushed to github online successfully")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backend_ci.py 'Your commit message'")
        sys.exit(1)
    
    message = sys.argv[1]
    git_workflow(message)
import os
import subprocess
from multiprocessing import Pool, cpu_count
from datetime import datetime

EXCLUDED_DIRS = {'.venv', 'venv', '__pycache__', 'build', 'dist', '.git'}
PYLINTRC_PATH = os.path.abspath(".pylintrc")  # Adjust if your config is elsewhere
LOG_FILE = "pylint_cleanup.log"

def remove_trailing_whitespace_from_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    with open(filepath, 'w', encoding='utf-8') as file:
        for line in lines:
            file.write(line.rstrip() + '\n')

def run_pylint_and_log(filepath):
    print(f"Linting: {filepath}")
    try:
        result = subprocess.run(
            ['pylint', '--rcfile', PYLINTRC_PATH, filepath],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False
        )
        return f"===== {filepath} =====\n{result.stdout}\n"
    except FileNotFoundError:
        return f"ERROR: Pylint not installed for file {filepath}\n"

def collect_python_files(directory):
    python_files = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                remove_trailing_whitespace_from_file(filepath)
                python_files.append(filepath)
    return python_files

def main():
    target_directory = "."  # Adjust as needed
    python_files = collect_python_files(target_directory)

    print(f"\nFound {len(python_files)} Python files to process.\n")

    with Pool(processes=cpu_count()) as pool:
        results = pool.map(run_pylint_and_log, python_files)

    with open(LOG_FILE, 'w', encoding='utf-8') as log_file:
        log_file.write(f"# Pylint run on {datetime.now()}\n\n")
        log_file.writelines(results)

    print(f"\nDone. Pylint output logged to: {LOG_FILE}")

if __name__ == "__main__":
    main()

import os
import time
import subprocess
import tempfile
import uuid
from pathlib import Path

WORKSPACE_DIR = Path('c:/DocWeave-A-Multi-Agent-System-for-Automated-Code-Documentation-Generation/workspace')
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
url = 'https://github.com/psf/requests.git'
dest = WORKSPACE_DIR / uuid.uuid4().hex

cmd = ['git', 'clone', '--progress', '--depth', '1', url, str(dest)]
env = os.environ.copy()
env['GIT_TERMINAL_PROMPT'] = '0'

with tempfile.NamedTemporaryFile(mode='w+', delete=False, dir=WORKSPACE_DIR) as temp_log:
    log_path = temp_log.name

print(f"Logging to {log_path}")
with open(log_path, 'w') as log_file:
    process = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT, env=env)

with open(log_path, 'r') as log_read:
    while process.poll() is None:
        lines = log_read.readlines()
        for line in lines:
            cleaned = line.replace('\r', '\n').strip()
            for part in cleaned.split('\n'):
                if part.strip():
                    print("GIT:", part.strip())
        time.sleep(0.1)

    lines = log_read.readlines()
    for line in lines:
        cleaned = line.replace('\r', '\n').strip()
        for part in cleaned.split('\n'):
            if part.strip():
                print("GIT:", part.strip())
                
print(f"Finished with {process.returncode}")
try:
    os.remove(log_path)
except:
    pass

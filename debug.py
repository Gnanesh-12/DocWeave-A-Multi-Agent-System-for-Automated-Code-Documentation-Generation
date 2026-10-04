import sys
import threading
import traceback
import time

def dump_threads():
    while True:
        time.sleep(2)
        with open("thread_dump.txt", "a") as f:
            f.write("=== THREAD DUMP ===\n")
            for th in threading.enumerate():
                f.write(f"Thread: {th.name}\n")
                stack = sys._current_frames().get(th.ident)
                if stack:
                    f.write("".join(traceback.format_stack(stack)))
            f.write("\n")

t = threading.Thread(target=dump_threads, daemon=True)
t.start()

import generate_docstrings
import sys
sys.argv = ["generate_docstrings.py", "--repo-path", "data/test_mixed_repo", "--test-mode", "placeholder"]
generate_docstrings.main()

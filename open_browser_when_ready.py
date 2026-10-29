"""Open the local UI only after the DRRAS HTTP server responds."""
import os
import sys
import time
import urllib.error
import urllib.request
import webbrowser

port = int(sys.argv[1]) if len(sys.argv) > 1 else 5055
url = f"http://127.0.0.1:{port}"
deadline = time.monotonic() + 90
while time.monotonic() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            if 200 <= response.status < 500:
                print(f"DRRAS is responding at {url}; opening the default browser.", flush=True)
                if os.environ.get("DRRAS_NO_BROWSER") != "1":
                    webbrowser.open(url)
                break
    except (OSError, urllib.error.URLError):
        time.sleep(1)
else:
    print(f"DRRAS did not become ready within 90 seconds. Open {url} after checking the server console.", flush=True)

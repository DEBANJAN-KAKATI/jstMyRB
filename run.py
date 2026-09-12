import os
import sys
import time
import socket
import threading
import webbrowser
import subprocess
import uvicorn

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from server import app

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', port)) == 0

def find_available_port(start_port: int = 8000, max_attempts: int = 20) -> int:
    for p in range(start_port, start_port + max_attempts):
        if not is_port_in_use(p):
            return p
    return start_port

def wait_for_server_and_open_browser(url: str, port: int, timeout: float = 35.0):
    """
    Polls the port until the server is actually accepting connections,
    then launches the browser via multiple fallback mechanisms.
    """
    print(f"⏳ Waiting for server to initialize at {url} ...")
    start = time.time()
    server_ready = False
    
    while time.time() - start < timeout:
        if is_port_in_use(port):
            server_ready = True
            break
        time.sleep(0.3)
    
    if server_ready:
        print(f"✅ Server is live! Opening browser at: {url}")
        time.sleep(0.6)
        opened = False
        # 1. Primary: Windows shell command (most reliable across all Win 10/11 browser setups)
        if sys.platform == "win32":
            try:
                subprocess.Popen(f'start "" "{url}"', shell=True)
                opened = True
            except Exception as e:
                print(f"Note on shell launch: {e}")

        # 2. Secondary fallback: standard library webbrowser
        if not opened:
            try:
                opened = webbrowser.open(url)
            except Exception as e:
                print(f"Note on browser launch: {e}")

        if not opened:
            print(f"\n👉 Please open your browser and navigate to: {url}\n")
    else:
        print(f"⚠️ Server initialization took longer than {timeout}s.")
        print(f"👉 Please open your browser and visit: {url}")

if __name__ == "__main__":
    print("=" * 65)
    print("🚀 Starting ResumeAgent Pro for Debanjan Kakati")
    print("=" * 65)

    # Automatically find an open port or use 8000
    chosen_port = find_available_port(8000)
    app_url = f"http://127.0.0.1:{chosen_port}"
    print(f"🔗 Local Web URL: {app_url}")

    # Launch watchdog thread that waits for the server to be listening
    threading.Thread(target=wait_for_server_and_open_browser, args=(app_url, chosen_port), daemon=True).start()

    try:
        uvicorn.run(app, host="127.0.0.1", port=chosen_port, reload=False, log_level="info")
    except KeyboardInterrupt:
        print("\nResumeAgent Pro stopped by user.")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        import traceback
        traceback.print_exc()
        try:
            input("\nPress Enter to exit...")
        except Exception:
            pass

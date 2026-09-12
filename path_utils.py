import os
import sys
import shutil

def get_base_dir() -> str:
    """
    Returns the application root directory.
    When running as a PyInstaller bundle, returns the folder containing the .exe
    (or sys._MEIPASS for read-only bundled assets).
    """
    if getattr(sys, 'frozen', False):
        # The directory containing the .exe executable
        return os.path.dirname(sys.executable)
    # The directory containing the script
    return os.path.dirname(os.path.abspath(__file__))

def get_bundle_dir() -> str:
    """
    Returns the bundled assets directory (checks local base dir first if static/
    exists next to .exe, otherwise sys._MEIPASS for PyInstaller onefile).
    """
    if getattr(sys, 'frozen', False):
        base = get_base_dir()
        if os.path.exists(os.path.join(base, "static")):
            return base
        if hasattr(sys, '_MEIPASS'):
            return sys._MEIPASS
        return base
    return get_base_dir()

def is_serverless() -> bool:
    """
    Detects if running on Vercel or other serverless environment.
    """
    return bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

def get_writable_dir(subfolder: str = "data") -> str:
    """
    Returns a guaranteed writable directory for SQLite databases, JSON profiles,
    and generated outputs. On Vercel / serverless or read-only environments,
    falls back to /tmp/resume_agent/<subfolder> and seeds initial profile data.
    """
    use_tmp = is_serverless()
    base = get_base_dir()
    target = os.path.join(base, subfolder)

    if not use_tmp:
        try:
            os.makedirs(target, exist_ok=True)
            test_file = os.path.join(target, ".perm_test")
            with open(test_file, "w") as f:
                f.write("1")
            os.remove(test_file)
        except (OSError, IOError, PermissionError):
            use_tmp = True

    if use_tmp:
        target = os.path.join("/tmp", "resume_agent", subfolder)
        os.makedirs(target, exist_ok=True)

    # Seed data files into writable directory if needed
    if subfolder == "data":
        source_data_dir = os.path.join(get_bundle_dir(), "data")
        if not os.path.exists(source_data_dir):
            source_data_dir = os.path.join(get_base_dir(), "data")

        for fname in ["profile_store.json", "resume_agent.db", "settings.json"]:
            dest_file = os.path.join(target, fname)
            src_file = os.path.join(source_data_dir, fname)
            if not os.path.exists(dest_file):
                if os.path.exists(src_file):
                    try:
                        shutil.copy2(src_file, dest_file)
                    except Exception as e:
                        print(f"Notice: could not copy {fname} to {dest_file}: {e}")
                elif fname == "profile_store.json":
                    example_src = os.path.join(source_data_dir, "profile_store.example.json")
                    if os.path.exists(example_src):
                        try:
                            shutil.copy2(example_src, dest_file)
                        except Exception as e:
                            print(f"Notice: could not copy profile_store.example.json to {dest_file}: {e}")

    return target

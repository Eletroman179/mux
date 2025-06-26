import os
import stat
import base64
import shutil
import requests
import tempfile
import pwd
import pty

def run_cmd(cmd, sudo=False) -> int:
    if sudo:
        cmd = ["sudo"] + cmd

    print(f"🔧 Running: {' '.join(cmd)}", flush=True)

    try:
        # pty.spawn takes care of all the terminal stuff for us
        exitcode = pty.spawn(cmd)
        return 0 if exitcode == 0 else 1
    except Exception as e:
        print(f"❌ Command failed: {' '.join(cmd)}")
        print(str(e))
        return 1

def get_real_user_home() -> str:
    # Get the username of the user who invoked sudo
    sudo_user = os.environ.get('SUDO_USER')
    if sudo_user:
        # Lookup the home directory of that user
        return pwd.getpwnam(sudo_user).pw_dir
    else:
        # Not running under sudo, use current user
        return os.path.expanduser("~")

def download(path: str, download_to="") -> tuple[int, str]:
    url = f'https://api.github.com/repos/Eletroman179/mux/contents/{path}'
    res = requests.get(url)

    if res.status_code == 200:
        data = res.json()
        content_base64 = data.get('content', '')
        if not content_base64:
            return (1, f"No content found for {path}")

        content = base64.b64decode(content_base64)

        download_to = os.path.expanduser(download_to or path)
        parent_dir = os.path.dirname(download_to)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        with open(download_to, 'wb') as file:
            file.write(content)

        return (0, f'Downloaded {path} successfully to {download_to}')
    elif res.status_code == 404:
        return (1, f'Error 404: {path} not found in repository.')
    else:
        return (1, f'Error {res.status_code}: Could not fetch content.')

def install_to_user_bin(script_path: str, name: str = "mux") -> tuple[int, str]:
    """
    Copies the script to /usr/bin with the given name and makes it executable.
    """
    target_dir = "/usr/bin"
    target_path = os.path.join(target_dir, name)

    try:
        shutil.copy(script_path, target_path)
        st = os.stat(target_path)
        # Set executable bits for user, group, and others
        os.chmod(target_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return (0, f"Installed {name} to {target_path}. Make sure /usr/bin is in your PATH.")
    except PermissionError:
        return (1, "Permission denied: You need to run this script as root (use sudo).")
    except Exception as e:
        return (1, f"Failed to install: {e}")


def download_and_install(path: str, name: str) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = os.path.join(tmpdir, name)
        status, msg = download(path, temp_path)
        if status == 0:
            install_status, install_msg = install_to_user_bin(temp_path, name)
            if install_status == 0:
                return (0, f"Installed successfully! msg: {install_msg}")
            else:
                return (1, install_msg)
        else:
            return (1, f"Download failed: {msg}")


def main() -> int:
    status, msg = download_and_install("code/main.py", "mux")
    if status != 0:
        print(f"Failed to install main.py: {msg}")
        return 1
    else:
        print(f"Main file downloaded successfully. msg: {msg}")

    # Ensure config directory exists
    config_dir = os.path.join(get_real_user_home(), ".config/mux")
    os.makedirs(config_dir, exist_ok=True)

    # Attempt to download config, warn if missing
    config_status, config_msg = download("code/config.conf", os.path.join(config_dir, "mux.conf"))
    if config_status != 0:
        print(f"Warning: Config file missing or not downloaded: {config_msg}")
    else:
        print(f"Config downloaded successfully. msg: {config_msg}")
    
    run_cmd(["nano", os.path.join(get_real_user_home(), ".config/mux/mux.conf")])
    return 0


if __name__ == '__main__':
    exit(main())

import os
import stat
import base64
import shutil
import requests
import tempfile

def download(path: str, download_to="") -> tuple[int, str]:
    """Downloads a file from github

    Args:
        path (str): The path to the github file
        download_to (str, optional): The file that it will download to. Defaults to "".

    Returns:
        tuple[int, str]: (0, success message) or (1, error message)
    """
    url = f'https://api.github.com/repos/Eletroman179/mux/contents/{path}'
    res = requests.get(url)

    if res.status_code == 200:
        data = res.json()
        content = base64.b64decode(data.get('content', ''))

        download_to = os.path.expanduser(download_to or path)
        os.makedirs(os.path.dirname(download_to), exist_ok=True) if os.path.dirname(download_to) else None

        # Write as binary to support all file types
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
        os.chmod(target_path, st.st_mode | stat.S_IEXEC)
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
                return (0, "Installed successfully!")
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

    # Attempt to download config, warn if missing
    config_status, config_msg = download("code/config.conf", os.path.expanduser("~/.config/mux/mux.conf"))
    if config_status != 0:
        print(f"Warning: Config file missing or not downloaded: {config_msg}")
    else:
        print(f"Config downloaded successfully. msg: {msg}")
    return 0

if __name__ == '__main__':
    exit(main())

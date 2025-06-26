import os
import stat
import base64
import shutil
import requests
import tempfile
from typing import Literal

def download(path: str, download_to="") -> tuple[Literal[0], str] | tuple[Literal[1], str]:
    """Downloads a file from github

    Args:
        path (str): The path to the github file
        download_to (str, optional): The file that it will download to. Defaults to "".

    Returns:
        tuple[Literal[0], str]: On success, returns (0, success message).
        tuple[Literal[1], str]: On failure, returns (1, error message).
    """
    url = f'https://api.github.com/repos/Eletroman179/mux/contents/{path}'
    res = requests.get(url)

    if res.status_code == 200:
        data = res.json()
        content = base64.b64decode(data.get('content', ''))

        # Handle default and ~ paths
        download_to = os.path.expanduser(download_to or path)

        # Make sure any parent folders exist
        os.makedirs(os.path.dirname(download_to), exist_ok=True) if os.path.dirname(download_to) else None

        with open(download_to, 'w') as file:
            file.write(content.decode('utf-8'))

        return (0, 'Downloaded successfully')
    else:
        return (1, f'Error {res.status_code}: Could not fetch content.')

def install_to_user_bin(script_path: str, name: str = "mux") -> None:
    """
    Copies the script to /usr/bin with the given name and makes it executable.
    
    :param script_path: Path to your script file
    :param name: Name of the executable to create in /usr/bin/ (default: 'mux')
    """
    target_dir = os.path.expanduser("/usr/bin")
    os.makedirs(target_dir, exist_ok=True)

    target_path = os.path.join(target_dir, name)

    shutil.copy(script_path, target_path)
    # Make file executable
    st = os.stat(target_path)
    os.chmod(target_path, st.st_mode | stat.S_IEXEC)

    print(f"Installed {name} to {target_path}. Make sure /usr/bin is in your PATH.")

def download_and_install(path: str, name: str) -> tuple[Literal[0], str] | tuple[Literal[1], str]:
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = os.path.join(tmpdir, name)
        
        status, msg = download(path, temp_path)
        if status == 0:
            install_to_user_bin(temp_path, name)
            return (0, "Installed successfully!")
        else:
            return (1, f"Download failed: {msg}")

def main() -> Literal[1] | Literal[0]:
    status, msg = download_and_install("code/main.py", "mux")
    if status != 0:
        print(f"Failed to install main.py: {msg}")
        return 1
    
    status, msg = download("code/config.conf", os.path.expanduser("~/.config/mux/mux.conf"))
    if status != 0:
        print(f"Failed to download config.conf: {msg}")
        return 1
    else:
        print("Config downloaded successfully.")
        return 0

if __name__ == '__main__':
    exit(main())
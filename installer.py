from time import sleep
from itertools import repeat
from io import StringIO
import os
import stat
import base64
import shutil
import requests
import tempfile
import pwd
import pty
import json

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

def pretty_inline_list(data, indent_level=4):
    indent = ' ' * indent_level
    items = [f"{indent}{json.dumps(item, separators=(',', ': '))}" for item in data]
    closing_indent = ' ' * (indent_level - 2)
    return "[\n" + ",\n".join(items) + "\n" + closing_indent + "]"

def dump_inline(config, path):
    tmp_config = dict(config)
    general = dict(tmp_config.get("general", {}))

    # Extract and remove fields you want to format inline
    pkg_managers = general.pop("PACKAGE_MANAGERS", [])
    update_cmd = general.pop("update_command", None)

    tmp_config["general"] = general  # remove inline fields temporarily

    # Pretty print the rest of config
    buffer = StringIO()
    json.dump(tmp_config, buffer, indent=2)
    result = buffer.getvalue()

    # Generate inline JSON for the two fields
    inline_pm = pretty_inline_list(pkg_managers, indent_level=4)
    inline_uc = json.dumps(update_cmd, separators=(',', ': ')) if update_cmd else "{}"

    # Prepare the inline lines to insert
    indent = "  "
    inline_lines = f'\n{indent}  "PACKAGE_MANAGERS": {inline_pm},\n{indent}  "update_command": {inline_uc},'

    # Inject inline fields back into "general"
    parts = result.split('"general": {')
    if len(parts) != 2:
        with open(path, "w") as f:
            json.dump(config, f, indent=2)
        return

    before = parts[0] + '"general": {'
    after = parts[1]
    final = before + inline_lines + after

    # Write final result
    with open(path, "w") as f:
        f.write(final)

def add_pm(path: str, name: str, install_flag: str, remove_flag: str, sudo: bool):
    pm = {
        "name": name, 
        "install_flag": install_flag, 
        "remove_flag": remove_flag, 
        "sudo": sudo
    }
        
    with open(path, "r") as f:
        config = json.load(f)

    config["general"]["PACKAGE_MANAGERS"].append(pm)

    dump_inline(config, path)
    
def change_uc(path: str, name: str, flag: str, sudo: bool):
    pm = {
        "name": name, 
        "flag": flag, 
        "sudo": sudo
    }
        
    with open(path, "r") as f:
        config = json.load(f)

    config["general"]["update_command"] = pm

    dump_inline(config, path)

def remove_all_pm(path: str):
    with open(path, "r") as f:
        config = json.load(f)

    config["general"]["PACKAGE_MANAGERS"] = []

    with open(path, "w") as f:
        json.dump(config, f, indent=2)

def prompt_input(prompt: str, ops=[]) -> str:
    print(f"=>> {prompt}")
    formatted_ops = " ".join(f"[{i[0].upper()}]{i[1:]}" for i in ops)
    if ops:
        print(f"=>> {formatted_ops}")
    usr = input("=>>")
        
    return usr

def prompt_pm() -> tuple[str, str, str, bool]:
    while True:
        raw = prompt_input("Enter package manager (format: name, install_flag, remove_flag, sudo [true/false])")
        parts = [p.strip() for p in raw.split(",")]

        if len(parts) != 4:
            print("❌ Please enter exactly 4 comma-separated values.")
            continue

        name, install_flag, remove_flag, sudo_str = parts

        if sudo_str.lower() not in ["true", "false"]:
            print("❌ 'sudo' must be 'true' or 'false'.")
            continue

        sudo = sudo_str.lower() == "true"
        return name, install_flag, remove_flag, sudo
    
def prompt_uc() -> tuple[str, str, bool]:
    while True:
        raw = prompt_input("Enter package manager (format: name, flag, sudo [true/false])")
        parts = [p.strip() for p in raw.split(",")]

        if len(parts) != 3:
            print("❌ Please enter exactly 3 comma-separated values.")
            continue

        name, flag, sudo_str = parts

        if sudo_str.lower() not in ["true", "false"]:
            print("❌ 'sudo' must be 'true' or 'false'.")
            continue

        sudo = sudo_str.lower() == "true"
        return name, flag, sudo

def main() -> int:
    usr_action = prompt_input("What type of install would you like?", ["Custom", "Default"])
    
    status, msg = download_and_install("code/main.py", "mux")
    if status != 0:
        print(f"Failed to install main.py: {msg}")
        return 1
    else:
        print(f"Main file downloaded successfully. msg: {msg}")

    # Ensure config directory exists
    config_dir = os.path.join(get_real_user_home(), ".config/mux")
    config_path = os.path.join(config_dir, "mux.conf")
    os.makedirs(config_dir, exist_ok=True)

    # Attempt to download config, warn if missing
    config_status, config_msg = download("code/config.conf", os.path.join(config_dir, "mux.conf"))
    if config_status != 0:
        print(f"Warning: Config file missing or not downloaded: {config_msg}")
    else:
        print(f"Config downloaded successfully. msg: {config_msg}")
    
    num_pkg_magr = 0
    
    if usr_action.lower() == "c":
        if prompt_input("Would you like to change the package managers?", ["Yes", "No"]).lower() == "y":
            remove_all_pm(config_path)
            
            # Get how many package managers to add
            while True:
                num = prompt_input("How many package managers would you like to add?")
                if num.isdigit():
                    num_pkg_magr = int(num)
                    break
                print("Invalid number.")
            
            for _ in repeat(0, num_pkg_magr):
                name, install_flag, remove_flag, sudo = prompt_pm()
                add_pm(config_path, name, install_flag, remove_flag, sudo)
        
        if prompt_input("Would you like to change the update command?", ["Yes", "No"]).lower() == "y":
            name_update, flag_update, sudo_update = prompt_uc()
            change_uc(config_path, name_update, flag_update, sudo_update)
            
    print("Running nano in 1 second")
    sleep(1)    
    run_cmd(["nano", os.path.join(get_real_user_home(), ".config/mux/mux.conf")])
    return 0


if __name__ == '__main__':
    exit(main())
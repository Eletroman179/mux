#!/usr/bin/env python3

import sys
import os
import subprocess
import shutil
import json
import base64
import requests
import importlib.util
import sysconfig
import termios
import tty
import pty
import ast
import configparser
from typing import Any


# Sorry
def get_config_path() -> str:
    config_dir = os.path.expanduser("~/.config/mux")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "mux.conf")


def unescape_ansi_quoted(s: str) -> str:
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    return s.encode("utf-8").decode("unicode_escape")


def try_convert(value: str) -> float | int | str | bool:
    value = unescape_ansi_quoted(value)

    v = value.lower()
    if v in ("true", "yes", "on"):
        return True
    if v in ("false", "no", "off"):
        return False
    try:
        if "." in value:
            return float(value)
        else:
            return int(value)
    except ValueError:
        return value


def load_config() -> dict:
    path = get_config_path()
    config = configparser.ConfigParser()
    config.optionxform = str  # type: ignore
    if os.path.exists(path):
        config.read(path)
        result = {}
        for section in config.sections():
            result[section] = {k: try_convert(v) for k, v in config[section].items()}
        if config.defaults():
            result["DEFAULT"] = {
                k: try_convert(v) for k, v in config.defaults().items()
            }
        return result
    return {}


config = load_config()

colors = config.get("colors", {})

GREEN = colors.get("GREEN", "")
YELLOW = colors.get("YELLOW", "")
RED = colors.get("RED", "")
BLUE = colors.get("BLUE", "")
RESET = colors.get("RESET", "")

general = config.get("general", {})

editor = general.get("editor")
show_warning = general.get("show_warning")
package_managers_str = general.get("PACKAGE_MANAGERS")

if package_managers_str:
    import ast

    PACKAGE_MANAGERS = ast.literal_eval(package_managers_str)
else:
    print("PACKAGE_MANAGERS not found in config.")

SUPPORTED_ACTIONS = [
    "install",
    "remove",
    "update",
    "search",
    "find",
    "build",
    "config",
    "help",
    "download",
]


def print_color(text: str, color) -> None:
    print(f"{color}{text}{RESET}")


def help() -> None:
    help_mesage = """
    useage: mux <command> [<args>]
    
    install          install a program
    remove           uninstall a program
    update           updates a program
    search | find    finds a program
    build            builds a program using a muxFile
    """
    print_color(help_mesage, YELLOW)


def read_key() -> str | Any:
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch1 = sys.stdin.read(1)
        if ch1 == "\x1b":
            ch2 = sys.stdin.read(1)
            ch3 = sys.stdin.read(1)
            return ch1 + ch2 + ch3
        elif ch1 == "\x03":
            raise KeyboardInterrupt()
        else:
            return ch1
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def draw_menu(items: list, start=0) -> str:
    longest = max(len(x) for x in items)
    selected = start
    print("\n" * len(items), end="")

    while True:
        print(f"\x1b[{len(items)}F", end="")  # move up to top of menu
        for i, item in enumerate(items):
            padded_item = item.center(longest)
            if i == selected:
                print(f"\033[7m[*] {padded_item}\033[0m")
            else:
                print(f"[ ] {padded_item}")

        key = read_key()

        if key == "\x1b[A":
            selected = (selected - 1) % len(items)
        elif key == "\x1b[B":
            selected = (selected + 1) % len(items)
        elif key in ("\r", "\n"):
            # Redraw menu with only the selected item marked with [*], no highlight
            print(f"\x1b[{len(items)}F", end="")  # move to top
            for i, item in enumerate(items):
                padded_item = item.center(longest)
                prefix = "[*]" if i == selected else "[ ]"
                print(f"{prefix} {padded_item}")
            return items[selected]


def run_cmd(cmd, sudo=False) -> int:
    if sudo:
        cmd = ["sudo"] + cmd

    print(f"🔧 Running: {' '.join(cmd)}", flush=True)

    try:
        # pty.spawn takes care of all the terminal stuff for us
        exitcode = pty.spawn(cmd)
        return 0 if exitcode == 0 else 1
    except Exception as e:
        print_color(f"❌ Command failed: {' '.join(cmd)}", RED)
        print_color(str(e), RED)
        return 1


def is_installed(pkg) -> bool:
    for manager in PACKAGE_MANAGERS:
        if shutil.which(manager):
            if manager == "flatpak":
                result = subprocess.run(
                    ["flatpak", "list"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                if pkg.lower() in result.stdout.lower():
                    return True
            elif manager == "pacman":
                result = subprocess.run(
                    [manager, "-Q", pkg], stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                if result.returncode == 0:
                    return True
            else:
                result = subprocess.run(
                    [manager, "-Qi", pkg],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                if result.returncode == 0:
                    return True
    return False


def is_up_to_date(pkg) -> bool:
    """Check if the package is up-to-date (pacman only)."""
    result = subprocess.run(["pacman", "-Qi", pkg], capture_output=True, text=True)
    if result.returncode != 0:
        print_color(f"❌ {pkg} is not installed.", RED)
        return False

    installed_version = None
    for line in result.stdout.splitlines():
        if line.startswith("Version"):
            installed_version = line.split(":", 1)[1].strip()
            break

    if not installed_version:
        print_color(f"❌ Could not determine installed version of {pkg}.", RED)
        return False

    result = subprocess.run(["pacman", "-Si", pkg], capture_output=True, text=True)
    if result.returncode != 0:
        print_color(f"❌ Could not check updates for {pkg}.", RED)
        return False

    available_version = None
    for line in result.stdout.splitlines():
        if line.startswith("Version"):
            available_version = line.split(":", 1)[1].strip()
            break

    if not available_version:
        print_color(f"❌ Could not determine available version of {pkg}.", RED)
        return False

    if installed_version == available_version:
        print_color(
            f"{pkg} is up-to-date (installed: {installed_version}, available: {available_version}).",
            GREEN,
        )
        return True
    else:
        print_color(
            f"{pkg} is not up-to-date (installed: {installed_version}, available: {available_version}).",
            YELLOW,
        )
        return False


def search_pkg(pkg) -> None:
    """Search for a package in available package managers."""
    for manager in PACKAGE_MANAGERS:
        if shutil.which(manager):
            print_color(f'🔍 Using {manager} to search for "{pkg}"...', GREEN)
            result = subprocess.run(
                [manager, "-Ss", pkg], capture_output=True, text=True
            )
            for line in result.stdout.splitlines():
                if "/" in line.split():
                    print(f"\033[1;34m{line}\033[0m")
                else:
                    print(line)
            return
    print_color("❌ No supported package manager found (pacman, yay, paru).", RED)


def edit_config() -> None:
    subprocess.run([editor, get_config_path()], check=False)


# ────────────────────────────────────────────────────────────────────────────────
# DOWNLOAD RELATED FUNCTIONS
# ────────────────────────────────────────────────────────────────────────────────


def get_stdlib_modules():
    stdlib_path = sysconfig.get_paths()["stdlib"]
    modules = set()

    for root, dirs, files in os.walk(stdlib_path):
        for name in files:
            if name.endswith(".py"):
                rel_path = os.path.relpath(os.path.join(root, name), stdlib_path)
                mod = rel_path.replace("/", ".").replace("\\", ".").removesuffix(".py")
                modules.add(mod.split(".")[0])
        for name in dirs:
            modules.add(name.split(".")[0])

    return modules


def get_imports(file_path):
    with open(file_path, "r") as f:
        tree = ast.parse(f.read())

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                imports.add(n.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
    return imports


def detect_stdlib_imports(file_path):
    stdlib = get_stdlib_modules()
    imports = get_imports(file_path)

    result = {}
    for imp in imports:
        result[imp] = imp in stdlib

    return result


def detect_imports(path) -> list[str]:
    imports = []
    for name, is_std in detect_stdlib_imports(path).items():
        if is_std:
            imports.append(name)
    return imports


def pip_install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])


def download_imports(path):
    imports = detect_imports(path)
    for package in imports:
        pip_install(package)


# ────────────────────────────────────────────────────────────────────────────────
# BUILD RELATED FUNCTIONS
# ────────────────────────────────────────────────────────────────────────────────


def pacman_installed(pkg) -> bool:
    result = subprocess.run(
        ["pacman", "-Qi", pkg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return result.returncode == 0


def pip_installed(pkg) -> bool:
    result = subprocess.run(
        ["pip", "show", pkg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return result.returncode == 0


def is_stdlib_module(name) -> bool:
    try:
        spec = importlib.util.find_spec(name)
        if spec is None:
            return False
        if spec.origin == "built-in":
            return True
        stdlib_path = sysconfig.get_paths()["stdlib"]
        if spec.origin and spec.origin.startswith(stdlib_path):
            return True
        return False
    except ModuleNotFoundError:
        return False


def view(owner, repo, path, branch="main", token=None) -> str | int:
    """
    Fetch and return content of a file from GitHub via API.
    Returns the decoded text, or an integer HTTP status code if not 200.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {}
    params = {"ref": branch}
    if token:
        headers["Authorization"] = f"token {token}"

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        if data.get("type") == "file":
            return base64.b64decode(data["content"]).decode()
    return response.status_code


def handle_git(repo_url, file, token=None) -> None:
    """
    Fetch and run /mux/installer.py from a GitHub repo via the API. Never clones.
    """
    try:
        if repo_url.startswith("git@github.com:"):
            path = repo_url.split("git@github.com:")[1]
        elif repo_url.startswith("https://github.com/"):
            path = repo_url.split("github.com/")[1]
        else:
            print_color(f"[Error] Unsupported repo URL format: {repo_url}", RED)
            return

        if path.endswith(".git"):
            path = path[:-4]

        owner, repo_name = path.split("/")[:2]

    except Exception as e:
        print_color(f"[Error] Could not parse repo URL '{repo_url}': {e}", RED)
        return

    content = view(owner, repo_name, file, token=token)
    if isinstance(content, int):
        print_color(
            f"[Error] /mux/installer.py not found or failed to fetch. status_code: {content}",
            RED,
        )
    else:
        print_color("Running /mux/installer.py...", GREEN)
        exec(content, globals())


def apply_muxfile(path, token=None) -> None:
    """
    Read a JSON muxFile and process pacman, pip, git packages.
    For git entries, run handle_git().
    """
    with open(path) as f:
        muxfile: dict = json.load(f)
    required = ["packages", "docs"]

    # run checks to verify the muxfile
    for key in required:
        if key not in muxfile:
            print_color(f"[ERROR] {path} is missing required key: '{key}'", RED)
            return

    if show_warning:
        # confirm the user input
        print_color(
            f"[WARNING] If you do not trust this file, DO NOT install anything.", YELLOW
        )
        print_color(
            f"[WARNING] Please review the documentation before proceeding.", YELLOW
        )

    print_color(f"[INFO]    Docs: {muxfile['docs']}\n", YELLOW)
    print_color(":: Proceed with installation?", BLUE)
    inp = False if draw_menu(["Yes", "No"]) == "No" else True

    if not inp:
        print_color("\n[INFO] User aborted installation", RED)
        return

    # install the mufile
    for item in muxfile["packages"]:
        if item["type"] == "pacman":
            pkg = item["name"]
            if pacman_installed(pkg):
                print_color(f"[skip] pacman package '{pkg}' already installed", YELLOW)
            else:
                run_cmd(["pacman", "-S", pkg], sudo=True)

        elif item["type"] == "flatpak":
            for app in item["apps"]:
                if is_installed(app):
                    print_color(f"[skip] flatpak app '{app}' already installed", YELLOW)
                else:
                    run_cmd(["flatpak", "install", "-y", "flathub", app])

        elif item["type"] == "pip":
            for mod in item["modules"]:
                if is_stdlib_module(mod):
                    print_color(
                        f"[skip] '{mod}' is built-in or stdlib module, no pip install needed",
                        YELLOW,
                    )
                elif pip_installed(mod):
                    print_color(f"[skip] pip package '{mod}' already installed", YELLOW)
                else:
                    run_cmd(["pip", "install", mod])

        elif item["type"] == "git":
            handle_git(item["repo"], item["file"], token=token)

        else:
            print_color(f"[skip] unknown package type '{item['type']}'", YELLOW)


# ────────────────────────────────────────────────────────────────────────────────
# MAIN ENTRYPOINT
# ────────────────────────────────────────────────────────────────────────────────


def main() -> None:
    if len(sys.argv) < 2:
        print_color("Use 'mux help' to view the full list of all the commands", RED)
        sys.exit(1)

    action = sys.argv[1]
    pkg = sys.argv[2] if len(sys.argv) > 2 else ""

    if action not in SUPPORTED_ACTIONS:
        print_color(f"Unknown action: {action}", RED)
        print_color("Use 'mux help' to view the full list of all the commands", RED)
        sys.exit(1)

    if action == "build":
        # If you want to specify a different file, pass as second argument
        mux_path = "muxFile" if not pkg else pkg
        if os.path.exists(mux_path):
            apply_muxfile(mux_path)
        else:
            print_color(f"No muxFile found at '{mux_path}'", RED)
        return

    elif action == "help":
        help()

    elif action == "config":
        edit_config()

    elif action in ["search", "find"]:
        if not pkg:
            print_color("❌ Please provide a package name to search.", RED)
            sys.exit(1)
        search_pkg(pkg)
    elif action == "download":
        download_imports(pkg)
    else:
        # install, remove, update
        perform_action(action, pkg)


def perform_action(action, pkg) -> None:
    """
    Perform install/remove/update using available package managers.
    """
    for manager in PACKAGE_MANAGERS:
        if not shutil.which(manager):
            continue

        print_color("=" * 60, GREEN)
        print_color(f"Trying to {action} with {manager}", GREEN)

        sudo = manager == "pacman"
        opts = []

        if action == "install":
            if is_installed(pkg):
                print_color(f"{pkg} is already installed.", YELLOW)
                if manager != "flatpak" and is_up_to_date(pkg):
                    print_color(
                        f"{pkg} is already up-to-date. Skipping installation.", YELLOW
                    )
                    return
                else:
                    return

            if manager == "flatpak":
                opts = ["install", "-y", "flathub", pkg]
            else:
                opts = ["-S", pkg]

        elif action == "remove":
            if manager == "flatpak":
                opts = ["uninstall", "-y", pkg]
            else:
                opts = ["-R", pkg]

        elif action == "update":
            if manager == "flatpak":
                opts = ["update", "-y"]
            elif not pkg:
                opts = ["-Syu"]
            elif is_up_to_date(pkg):
                print_color(
                    f"{pkg} is already up-to-date. There is nothing to do.", YELLOW
                )
                return
            else:
                opts = ["-S", pkg]

        if run_cmd([manager] + opts, sudo=sudo) == 0:
            print_color("=" * 60, GREEN)
            return
    print_color("=" * 60, GREEN)
    print_color(
        "❌ No supported package manager succeeded (pacman, yay, paru, flatpak).                        :(",
        RED,
    )


if __name__ == "__main__":
    main()
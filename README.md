# mux

**mux** is a universal Linux package wrapper that lets you manage software from multiple sources (like `pacman`, `pip`, `git`, etc.) with a unified interface.

---

## 📥 Installation

Install `mux` by running the official installer script:

```bash
curl -O https://raw.githubusercontent.com/Eletroman179/mux/main/installer.py
sudo python installer.py
```

> ⚙️ The installer supports **interactive setup**, allowing you to configure your preferred package manager(s) and update command.

---

## ⚙️ Installer Features

During setup, you can choose between:

* **\[D]efault** setup: Uses the default config with `pacman`.
* **\[C]ustom** setup:

  * Choose your own package manager(s)
  * Define install/remove flags and whether each command needs `sudo`
  * Set your own update command

You can always manually edit the config at:

```bash
~/.config/mux/mux.conf
```

---

## 📦 Features

* ✅ Install packages from multiple backends
* 🔍 Search or find packages
* 🧼 Remove packages
* 🔄 Update packages
* 🛠️ Build from `muxFile` (JSON-based build file)

---

## 🧪 muxFile Example

```json
{
  "packages": [
    {
      "type": "pacman",
      "name": "btop"
    },
    {
      "type": "pip",
      "modules": ["requests", "numpy"]
    },
    {
      "type": "git",
      "repo": "git@github.com:Eletroman179/mux_test.git",
      "file": "installer.py"
    }
  ],
  "docs": "https://github.com/Eletroman179/mux_test/blob/main/README.md"
}
```

---

## 💡 Usage

```bash
mux install <package>     # install a package
mux remove <package>      # uninstall a package
mux update <package>      # update a package
mux search <package>      # search for a package
mux find <package>        # alias for search
mux build                 # build packages from muxFile
```

---

## 🌐 Supported Package Types

| Type     | Description                            |
| -------- | -------------------------------------- |
| `pacman` | Arch Linux package manager             |
| `pip`    | Python packages                        |
| `git`    | Clone and run install scripts from Git |

> You can configure other managers like `dnf`, `apt`, `yay`, `flatpak`, etc. using the custom installer mode.

---

## 🛠 Config Location

After installation, the config file is saved here:

```bash
~/.config/mux/mux.conf
```

You can manually edit this file to:

* Add or remove package managers
* Change update command
* Fine-tune `mux` behavior

---

## 📄 License

MIT License — see [LICENSE](./LICENSE)

---

## 👤 Author

**[@Eletroman179](https://github.com/Eletroman179)**

---

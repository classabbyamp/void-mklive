#!/usr/bin/python3

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass, field, fields
from itertools import chain, zip_longest
from pathlib import Path
from sys import stderr
from typing import Any


# dialog colors
BLACK=r"\Z0"
RED=r"\Z1"
GREEN=r"\Z2"
YELLOW=r"\Z3"
BLUE=r"\Z4"
MAGENTA=r"\Z5"
CYAN=r"\Z6"
WHITE=r"\Z7"
BOLD=r"\Zb"
REVERSE=r"\Zr"
UNDERLINE=r"\Zu"
RESET=r"\Zn"

MENULABEL=(f"{BOLD}Use UP and DOWN keys to navigate menus. "
           f"Use TAB to switch between buttons and ENTER to select.{RESET}")
MENUSIZE=["14", "60", "0"]
INPUTSIZE=["8", "60"]
MSGBOXSIZE=["8", "70"]
YESNOSIZE=INPUTSIZE
WIDGET_SIZE=["10", "70"]


def dialog(*args) -> tuple[int, str]:
    proc = subprocess.run(["dialog", "--colors", "--keep-tite", "--no-shadow", "--no-mouse",
                    "--backtitle", f"{BOLD}{WHITE}Void Linux Installer -- https://www.voidlinux.org ({VERSION})",
                    "--cancel-label", "Back", "--aspect", "20", *args],
                   stderr=subprocess.PIPE, text=True)
    return (proc.returncode, proc.stderr)


def infobox(*args, title: str = ""):
    subprocess.run(["dialog", "--colors", "--no-shadow", "--no-mouse",
                    "--backtitle", f"{BOLD}{WHITE}Void Linux Installer -- https://www.voidlinux.org ({VERSION})",
                    "--aspect", "20", "--title", title, "--infobox", *args],
                   stderr=subprocess.PIPE, text=True)


@dataclass(init=False)
class State:
    # facts
    arch: str
    libc: str
    efi: bool
    efi_bits: int | None = None

    # conf-ish
    target_dir: Path = Path("/mnt/target")
    log: Path = Path("/dev/tty8")
    conf_file: Path = Path("/tmp/.void-installer.json")

    # state
    done: dict[str, bool] = field(default_factory=dict)

    def __init__(self) -> None:
        self.arch = os.uname().machine
        self.libc = "glibc" # TODO: inspect xbps-uhelper arch
        self.efi =  Path("/sys/firmware/efi/systab").exists()
        if self.efi:
            try:
                self.efi_bits = int(Path("/sys/firmware/efi/fw_platform_size").read_text())
            except ValueError:
                self.efi_bits = None

    @property
    def grub_target(self) -> str:
        if self.efi:
            match self.arch:
                case "x86_64" | "i686":
                    if self.efi_bits == 32:
                        return "i386-efi"
                    elif self.efi_bits == 64:
                        return "x86_64-efi"
                case "aarch64":
                    if self.efi_bits == 64:
                        return "arm64-efi"
        else:
            match self.arch:
                case "x86_64" | "i686":
                    return "i386-pc"
        raise ValueError(f"unknown target for bootloader: {self.arch} ({self.efi_bits} bits)")

    @property
    def default_item(self) -> str | None:
        for k, v in self.done.items():
            if not v:
                return k


@dataclass
class Config:
    # menu_keymap
    keymap: str | None = None
    # menu_source
    source: str | None = None
    # menu_hostname
    hostname: str | None = None
    # menu_timezone
    timezone: str | None = None
    # menu_rootpassword
    root_password: str | None = None

    @classmethod
    def load(cls):
        with STATE.conf_file.open() as fp:
            try:
                raw = json.load(fp)
            except json.JSONDecodeError:
                raw = {}
        return cls(**raw)

    def dump(self):
        with STATE.conf_file.open("w") as fp:
            json.dump(asdict(self), fp, indent=2)

    def update(self, key: str, value: Any):
        setattr(self, key, value)
        self.dump()

    def __str__(self) -> str:
        out = []
        for f in fields(self):
            out.append(f"{f.name} = {getattr(self, f.name)}")
        return "\n".join(out)


VERSION = "@@MKLIVE_VERSION@@"
STATE = State()
# load conf from file if it exists
if STATE.conf_file.is_file():
    CONF = Config.load()
# otherwise, start from scratch
else:
    CONF = Config()


entries = {
    "Keyboard": "Set system keyboard",
    "Network": "Set up the network",
    "Source": "Set source installation",
    "Mirror": "Select XBPS mirror",
    "Hostname": "Set system hostname",
    "Locale": "Set system locale",
    "Timezone": "Set system time zone",
    "RootPassword": "Set system root password",
    "UserAccount": "Set primary user name and password",
    "BootLoader": "Set disk to install bootloader",
    "Partition": "Partition disk(s)",
    "Filesystems": "Configure filesystems and mount points",
    "Install": "Start installation with saved settings",
    "Exit": "Exit installation",
}

if STATE.libc == "musl":
    del entries["Locale"]

STATE.done = {k: False for k in entries}


def menu_keymap():
    keymaps = sorted(
        p.name.removesuffix(".map.gz")
        for p in Path("/usr/share/kbd/keymaps").rglob("*.map.gz", case_sensitive=False)
        if p.is_file(follow_symlinks=False)
    )

    if CONF.keymap:
        def_itm = ["--default-item", CONF.keymap]
    else:
        def_itm = []

    ret, ans = dialog("--title", " Select your keymap ", *def_itm, "--menu", MENULABEL, "14", "70", "14",
                         *(chain.from_iterable(zip_longest(keymaps, [], fillvalue=""))))
    if ret == 0:
        CONF.update("keymap", ans)
        if CONF.keymap:
            subprocess.run(["loadkeys", CONF.keymap])
        STATE.done["Keyboard"] = True


def set_keymap():
    if Path("/etc/vconsole.conf").is_file():
        # TODO: sed KEYMAP in vconsole.conf
        ...
    else:
        # TODO: sed KEYMAP in rc.conf
        ...


def test_network() -> bool:
    ...


def menu_network():
    ...


def menu_source():
    match CONF.source:
        case "local":
            def_itm = ["--default-item", "Local"]
        case "net":
            def_itm = ["--default-item", "Network"]
        case _:
            def_itm = []

    ret, ans = dialog("--title", " Select installation source ", *def_itm, "--menu", MENULABEL, "8", "70", "0",
                      "Local", "Copy from ISO image",
                      "Network", "Base system only, downloaded from repository")

    if ret == 0:
        match ans:
            case "Local":
                CONF.update("source", "local")
            case "Network":
                CONF.update("source", "net")
                if "network" not in STATE.done:
                    if not test_network():
                        menu_network()
        STATE.done["Source"] = True


def menu_mirror():
    # TODO: stderr to log
    if shutil.which("xmirror"):
        proc = subprocess.run("xmirror")
        if proc.returncode == 0:
            STATE.done["Mirror"] = True
    else:
        dialog("--title", f"{BOLD} Mirror Setup {RESET}",
               "--msgbox", f"{BOLD}xmirror{RESET} is not available, using the default mirror.",
               *MSGBOXSIZE)
        STATE.done["Mirror"] = True


def menu_hostname():
    ret, ans = dialog("--inputbox", "Set the machine hostname:", *INPUTSIZE,
                      CONF.hostname if CONF.hostname else "")
    if ret == 0:
        CONF.update("hostname", ans.strip())


def menu_locale():
    ...


def menu_timezone():
    areas=["Africa", "America", "Antarctica", "Arctic", "Asia", "Atlantic",
           "Australia", "Europe", "Indian", "Pacific"]

    if CONF.timezone:
        area, _, location = CONF.timezone.partition("/")
        location = location.replace("_", " ")
    else:
        area = None
        location = None

    while True:
        if area:
            def_itm = ["--default-item", area]
        else:
            def_itm = []
        ret, ans = dialog("--title", " Select area ", *def_itm, "--menu", MENULABEL, "19", "51", "19",
                          *(chain.from_iterable(zip_longest(areas, [], fillvalue=""))))
        if ret == 0 and ans:
            area = ans
            locations = sorted(str(v).removeprefix(f"/usr/share/zoneinfo/{area}/").replace("_", " ")
                               for v in (Path("/usr/share/zoneinfo") / area).rglob("*"))
            if location in locations:
                def_itm = ["--default-item", location]
            else:
                def_itm = []
            ret, ans = dialog("--title", f" Select location ({area}) ", *def_itm, "--menu", MENULABEL, "19", "51", "19",
                              *(chain.from_iterable(zip_longest(locations, [], fillvalue=""))))
            if ret == 0 and ans:
                CONF.update("timezone", f"{area}/{ans.replace(" ", "_")}")
                STATE.done["Timezone"] = True
                return

        elif ret != 0:
            return


def menu_rootpassword():
    passwd1 = None
    passwd2 = None

    while True:
        desc = "Enter the root password"
        if passwd1 and not passwd2:
            desc += " (again)"

        ret, ans = dialog("--insecure", "--passwordbox", desc, *INPUTSIZE)

        if ret == 0:
            if not passwd1:
                passwd1 = ans
            else:
                passwd2 = ans

            if passwd1 and passwd2:
                if passwd1 != passwd2:
                    passwd1 = None
                    passwd2 = None
                    dialog("--msgbox", "Passwords do not match! Please enter again.", *MSGBOXSIZE)
                    continue
                else:
                    break

    CONF.update("root_password", passwd1)
    STATE.done["RootPassword"] = True


def menu_useraccount():
    ...


def menu_bootloader():
    ...


def menu_partitions():
    ...


def menu_filesystems():
    ...


def menu_install():
    ...


def menu():
    ret, ans = dialog("--default-item", STATE.default_item,
                      "--extra-button", "--extra-label", "Settings",
                      "--title", " Void Linux installation menu ",
                      "--menu", MENULABEL, "10", "70", "0",
                      *(chain.from_iterable(entries.items())))

    if ret == 3:
        dialog("--title", "Saved settings for installation", "--msgbox",
               str(CONF), "16", "80")
        return
    elif ret != 0:
        # TODO: better error/way to break out of loop
        raise StopIteration

    match ans:
        case "Keyboard":
            menu_keymap()
        case "Network":
            menu_network()
        case "Source":
            menu_source()
        case "Mirror":
            menu_mirror()
        case "Hostname":
            menu_hostname()
        case "Locale":
            menu_locale()
        case "Timezone":
            menu_timezone()
        case "RootPassword":
            menu_rootpassword()
        case "UserAccount":
            menu_useraccount()
        case "BootLoader":
            menu_bootloader()
        case "Partition":
            menu_partitions()
        case "Filesystems":
            menu_filesystems()
        case "Install":
            menu_install()
        case "Exit":
            # TODO: better escape
            raise StopIteration
        case _:
            ret, _ = dialog("--yesno", "Abort Installation?", *YESNOSIZE)
            if ret == 0:
                # TODO: better escape
                raise StopIteration


def main():
    if shutil.which("dialog") is None:
        print("ERROR: missing dialog command, exiting...", file=stderr)
        exit(1)

    # TODO
    # if os.geteuid() != 0:
    #     print("ERROR: void-installer must run as root, exiting...", file=stderr)
    #     exit(1)

    # disable printk
    try:
        Path("/proc/sys/kernel/printk").write_text("0")
    except PermissionError:
        pass

    dialog("--title", f"{BOLD}{RED} Enter the void ... {RESET}",
           "--msgbox", (
                r"\nWelcome to the Void Linux installation. A simple and minimal "
                "Linux distribution made from scratch and built from the source package tree "
                r"available for XBPS, a new alternative binary package system.\n\n"
                "The installation should be pretty straightforward. "
                "If you are in trouble please join us at "
                fr"{BOLD}#voidlinux{RESET} on {BOLD}irc.libera.chat{RESET}.\n\n"
                fr"{BOLD}https://www.voidlinux.org{RESET}\n\n"
            ), "16", "80")

    while True:
        try:
            menu()
        except StopIteration:
            break


if __name__ == "__main__":
    main()

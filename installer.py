#!/usr/bin/python3

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass, fields
from itertools import chain
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
    conf_file: Path = Path("/tmp/.void-installer.conf")

    # state
    default_item: str | None = None

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


@dataclass
class Config:
    hostname: str | None = None

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


def menu():
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

    if STATE.default_item is None:
        STATE.default_item = "Keyboard"

    ret, answer = dialog("--default-item", STATE.default_item,
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

    match answer:
        case "Keyboard":
            ...
        case "Network":
            ...
        case "Source":
            ...
        case "Mirror":
            ...
        case "Hostname":
            ...
        case "Locale":
            ...
        case "Timezone":
            ...
        case "RootPassword":
            ...
        case "UserAccount":
            ...
        case "BootLoader":
            ...
        case "Partition":
            ...
        case "Filesystems":
            ...
        case "Install":
            ...
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

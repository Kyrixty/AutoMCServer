import threading
import datetime
import textwrap
import platform
import pyngrok
import json
import sys
import os

from typing import List
from colorama import init, Fore, Back
from pyngrok import ngrok
from pydantic import BaseModel
from json import JSONDecodeError

if getattr(sys, "frozen", False):
    BASEDIR = os.path.dirname(sys.executable)
elif __file__:
    BASEDIR = os.path.dirname(__file__)
CONFIG_FILE_PATH = f"{BASEDIR}/auto-server-config.json"


def enter_to_exit() -> None:
    input("Press Enter to Exit. ")
    # Shutdown any processes
    exit()


class ConfigError(Exception):
    def __str__(self) -> str:
        return "Invalid Config!"


class Config(BaseModel):
    ip: str = "localhost"
    port: int = 25565
    max_mem_mb: int = 2048
    nogui: bool = True
    jar_name: str = "server.jar"

    def save(self) -> None:
        with open(CONFIG_FILE_PATH, mode="w") as f:
            f.write(self.json())

    @classmethod
    def load(cls) -> "Config":
        with open(CONFIG_FILE_PATH, mode="r") as f:
            try:
                return Config(**json.load(f))
            except (ValueError, JSONDecodeError) as e:
                raise ConfigError


def clear_console():
    os.system("cls") if os.name == "nt" else os.system("clear")


def clear_decorator(func):
    def wrapper(*args, **kwargs):
        clear_console()
        func(*args, **kwargs)

    return wrapper


def has_cfg_file() -> bool:
    return os.path.isfile(CONFIG_FILE_PATH)


class Console:
    def __init__(self) -> None:
        init(autoreset=True)
        self.msgs: List[str] = []

    def log(self, msg: str) -> None:
        self._handle_msg_print(Fore.GREEN, f"[LOG]: {msg}")

    def warn(self, msg: str) -> None:
        self._handle_msg_print(Fore.YELLOW, f"[WARN]: {msg}")

    def error(self, msg: str) -> None:
        self._handle_msg_print(Fore.RED, f"[ERROR]: {msg}")

    def _handle_msg_print(self, fore: str, msg: str) -> None:
        self.msgs.append(
            f"{fore}[{datetime.datetime.now().time().strftime('%H:%M:%S')}]{msg}"
        )
        self.flush_msgs()

    @clear_decorator
    def flush_msgs(self) -> None:
        for msg in self.msgs:
            print(msg)


def setup_config(console: Console) -> Config:
    console.log(
        f"Setting up config. {Fore.BLACK}{Back.WHITE}Leave manual values blank for default values."
    )
    console.log("Detecting config values from 'server.properties' file..")
    sp_path = f"{BASEDIR}/server.properties"
    if not os.path.isfile(sp_path):
        console.error(
            "Could not find 'server.properties' file! Ensure this executable or python file is in the same directory as your server's 'server.properties' file."
        )
        return
    props = {}
    with open(sp_path, mode="r") as f:
        for line in f.readlines():
            if line.startswith("#"):
                continue
            data = line.split("=")
            key, value = data[0], data[1].strip()
            props[key] = value

    if not "server-ip" in props or not "server-port" in props:
        console.error(
            "Could not find server IP or port based on 'server.properties' file. Please ensure these key-value pairs exist."
        )
        enter_to_exit()
    max_mem_mb = input(
        "Please specify in MB how much RAM you would like your server to use (1024 MB = 1 GB, default=2048): "
    )
    try:
        if max_mem_mb == "":
            max_mem_mb = 2048
        else:
            max_mem_mb = int(max_mem_mb)
    except ValueError:
        console.error("Invalid value passed for RAM. Please ensure it is an integer.")
        return
    ip, port = props["server-ip"], props["server-port"]
    nogui = input("Run the server in a GUI (y/n, default=y): ").lower() == "n"
    jar_name = input(
        "Enter the name of your server JAR/BAT file (including the trailing .jar/.bat) (default=server.jar): "
    )
    console.warn(
        textwrap.dedent(
            """\
        In order to expose your server publicly, you need to sign up for Ngrok. 
        Sign up for free at: https://dashboard.ngrok.com/signup
        If you have already signed up, make sure your authtoken is installed.
        Your authtoken is available on your dashboard: https://dashboard.ngrok.com/get-started/your-authtoken"""
        )
    )
    token = input("Paste your authtoken here: ")
    return (
        Config(
            ip=ip,
            port=port,
            max_mem_mb=max_mem_mb,
            nogui=nogui,
            jar_name=jar_name if jar_name else 'server.jar',
        ),
        token,
    )


if __name__ == "__main__":
    console = Console()
    console.log("Auto MC Server (AMCS) v0.2 ALPHA (CTRL+C to quit).")
    if platform.system() != "Windows":
        console.warn(f"{Back.WHITE}AMCS has been tested on Windows 10 - you may run into errors on this OS.")
    console.log(
        "Ensure you have read https://minecraft.fandom.com/wiki/Tutorials/Setting_up_a_server, especially if your server is public!"
    )
    if not has_cfg_file():
        cfg, token = setup_config(console)
        ngrok.install_ngrok()
        console.log("Saving authtoken to Ngrok configuration file..")
        os.system(f"ngrok authtoken {token}")
        if cfg is None:
            console.warn("Config setup failed!")
            enter_to_exit()
        cfg.save()
    else:
        try:
            cfg = Config.load()
        except ConfigError as e:
            console.error(str(e))
            enter_to_exit()
    console.log("Loaded config successfully. Delete the config file to change it.")
    console.log("Launching server JAR file..")

    if not os.path.isfile(f"{BASEDIR}/{cfg.jar_name}"):
        console.error(f"Could not find your server's JAR file '{cfg.jar_name}'. Ensure that it is in the same directory as this file.")
        enter_to_exit()
    console.log(f"Found JAR '{cfg.jar_name}'")

    def do_server_start():
        if cfg.jar_name.endswith(".bat"):
            cmd = "run.bat"
        elif cfg.jar_name.endswith(".jar"):
            cmd = f"java -Xmx{cfg.max_mem_mb}M -Xms{cfg.max_mem_mb}M -jar {cfg.jar_name} {'nogui' if cfg.nogui else ''}"
        else:
            console.error("Unrecognized server file, it must be a JAR or BAT file.")
            input("Press ENTER to exit.")
            exit()
        os.system(f"start /wait {cmd}")
    
    console.log("Starting MC Server process (a new terminal should appear).")
    dss_thread = threading.Thread(target=do_server_start, daemon=True)
    dss_thread.start()
    console.log("Starting Ngrok tunnel.")
    # try:
    tunnel = ngrok.connect(cfg.port, "tcp")
    # except pyngrok.exception.PyngrokError as e:
    #     console.error(str(e))
    #     console.error(
    #         "TCP tunnels are only available to registered users.\nSign up for free at: https://dashboard.ngrok.com/signup\n\nIf you have already signed up, make sure your authtoken is installed.\nYour authtoken is available on your dashboard: https://dashboard.ngrok.com/get-started/your-authtoken"
    #     )
    #     enter_to_exit()
    console.log(f"Public server address: {Back.WHITE}{tunnel.public_url.removeprefix('tcp://')}")
    console.log(
        f"^ Send this address to your friends that will join, it is the server address."
    )
    console.log(
        f"Let us know how we can improve! https://github.com/Kyrixty/AutoMCServer/issues"
    )
    while True:
        ...

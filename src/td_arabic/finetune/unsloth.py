"""Install and launch Unsloth Studio, where the model is trained.

Unsloth Studio is Unsloth's official local web app. It trains on macOS (MLX, Apple Silicon),
Windows (NVIDIA GPU, without WSL) and Linux (NVIDIA GPU), and installs itself with the
official one-line installer of each system (https://unsloth.ai/docs/new/studio/install):

- macOS, Linux: ``curl -fsSL https://unsloth.ai/install.sh | sh``
- Windows (PowerShell): ``irm https://unsloth.ai/install.ps1 | iex``

It lives in its own environment (``~/.unsloth/studio``, or ``UNSLOTH_STUDIO_HOME``), separate
from this project: installing or updating it never touches the studio, the API or the corpus.
The same installer also updates an existing installation.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

INSTALL_URL = {"posix": "https://unsloth.ai/install.sh", "windows": "https://unsloth.ai/install.ps1"}
DEFAULT_PORT = 8888


def system_name() -> str:
    """Return ``mac``, ``windows`` or ``linux`` (other systems count as ``linux``)."""
    return {"darwin": "mac", "win32": "windows"}.get(sys.platform, "linux")


def studio_home() -> Path:
    """Folder of the Unsloth Studio installation (``UNSLOTH_STUDIO_HOME`` or ``~/.unsloth/studio``)."""
    env = os.getenv("UNSLOTH_STUDIO_HOME")
    return Path(env).expanduser() if env else Path.home() / ".unsloth" / "studio"


def unsloth_command() -> str | None:
    """Return the ``unsloth`` command if Unsloth Studio is installed, else None."""
    found = shutil.which("unsloth")
    if found:
        return found
    scripts = studio_home() / "unsloth_studio" / ("Scripts" if system_name() == "windows" else "bin")
    exe = scripts / ("unsloth.exe" if system_name() == "windows" else "unsloth")
    return str(exe) if exe.exists() else None


def has_nvidia_gpu() -> bool:
    """Tell whether an NVIDIA GPU and its driver are visible (``nvidia-smi -L`` succeeds)."""
    smi = shutil.which("nvidia-smi")
    if not smi:
        return False
    try:
        return subprocess.run([smi, "-L"], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def install_command(system: str | None = None) -> list[str]:
    """Return the official installer command of a system.

    Args:
        system: ``mac``, ``linux`` or ``windows``; defaults to this machine.

    Returns:
        The command as an argument list (run without a shell).
    """
    if (system or system_name()) == "windows":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "ByPass", "-Command",
                f"irm {INSTALL_URL['windows']} | iex"]
    return ["sh", "-c", f"curl -fsSL {INSTALL_URL['posix']} | sh"]


def warnings_for(system: str, machine: str, nvidia: bool, which=shutil.which) -> list[str]:
    """List what may prevent training on this machine (installation still possible).

    Args:
        system: ``mac``, ``linux`` or ``windows``.
        machine: ``platform.machine()`` (``arm64``, ``x86_64``, ``AMD64``…).
        nvidia: Whether an NVIDIA GPU is visible.
        which: Command lookup (``shutil.which``), replaceable in tests.

    Returns:
        Messages in French, empty when nothing is missing.
    """
    out = []
    if system == "mac":
        if machine != "arm64":
            out.append("Mac Intel : l'entraînement MLX demande une puce Apple (M1 à M5). Unsloth Studio "
                       "s'installe, mais pour entraîner, utilisez un Mac Apple Silicon ou Google Colab.")
        missing = [tool for tool in ("git", "cmake") if not which(tool)]
        if missing:
            out.append(f"Outils absents : {', '.join(missing)}. Installez-les avec Homebrew : "
                       f"`brew install {' '.join(missing)}`.")
    else:
        if not nvidia:
            out.append("Aucun GPU NVIDIA détecté (nvidia-smi) : sur Windows et Linux, l'entraînement demande "
                       "un GPU NVIDIA avec son pilote. Sans GPU, utilisez Google Colab.")
        if system == "linux" and not which("cmake"):
            out.append("cmake absent : `sudo apt install cmake build-essential` (nécessaire pour entraîner).")
        if system == "windows":
            out.append("Windows : l'entraînement demande « Visual Studio Build Tools 2022 » (compilateur C++). "
                       "L'installeur d'Unsloth installe Git et CMake lui-même.")
    return out


def report() -> dict:
    """Describe the machine and the Unsloth Studio installation (``td-arabic finetune check``)."""
    system, nvidia = system_name(), (system_name() != "mac" and has_nvidia_gpu())
    command = unsloth_command()
    return {
        "systeme": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "gpu": "Apple Silicon (MLX)" if system == "mac" and platform.machine() == "arm64"
               else "NVIDIA" if nvidia else "aucun GPU utilisable",
        "unsloth_studio": command or "non installé (td-arabic finetune install)",
        "dossier_unsloth": str(studio_home()),
        "installeur": install_command(system)[-1],
        "avertissements": warnings_for(system, platform.machine(), nvidia),
    }


def install(dry_run: bool = False, runner=subprocess.call) -> int:
    """Install (or update) Unsloth Studio with the official installer of this system.

    Args:
        dry_run: Only print the command.
        runner: Function running the command (``subprocess.call``), replaceable in tests.

    Returns:
        The installer's exit code (0 for a dry run).
    """
    system = system_name()
    command = install_command(system)
    for message in warnings_for(system, platform.machine(), system != "mac" and has_nvidia_gpu()):
        print(f"Attention : {message}", file=sys.stderr)
    action = "Mise à jour" if unsloth_command() else "Installation"
    print(f"{action} d'Unsloth Studio ({system}) : {command[-1]}", file=sys.stderr, flush=True)
    if dry_run:
        return 0
    code = runner(command)
    if code == 0:
        print("Unsloth Studio est prêt : lancez-le avec `td-arabic finetune studio`.", file=sys.stderr)
    return code


def launch(port: int = DEFAULT_PORT, data_folder: Path | None = None, runner=subprocess.call) -> int:
    """Start Unsloth Studio and say which files to load in it.

    Args:
        port: Local port of the web app.
        data_folder: Folder holding ``train.jsonl`` / ``valid.jsonl`` (shown to the user).
        runner: Function running the command (``subprocess.call``), replaceable in tests.

    Returns:
        Unsloth Studio's exit code.

    Raises:
        FileNotFoundError: If Unsloth Studio is not installed.
    """
    command = unsloth_command()
    if not command:
        raise FileNotFoundError("Unsloth Studio n'est pas installé : lancez `td-arabic finetune install`.")
    if data_folder:
        print(f"Dans Unsloth Studio, onglet « Local », chargez {data_folder / 'train.jsonl'} "
              f"(format « chatml » ou « auto ») ; valid.jsonl sert à l'évaluation.", file=sys.stderr)
    print(f"Unsloth Studio : http://127.0.0.1:{port}", file=sys.stderr, flush=True)
    return runner([command, "studio", "-p", str(port)])

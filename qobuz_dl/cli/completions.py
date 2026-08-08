"""
cli/completions.py — Shell tab-completion script generation and installation.
Also exports _complete_id_prefixes, used as shell_complete= in dl and info.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List, Optional

import click

from ..utils import console, dbg


# ─────────────────────────────────────────────────────────────────────────────
# Shared shell-completion helper (used by dl and info commands)
# ─────────────────────────────────────────────────────────────────────────────

def _complete_id_prefixes(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> List[Any]:
    """Suggest ar-id / al-id / tr-id prefixes for positional URL/ID arguments."""
    from click.shell_completion import CompletionItem

    prefixes = [
        CompletionItem("al-id", help="album ID"),
        CompletionItem("tr-id", help="track ID"),
    ]

    if ctx.command.name != "info":
        prefixes.insert(0, CompletionItem("ar-id", help="artist ID"))

    return [p for p in prefixes if p.value.startswith(incomplete)]


# ─────────────────────────────────────────────────────────────────────────────
# Shell detection and script generation
# ─────────────────────────────────────────────────────────────────────────────

_SHELL_INSTALL_PATHS: dict[str, Path] = {
    "fish": Path.home() / ".config" / "fish" / "completions" / "qobuz-dl.fish",
    "bash": Path.home() / ".bash_completion.d" / "qobuz-dl",
    "zsh":  Path.home() / ".zfunc" / "_qobuz-dl",
}

_SHELL_ACTIVATE_HINTS: dict[str, str] = {
    "fish": "Restart your shell, or run:  source ~/.config/fish/completions/qobuz-dl.fish",
    "bash": (
        "Add this line to ~/.bashrc, then run  source ~/.bashrc :\n"
        '  source "~/.bash_completion.d/qobuz-dl"'
    ),
    "zsh": (
        "Add these lines to ~/.zshrc, then run  source ~/.zshrc :\n"
        "  fpath=(~/.zfunc $fpath)\n"
        "  autoload -Uz compinit && compinit"
    ),
}


def _detect_shell() -> Optional[str]:
    """Guess the running shell from $SHELL."""
    name = Path(os.environ.get("SHELL", "")).name
    return name if name in _SHELL_INSTALL_PATHS else None


def _generate_completion_script(shell: str) -> str:
    """Ask Click to emit its native completion script for *shell*."""
    from click.shell_completion import get_completion_class
    from ..cli import cli  # import here to avoid circular at module load

    cls = get_completion_class(shell)
    if cls is None:
        raise click.ClickException(
            f"Click does not have a built-in completion class for '{shell}'.\n"
            "  Make sure Click ≥ 8.1 is installed."
        )
    complete = cls(cli, {}, "qobuz-dl", "_QOBUZ_DL_COMPLETE")
    script   = complete.source()
    if not script or not script.strip():
        raise click.ClickException(
            f"Completion script generation produced no output for shell '{shell}'."
        )
    return script


# ─────────────────────────────────────────────────────────────────────────────
# Command
# ─────────────────────────────────────────────────────────────────────────────

@click.command("completions")
@click.option(
    "--shell", "shell_name",
    type=click.Choice(["fish", "bash", "zsh"]),
    default=None,
    help="Target shell.  Auto-detected from $SHELL when omitted.",
)
@click.option(
    "--install", is_flag=True,
    help="Write the script to the standard completions directory and show activation instructions.",
)
@click.option(
    "--print-only", is_flag=True,
    help="Print the raw completion script to stdout (overrides --install).",
)
def completions_cmd(shell_name: Optional[str], install: bool, print_only: bool) -> None:
    """Generate or install shell tab-completion scripts.

    \b
    One-shot install (auto-detects your shell):
      qobuz-dl completions --install

    Explicit shell:\n
      qobuz-dl completions --shell fish --install\n
      qobuz-dl completions --shell bash --install\n
      qobuz-dl completions --shell zsh  --install

    Print the raw script to stdout (pipe it wherever you like):\n
      qobuz-dl completions --shell fish --print-only

    \b
    Manual activation (if --install doesn't fit your setup):
      fish  →  _QOBUZ_DL_COMPLETE=fish_source qobuz-dl \\
                 > ~/.config/fish/completions/qobuz-dl.fish
      bash  →  eval "$(_QOBUZ_DL_COMPLETE=bash_source qobuz-dl)"   # add to ~/.bashrc
      zsh   →  eval "$(_QOBUZ_DL_COMPLETE=zsh_source  qobuz-dl)"   # add to ~/.zshrc
    """
    shell = shell_name
    if shell is None:
        shell = _detect_shell()
        if shell is None:
            raise click.ClickException(
                f"Cannot auto-detect shell from $SHELL={os.environ.get('SHELL', '')!r}.\n"
                "  Pass --shell fish|bash|zsh explicitly."
            )
        console.print(f"[dim]Auto-detected shell:[/] {shell}")

    with console.status(f"Generating {shell} completion script…"):
        script = _generate_completion_script(shell)

    dbg(f"Completion script — {len(script)} chars, first line: {script.splitlines()[0]!r}")

    if print_only:
        click.echo(script)
        return

    if install:
        dest = _SHELL_INSTALL_PATHS[shell]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(script + "\n")
        console.print(f"[green]✓[/] Completion script written → [cyan]{dest}[/]")
        console.print()
        console.print(_SHELL_ACTIVATE_HINTS[shell])
        return

    click.echo(script)
    console.print()
    console.print(
        click.style(
            f"Pipe this into your shell's completions directory, or run:\n\n"
            f"  qobuz-dl completions --shell {shell} --install\n\n"
            + _SHELL_ACTIVATE_HINTS[shell],
        )
    )

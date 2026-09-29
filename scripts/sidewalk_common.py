"""Shared helpers for the Python build scripts in this folder.

Imported by prepare-sdk.py and build-firmware.py. Nothing here needs a POSIX
shell, Git, or any package outside the Python standard library, so the scripts
run the same from PowerShell, Command Prompt, macOS, and Linux.
"""

from __future__ import annotations

import glob
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SDK_URL = "https://github.com/stm32-hotspot/STM32-Sidewalk-SDK/archive/refs/heads/main.zip"
SDK_VERIFY = "apps/st/stm32wba/sid_ble/STM32CubeIDE/STM32WBA55/.cproject"
SDK_NAMES = ("STM32-Sidewalk-SDK", "STM32-Sidewalk-SDK-main")

CR = chr(13)
LF = chr(10)
CRLF = CR + LF


def search_bases() -> list[Path]:
    """Folders where the ST packages are looked for, most specific first."""
    home = Path.home()
    return [REPO_ROOT.parent, home / "Downloads", home / "dev" / "sidewalk", home]


def find_package(label: str, override: str | None, verify: str, names: tuple[str, ...]) -> Path | None:
    """Return the first folder matching one of `names` that contains `verify`.

    `override` (an environment variable or command-line value) wins, and is an
    error if it does not contain `verify`. `names` may contain wildcards.
    """
    if override:
        root = Path(override).expanduser()
        if (root / verify).exists():
            return root
        sys.exit(f"error: {label} override does not look right: {root} (missing {verify})")
    for base in search_bases():
        for name in names:
            for hit in sorted(glob.glob(str(base / name)), reverse=True):
                if (Path(hit) / verify).exists():
                    return Path(hit)
    return None


def fail_missing(label: str, url: str, var: str, looked_for: tuple[str, ...]) -> None:
    lines = [
        f"error: could not find {label}.",
        "",
        "Download it from",
        f"    {url}",
        "and extract it next to this repo (or into your Downloads folder). Looked for:",
    ]
    for base in search_bases():
        for name in looked_for:
            lines.append(f"    {base / name}")
    lines.append(f"or point the {var} environment variable at it.")
    sys.exit(LF.join(lines))


def find_sdk(override: str | None = None) -> Path:
    override = override or os.environ.get("SDK_ROOT")
    sdk = find_package("STM32-Sidewalk-SDK", override, SDK_VERIFY, SDK_NAMES)
    if sdk is None:
        fail_missing("the STM32-Sidewalk-SDK", SDK_URL, "SDK_ROOT", SDK_NAMES)
    return sdk


# --------------------------------------------------------------------------
# Unified-diff application, so no `git` or `patch` executable is needed.
# --------------------------------------------------------------------------

class PatchError(Exception):
    pass


_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def split_lines(text: str) -> tuple[list[str], list[str]]:
    """Split on newlines only. Returns (line contents, line endings).

    str.splitlines() is avoided on purpose: it also breaks on form feeds and
    other separators that can legitimately appear inside a source line.
    """
    contents: list[str] = []
    endings: list[str] = []
    parts = text.split(LF)
    for index, part in enumerate(parts):
        last = index == len(parts) - 1
        if last and part == "":
            break
        ending = "" if last else LF
        if part.endswith(CR) and not last:
            part, ending = part[:-1], CRLF
        contents.append(part)
        endings.append(ending)
    return contents, endings


def parse_patch(text: str) -> list[tuple[str, list[tuple[int, list[str], list[str]]]]]:
    """Parse a git-style unified diff of text files.

    Returns [(path, [(old_start, old_lines, new_lines), ...]), ...] where the
    line lists hold line content without line endings.
    """
    files: list[tuple[str, list]] = []
    lines, _ = split_lines(text)
    i = 0
    current: list | None = None
    while i < len(lines):
        line = lines[i]
        if line.startswith("diff --git "):
            current = None
            i += 1
            continue
        if line.startswith(("new file mode", "deleted file mode", "rename from", "GIT binary patch", "Binary files")):
            raise PatchError(f"unsupported patch feature: {line}")
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            current = []
            files.append((path, current))
            i += 1
            continue
        match = _HUNK.match(line)
        if match and current is not None:
            old_start = int(match.group(1))
            old_count = int(match.group(2) or "1")
            new_count = int(match.group(4) or "1")
            old: list[str] = []
            new: list[str] = []
            i += 1
            while i < len(lines) and (len(old) < old_count or len(new) < new_count):
                body = lines[i]
                if body.startswith("\\"):          # "\ No newline at end of file"
                    i += 1
                    continue
                tag, content = (body[:1], body[1:]) if body else (" ", "")
                if tag == " ":
                    old.append(content)
                    new.append(content)
                elif tag == "-":
                    old.append(content)
                elif tag == "+":
                    new.append(content)
                else:
                    raise PatchError(f"unexpected line in hunk: {body!r}")
                i += 1
            current.append((old_start, old, new))
            continue
        i += 1
    return files


def _locate(haystack: list[str], needle: list[str], guess: int) -> int | None:
    """Index where `needle` occurs in `haystack`, searching outwards from `guess`."""
    if not needle:
        return min(max(guess, 0), len(haystack))
    last = len(haystack) - len(needle)
    if last < 0:
        return None
    guess = min(max(guess, 0), last)
    for distance in range(0, last + 1):
        for pos in (guess - distance, guess + distance):
            if 0 <= pos <= last and haystack[pos:pos + len(needle)] == needle:
                return pos
    return None


def apply_patch(patch_file: Path, root: Path, only: str | None = None) -> list[str]:
    """Apply `patch_file` to the tree at `root`. Returns the files changed.

    Matching ignores the CRLF/LF difference, and every existing line keeps its
    own line ending; added lines take the ending used around them. Hunks are
    located by content, so a small drift in line numbers is tolerated. A hunk
    that is already applied is skipped, which makes re-running safe. Nothing is
    written unless every hunk of every file can be placed. `only` limits the
    work to paths ending with that text.
    """
    parsed = parse_patch(patch_file.read_bytes().decode("utf-8", errors="surrogateescape"))
    pending: list[tuple[Path, bytes]] = []
    changed: list[str] = []
    for rel, hunks in parsed:
        if only and not rel.endswith(only):
            continue
        target = root / rel
        if not target.is_file():
            raise PatchError(f"file to patch is missing: {target}")
        text = target.read_bytes().decode("utf-8", errors="surrogateescape")
        lines, endings = split_lines(text)
        dominant = CRLF if endings.count(CRLF) > endings.count(LF) else LF
        offset = 0
        touched = False
        for old_start, old, new in hunks:
            guess = old_start - 1 + offset
            at = _locate(lines, old, guess)
            if at is None:
                if _locate(lines, new, guess) is not None:
                    continue                      # this hunk is already applied
                raise PatchError(f"hunk at line {old_start} does not match {rel}")
            if at < len(endings):
                near = endings[at]
            elif at:
                near = endings[at - 1]
            else:
                near = dominant
            eol = near or dominant
            open_tail = bool(old) and at + len(old) == len(lines) and endings[at + len(old) - 1] == ""
            lines[at:at + len(old)] = new
            endings[at:at + len(old)] = [eol] * len(new)
            if open_tail and new:
                endings[at + len(new) - 1] = ""   # the file had no final newline; keep it so
            offset += len(new) - len(old)
            touched = True
        if touched:
            out = "".join(content + ending for content, ending in zip(lines, endings))
            pending.append((target, out.encode("utf-8", errors="surrogateescape")))
            changed.append(rel)
    for target, data in pending:
        target.write_bytes(data)
    return changed

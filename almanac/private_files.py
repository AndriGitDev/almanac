"""Private local persistence for vault payloads and operational records."""

import os
import stat
import tempfile
from pathlib import Path


def write_private_text(path, text):
    """Atomically replace a file with mode 0600, without following its symlink."""
    path = Path(path)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".tmp-{path.stem}-", suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def append_private_text(path, text):
    """Append to a regular private file; refuse a symlink or special file."""
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NONBLOCK
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("Private output must be a regular file")
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = None
            handle.write(text)
    finally:
        if fd is not None:
            os.close(fd)

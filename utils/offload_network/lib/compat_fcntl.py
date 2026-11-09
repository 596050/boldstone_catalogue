"""Windows subset of flock used by legacy fleet state readers/writers."""

import errno
import msvcrt
import os
import time

LOCK_SH, LOCK_EX, LOCK_NB, LOCK_UN = 1, 2, 4, 8


def flock(fd, operation):
    os.lseek(fd, 0, os.SEEK_SET)
    if operation & LOCK_UN:
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        return
    while True:
        try:
            # Exclusive read locks are safe, albeit less concurrent than LOCK_SH.
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return
        except OSError as exc:
            if operation & LOCK_NB:
                raise BlockingIOError(errno.EAGAIN, "state lock held") from exc
            time.sleep(0.05)

"""`.github/scripts/retry.sh` recovers from a transient failure and from a stall.

Issue #183 was a *stall*, not an error, and that distinction drives the design.
A `timeout-minutes:` on the step bounds the step, so the six-hour burn stops —
but it cannot make a retry useful, because the first attempt hangs, consumes
the whole budget, and the step dies having never reached attempt two. The
timeout has to sit on each attempt. These tests pin both halves: the retry
recovers, and the per-attempt bound is what lets it.

The script prefers coreutils ``timeout`` and falls back to a shell watchdog for
the macOS runners, which have neither ``timeout`` nor ``gtimeout``. Both paths
are exercised here, because a fallback nobody runs is a fallback that rots.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RETRY = REPO_ROOT / ".github" / "scripts" / "retry.sh"

# A faithful stand-in for coreutils `timeout`: SIGTERM at expiry, SIGKILL five
# seconds later, exit 124. Used to exercise the branch that the macOS runners
# never take, and vice versa.
FAKE_TIMEOUT = """\
#!/usr/bin/env python3
import subprocess, sys
argv = sys.argv[1:]
if argv[0] == "-k":            # coreutils' escalate-to-KILL flag
    argv = argv[2:]
limit = float(argv[0]); cmd = argv[1:]
p = subprocess.Popen(cmd)
try:
    sys.exit(p.wait(timeout=limit))
except subprocess.TimeoutExpired:
    p.terminate()
    try:
        p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill(); p.wait()
    sys.exit(124)
"""


def _write_executable(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


class RetryScriptTest(unittest.TestCase):
    """Each test runs under both timeout implementations."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    # What the watchdog path needs beyond shell builtins. Hiding `timeout` by
    # emptying PATH would hide `bash` with it, so the sanitised PATH is built
    # by name from this list instead — which also documents the fallback's
    # actual dependencies.
    WATCHDOG_TOOLCHAIN = ("bash", "sh", "env", "sleep", "mktemp", "rm", "cat", "touch", "kill")

    def _env(self, *, coreutils: bool) -> dict[str, str]:
        env = dict(os.environ)
        if coreutils:
            fake_bin = self.tmp / "bin"
            fake_bin.mkdir(exist_ok=True)
            _write_executable(fake_bin / "timeout", FAKE_TIMEOUT)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
        else:
            sanitised = self.tmp / "no-timeout-bin"
            sanitised.mkdir(exist_ok=True)
            for tool in self.WATCHDOG_TOOLCHAIN:
                found = shutil.which(tool)
                link = sanitised / tool
                if found and not link.exists():
                    link.symlink_to(found)
            env["PATH"] = str(sanitised)
        return env

    def test_the_sanitised_path_really_hides_timeout(self) -> None:
        """Guards the test rig itself: a leaky PATH would silently test one path twice."""
        env = self._env(coreutils=False)
        for tool in ("timeout", "gtimeout"):
            self.assertIsNone(shutil.which(tool, path=env["PATH"]), tool)
        self.assertIsNotNone(shutil.which("bash", path=env["PATH"]))

    def _run(self, args: list[str], *, coreutils: bool) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(RETRY), *args],
            capture_output=True,
            text=True,
            env=self._env(coreutils=coreutils),
            timeout=120,
        )

    def _both_paths(self):
        for coreutils in (True, False):
            with self.subTest(timeout_impl="coreutils" if coreutils else "watchdog"):
                yield coreutils

    def test_a_command_that_succeeds_runs_once(self) -> None:
        for coreutils in self._both_paths():
            counter = self.tmp / f"once-{coreutils}"
            script = _write_executable(
                self.tmp / f"once-{coreutils}.sh",
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env bash
                    echo run >> {counter}
                    exit 0
                    """
                ),
            )
            result = self._run(
                ["--attempts", "3", "--timeout", "10", "--", str(script)],
                coreutils=coreutils,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(1, len(counter.read_text().splitlines()))

    def test_it_recovers_from_a_single_transient_failure(self) -> None:
        """The mirror fails once, then answers. No human should see this."""
        for coreutils in self._both_paths():
            marker = self.tmp / f"flaky-{coreutils}"
            script = _write_executable(
                self.tmp / f"flaky-{coreutils}.sh",
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env bash
                    if [ ! -f {marker} ]; then touch {marker}; exit 1; fi
                    exit 0
                    """
                ),
            )
            result = self._run(
                ["--attempts", "3", "--timeout", "10", "--delay", "1", "--", str(script)],
                coreutils=coreutils,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("attempt 1/3 exited 1", result.stdout + result.stderr)
            self.assertIn("succeeded on attempt 2/3", result.stdout)

    def test_a_stalled_attempt_is_cut_short_and_the_next_one_succeeds(self) -> None:
        """The #183 failure mode: attempt one hangs, and the retry still helps.

        Without a per-attempt bound this is the case that cannot be recovered,
        so the assertion that matters is the elapsed time — the hang is 600s
        and the whole invocation has to finish in a small multiple of the 3s
        per-attempt limit.
        """
        for coreutils in self._both_paths():
            counter = self.tmp / f"hang-{coreutils}"
            script = _write_executable(
                self.tmp / f"hang-{coreutils}.sh",
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env bash
                    n=$(cat {counter} 2>/dev/null || echo 0); n=$((n+1)); echo $n > {counter}
                    if [ "$n" -eq 1 ]; then exec sleep 600; fi
                    exit 0
                    """
                ),
            )
            started = time.monotonic()
            result = self._run(
                ["--attempts", "3", "--timeout", "3", "--delay", "1", "--", str(script)],
                coreutils=coreutils,
            )
            elapsed = time.monotonic() - started

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("timed out after 3s", result.stdout + result.stderr)
            self.assertIn("succeeded on attempt 2/3", result.stdout)
            self.assertLess(elapsed, 60, "the stalled attempt was not bounded")

    def test_a_permanent_stall_exhausts_its_attempts_and_reports_124(self) -> None:
        for coreutils in self._both_paths():
            started = time.monotonic()
            result = self._run(
                ["--attempts", "2", "--timeout", "2", "--delay", "1", "--", "sleep", "600"],
                coreutils=coreutils,
            )
            elapsed = time.monotonic() - started
            self.assertEqual(124, result.returncode)
            self.assertIn("no attempts left", result.stdout + result.stderr)
            self.assertLess(elapsed, 60)

    def test_a_permanent_error_propagates_its_exit_status(self) -> None:
        for coreutils in self._both_paths():
            result = self._run(
                ["--attempts", "2", "--timeout", "10", "--delay", "1", "--", "bash", "-c", "exit 7"],
                coreutils=coreutils,
            )
            self.assertEqual(7, result.returncode)

    def test_it_refuses_an_empty_command(self) -> None:
        result = self._run(["--attempts", "2"], coreutils=True)
        self.assertEqual(2, result.returncode)


if __name__ == "__main__":
    unittest.main()

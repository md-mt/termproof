from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import DockerBackendConfig
from .protocols import SessionBackend as SessionBackend
from .session import TerminalSession


class PexpectBackend:
    """pexpect backend that records the cast itself.

    Spawns the child directly and writes the ``.cast`` from the pty output it
    is already reading, so no external recorder is involved.
    """

    name = "pexpect"

    def create_session(
        self,
        argv: list[str],
        cast_path: Path,
        cwd: str | None,
        env: dict[str, str],
        cols: int,
        rows: int,
    ) -> TerminalSession:
        return TerminalSession(argv, cast_path, cwd, env, cols, rows, recorder="internal")


class PexpectAsciinemaBackend:
    """pexpect backend that delegates recording to the ``asciinema`` CLI.

    Needs asciinema on PATH — ``pip install 'termproof[record]'``. Use it when
    the cast has to be one asciinema itself wrote.
    """

    name = "pexpect_asciinema"

    def create_session(
        self,
        argv: list[str],
        cast_path: Path,
        cwd: str | None,
        env: dict[str, str],
        cols: int,
        rows: int,
    ) -> TerminalSession:
        return TerminalSession(argv, cast_path, cwd, env, cols, rows, recorder="asciinema")


class DockerSessionBackend:
    name = "docker"

    def __init__(
        self,
        config: DockerBackendConfig | None = None,
        docker_bin: str = "docker",
    ) -> None:
        self.config = config or DockerBackendConfig()
        self.docker_bin = docker_bin

    def create_session(
        self,
        argv: list[str],
        cast_path: Path,
        cwd: str | None,
        env: dict[str, str],
        cols: int,
        rows: int,
    ) -> TerminalSession:
        if not self.config.image:
            raise RuntimeError("docker session backend requires docker.image in config")
        return TerminalSession(
            self._docker_argv(argv, cwd, env),
            cast_path,
            None,
            {},
            cols,
            rows,
        )

    def _docker_argv(
        self,
        argv: list[str],
        cwd: str | None,
        env: dict[str, str],
    ) -> list[str]:
        command = [self.docker_bin, "run", "--rm", "--interactive", "--tty"]
        for item in self.config.volumes:
            command.extend(_volume_args(item, cwd))
        for key, value in {**self.config.env, **env}.items():
            command.extend(["--env", f"{key}={value}"])
        if self.config.workdir:
            command.extend(["--workdir", self.config.workdir])
        command.append(self.config.image)
        command.extend(argv)
        return command


def _volume_args(volume: Any, cwd: str | None) -> list[str]:
    if isinstance(volume, str):
        return ["--volume", volume]
    host = _host_path(str(volume["host"]), cwd)
    container = str(volume.get("container", volume.get("target")))
    suffix = ":ro" if bool(volume.get("read_only", False)) else ""
    return ["--volume", f"{host}:{container}{suffix}"]


def _host_path(value: str, cwd: str | None) -> str:
    path = Path(value).expanduser()
    if path.is_absolute():
        return str(path)
    return str((Path(cwd or ".") / path).resolve())

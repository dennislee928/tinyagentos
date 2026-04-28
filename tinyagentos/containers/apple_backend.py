"""Apple Containerization backend — shells out to apple/container CLI.

The Mac .app launcher injects ``TAOS_CONTAINER_BIN`` pointing at the
bundled CLI under ``Contents/Resources/bin/container``. On developer
machines without the .app, falls back to ``container`` on ``PATH``.

All ``subprocess`` calls go through ``asyncio.create_subprocess_exec``
(no shell). Failure shape matches the other backends:
``{success: bool, output: str, note?: str}``.
"""
from __future__ import annotations

import asyncio
import logging
import os

from .backend import ContainerBackend, ContainerInfo

logger = logging.getLogger(__name__)


class AppleContainerBackend(ContainerBackend):
    def __init__(self) -> None:
        self.binary = os.environ.get("TAOS_CONTAINER_BIN", "container")

    async def _run(self, cmd: list[str], timeout: int = 120) -> tuple[int, str]:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, stdout.decode() if stdout else ""

    # All ABC methods raise NotImplementedError until subsequent tasks.
    async def list_containers(self, prefix: str = "taos-agent-"):
        raise NotImplementedError

    async def set_root_quota(self, name, size_gib):
        raise NotImplementedError

    async def create_container(self, name, image="images:debian/bookworm",
                               memory_limit=None, cpu_limit=None,
                               mounts=None, env=None, host_uid=None,
                               root_size_gib=None):
        raise NotImplementedError

    async def exec_in_container(self, name, cmd, timeout=300):
        raise NotImplementedError

    async def push_file(self, name, local_path, remote_path):
        raise NotImplementedError

    async def start_container(self, name):
        raise NotImplementedError

    async def stop_container(self, name, force=False):
        raise NotImplementedError

    async def restart_container(self, name):
        raise NotImplementedError

    async def destroy_container(self, name):
        raise NotImplementedError

    async def get_container_logs(self, name, lines=100):
        raise NotImplementedError

    async def rename_container(self, old_name, new_name):
        raise NotImplementedError

    async def add_proxy_device(self, name, device_name, listen, connect, bind_mode=None):
        raise NotImplementedError

    async def snapshot_create(self, name, snapshot_name):
        raise NotImplementedError

    async def snapshot_restore(self, name, snapshot_name):
        raise NotImplementedError

    async def snapshot_list(self, name):
        raise NotImplementedError

    async def set_env(self, name, key, value):
        raise NotImplementedError

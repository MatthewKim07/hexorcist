"""Per-task sandbox containers. The only place user or AI written code ever executes.

Each compile or emulation gets a brand new container, which is always removed
afterwards. Inputs go in as a tar on stdin because a read-only rootfs rejects
put_archive and tmpfs mounts do not exist until the container starts. Results
come back as one JSON document on stdout.
"""
from __future__ import annotations

import base64
import io
import json
import re
import socket
import tarfile
import time
from dataclasses import dataclass, field
from typing import Optional

import docker
from docker.errors import APIError, DockerException, ImageNotFound
from docker.types import LogConfig, Ulimit
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import ReadTimeout

from .config import Settings

TMPFS_OPTS = "rw,noexec,nosuid,nodev,uid=1000,gid=1000,mode=0700"
MEM_LIMIT = "512m"
NANO_CPUS = 1_000_000_000
PIDS_LIMIT = 128
MAX_OUTPUT_BYTES = 32 * 1024 * 1024

# Paths a compile log can reveal an attempt to read. Sketches have no business touching these.
_FILE_READ_RE = re.compile(r"(/etc/[\w./-]+|/proc/[\w./-]+|/sys/[\w./-]+|/root/[\w./-]*|/home/[\w./-]+|~/[\w./-]+|/var/run/[\w./-]+)")


@dataclass
class ContainmentRecord:
    kind: str
    label: str
    container_id: str = ""
    image: str = ""
    limits: dict = field(default_factory=dict)
    duration_ms: float = 0.0
    exit_code: Optional[int] = None
    oom_killed: bool = False
    timed_out: bool = False
    timeout_s: int = 0
    removed: bool = False
    env_names: list[str] = field(default_factory=list)
    secrets_found: int = 0
    violations: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "label": self.label,
            "container_id": self.container_id,
            "image": self.image,
            "limits": self.limits,
            "duration_ms": round(self.duration_ms, 1),
            "exit_code": self.exit_code,
            "oom_killed": self.oom_killed,
            "timed_out": self.timed_out,
            "timeout_s": self.timeout_s,
            "removed": self.removed,
            "env_names": self.env_names,
            "secrets_found": self.secrets_found,
            "violations": self.violations,
        }


@dataclass
class CompileResult:
    ok: bool
    log: str
    elf: Optional[bytes]
    record: ContainmentRecord


@dataclass
class RunResult:
    trace: dict
    record: ContainmentRecord


class SandboxError(RuntimeError):
    pass


def _tar(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o444
            info.mtime = int(time.time())
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _limits_from_inspect(info: dict) -> dict:
    """Report what Docker says it enforced, not what we asked for."""
    host = info.get("HostConfig", {})
    config = info.get("Config", {})
    security = host.get("SecurityOpt") or []
    return {
        "network": host.get("NetworkMode"),
        "cap_drop": host.get("CapDrop") or [],
        "cap_add": host.get("CapAdd") or [],
        "no_new_privileges": any("no-new-privileges" in s for s in security),
        "read_only_rootfs": bool(host.get("ReadonlyRootfs")),
        "user": config.get("User"),
        "memory_bytes": host.get("Memory"),
        "memory_swap_bytes": host.get("MemorySwap"),
        "nano_cpus": host.get("NanoCpus"),
        "pids_limit": host.get("PidsLimit"),
        "tmpfs": sorted((host.get("Tmpfs") or {}).keys()),
        "binds": host.get("Binds") or [],
        "mounts": [m.get("Destination") for m in info.get("Mounts") or [] if m.get("Type") != "tmpfs"],
        "privileged": bool(host.get("Privileged")),
    }


class SandboxRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Optional[docker.DockerClient] = None

    @property
    def client(self) -> docker.DockerClient:
        if self._client is None:
            try:
                self._client = docker.from_env(timeout=120, max_pool_size=16)
            except DockerException as exc:
                raise SandboxError(f"cannot reach the Docker engine: {exc}") from exc
        return self._client

    def health(self) -> dict:
        try:
            self.client.ping()
            self.client.images.get(self.settings.sandbox_image)
            return {"docker": True, "image": True, "error": ""}
        except ImageNotFound:
            return {"docker": True, "image": False, "error": f"image {self.settings.sandbox_image} is not built"}
        except (DockerException, SandboxError, RequestsConnectionError, ReadTimeout) as exc:
            return {"docker": False, "image": False, "error": str(exc)}

    def _secret_values(self) -> list[str]:
        values = [self.settings.llm_api_key, self.settings.demo_passcode]
        return [v for v in values if v and len(v) >= 6]

    def _execute(self, kind: str, label: str, argv: list[str], files: dict[str, bytes], timeout_s: int) -> tuple[bytes, ContainmentRecord]:
        api = self.client.api
        record = ContainmentRecord(kind=kind, label=label, image=self.settings.sandbox_image, timeout_s=timeout_s)
        host_config = api.create_host_config(
            network_mode="none",
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            read_only=True,
            tmpfs={"/work": f"{TMPFS_OPTS},size=128m", "/tmp": f"{TMPFS_OPTS},size=128m"},
            mem_limit=MEM_LIMIT,
            memswap_limit=MEM_LIMIT,
            nano_cpus=NANO_CPUS,
            pids_limit=PIDS_LIMIT,
            ulimits=[Ulimit(name="core", soft=0, hard=0), Ulimit(name="nofile", soft=256, hard=256)],
            log_config=LogConfig(type=LogConfig.types.JSON, config={"max-size": "64m", "max-file": "1"}),
            auto_remove=False,
        )
        created = api.create_container(
            image=self.settings.sandbox_image,
            command=argv,
            environment={},
            stdin_open=True,
            network_disabled=True,
            labels={"hexorcist.sandbox": "1", "hexorcist.kind": kind},
            host_config=host_config,
        )
        cid = created["Id"]
        record.container_id = cid[:12]
        output = b""
        started = time.monotonic()
        try:
            stdin = api.attach_socket(cid, params={"stdin": 1, "stream": 1})
            api.start(cid)
            started = time.monotonic()
            self._send_stdin(stdin, _tar(files))

            try:
                result = api.wait(cid, timeout=timeout_s)
                record.exit_code = result.get("StatusCode")
            except (ReadTimeout, RequestsConnectionError):
                record.timed_out = True
                self._kill(cid)
                record.violations.append({"type": "timeout_kill", "detail": f"Killed at the {timeout_s} s wall-clock limit"})
                try:
                    record.exit_code = api.wait(cid, timeout=15).get("StatusCode")
                except (ReadTimeout, RequestsConnectionError):
                    record.exit_code = None
            record.duration_ms = (time.monotonic() - started) * 1000

            info = api.inspect_container(cid)
            record.limits = _limits_from_inspect(info)
            record.oom_killed = bool(info.get("State", {}).get("OOMKilled"))
            record.env_names = sorted(e.split("=", 1)[0] for e in info.get("Config", {}).get("Env") or [])
            if record.oom_killed:
                record.violations.append({"type": "oom_kill", "detail": f"Killed for exceeding the {MEM_LIMIT} memory limit"})
            elif record.exit_code not in (0, None) and not record.timed_out and kind != "compile":
                record.violations.append({"type": "nonzero_exit", "detail": f"Exited with status {record.exit_code}"})

            output = api.logs(cid, stdout=True, stderr=False, timestamps=False)
            if len(output) > MAX_OUTPUT_BYTES:
                output = output[:MAX_OUTPUT_BYTES]
                record.violations.append({"type": "output_truncated", "detail": "Output exceeded 32 MiB"})
        finally:
            try:
                api.remove_container(cid, force=True, v=True)
                record.removed = True
            except APIError as exc:
                record.violations.append({"type": "cleanup_failed", "detail": str(exc)})

        self._scan_secrets(output, record)
        return output, record

    @staticmethod
    def _send_stdin(stdin, payload: bytes) -> None:
        raw = getattr(stdin, "_sock", stdin)
        try:
            raw.sendall(payload)
            raw.shutdown(socket.SHUT_WR)
        except OSError:
            # The container already died. The exit status tells the real story.
            pass
        finally:
            try:
                stdin.close()
            except OSError:
                pass

    def _kill(self, cid: str) -> None:
        try:
            self.client.api.kill(cid)
        except APIError:
            pass

    def _scan_secrets(self, output: bytes, record: ContainmentRecord) -> None:
        """Prove no control-plane secret reached a sandbox by searching what came out of it."""
        for secret in self._secret_values():
            if secret.encode() in output:
                record.secrets_found += 1
                record.violations.append({"type": "secret_leak", "detail": "A control-plane secret appeared in sandbox output"})

    def compile(self, sketch: str, label: str = "compile") -> CompileResult:
        output, record = self._execute(
            "compile",
            label,
            ["compile"],
            {"sketch.ino": sketch.encode("utf-8", "replace")},
            self.settings.compile_timeout_s,
        )
        if record.timed_out or not output.strip():
            log = f"Compiler killed after {record.timeout_s} s." if record.timed_out else "Compiler produced no output."
            return CompileResult(ok=False, log=log, elf=None, record=record)
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            return CompileResult(ok=False, log=output.decode("utf-8", "replace")[:8000], elf=None, record=record)
        log = str(payload.get("log", ""))
        for path in sorted(set(_FILE_READ_RE.findall(_include_lines(log) + "\n" + _include_lines(sketch)))):
            record.violations.append({"type": "file_read_attempt", "detail": f"Compile tried to read {path}"})
        elf_b64 = payload.get("elf_b64") or ""
        elf = base64.b64decode(elf_b64) if payload.get("ok") and elf_b64 else None
        return CompileResult(ok=bool(payload.get("ok")) and elf is not None, log=log, elf=elf, record=record)

    def run(self, elf: bytes, scenario: dict, label: str, no_sim_cap: bool = False) -> RunResult:
        files = {"fw.elf": elf, "scenario.json": json.dumps(scenario).encode()}
        if no_sim_cap:
            files["no_sim_cap"] = b"1"
        output, record = self._execute("emulate", label, ["run"], files, self.settings.run_timeout_s)
        if record.timed_out:
            trace: dict = {"harness_error": True, "exit_reason": "timeout", "killed": True, "sim_ms": 0, "cycles": 0, "serial_log": [], "pin_events": [], "pwm_events": [], "input_trace": []}
            return RunResult(trace=trace, record=record)
        try:
            trace = json.loads(output)
        except json.JSONDecodeError:
            trace = {"harness_error": True, "log": output.decode("utf-8", "replace")[:4000]}
            record.violations.append({"type": "bad_output", "detail": "Harness output was not valid JSON"})
        if trace.get("harness_error"):
            record.violations.append({"type": "harness_error", "detail": str(trace.get("log", ""))[:500]})
        return RunResult(trace=trace, record=record)

    def probe(self, label: str = "sandbox self-inspection") -> tuple[dict, ContainmentRecord]:
        output, record = self._execute("probe", label, ["probe"], {"noop": b""}, self.settings.run_timeout_s)
        try:
            return json.loads(output), record
        except json.JSONDecodeError:
            return {"error": output.decode("utf-8", "replace")[:2000]}, record


def _include_lines(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if "include" in line or "No such file" in line or "fatal error" in line)

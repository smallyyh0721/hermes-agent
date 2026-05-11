"""SSH Connection Pool - Stable, secure SSH connections to target servers.

Design goals:
- ControlMaster-based connection reuse (single TCP connection per target)
- Automatic reconnection on failure
- Health checking with configurable intervals
- Secure defaults (StrictHostKeyChecking, no agent forwarding, etc.)
- Connection timeout and keepalive configuration
"""

import hashlib
import logging
import os
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class TargetHost:
    """Configuration for a single SSH target."""
    id: str
    host: str
    user: str
    port: int = 22
    keyfile: str = ""
    backend: str = "ssh"  # ssh | local
    role: str = ""
    owner: str = ""
    note: str = ""

    @property
    def display_name(self) -> str:
        if self.backend == "local":
            return f"{self.id} (local)"
        return f"{self.id} ({self.user}@{self.host}:{self.port})"


@dataclass
class ConnectionStatus:
    """Runtime state of a connection."""
    target: TargetHost
    state: ConnectionState = ConnectionState.DISCONNECTED
    last_connected: float = 0.0
    last_health_check: float = 0.0
    last_error: str = ""
    os_info: str = ""
    available_tools: List[str] = field(default_factory=list)


class SSHConnection:
    """A single managed SSH connection using ControlMaster.

    Provides:
    - Persistent connection via ControlMaster socket
    - Automatic keepalive (ServerAliveInterval)
    - Reconnection on failure
    - Command execution with timeout and output limits
    """

    # SSH options for security and stability
    # NOTE: ControlMaster is Linux/macOS only. On Windows, each command
    # spawns a fresh SSH connection (still fast with key auth).
    _CONTROLMASTER_OPTIONS = [
        ("ControlMaster", "auto"),
        ("ControlPersist", "600"),          # Keep connection alive 10 min after last use
    ]

    _COMMON_OPTIONS = [
        ("BatchMode", "yes"),               # No interactive prompts
        ("StrictHostKeyChecking", "accept-new"),  # Accept new keys, reject changed
        ("ConnectTimeout", "15"),           # Connection timeout
        ("ServerAliveInterval", "30"),      # Keepalive every 30s
        ("ServerAliveCountMax", "3"),       # Disconnect after 3 missed keepalives
        ("TCPKeepAlive", "yes"),            # OS-level TCP keepalive
        ("Compression", "yes"),             # Compress data (helps on slow links)
        ("LogLevel", "ERROR"),              # Suppress verbose SSH output
        ("ForwardAgent", "no"),             # Security: no agent forwarding
        ("ForwardX11", "no"),               # Security: no X11 forwarding
    ]

    def __init__(self, target: TargetHost, control_dir: Path = None):
        import platform as _platform
        self.target = target
        self._is_windows = _platform.system() == "Windows"

        if not self._is_windows:
            self.control_dir = control_dir or Path(tempfile.gettempdir()) / "proagent-ssh"
            self.control_dir.mkdir(parents=True, exist_ok=True)
            # Short deterministic socket name (avoid sun_path 104-byte limit on macOS)
            socket_id = hashlib.sha256(
                f"{target.user}@{target.host}:{target.port}".encode()
            ).hexdigest()[:16]
            self.control_socket = self.control_dir / f"{socket_id}.sock"
        else:
            self.control_dir = None
            self.control_socket = None

        self.state = ConnectionState.DISCONNECTED
        self.last_error = ""
        self._lock = threading.Lock()

    def _build_ssh_cmd(self, extra_args: List[str] = None) -> List[str]:
        """Build SSH command with all security and stability options."""
        cmd = ["ssh"]

        # ControlMaster only on Unix (Windows OpenSSH doesn't support Unix sockets)
        if not self._is_windows and self.control_socket:
            cmd.extend(["-o", f"ControlPath={self.control_socket}"])
            for key, value in self._CONTROLMASTER_OPTIONS:
                cmd.extend(["-o", f"{key}={value}"])

        for key, value in self._COMMON_OPTIONS:
            cmd.extend(["-o", f"{key}={value}"])

        if self.target.port != 22:
            cmd.extend(["-p", str(self.target.port)])
        if self.target.keyfile:
            keyfile = os.path.expanduser(self.target.keyfile)
            cmd.extend(["-i", keyfile])
        if extra_args:
            cmd.extend(extra_args)
        cmd.append(f"{self.target.user}@{self.target.host}")
        return cmd

    def connect(self) -> bool:
        """Establish SSH connection via ControlMaster.

        Returns True if connection is established successfully.
        """
        with self._lock:
            if self.state == ConnectionState.CONNECTED:
                # Check if existing connection is still alive
                if self._check_alive():
                    return True

            self.state = ConnectionState.CONNECTING
            cmd = self._build_ssh_cmd()
            cmd.append("echo 'proagent-connected'")

            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=20
                )
                if result.returncode == 0 and "proagent-connected" in result.stdout:
                    self.state = ConnectionState.CONNECTED
                    self.last_error = ""
                    logger.info("SSH connected: %s", self.target.display_name)
                    return True
                else:
                    error = result.stderr.strip() or result.stdout.strip()
                    self.state = ConnectionState.ERROR
                    self.last_error = error
                    logger.error("SSH connection failed to %s: %s", self.target.display_name, error)
                    return False
            except subprocess.TimeoutExpired:
                self.state = ConnectionState.ERROR
                self.last_error = "Connection timed out (20s)"
                logger.error("SSH connection timed out: %s", self.target.display_name)
                return False
            except Exception as e:
                self.state = ConnectionState.ERROR
                self.last_error = str(e)
                logger.error("SSH connection error to %s: %s", self.target.display_name, e)
                return False

    def _check_alive(self) -> bool:
        """Check if the ControlMaster socket is still alive."""
        if self._is_windows:
            # On Windows, no ControlMaster — just try a quick command
            cmd = self._build_ssh_cmd()
            cmd.append("echo alive")
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                return result.returncode == 0
            except (subprocess.TimeoutExpired, OSError):
                return False

        if not self.control_socket or not self.control_socket.exists():
            return False
        cmd = ["ssh", "-o", f"ControlPath={self.control_socket}", "-O", "check",
               f"{self.target.user}@{self.target.host}"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    def execute(self, command: str, timeout: int = 30, max_output_kb: int = 256) -> Tuple[int, str]:
        """Execute a command on the remote host.

        Args:
            command: Shell command to execute
            timeout: Maximum execution time in seconds
            max_output_kb: Maximum output size in KB

        Returns:
            Tuple of (return_code, output_text)
        """
        # Ensure connected
        if self.state != ConnectionState.CONNECTED:
            if not self.connect():
                return (-1, f"SSH not connected: {self.last_error}")

        cmd = self._build_ssh_cmd()
        cmd.extend(["bash", "-c", shlex.quote(command)])

        max_bytes = max_output_kb * 1024

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = result.stdout
            if result.stderr:
                output += "\n[stderr]\n" + result.stderr

            # Truncate if too large
            if len(output.encode("utf-8")) > max_bytes:
                output = output[:max_bytes] + "\n... [output truncated]"

            return (result.returncode, output)

        except subprocess.TimeoutExpired:
            return (-1, f"Command timed out after {timeout}s")
        except Exception as e:
            # Connection may have dropped
            self.state = ConnectionState.ERROR
            self.last_error = str(e)
            return (-1, f"SSH execution error: {e}")

    def disconnect(self) -> None:
        """Gracefully close the SSH connection."""
        with self._lock:
            if not self._is_windows and self.control_socket and self.control_socket.exists():
                try:
                    cmd = ["ssh", "-o", f"ControlPath={self.control_socket}",
                           "-O", "exit", f"{self.target.user}@{self.target.host}"]
                    subprocess.run(cmd, capture_output=True, timeout=5)
                except (OSError, subprocess.SubprocessError):
                    pass
                try:
                    self.control_socket.unlink()
                except OSError:
                    pass
            self.state = ConnectionState.DISCONNECTED

    def health_check(self) -> Dict[str, Any]:
        """Run a quick health check on the connection.

        Returns dict with connection status and basic remote info.
        """
        if self.state != ConnectionState.CONNECTED:
            if not self.connect():
                return {"status": "error", "error": self.last_error}

        rc, output = self.execute("uname -a && uptime", timeout=10)
        if rc == 0:
            return {"status": "ok", "info": output.strip()}
        else:
            return {"status": "degraded", "error": output}


class SSHPool:
    """Pool of SSH connections to multiple target hosts.

    Manages connection lifecycle, health checking, and reconnection.
    """

    def __init__(self, targets: List[TargetHost] = None):
        self._connections: Dict[str, SSHConnection] = {}
        self._statuses: Dict[str, ConnectionStatus] = {}
        self._lock = threading.Lock()

        if targets:
            for target in targets:
                self.add_target(target)

    def add_target(self, target: TargetHost) -> None:
        """Add a target host to the pool."""
        with self._lock:
            if target.backend == "local":
                # Local targets don't need SSH
                self._statuses[target.id] = ConnectionStatus(
                    target=target,
                    state=ConnectionState.CONNECTED,
                )
                return

            conn = SSHConnection(target)
            self._connections[target.id] = conn
            self._statuses[target.id] = ConnectionStatus(target=target)

    def remove_target(self, target_id: str) -> None:
        """Remove a target and close its connection."""
        with self._lock:
            conn = self._connections.pop(target_id, None)
            self._statuses.pop(target_id, None)
        if conn:
            conn.disconnect()

    def connect(self, target_id: str) -> bool:
        """Connect to a specific target. Returns True on success."""
        conn = self._connections.get(target_id)
        if conn is None:
            # Check if it's a local target
            status = self._statuses.get(target_id)
            if status and status.target.backend == "local":
                return True
            return False

        success = conn.connect()
        status = self._statuses.get(target_id)
        if status:
            status.state = conn.state
            if success:
                status.last_connected = time.time()
            else:
                status.last_error = conn.last_error
        return success

    def connect_all(self) -> Dict[str, bool]:
        """Connect to all targets. Returns {target_id: success}."""
        results = {}
        for target_id in list(self._connections.keys()):
            results[target_id] = self.connect(target_id)
        # Local targets are always "connected"
        for target_id, status in self._statuses.items():
            if status.target.backend == "local":
                results[target_id] = True
        return results

    def execute(self, target_id: str, command: str, timeout: int = 30) -> Tuple[int, str]:
        """Execute a command on a target host.

        For local targets, executes directly via subprocess.
        For SSH targets, executes via the SSH connection.
        """
        status = self._statuses.get(target_id)
        if not status:
            return (-1, f"Unknown target: {target_id}")

        if status.target.backend == "local":
            return self._execute_local(command, timeout)

        conn = self._connections.get(target_id)
        if not conn:
            return (-1, f"No connection for target: {target_id}")

        return conn.execute(command, timeout)

    def _execute_local(self, command: str, timeout: int = 30) -> Tuple[int, str]:
        """Execute a command locally."""
        try:
            result = subprocess.run(
                ["bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = result.stdout
            if result.stderr:
                output += "\n[stderr]\n" + result.stderr
            return (result.returncode, output)
        except subprocess.TimeoutExpired:
            return (-1, f"Command timed out after {timeout}s")
        except FileNotFoundError:
            # Windows fallback
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    shell=True,
                )
                output = result.stdout
                if result.stderr:
                    output += "\n[stderr]\n" + result.stderr
                return (result.returncode, output)
            except subprocess.TimeoutExpired:
                return (-1, f"Command timed out after {timeout}s")

    def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Run health checks on all targets."""
        results = {}
        for target_id, conn in self._connections.items():
            results[target_id] = conn.health_check()
            status = self._statuses.get(target_id)
            if status:
                status.last_health_check = time.time()
        # Local targets
        for target_id, status in self._statuses.items():
            if status.target.backend == "local" and target_id not in results:
                rc, output = self._execute_local("uname -a 2>/dev/null || ver", timeout=5)
                results[target_id] = {"status": "ok" if rc == 0 else "error", "info": output.strip()}
                status.last_health_check = time.time()
        return results

    def get_status(self, target_id: str = None) -> Dict[str, Any]:
        """Get connection status for one or all targets."""
        if target_id:
            status = self._statuses.get(target_id)
            if not status:
                return {"error": f"Unknown target: {target_id}"}
            return {
                "id": status.target.id,
                "display": status.target.display_name,
                "state": status.state.value,
                "last_connected": status.last_connected,
                "last_health_check": status.last_health_check,
                "last_error": status.last_error,
            }
        return {
            tid: {
                "display": s.target.display_name,
                "state": s.state.value,
                "last_error": s.last_error,
            }
            for tid, s in self._statuses.items()
        }

    def disconnect_all(self) -> None:
        """Disconnect all SSH connections."""
        for conn in self._connections.values():
            conn.disconnect()

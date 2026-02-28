"""Credential encryption and credentials.json management."""

import json
import logging
import os
from pathlib import Path
from cryptography.fernet import Fernet

logger = logging.getLogger("mtcs.credentials")


class CredentialManager:
    """Manage encrypted credentials with Fernet symmetric encryption."""

    def __init__(self, data_dir: Path | str):
        self.data_dir = Path(data_dir)
        self.key_file = self.data_dir / ".key"
        self.cred_file = self.data_dir / "credentials.json"
        self._fernet: Fernet | None = None
        self._file_mtime: float = 0.0

    def _ensure_key(self) -> bytes:
        """Load or generate the Fernet encryption key."""
        if self.key_file.exists():
            key = self.key_file.read_bytes().strip()
        else:
            key = Fernet.generate_key()
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.key_file.write_bytes(key)
            # Restrict permissions on Windows
            try:
                import subprocess
                subprocess.run(
                    ["icacls", str(self.key_file), "/inheritance:r",
                     "/grant:r", f"{os.getenv('USERNAME', 'User')}:F"],
                    capture_output=True, timeout=5
                )
            except Exception:
                pass  # Best-effort permission restriction
            logger.info("Generated new encryption key")
        return key

    def initialize(self) -> None:
        """Initialize the Fernet cipher."""
        key = self._ensure_key()
        self._fernet = Fernet(key)
        logger.info("Credential encryption initialized")

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string and return base64 token."""
        if not self._fernet:
            self.initialize()
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        """Decrypt a Fernet token back to plaintext."""
        if not self._fernet:
            self.initialize()
        return self._fernet.decrypt(token.encode()).decode()

    def load_credentials(self) -> list[dict]:
        """Load credentials from JSON file. Passwords are stored encrypted."""
        if not self.cred_file.exists():
            return []
        try:
            data = json.loads(self.cred_file.read_text(encoding="utf-8"))
            self._file_mtime = self.cred_file.stat().st_mtime
            accounts = data.get("accounts", [])
            logger.info(f"Loaded {len(accounts)} accounts from credentials.json")
            return accounts
        except Exception as e:
            logger.error(f"Failed to load credentials.json: {e}")
            return []

    def save_credentials(self, accounts: list[dict]) -> None:
        """Save credentials to JSON file with encrypted passwords."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        data = {"accounts": accounts}
        self.cred_file.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
        self._file_mtime = self.cred_file.stat().st_mtime
        logger.info(f"Saved {len(accounts)} accounts to credentials.json")

    def has_file_changed(self) -> bool:
        """Check if credentials.json was modified externally."""
        if not self.cred_file.exists():
            return False
        current_mtime = self.cred_file.stat().st_mtime
        return current_mtime != self._file_mtime

    def add_account(self, login: int, password: str, server: str, role: str) -> list[dict]:
        """Add an account with encrypted password."""
        accounts = self.load_credentials()
        encrypted_pw = self.encrypt(password)

        # Check for existing account with same login
        for acc in accounts:
            if acc["login"] == login:
                acc["encrypted_password"] = encrypted_pw
                acc["server"] = server
                acc["role"] = role
                self.save_credentials(accounts)
                return accounts

        accounts.append({
            "login": login,
            "encrypted_password": encrypted_pw,
            "server": server,
            "role": role,
        })
        self.save_credentials(accounts)
        return accounts

    def remove_account(self, login: int) -> list[dict]:
        """Remove an account by login."""
        accounts = self.load_credentials()
        accounts = [a for a in accounts if a["login"] != login]
        self.save_credentials(accounts)
        return accounts

    def get_decrypted_password(self, login: int) -> str | None:
        """Get decrypted password for a specific account."""
        accounts = self.load_credentials()
        for acc in accounts:
            if acc["login"] == login:
                return self.decrypt(acc["encrypted_password"])
        return None

    def test_roundtrip(self) -> bool:
        """Test encrypt/decrypt round-trip."""
        self.initialize()
        test_value = "TestPassword123!@#"
        encrypted = self.encrypt(test_value)
        decrypted = self.decrypt(encrypted)
        success = decrypted == test_value
        logger.info(f"Credential round-trip test: {'PASS' if success else 'FAIL'}")
        return success

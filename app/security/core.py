"""
Core Security Module - 核心安全模块
Provides encryption and password hashing functionality.
"""

import os
import base64
import json
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from threading import Lock

from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash


class EncryptionManager:
    """
    Manages field-level encryption using Fernet (AES-128-CBC with HMAC).
    加密管理器 - 使用 Fernet 进行字段级加密
    """
    
    KEYS_FILE = "encryption_keys.dat"
    SALT_SIZE = 16
    
    def __init__(self, master_key: str, keys_dir: Optional[str] = None):
        """
        Initialize encryption manager with master key.
        
        Args:
            master_key: The master password used to derive encryption keys
            keys_dir: Directory to store encrypted keys file
        """
        self.master_key = master_key
        self.keys_dir = Path(keys_dir) if keys_dir else Path(".")
        self.keys_file = self.keys_dir / self.KEYS_FILE
        
        # Load or create encryption keys
        self._load_or_create_keys()
    
    def _derive_key_from_master(self, salt: bytes) -> bytes:
        """Derive a Fernet key from the master password using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
        return key
    
    def _load_or_create_keys(self):
        """Load existing keys or create new ones."""
        if self.keys_file.exists():
            self._load_keys()
        else:
            self._create_keys()
    
    def _create_keys(self):
        """Create new encryption keys and save them."""
        # Generate a new Fernet key
        self.data_key = Fernet.generate_key()
        self.fernet_keys = [Fernet(self.data_key)]
        self.fernet = MultiFernet(self.fernet_keys)
        
        # Encrypt and save the data key
        self._save_keys()
    
    def _save_keys(self):
        """Save encrypted keys to file."""
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate salt for key derivation
        salt = os.urandom(self.SALT_SIZE)
        
        # Derive key from master password
        key_encryption_key = self._derive_key_from_master(salt)
        key_fernet = Fernet(key_encryption_key)
        
        # Prepare keys data
        keys_data = {
            "version": 1,
            "keys": [base64.urlsafe_b64encode(self.data_key).decode()],
            "created_at": datetime.utcnow().isoformat(),
        }
        
        # Encrypt keys data
        encrypted_data = key_fernet.encrypt(json.dumps(keys_data).encode())
        
        # Write to file: salt + encrypted data
        with open(self.keys_file, "wb") as f:
            f.write(salt)
            f.write(encrypted_data)
    
    def _load_keys(self):
        """Load and decrypt keys from file."""
        with open(self.keys_file, "rb") as f:
            salt = f.read(self.SALT_SIZE)
            encrypted_data = f.read()
        
        # Derive key from master password
        key_encryption_key = self._derive_key_from_master(salt)
        key_fernet = Fernet(key_encryption_key)
        
        try:
            # Decrypt keys data
            decrypted_data = key_fernet.decrypt(encrypted_data)
            keys_data = json.loads(decrypted_data.decode())
            
            # Load keys
            self.data_key = base64.urlsafe_b64decode(keys_data["keys"][0])
            self.fernet_keys = [
                Fernet(base64.urlsafe_b64decode(k)) for k in keys_data["keys"]
            ]
            self.fernet = MultiFernet(self.fernet_keys)
        except InvalidToken:
            raise ValueError("Invalid master key - unable to decrypt encryption keys")
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.
        
        Args:
            plaintext: The string to encrypt
            
        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            return plaintext
        
        encrypted = self.fernet.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string.
        
        Args:
            ciphertext: Base64-encoded encrypted string
            
        Returns:
            Decrypted plaintext string
        """
        if not ciphertext:
            return ciphertext
        
        try:
            encrypted = base64.urlsafe_b64decode(ciphertext.encode())
            decrypted = self.fernet.decrypt(encrypted)
            return decrypted.decode()
        except (InvalidToken, ValueError):
            # Return original if decryption fails (might not be encrypted)
            return ciphertext
    
    def rotate_key(self) -> None:
        """
        Rotate encryption keys. Old keys are retained for decryption.
        密钥轮换 - 保留旧密钥用于解密历史数据
        """
        # Generate new key
        new_key = Fernet.generate_key()
        new_fernet = Fernet(new_key)
        
        # Add new key to the front (primary key)
        self.fernet_keys.insert(0, new_fernet)
        self.fernet = MultiFernet(self.fernet_keys)
        self.data_key = new_key
        
        # Save updated keys
        self._save_keys_multi()
    
    def _save_keys_multi(self):
        """Save multiple keys to file."""
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        
        salt = os.urandom(self.SALT_SIZE)
        key_encryption_key = self._derive_key_from_master(salt)
        key_fernet = Fernet(key_encryption_key)
        
        # Get all keys as base64
        all_keys = []
        for fernet in self.fernet_keys:
            # Extract key from Fernet instance
            key_bytes = fernet._signing_key + fernet._encryption_key
            all_keys.append(base64.urlsafe_b64encode(
                base64.urlsafe_b64encode(key_bytes)
            ).decode())
        
        keys_data = {
            "version": 2,
            "keys": all_keys,
            "rotated_at": datetime.utcnow().isoformat(),
        }
        
        encrypted_data = key_fernet.encrypt(json.dumps(keys_data).encode())
        
        with open(self.keys_file, "wb") as f:
            f.write(salt)
            f.write(encrypted_data)
    
    @staticmethod
    def redact_sensitive(value: str, show_last: int = 4) -> str:
        """
        Redact sensitive data, showing only last N characters.
        脱敏处理 - 只显示最后N位
        
        Args:
            value: The sensitive string to redact
            show_last: Number of characters to show at the end
            
        Returns:
            Redacted string with asterisks
        """
        if not value or len(value) <= show_last:
            return "*" * len(value) if value else ""
        
        hidden_count = len(value) - show_last
        return "*" * hidden_count + value[-show_last:]


class PasswordManager:
    """
    Manages password hashing using Argon2id.
    密码管理器 - 使用 Argon2id 进行密码哈希
    """
    
    def __init__(
        self,
        time_cost: int = 3,
        memory_cost: int = 65536,
        parallelism: int = 4,
    ):
        """
        Initialize password manager with Argon2 parameters.
        
        Args:
            time_cost: Number of iterations
            memory_cost: Memory usage in KiB
            parallelism: Number of parallel threads
        """
        self.hasher = PasswordHasher(
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            hash_len=32,
            salt_len=16,
        )
    
    def hash_password(self, password: str) -> str:
        """
        Hash a password using Argon2id.
        
        Args:
            password: The plaintext password
            
        Returns:
            Argon2 hash string
        """
        return self.hasher.hash(password)
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify a password against a hash.
        
        Args:
            password: The plaintext password to verify
            password_hash: The stored Argon2 hash
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            self.hasher.verify(password_hash, password)
            return True
        except (VerifyMismatchError, InvalidHash):
            return False
    
    def needs_rehash(self, password_hash: str) -> bool:
        """
        Check if a password hash needs to be rehashed.
        
        Args:
            password_hash: The stored Argon2 hash
            
        Returns:
            True if hash should be regenerated
        """
        return self.hasher.check_needs_rehash(password_hash)


# Singleton instances
_encryption_manager: Optional[EncryptionManager] = None
_password_manager: Optional[PasswordManager] = None
_encryption_lock = Lock()  # 线程锁保护加密管理器初始化
_password_lock = Lock()     # 线程锁保护密码管理器初始化


def get_encryption_manager(master_key: Optional[str] = None) -> EncryptionManager:
    """
    Get or create the singleton EncryptionManager instance (thread-safe).

    Args:
        master_key: Master key for encryption (required on first call)

    Returns:
        EncryptionManager instance
    """
    global _encryption_manager

    # 双重检查锁定模式（Double-Checked Locking）
    if _encryption_manager is None:
        with _encryption_lock:
            # 再次检查，防止多个线程同时通过第一次检查
            if _encryption_manager is None:
                if master_key is None:
                    # 尝试从 Streamlit session state 获取（优先级最高）
                    try:
                        import streamlit as st
                        master_key = st.session_state.get("master_key")
                    except:
                        pass

                    # 仅在测试环境使用环境变量
                    if master_key is None and os.environ.get("TESTING") == "true":
                        master_key = os.environ.get("TEST_MASTER_KEY")

                    if master_key is None:
                        raise ValueError("需要主密钥才能初始化加密服务。请确保您已登录并正确输入主密钥。")

                keys_dir = os.environ.get("KEYS_DIR", ".")
                _encryption_manager = EncryptionManager(master_key, keys_dir)

    return _encryption_manager


def get_password_manager() -> PasswordManager:
    """
    Get or create the singleton PasswordManager instance (thread-safe).

    Returns:
        PasswordManager instance
    """
    global _password_manager

    # 双重检查锁定模式
    if _password_manager is None:
        with _password_lock:
            if _password_manager is None:
                _password_manager = PasswordManager()

    return _password_manager


def reset_managers():
    """Reset singleton instances (for testing purposes)."""
    global _encryption_manager, _password_manager
    _encryption_manager = None
    _password_manager = None

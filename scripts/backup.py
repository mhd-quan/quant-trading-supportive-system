#!/usr/bin/env python3
"""Backup script for Crypto Research Platform."""

import argparse
import os
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger


class BackupManager:
    """Manage database and configuration backups."""

    def __init__(
        self,
        data_path: str = "./data",
        backup_path: str = "./backups",
        config_path: str = "./configs",
    ):
        """Initialize backup manager.

        Args:
            data_path: Path to data directory
            backup_path: Path to store backups
            config_path: Path to configuration files
        """
        self.data_path = Path(data_path)
        self.backup_path = Path(backup_path)
        self.config_path = Path(config_path)

        # Create backup directory
        self.backup_path.mkdir(parents=True, exist_ok=True)

    def create_backup(
        self,
        include_data: bool = True,
        include_configs: bool = True,
        compress: bool = True,
        encrypt: bool = False,
        retention_days: int = 30,
    ) -> Path:
        """Create a complete backup.

        Args:
            include_data: Include database and data files
            include_configs: Include configuration files
            compress: Compress the backup
            encrypt: Encrypt the backup (requires GPG)
            retention_days: Delete backups older than this

        Returns:
            Path to backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = self.backup_path / timestamp

        logger.info(f"Creating backup: {backup_dir}")

        # Create temporary backup directory
        backup_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Backup database
            if include_data:
                logger.info("Backing up database...")
                self._backup_database(backup_dir)

            # Backup Parquet files
            if include_data:
                logger.info("Backing up Parquet files...")
                self._backup_parquet_files(backup_dir)

            # Backup configurations
            if include_configs:
                logger.info("Backing up configurations...")
                self._backup_configs(backup_dir)

            # Create tarball
            if compress:
                logger.info("Compressing backup...")
                archive_path = self._create_tarball(backup_dir, timestamp)

                # Encrypt if requested
                if encrypt:
                    logger.info("Encrypting backup...")
                    archive_path = self._encrypt_backup(archive_path)

                # Clean up temporary directory
                shutil.rmtree(backup_dir)
            else:
                archive_path = backup_dir

            # Clean old backups
            self._cleanup_old_backups(retention_days)

            logger.info(f"Backup created: {archive_path}")
            return archive_path

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            # Clean up on failure
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            raise

    def _backup_database(self, backup_dir: Path) -> None:
        """Backup DuckDB database."""
        db_file = self.data_path / "crypto.duckdb"

        if not db_file.exists():
            logger.warning(f"Database not found: {db_file}")
            return

        dest = backup_dir / "database"
        dest.mkdir(exist_ok=True)

        # Copy database file
        shutil.copy2(db_file, dest / "crypto.duckdb")

        # Also backup WAL files if they exist
        wal_file = Path(str(db_file) + ".wal")
        if wal_file.exists():
            shutil.copy2(wal_file, dest / "crypto.duckdb.wal")

        logger.info(f"Database backed up: {db_file.stat().st_size / 1024 / 1024:.2f} MB")

    def _backup_parquet_files(self, backup_dir: Path) -> None:
        """Backup Parquet data lake."""
        lake_path = self.data_path / "lake"

        if not lake_path.exists():
            logger.warning(f"Data lake not found: {lake_path}")
            return

        dest = backup_dir / "lake"

        # Copy entire lake directory
        shutil.copytree(lake_path, dest)

        # Calculate total size
        total_size = sum(
            f.stat().st_size for f in dest.rglob("*") if f.is_file()
        )

        logger.info(f"Parquet files backed up: {total_size / 1024 / 1024:.2f} MB")

    def _backup_configs(self, backup_dir: Path) -> None:
        """Backup configuration files."""
        if not self.config_path.exists():
            logger.warning(f"Config path not found: {self.config_path}")
            return

        dest = backup_dir / "configs"
        shutil.copytree(self.config_path, dest)

        # Also backup .env file if it exists
        env_file = Path(".env")
        if env_file.exists():
            shutil.copy2(env_file, dest / ".env")

        logger.info("Configuration files backed up")

    def _create_tarball(self, backup_dir: Path, timestamp: str) -> Path:
        """Create compressed tarball of backup."""
        archive_path = self.backup_path / f"backup-{timestamp}.tar.gz"

        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(backup_dir, arcname=timestamp)

        size_mb = archive_path.stat().st_size / 1024 / 1024
        logger.info(f"Archive created: {size_mb:.2f} MB")

        return archive_path

    def _encrypt_backup(self, archive_path: Path) -> Path:
        """Encrypt backup using GPG."""
        encrypted_path = Path(str(archive_path) + ".gpg")

        try:
            subprocess.run(
                [
                    "gpg",
                    "--symmetric",
                    "--cipher-algo",
                    "AES256",
                    "--output",
                    str(encrypted_path),
                    str(archive_path),
                ],
                check=True,
            )

            # Remove unencrypted archive
            archive_path.unlink()

            logger.info("Backup encrypted")
            return encrypted_path

        except subprocess.CalledProcessError as e:
            logger.error(f"Encryption failed: {e}")
            raise

    def _cleanup_old_backups(self, retention_days: int) -> None:
        """Delete backups older than retention period."""
        cutoff_time = datetime.now().timestamp() - (retention_days * 86400)

        deleted_count = 0
        for backup in self.backup_path.glob("backup-*"):
            if backup.stat().st_mtime < cutoff_time:
                logger.info(f"Deleting old backup: {backup}")
                backup.unlink()
                deleted_count += 1

        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} old backups")

    def restore_backup(self, backup_file: Path, decrypt: bool = False) -> None:
        """Restore from backup.

        Args:
            backup_file: Path to backup file
            decrypt: Whether to decrypt first
        """
        logger.info(f"Restoring backup from: {backup_file}")

        # Decrypt if needed
        if decrypt:
            logger.info("Decrypting backup...")
            decrypted_path = Path(str(backup_file).replace(".gpg", ""))

            subprocess.run(
                [
                    "gpg",
                    "--decrypt",
                    "--output",
                    str(decrypted_path),
                    str(backup_file),
                ],
                check=True,
            )

            backup_file = decrypted_path

        # Extract tarball
        logger.info("Extracting backup...")
        with tarfile.open(backup_file, "r:gz") as tar:
            tar.extractall(path=self.backup_path / "restore")

        # Find extracted directory
        restore_dir = next((self.backup_path / "restore").iterdir())

        # Restore database
        if (restore_dir / "database").exists():
            logger.info("Restoring database...")
            db_file = restore_dir / "database" / "crypto.duckdb"
            shutil.copy2(db_file, self.data_path / "crypto.duckdb")

        # Restore Parquet files
        if (restore_dir / "lake").exists():
            logger.info("Restoring Parquet files...")
            lake_dest = self.data_path / "lake"
            if lake_dest.exists():
                shutil.rmtree(lake_dest)
            shutil.copytree(restore_dir / "lake", lake_dest)

        # Restore configs
        if (restore_dir / "configs").exists():
            logger.info("Restoring configurations...")
            for config_file in (restore_dir / "configs").glob("*"):
                shutil.copy2(config_file, self.config_path / config_file.name)

        # Clean up
        shutil.rmtree(self.backup_path / "restore")

        if decrypt and decrypted_path.exists():
            decrypted_path.unlink()

        logger.info("Restore completed")


def run_backup(
    data_path: str = "./data",
    backup_path: str = "./backups",
    encrypt: bool = False,
) -> None:
    """Run backup operation.

    Args:
        data_path: Path to data directory
        backup_path: Path to store backups
        encrypt: Encrypt the backup
    """
    manager = BackupManager(data_path=data_path, backup_path=backup_path)

    manager.create_backup(
        include_data=True,
        include_configs=True,
        compress=True,
        encrypt=encrypt,
        retention_days=30,
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Backup crypto research platform")

    parser.add_argument(
        "--data-path",
        default="./data",
        help="Path to data directory (default: ./data)",
    )
    parser.add_argument(
        "--backup-path",
        default="./backups",
        help="Path to store backups (default: ./backups)",
    )
    parser.add_argument(
        "--encrypt",
        action="store_true",
        help="Encrypt backup with GPG",
    )
    parser.add_argument(
        "--restore",
        type=str,
        help="Restore from backup file",
    )
    parser.add_argument(
        "--decrypt",
        action="store_true",
        help="Decrypt backup before restoring",
    )

    args = parser.parse_args()

    manager = BackupManager(
        data_path=args.data_path,
        backup_path=args.backup_path,
    )

    if args.restore:
        # Restore mode
        manager.restore_backup(
            backup_file=Path(args.restore),
            decrypt=args.decrypt,
        )
    else:
        # Backup mode
        manager.create_backup(
            include_data=True,
            include_configs=True,
            compress=True,
            encrypt=args.encrypt,
            retention_days=30,
        )


if __name__ == "__main__":
    main()

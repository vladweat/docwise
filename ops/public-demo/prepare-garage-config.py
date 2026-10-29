#!/usr/bin/env python3
"""Create private, persistent Garage configuration for the public demo."""

from pathlib import Path
from secrets import token_hex, token_urlsafe


config_path = Path(__file__).with_name("garage.local.toml")
if config_path.exists():
    raise SystemExit(f"{config_path} already exists; remove it only to rotate Garage secrets")

config = f'''metadata_dir = "/var/lib/garage/meta"
data_dir = "/var/lib/garage/data"
db_engine = "sqlite"
replication_factor = 1
rpc_bind_addr = "[::]:3901"
rpc_public_addr = "127.0.0.1:3901"
rpc_secret = "{token_hex(32)}"

[s3_api]
api_bind_addr = "[::]:3900"
s3_region = "garage"
root_domain = ".s3.garage.localhost"
public_endpoint = "http://minio:3900"

[admin]
api_bind_addr = "0.0.0.0:3903"
admin_token = "{token_urlsafe(32)}"
metrics_token = "{token_urlsafe(32)}"
'''
config_path.write_text(config, encoding="utf-8")
config_path.chmod(0o600)
print(f"Created {config_path} with mode 0600")

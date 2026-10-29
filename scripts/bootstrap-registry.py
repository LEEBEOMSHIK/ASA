"""Create ASA's isolated local PostgreSQL cluster, never change another project's DB."""
import os
from pathlib import Path
import secrets
import socket
import subprocess
from uuid import uuid4

import psycopg
from psycopg import sql

from asa.registry.repository import migrate

root = Path(__file__).resolve().parents[1]
local = root / ".local"
data = local / "postgres"
env_file = root / ".env"
bin_dir = Path(os.environ.get("ASA_POSTGRES_BIN", "C:/Program Files/PostgreSQL/18/bin"))
port = int(os.environ.get("ASA_POSTGRES_PORT", "55439"))
template_env = root / ".env.example"
is_template = env_file.exists() and env_file.read_bytes() == template_env.read_bytes()
if (env_file.exists() and not is_template) or data.exists():
    raise SystemExit("Existing .env or cluster found; refusing to overwrite. See local development guide.")
if not (bin_dir / "initdb.exe").is_file():
    raise SystemExit("Set ASA_POSTGRES_BIN to the installed PostgreSQL bin directory.")
with socket.socket() as probe:
    probe.bind(("127.0.0.1", port))
local.mkdir(exist_ok=True)
admin_password = secrets.token_hex(32)
app_password = secrets.token_hex(32)
owner_key = secrets.token_urlsafe(36)
workspace = uuid4()
pwfile = local / "postgres-init-password"
pwfile.write_text(admin_password, encoding="utf-8")
flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
try:
    subprocess.run([str(bin_dir / "initdb.exe"), "-D", str(data), "-U", "asa_admin",
                    "--pwfile", str(pwfile), "--auth=scram-sha-256", "--encoding=UTF8",
                    "--locale=C"], check=True, creationflags=flags, capture_output=True)
finally:
    pwfile.unlink(missing_ok=True)
with (data / "postgresql.conf").open("a", encoding="utf-8") as config:
    config.write(f"\nlisten_addresses = '127.0.0.1'\nport = {port}\n")
subprocess.run([str(bin_dir / "pg_ctl.exe"), "-D", str(data), "-l", str(local / "postgres.log"),
                "-w", "start"], check=True, creationflags=flags,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
admin_dsn = f"postgresql://asa_admin:{admin_password}@127.0.0.1:{port}/postgres"
with psycopg.connect(admin_dsn, autocommit=True) as conn:
    conn.execute(sql.SQL("CREATE ROLE asa_app LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE")
                 .format(sql.Literal(app_password)))
    conn.execute("CREATE DATABASE asa OWNER asa_app")
    conn.execute("CREATE DATABASE asa_registry_test OWNER asa_app")
dsn = f"postgresql://asa_app:{app_password}@127.0.0.1:{port}/asa"
test_dsn = f"postgresql://asa_app:{app_password}@127.0.0.1:{port}/asa_registry_test"
migrate(dsn, workspace)
env_file.write_text(
    f"ASA_DATABASE_URL={dsn}\nASA_TEST_DATABASE_URL={test_dsn}\n"
    f"ASA_OWNER_ACCESS_KEY={owner_key}\nASA_WORKSPACE_ID={workspace}\n"
    "ASA_AI_PROVIDER=openai\nASA_AI_MODEL=\nASA_AI_API_KEY=\n"
    "ASA_AI_TIMEOUT_SECONDS=60\nASA_FFMPEG_PATH=ffmpeg\nLANGSMITH_TRACING=false\n",
    encoding="utf-8",
)
(local / "postgres-admin.env").write_text(f"ASA_ADMIN_DATABASE_URL={admin_dsn}\n", encoding="utf-8")
print(f"ASA local DB ready on 127.0.0.1:{port}. Owner access key saved in .env; no secrets printed.")

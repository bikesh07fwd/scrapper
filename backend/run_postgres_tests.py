"""
backend/run_postgres_tests.py — Isolated PostgreSQL Test Database Runner.

Creates a temporary isolated test database on Neon, runs the full pytest suite
with coverage tracking, and drops the test database cleanly afterward.
"""

import os
import sys
import asyncio
import subprocess
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def main():
    # Load DATABASE_URL from environment or local .env
    prod_url = os.getenv("DATABASE_URL")
    if not prod_url:
        # Try loading from .env file
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    if line.startswith("DATABASE_URL="):
                        prod_url = line.split("=", 1)[1].strip()
                        break
                        
    if not prod_url:
        print("DATABASE_URL is not defined in environment or .env. Cannot run PostgreSQL tests.")
        sys.exit(1)
        
    # Extract base URL and build test database URL
    base_url = prod_url.rsplit("/", 1)[0]
    test_db_name = "neondb_test"
    test_url = f"{base_url}/{test_db_name}"
    
    print(f"\n[1/4] Connecting to Neon to provision isolated test database: '{test_db_name}'...")
    
    # Connect to primary db using autocommit mode to run CREATE DATABASE
    admin_engine = create_async_engine(prod_url, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        try:
            # Check if database exists
            res = await conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname='{test_db_name}'"))
            if not res.scalar():
                await conn.execute(text(f"CREATE DATABASE {test_db_name}"))
                print(f"-> Database '{test_db_name}' created successfully on Neon.")
            else:
                print(f"-> Database '{test_db_name}' already exists. Reusing it.")
        except Exception as e:
            print(f"Error creating database: {e}")
            await admin_engine.dispose()
            sys.exit(1)
            
    await admin_engine.dispose()
    
    # 2. Run pytest with TEST_DATABASE_URL set
    os.environ["TEST_DATABASE_URL"] = test_url
    print(f"\n[2/4] Executing pytest test suite with coverage tracking...")
    print(f"-> TEST_DATABASE_URL is set to isolated endpoint.")
    
    cwd = os.path.dirname(__file__)
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
        "--cov=.",
        "--cov-report=term-missing",
    ]
    
    exit_code = 0
    try:
        # Run subprocess
        res = subprocess.run(cmd, cwd=cwd)
        exit_code = res.returncode
    except Exception as e:
        print(f"Failed to run pytest: {e}")
        exit_code = 1
        
    # 3. Drop test database to clean up Neon cluster
    print(f"\n[3/4] Terminating test connections and dropping database '{test_db_name}'...")
    admin_engine = create_async_engine(prod_url, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        try:
            # Terminate active test sessions to allow drop database
            await conn.execute(text(
                f"SELECT pg_terminate_backend(pg_stat_activity.pid) "
                f"FROM pg_stat_activity "
                f"WHERE pg_stat_activity.datname = '{test_db_name}' "
                f"AND pid <> pg_backend_pid()"
            ))
            await conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name}"))
            print(f"-> Database '{test_db_name}' dropped cleanly.")
        except Exception as e:
            print(f"Error dropping database: {e}")
            
    await admin_engine.dispose()
    
    print(f"\n[4/4] Verification finished. Exit code: {exit_code}\n")
    sys.exit(exit_code)


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

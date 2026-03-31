#!/usr/bin/env python3
"""
Destructive database wipe script — USE WITH CAUTION.
Destroys ALL business tables in PostgreSQL and flushes Redis DB 0.

Usage:
    export POSTGRES_USER=your_user
    export POSTGRES_PASSWORD=your_password
    export POSTGRES_HOST=localhost
    export POSTGRES_PORT=5433
    export POSTGRES_DB=canteen_system
    export REDIS_HOST=localhost
    export REDIS_PORT=6380
    python scripts/wipe_dbs.py

Or edit the DEFAULT VALUES below.
"""

import os
import sys

# ── Credentials (edit these or set environment variables) ─────────────────────
PG_USER     = os.getenv("POSTGRES_USER", "postgres")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
PG_HOST     = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT     = os.getenv("POSTGRES_PORT", "5433")
PG_DB       = os.getenv("POSTGRES_DB", "canteen_system")

REDIS_HOST  = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT  = int(os.getenv("REDIS_PORT", "6380"))
REDIS_DB    = int(os.getenv("REDIS_DB", "0"))

# ── PostgreSQL ───────────────────────────────────────────────────────────────


def wipe_postgres():
    print(f"\n{'='*60}")
    print("  PostgreSQL 焦土政策")
    print(f"{'='*60}")
    print(f"  Target: postgresql://{PG_USER}:***@{PG_HOST}:{PG_PORT}/{PG_DB}")
    print()

    try:
        from sqlalchemy import create_engine, text, inspect
    except ImportError:
        print("[ERROR] sqlalchemy not installed: pip install sqlalchemy")
        sys.exit(1)

    DATABASE_URL = (
        f"postgresql://{PG_USER}:{PG_PASSWORD}@"
        f"{PG_HOST}:{PG_PORT}/{PG_DB}"
    )

    engine = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")

    # Connect and check
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        print(f"  [OK] Connected to PostgreSQL — {PG_DB}")

    # Reflect all tables
    inspector = inspect(engine)
    schemas = inspector.get_schema_names()

    # Collect tables in public schema (and any app schemas)
    table_list = []
    for schema in ["public", "tis", "app"]:
        try:
            tables = inspector.get_table_names(schema=schema)
            for t in tables:
                table_list.append((schema, t))
        except Exception:
            pass

    if not table_list:
        print("  [INFO] No tables found — database is already clean")
        return

    print(f"  [FOUND] {len(table_list)} table(s) to destroy:")
    for schema, t in table_list:
        print(f"           {schema}.{t}")

    # Drop all tables CASCADE
    with engine.connect() as conn:
        # Build DROP statements — preserve pgvector extension and DB-level objects
        preserved = {"spatial_ref_sys", "geometry_columns", "geography_columns",
                     "raster_overviews", "raster_columns", "pgvector_statistic"}
        for schema, table in table_list:
            if table in preserved:
                print(f"  [SKIP] {schema}.{table} (preserved system object)")
                continue
            try:
                conn.execute(text(f'DROP TABLE IF EXISTS "{schema}"."{table}" CASCADE'))
                print(f"  [DROPPED] {schema}.{table}")
            except Exception as e:
                print(f"  [WARN] {schema}.{table}: {e}")

    # Also drop sequences, views, types in public that reference dropped tables
    with engine.connect() as conn:
        for obj_type in ["SEQUENCE", "VIEW", "TYPE", "DOMAIN"]:
            try:
                result = conn.execute(text(f"""
                    SELECT objname, objtype
                    FROM pg_catalog.pg_depend
                    WHERE refobjid IN (
                        SELECT oid FROM pg_class WHERE relnamespace =
                        (SELECT oid FROM pg_namespace WHERE nspname = 'public')
                    )
                    AND deptype = 'a'
                """))
                # Drop owned
                conn.execute(text("DROP OWNED BY CURRENT_USER CASCADE"))
                print(f"  [OK] Dropped owned objects")
            except Exception:
                pass

    # Verify clean
    inspector2 = inspect(engine)
    remaining = inspector2.get_table_names(schema="public")
    if remaining:
        print(f"\n  [WARN] {len(remaining)} table(s) remain:")
        for t in remaining:
            print(f"          {t}")
    else:
        print(f"\n  [SUCCESS] PostgreSQL is now clean — 0 tables remaining")

    engine.dispose()


# ── Redis ───────────────────────────────────────────────────────────────────


def wipe_redis():
    print(f"\n{'='*60}")
    print("  Redis 焦土政策")
    print(f"{'='*60}")
    print(f"  Target: redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
    print()

    try:
        import redis
    except ImportError:
        print("[ERROR] redis package not installed: pip install redis")
        sys.exit(1)

    client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
    )

    try:
        client.ping()
        print(f"  [OK] Connected to Redis")
    except redis.ConnectionError as e:
        print(f"  [ERROR] Cannot connect to Redis: {e}")
        print(f"         Is the container 'ash_2' running?")
        print(f"         Check: docker ps -a | grep redis")
        sys.exit(1)

    # Count keys before
    key_count = client.dbsize()
    print(f"  [FOUND] {key_count} key(s) in DB {REDIS_DB}")

    # FLUSHDB — destructive!
    client.flushdb()
    print(f"  [FLUSHED] redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")

    # Verify
    remaining = client.dbsize()
    if remaining == 0:
        print(f"\n  [SUCCESS] Redis DB {REDIS_DB} is now clean — 0 keys remaining")
    else:
        print(f"\n  [WARN] {remaining} key(s) still remain after flush!")

    client.close()


# ── Main ────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  ⚠️  TIS 焦土清理脚本 ⚠️")
    print("  This will DESTROY all data in the target databases!")
    print("=" * 60)

    confirm = input("\n  Type YES to proceed: ").strip()
    if confirm != "YES":
        print("\n  [ABORTED] No changes made.")
        sys.exit(0)

    try:
        wipe_postgres()
        wipe_redis()
        print("\n" + "=" * 60)
        print("  ✅ 清理完毕 — 数据库已清空，可安全接管")
        print("=" * 60)
        print("\n  Next steps:")
        print("  1. Update .env with new DATABASE_URL and REDIS_URL")
        print("  2. Run: alembic upgrade head")
    except Exception as e:
        print(f"\n  [FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

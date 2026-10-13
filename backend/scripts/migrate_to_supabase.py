"""
Database Migration Script: SQLite -> Supabase PostgreSQL.
Transfers 100% of data (data_sources, indicators, indicator_values, daily_reports)
from the local SQLite database into Supabase PostgreSQL.
"""

import os
import sys
import argparse
import sqlite3
from typing import List, Dict, Any
from datetime import datetime, date
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.models import Base, DataSource, Indicator, IndicatorValue, DailyReport, IngestionLog

SQLITE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "gmip.db"))


def migrate(pg_url: str):
    if not os.path.exists(SQLITE_PATH):
        print(f"❌ SQLite database not found at: {SQLITE_PATH}")
        sys.exit(1)

    print(f"🔌 Connecting to SQLite: {SQLITE_PATH}")
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    # Format postgres URL if needed (convert postgres:// to postgresql://)
    if pg_url.startswith("postgres://"):
        pg_url = pg_url.replace("postgres://", "postgresql://", 1)

    print(f"🚀 Connecting to Supabase PostgreSQL...")
    pg_engine = create_engine(pg_url, pool_pre_ping=True, echo=False)
    
    # Test connection
    with pg_engine.connect() as conn:
        res = conn.execute(text("SELECT version();")).fetchone()
        print(f"✅ Connected to PostgreSQL: {res[0][:60]}...")

    # Step 1: Create all tables in PostgreSQL
    print("📦 Creating GMIP tables in Supabase (if not exist)...")
    Base.metadata.create_all(bind=pg_engine)
    print("✅ Tables created / verified successfully.")

    PgSession = sessionmaker(bind=pg_engine)
    pg_session = PgSession()

    try:
        # Step 2: Migrate data_sources
        sqlite_cur.execute("SELECT id, name, base_url, auth_type, rate_limit_per_minute, is_active FROM data_sources")
        sources_rows = sqlite_cur.fetchall()
        print(f"🔄 Migrating {len(sources_rows)} data_sources...")
        for row in sources_rows:
            existing = pg_session.query(DataSource).filter_by(id=row["id"]).first()
            if not existing:
                ds = DataSource(
                    id=row["id"],
                    name=row["name"],
                    base_url=row["base_url"],
                    auth_type=row["auth_type"],
                    rate_limit_per_minute=row["rate_limit_per_minute"],
                    is_active=bool(row["is_active"]),
                )
                pg_session.add(ds)
        pg_session.commit()
        print("✅ data_sources migrated.")

        # Step 3: Migrate indicators
        sqlite_cur.execute("SELECT id, symbol, name_vi, name_en, category, unit, frequency, primary_source_id, fallback_source_id, priority, is_active FROM indicators")
        indicators_rows = sqlite_cur.fetchall()
        print(f"🔄 Migrating {len(indicators_rows)} indicators...")
        for row in indicators_rows:
            existing = pg_session.query(Indicator).filter_by(id=row["id"]).first()
            if not existing:
                ind = Indicator(
                    id=row["id"],
                    symbol=row["symbol"],
                    name_vi=row["name_vi"],
                    name_en=row["name_en"],
                    category=row["category"],
                    unit=row["unit"],
                    frequency=row["frequency"],
                    primary_source_id=row["primary_source_id"],
                    fallback_source_id=row["fallback_source_id"],
                    priority=row["priority"],
                    is_active=bool(row["is_active"]),
                )
                pg_session.add(ind)
        pg_session.commit()
        print("✅ indicators migrated.")

        # Step 4: Migrate daily_reports
        sqlite_cur.execute("SELECT id, report_date, title, summary, risk_level, content_markdown, status, published_at FROM daily_reports")
        reports_rows = sqlite_cur.fetchall()
        print(f"🔄 Migrating {len(reports_rows)} daily_reports...")
        for row in reports_rows:
            existing = pg_session.query(DailyReport).filter_by(id=row["id"]).first()
            if not existing:
                r_date = datetime.strptime(row["report_date"], "%Y-%m-%d").date() if isinstance(row["report_date"], str) else row["report_date"]
                dr = DailyReport(
                    id=row["id"],
                    report_date=r_date,
                    title=row["title"],
                    summary=row["summary"],
                    risk_level=row["risk_level"],
                    content_markdown=row["content_markdown"],
                    status=row["status"],
                    published_at=datetime.now(),
                )
                pg_session.add(dr)
        pg_session.commit()
        print("✅ daily_reports migrated.")

        # Step 5: Migrate indicator_values (26,400 records in batches)
        sqlite_cur.execute("SELECT COUNT(*) FROM indicator_values")
        total_vals = sqlite_cur.fetchone()[0]
        print(f"🔄 Migrating {total_vals:,} indicator_values in chunks of 2,000...")

        sqlite_cur.execute("""
            SELECT indicator_id, record_date, value, change_1d, change_1w, change_1m, 
                   change_yoy, ma_20, ma_50, trend_state, source_used 
            FROM indicator_values 
            ORDER BY record_date ASC, indicator_id ASC
        """)

        batch_size = 2000
        batch = []
        inserted_count = 0

        while True:
            rows = sqlite_cur.fetchmany(batch_size)
            if not rows:
                break

            for r in rows:
                r_date = datetime.strptime(r["record_date"], "%Y-%m-%d").date() if isinstance(r["record_date"], str) else r["record_date"]
                batch.append({
                    "indicator_id": r["indicator_id"],
                    "record_date": r_date,
                    "value": r["value"],
                    "change_1d": r["change_1d"],
                    "change_1w": r["change_1w"],
                    "change_1m": r["change_1m"],
                    "change_yoy": r["change_yoy"],
                    "ma_20": r["ma_20"],
                    "ma_50": r["ma_50"],
                    "trend_state": r["trend_state"],
                    "source_used": r["source_used"],
                })

            # Bulk insert using SQLAlchemy Core with ON CONFLICT DO NOTHING
            stmt = text("""
                INSERT INTO indicator_values (
                    indicator_id, record_date, value, change_1d, change_1w, change_1m, 
                    change_yoy, ma_20, ma_50, trend_state, source_used
                ) VALUES (
                    :indicator_id, :record_date, :value, :change_1d, :change_1w, :change_1m, 
                    :change_yoy, :ma_20, :ma_50, :trend_state, :source_used
                )
                ON CONFLICT (indicator_id, record_date) DO UPDATE SET
                    value = EXCLUDED.value,
                    change_1d = EXCLUDED.change_1d,
                    change_1w = EXCLUDED.change_1w,
                    change_1m = EXCLUDED.change_1m,
                    change_yoy = EXCLUDED.change_yoy,
                    ma_20 = EXCLUDED.ma_20,
                    ma_50 = EXCLUDED.ma_50,
                    trend_state = EXCLUDED.trend_state,
                    source_used = EXCLUDED.source_used
            """)
            pg_session.execute(stmt, batch)
            pg_session.commit()
            inserted_count += len(batch)
            print(f"  ⚡ Migrated {inserted_count:,} / {total_vals:,} values...")
            batch.clear()

        print("✅ indicator_values migration completed.")

        # Verification step
        print("\n📊 Verification of row counts in Supabase:")
        with pg_engine.connect() as conn:
            for tbl in ["data_sources", "indicators", "daily_reports", "indicator_values"]:
                cnt = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
                print(f"  • {tbl}: {cnt:,} rows")

        print("\n🎉 SUCCESS: All GMIP data has been migrated to Supabase PostgreSQL!")

    except Exception as e:
        pg_session.rollback()
        print(f"❌ Migration error: {e}")
        raise
    finally:
        pg_session.close()
        sqlite_conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate SQLite GMIP database to Supabase PostgreSQL")
    parser.add_argument("--db-url", type=str, default=os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL"),
                        help="PostgreSQL connection string (e.g. postgresql://postgres:PASSWORD@db.yhnybljuqihlsxcgjvqw.supabase.co:5432/postgres)")
    args = parser.parse_args()

    if not args.db_url:
        print("❌ Error: Missing PostgreSQL connection string.")
        print("Provide --db-url or set SUPABASE_DB_URL / DATABASE_URL in environment.")
        print("Format: postgresql://postgres:[YOUR-PASSWORD]@db.yhnybljuqihlsxcgjvqw.supabase.co:5432/postgres")
        sys.exit(1)

    migrate(args.db_url)

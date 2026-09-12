import os
import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from path_utils import get_base_dir, get_bundle_dir, get_writable_dir

DB_DIR = get_writable_dir("data")
DB_PATH = os.path.join(DB_DIR, "resume_agent.db")
JSON_PROFILE_PATH = os.path.join(DB_DIR, "profile_store.json")
BUNDLED_JSON_PATH = os.path.join(get_bundle_dir(), "data", "profile_store.json")

class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_tables()
        self._migrate_from_json_if_needed()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Master Profile Store Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS profile_store (
                id TEXT PRIMARY KEY,
                data_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # 2. Vault Version History Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS vault_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                diff_json TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );
            """)

            # 3. Job Applications Table (Kanban CRM)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_applications (
                id TEXT PRIMARY KEY,
                company TEXT NOT NULL,
                role TEXT NOT NULL,
                stage TEXT NOT NULL DEFAULT 'Applied',
                jd_snapshot TEXT,
                jd_parsed_json TEXT,
                resume_version_id TEXT,
                cover_letter_text TEXT,
                ats_score REAL DEFAULT 0,
                notes TEXT,
                next_action_date TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # 4. API Usage & Cost Log Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                estimated_cost_usd REAL DEFAULT 0.0,
                purpose TEXT,
                timestamp TEXT NOT NULL
            );
            """)

            # 5. AI Response Cache Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_cache (
                cache_key TEXT PRIMARY KEY,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)
            conn.commit()

    def _migrate_from_json_if_needed(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM profile_store WHERE id = 'master_profile'")
            row = cursor.fetchone()
            if not row:
                # Load from json file
                source_json = None
                if os.path.exists(JSON_PROFILE_PATH):
                    source_json = JSON_PROFILE_PATH
                elif os.path.exists(BUNDLED_JSON_PATH):
                    source_json = BUNDLED_JSON_PATH

                if source_json:
                    try:
                        with open(source_json, "r", encoding="utf-8") as f:
                            profile_data = json.load(f)
                        now = datetime.utcnow().isoformat()
                        cursor.execute(
                            "INSERT INTO profile_store (id, data_json, updated_at) VALUES ('master_profile', ?, ?)",
                            (json.dumps(profile_data), now)
                        )
                        conn.commit()
                        print(f"✓ Successfully migrated profile data from {source_json} to SQLite database!")
                    except Exception as e:
                        print(f"Error during SQLite migration: {e}")

    # Profile Store methods
    def load_profile(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data_json FROM profile_store WHERE id = 'master_profile'")
            row = cursor.fetchone()
            if row:
                return json.loads(row["data_json"])
        return {}

    def save_profile(self, data: Dict[str, Any], entity_type: str = "general", entity_id: str = "update", diff: Optional[Dict[str, Any]] = None):
        now = datetime.utcnow().isoformat()
        data_str = json.dumps(data)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO profile_store (id, data_json, updated_at)
                VALUES ('master_profile', ?, ?)
                ON CONFLICT(id) DO UPDATE SET data_json = excluded.data_json, updated_at = excluded.updated_at
            """, (data_str, now))

            # Store version history diff if provided
            if diff:
                cursor.execute("""
                    INSERT INTO vault_versions (entity_type, entity_id, diff_json, timestamp)
                    VALUES (?, ?, ?, ?)
                """, (entity_type, entity_id, json.dumps(diff), now))

            conn.commit()

        # Also sync to JSON file for backward compatibility
        try:
            with open(JSON_PROFILE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning syncing to JSON file: {e}")

    def get_version_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vault_versions ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    # Job Applications CRM methods
    def get_applications(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM job_applications ORDER BY updated_at DESC")
            return [dict(r) for r in cursor.fetchall()]

    def get_application(self, app_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM job_applications WHERE id = ?", (app_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def upsert_application(self, app_data: Dict[str, Any]):
        now = datetime.utcnow().isoformat()
        app_id = app_data.get("id") or f"app_{int(datetime.utcnow().timestamp())}_{app_data.get('company', '').lower().replace(' ', '_')}"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO job_applications (
                    id, company, role, stage, jd_snapshot, jd_parsed_json,
                    resume_version_id, cover_letter_text, ats_score, notes,
                    next_action_date, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    company = excluded.company,
                    role = excluded.role,
                    stage = excluded.stage,
                    jd_snapshot = excluded.jd_snapshot,
                    jd_parsed_json = excluded.jd_parsed_json,
                    resume_version_id = excluded.resume_version_id,
                    cover_letter_text = excluded.cover_letter_text,
                    ats_score = excluded.ats_score,
                    notes = excluded.notes,
                    next_action_date = excluded.next_action_date,
                    updated_at = excluded.updated_at
            """, (
                app_id,
                app_data.get("company", ""),
                app_data.get("role", ""),
                app_data.get("stage", "Applied"),
                app_data.get("jd_snapshot", ""),
                json.dumps(app_data.get("jd_parsed", {})) if isinstance(app_data.get("jd_parsed"), dict) else app_data.get("jd_parsed_json", ""),
                app_data.get("resume_version_id", ""),
                app_data.get("cover_letter_text", ""),
                app_data.get("ats_score", 0.0),
                app_data.get("notes", ""),
                app_data.get("next_action_date", ""),
                app_data.get("created_at", now),
                now
            ))
            conn.commit()
        return app_id

    def delete_application(self, app_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM job_applications WHERE id = ?", (app_id,))
            conn.commit()
            return cursor.rowcount > 0

    # API Usage logging
    def log_api_usage(self, provider: str, model: str, tokens_in: int, tokens_out: int, cost_usd: float, purpose: str = ""):
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO api_usage_log (provider, model, tokens_in, tokens_out, estimated_cost_usd, purpose, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (provider, model, tokens_in, tokens_out, cost_usd, purpose, now))
            conn.commit()

    def get_api_usage_summary(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT provider, model, SUM(tokens_in) as total_tokens_in, SUM(tokens_out) as total_tokens_out,
                       SUM(estimated_cost_usd) as total_cost, COUNT(*) as call_count
                FROM api_usage_log
                GROUP BY provider, model
            """)
            rows = [dict(r) for r in cursor.fetchall()]
            cursor.execute("SELECT SUM(estimated_cost_usd) as total_cost, COUNT(*) as total_calls FROM api_usage_log")
            total = dict(cursor.fetchone() or {})
            return {"by_model": rows, "total": total}

    # Cache methods
    def get_cache(self, key: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT response_json FROM ai_cache WHERE cache_key = ?", (key,))
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row["response_json"])
                except Exception:
                    return None
        return None

    def set_cache(self, key: str, data: Dict[str, Any]):
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ai_cache (cache_key, response_json, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET response_json = excluded.response_json, created_at = excluded.created_at
            """, (key, json.dumps(data), now))
            conn.commit()

db = Database()

"""Pipeline monitor — polls the database and prints real-time extraction status."""
import sys
import time
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "unrealmake.db")
POLL_INTERVAL = 3  # seconds


def monitor():
    if os.getenv("APP_ENV", "development").lower() == "production":
        print("Monitor is dev-only and disabled in production.")
        return
    print("=" * 60)
    print("  Pipeline Monitor — Real-time Extraction Status")
    print("=" * 60)
    print(f"  DB: {DB_PATH}")
    print(f"  Polling every {POLL_INTERVAL}s  |  Ctrl+C to stop")
    print("=" * 60)

    prev_counts = {}

    while True:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Active import tasks
            cur.execute(
                "SELECT id, project_id, status, current_phase, progress, error "
                "FROM import_tasks ORDER BY created_at DESC LIMIT 1"
            )
            task = cur.fetchone()

            # Asset counts
            cur.execute("SELECT COUNT(*) FROM characters")
            char_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM scenes")
            scene_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM locations")
            loc_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM props")
            prop_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM character_variants")
            var_count = cur.fetchone()[0]

            # Recent AI call logs
            cur.execute(
                "SELECT provider, model, operation_type, input_tokens, output_tokens, "
                "elapsed, created_at FROM ai_call_logs ORDER BY created_at DESC LIMIT 3"
            )
            recent_calls = cur.fetchall()

            conn.close()

            # Build display
            now = time.strftime("%H:%M:%S")
            counts = {
                "char": char_count,
                "scene": scene_count,
                "loc": loc_count,
                "prop": prop_count,
                "var": var_count,
            }

            # Detect changes
            changes = []
            for k, v in counts.items():
                old = prev_counts.get(k, 0)
                if v > old:
                    changes.append(f"{k} +{v - old}")
            prev_counts = counts

            change_str = " | ".join(changes) if changes else "no change"

            # Clear line and print
            print(f"\n[{now}] {change_str}")
            print(
                f"  Assets: "
                f"chars={char_count}  scenes={scene_count}  "
                f"locs={loc_count}  props={prop_count}  variants={var_count}"
            )

            if task:
                status = task["status"]
                phase = task["current_phase"]
                error = task["error"]
                tid = task["id"][:8]
                print(f"  Task:   {tid}..  status={status}  phase={phase}")
                if error:
                    print(f"  ERROR:  {error}")

            if recent_calls:
                print("  Recent AI calls:")
                for call in recent_calls:
                    provider = call["provider"] or "?"
                    model = call["model"] or "?"
                    op = call["operation_type"] or "?"
                    elapsed = call["elapsed"] or 0
                    in_tok = call["input_tokens"] or 0
                    out_tok = call["output_tokens"] or 0
                    ts = call["created_at"] or ""
                    ts_short = ts[11:19] if len(ts) > 19 else ts
                    print(
                        f"    [{ts_short}] {provider}/{model} "
                        f"op={op} in={in_tok} out={out_tok} {elapsed}s"
                    )

            sys.stdout.flush()

        except KeyboardInterrupt:
            print("\nMonitor stopped.")
            break
        except Exception as e:
            print(f"\n[{time.strftime('%H:%M:%S')}] Monitor error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    monitor()

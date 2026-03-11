"""SQLite 数据库封装 — 知识库构建流水线的结构化存储层.

职责:
  - 创建/初始化 SQLite 数据库（12 张表）
  - 提供实体级 CRUD 操作
  - 与 JSON 文件互为备份，支持画布系统对接查询

新增 (R7):
  - segments: 镜头合并后的段落
  - vff_prompts: Visual Fusion Flow 中文视频生产提示词
"""

import json
import sqlite3
from datetime import datetime


class PipelineDB:
    """流水线 SQLite 存储封装。"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_tables()

    def _init_tables(self):
        """创建全部表结构（幂等）。"""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS project (
                id TEXT PRIMARY KEY,
                name TEXT,
                novel_path TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS chapters (
                id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES project(id),
                title TEXT,
                content TEXT,
                summary TEXT,
                word_count INTEGER,
                "order" INTEGER,
                start_marker TEXT,
                end_marker TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS characters (
                id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES project(id),
                name TEXT,
                aliases TEXT,
                role TEXT,
                age_range TEXT,
                appearance TEXT,
                costume TEXT,
                casting_tags TEXT,
                visual_reference TEXT,
                description TEXT,
                personality TEXT,
                desire TEXT,
                flaw TEXT,
                arc TEXT,
                relationships TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS scenes (
                id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES project(id),
                chapter_id TEXT REFERENCES chapters(id),
                heading TEXT,
                location TEXT,
                time_of_day TEXT,
                description TEXT,
                action TEXT,
                dialogue TEXT,
                characters_present TEXT,
                key_props TEXT,
                dramatic_purpose TEXT,
                tension_score REAL,
                "order" INTEGER,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS beats (
                id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES project(id),
                title TEXT,
                description TEXT,
                beat_type TEXT,
                save_the_cat TEXT,
                emotional_value REAL,
                hook_potential TEXT,
                rhythm_warning TEXT,
                "order" INTEGER,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS knowledge (
                id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES project(id),
                world_building TEXT,
                style_guide TEXT,
                synopsis TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS shots (
                id TEXT PRIMARY KEY,
                scene_id TEXT REFERENCES scenes(id),
                project_id TEXT REFERENCES project(id),
                shot_number INTEGER,
                goal TEXT,
                composition TEXT,
                camera_movement TEXT,
                framing TEXT,
                emotion_target TEXT,
                duration_hint TEXT,
                characters TEXT,
                transition_in TEXT,
                transition_out TEXT,
                dramatic_intensity REAL,
                "order" INTEGER,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS character_states (
                id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES project(id),
                character_id TEXT,
                scene_id TEXT REFERENCES scenes(id),
                emotion TEXT,
                inner_objective TEXT,
                opponent_tension TEXT,
                action_beat TEXT,
                status_note TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS dialogue (
                id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES project(id),
                scene_id TEXT REFERENCES scenes(id),
                character_id TEXT,
                line TEXT,
                subtext TEXT,
                emotion_intensity REAL,
                "order" INTEGER,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS shot_prompts (
                id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES project(id),
                shot_id TEXT REFERENCES shots(id),
                prompt_text TEXT,
                style_params TEXT,
                negative_prompt TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS segments (
                id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES project(id),
                scene_id TEXT REFERENCES scenes(id),
                shot_ids TEXT,
                segment_number INTEGER,
                target_duration TEXT,
                target_model TEXT,
                merge_rationale TEXT,
                "order" INTEGER,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS vff_prompts (
                id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES project(id),
                segment_id TEXT REFERENCES segments(id),
                scene_id TEXT,
                continuity TEXT,
                time_scene_props TEXT,
                vff_body TEXT,
                character_refs TEXT,
                scene_refs TEXT,
                merge_rationale TEXT,
                style_metadata TEXT,
                raw_text TEXT,
                created_at TEXT
            );
        """)
        self.conn.commit()

        # ALTER TABLE — 幂等添加新列到已有表
        alter_cols = [
            ("scenes", "dramatic_intensity", "REAL"),
            ("scenes", "related_beats", "TEXT"),
            ("beats", "dramatic_intensity", "REAL"),
            ("beats", "related_scenes", "TEXT"),
        ]
        for table, col, col_type in alter_cols:
            try:
                self.conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{col}" {col_type}')
                self.conn.commit()
            except Exception:
                pass  # 列已存在

    # ── 辅助 ──────────────────────────────────────────────────────

    @staticmethod
    def _json_field(value) -> str | None:
        """将 dict/list 序列化为 JSON 字符串，str/None 直接返回。"""
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    # ── Project ───────────────────────────────────────────────────

    def upsert_project(self, project_id: str, name: str, novel_path: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO project (id, name, novel_path, created_at) VALUES (?, ?, ?, ?)",
            (project_id, name, novel_path, self._now()),
        )
        self.conn.commit()

    # ── Chapters ──────────────────────────────────────────────────

    def upsert_chapter(self, project_id: str, ch: dict):
        self.conn.execute(
            """INSERT OR REPLACE INTO chapters
               (id, project_id, title, content, summary, word_count, "order",
                start_marker, end_marker, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ch["id"], project_id, ch.get("title"),
                ch.get("content"), ch.get("summary"),
                ch.get("word_count"), ch.get("order"),
                ch.get("start_marker"), ch.get("end_marker"),
                self._now(),
            ),
        )
        self.conn.commit()

    def update_chapter_summary(self, chapter_id: str, summary: str):
        self.conn.execute(
            "UPDATE chapters SET summary = ? WHERE id = ?",
            (summary, chapter_id),
        )
        self.conn.commit()

    def get_chapters(self, project_id: str) -> list[dict]:
        rows = self.conn.execute(
            'SELECT * FROM chapters WHERE project_id = ? ORDER BY "order"',
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Characters ────────────────────────────────────────────────

    def upsert_character(self, project_id: str, ch: dict):
        self.conn.execute(
            """INSERT OR REPLACE INTO characters
               (id, project_id, name, aliases, role, age_range,
                appearance, costume, casting_tags, visual_reference,
                description, personality, desire, flaw, arc,
                relationships, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ch["id"], project_id, ch.get("name"),
                self._json_field(ch.get("aliases")),
                ch.get("role"), ch.get("age_range"),
                self._json_field(ch.get("appearance")),
                self._json_field(ch.get("costume")),
                self._json_field(ch.get("casting_tags")),
                ch.get("visual_reference"),
                ch.get("description"), ch.get("personality"),
                ch.get("desire"), ch.get("flaw"), ch.get("arc"),
                self._json_field(ch.get("relationships")),
                self._now(),
            ),
        )
        self.conn.commit()

    def get_characters(self, project_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM characters WHERE project_id = ?",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Scenes ────────────────────────────────────────────────────

    def upsert_scene(self, project_id: str, sc: dict):
        self.conn.execute(
            """INSERT OR REPLACE INTO scenes
               (id, project_id, chapter_id, heading, location, time_of_day,
                description, action, dialogue, characters_present,
                key_props, dramatic_purpose, tension_score, "order", created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sc["id"], project_id, sc.get("chapter_id"),
                sc.get("heading"), sc.get("location"), sc.get("time_of_day"),
                sc.get("description"), sc.get("action"),
                self._json_field(sc.get("dialogue")),
                self._json_field(sc.get("characters_present")),
                self._json_field(sc.get("key_props")),
                sc.get("dramatic_purpose"), sc.get("tension_score"),
                sc.get("order"),
                self._now(),
            ),
        )
        self.conn.commit()

    def get_scenes(self, project_id: str) -> list[dict]:
        rows = self.conn.execute(
            'SELECT * FROM scenes WHERE project_id = ? ORDER BY "order"',
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Beats ─────────────────────────────────────────────────────

    def upsert_beat(self, project_id: str, bt: dict):
        self.conn.execute(
            """INSERT OR REPLACE INTO beats
               (id, project_id, title, description, beat_type,
                save_the_cat, emotional_value, hook_potential,
                rhythm_warning, "order", created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                bt["id"], project_id, bt.get("title"),
                bt.get("description"), bt.get("beat_type"),
                bt.get("save_the_cat"), bt.get("emotional_value"),
                bt.get("hook_potential"), bt.get("rhythm_warning"),
                bt.get("order"),
                self._now(),
            ),
        )
        self.conn.commit()

    def get_beats(self, project_id: str) -> list[dict]:
        rows = self.conn.execute(
            'SELECT * FROM beats WHERE project_id = ? ORDER BY "order"',
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Knowledge ─────────────────────────────────────────────────

    def upsert_knowledge(self, project_id: str, kn: dict):
        self.conn.execute(
            """INSERT OR REPLACE INTO knowledge
               (id, project_id, world_building, style_guide, synopsis, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                kn.get("id", f"kb_{project_id}"),
                project_id,
                self._json_field(kn.get("world_building")),
                self._json_field(kn.get("style_guide")),
                kn.get("synopsis"),
                self._now(),
            ),
        )
        self.conn.commit()

    # ── Shots ──────────────────────────────────────────────────────

    def upsert_shot(self, project_id: str, sh: dict):
        self.conn.execute(
            """INSERT OR REPLACE INTO shots
               (id, scene_id, project_id, shot_number, goal, composition,
                camera_movement, framing, emotion_target, duration_hint,
                characters, transition_in, transition_out,
                dramatic_intensity, "order", created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sh["id"], sh.get("scene_id"), project_id,
                sh.get("shot_number"), sh.get("goal"),
                sh.get("composition"), sh.get("camera_movement"),
                sh.get("framing"), sh.get("emotion_target"),
                sh.get("duration_hint"),
                self._json_field(sh.get("characters")),
                sh.get("transition_in"), sh.get("transition_out"),
                sh.get("dramatic_intensity"), sh.get("order"),
                self._now(),
            ),
        )
        self.conn.commit()

    def get_shots(self, project_id: str, scene_id: str = None) -> list[dict]:
        if scene_id:
            rows = self.conn.execute(
                'SELECT * FROM shots WHERE project_id = ? AND scene_id = ? ORDER BY "order"',
                (project_id, scene_id),
            ).fetchall()
        else:
            rows = self.conn.execute(
                'SELECT * FROM shots WHERE project_id = ? ORDER BY "order"',
                (project_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Character States ───────────────────────────────────────────

    def upsert_character_state(self, project_id: str, cs: dict):
        self.conn.execute(
            """INSERT OR REPLACE INTO character_states
               (id, project_id, character_id, scene_id,
                emotion, inner_objective, opponent_tension,
                action_beat, status_note, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                cs["id"], project_id, cs.get("character_id"),
                cs.get("scene_id"), cs.get("emotion"),
                cs.get("inner_objective"),
                self._json_field(cs.get("opponent_tension")),
                cs.get("action_beat"), cs.get("status_note"),
                self._now(),
            ),
        )
        self.conn.commit()

    def get_character_states(self, project_id: str, scene_id: str = None) -> list[dict]:
        if scene_id:
            rows = self.conn.execute(
                "SELECT * FROM character_states WHERE project_id = ? AND scene_id = ?",
                (project_id, scene_id),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM character_states WHERE project_id = ?",
                (project_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Dialogue ───────────────────────────────────────────────────

    def upsert_dialogue(self, project_id: str, dl: dict):
        self.conn.execute(
            """INSERT OR REPLACE INTO dialogue
               (id, project_id, scene_id, character_id,
                line, subtext, emotion_intensity, "order", created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                dl["id"], project_id, dl.get("scene_id"),
                dl.get("character_id"), dl.get("line"),
                dl.get("subtext"), dl.get("emotion_intensity"),
                dl.get("order"),
                self._now(),
            ),
        )
        self.conn.commit()

    def get_dialogue(self, project_id: str, scene_id: str = None) -> list[dict]:
        if scene_id:
            rows = self.conn.execute(
                'SELECT * FROM dialogue WHERE project_id = ? AND scene_id = ? ORDER BY "order"',
                (project_id, scene_id),
            ).fetchall()
        else:
            rows = self.conn.execute(
                'SELECT * FROM dialogue WHERE project_id = ? ORDER BY "order"',
                (project_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Shot Prompts ───────────────────────────────────────────────

    def upsert_shot_prompt(self, project_id: str, sp: dict):
        self.conn.execute(
            """INSERT OR REPLACE INTO shot_prompts
               (id, project_id, shot_id, prompt_text,
                style_params, negative_prompt, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                sp["id"], project_id, sp.get("shot_id"),
                sp.get("prompt_text"),
                self._json_field(sp.get("style_params")),
                sp.get("negative_prompt"),
                self._now(),
            ),
        )
        self.conn.commit()

    def get_shot_prompts(self, project_id: str, shot_id: str = None) -> list[dict]:
        if shot_id:
            rows = self.conn.execute(
                "SELECT * FROM shot_prompts WHERE project_id = ? AND shot_id = ?",
                (project_id, shot_id),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM shot_prompts WHERE project_id = ?",
                (project_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Segments (R7) ────────────────────────────────────────────

    def upsert_segment(self, project_id: str, seg: dict):
        self.conn.execute(
            """INSERT OR REPLACE INTO segments
               (id, project_id, scene_id, shot_ids, segment_number,
                target_duration, target_model, merge_rationale,
                "order", created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                seg["id"], project_id, seg.get("scene_id"),
                self._json_field(seg.get("shot_ids")),
                seg.get("segment_number"),
                seg.get("target_duration"),
                seg.get("target_model"),
                seg.get("merge_rationale"),
                seg.get("order"),
                self._now(),
            ),
        )
        self.conn.commit()

    def get_segments(self, project_id: str, scene_id: str = None) -> list[dict]:
        if scene_id:
            rows = self.conn.execute(
                'SELECT * FROM segments WHERE project_id = ? AND scene_id = ? ORDER BY "order"',
                (project_id, scene_id),
            ).fetchall()
        else:
            rows = self.conn.execute(
                'SELECT * FROM segments WHERE project_id = ? ORDER BY "order"',
                (project_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── VFF Prompts (R7) ─────────────────────────────────────────

    def upsert_vff_prompt(self, project_id: str, vp: dict):
        self.conn.execute(
            """INSERT OR REPLACE INTO vff_prompts
               (id, project_id, segment_id, scene_id,
                continuity, time_scene_props, vff_body,
                character_refs, scene_refs, merge_rationale,
                style_metadata, raw_text, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                vp["id"], project_id, vp.get("segment_id"),
                vp.get("scene_id"), vp.get("continuity"),
                vp.get("time_scene_props"), vp.get("vff_body"),
                self._json_field(vp.get("character_refs")),
                self._json_field(vp.get("scene_refs")),
                vp.get("merge_rationale"),
                self._json_field(vp.get("style_metadata")),
                vp.get("raw_text"),
                self._now(),
            ),
        )
        self.conn.commit()

    def get_vff_prompts(self, project_id: str, segment_id: str = None,
                         scene_id: str = None) -> list[dict]:
        if segment_id:
            rows = self.conn.execute(
                "SELECT * FROM vff_prompts WHERE project_id = ? AND segment_id = ?",
                (project_id, segment_id),
            ).fetchall()
        elif scene_id:
            rows = self.conn.execute(
                "SELECT * FROM vff_prompts WHERE project_id = ? AND scene_id = ?",
                (project_id, scene_id),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM vff_prompts WHERE project_id = ?",
                (project_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Scene/Beat 更新 dramatic_intensity / related 字段 ──────────

    def update_scene_intensity(self, scene_id: str, dramatic_intensity: float,
                                related_beats: list | None = None):
        if related_beats is not None:
            self.conn.execute(
                "UPDATE scenes SET dramatic_intensity = ?, related_beats = ? WHERE id = ?",
                (dramatic_intensity, self._json_field(related_beats), scene_id),
            )
        else:
            self.conn.execute(
                "UPDATE scenes SET dramatic_intensity = ? WHERE id = ?",
                (dramatic_intensity, scene_id),
            )
        self.conn.commit()

    def update_beat_intensity(self, beat_id: str, dramatic_intensity: float,
                               related_scenes: list | None = None):
        if related_scenes is not None:
            self.conn.execute(
                "UPDATE beats SET dramatic_intensity = ?, related_scenes = ? WHERE id = ?",
                (dramatic_intensity, self._json_field(related_scenes), beat_id),
            )
        else:
            self.conn.execute(
                "UPDATE beats SET dramatic_intensity = ? WHERE id = ?",
                (dramatic_intensity, beat_id),
            )
        self.conn.commit()

    # ── Utility ───────────────────────────────────────────────────

    def table_count(self, table: str) -> int:
        row = self.conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()
        return row[0] if row else 0

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

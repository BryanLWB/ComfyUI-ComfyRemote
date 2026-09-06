from __future__ import annotations

import ctypes
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Blob(ctypes.Structure):
    _fields_ = [("size", ctypes.c_ulong), ("data", ctypes.POINTER(ctypes.c_char))]


def protect(data: bytes, *, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        raise RuntimeError("This first release requires Windows credential protection")
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    target = Blob()
    fn = (
        ctypes.windll.crypt32.CryptUnprotectData
        if decrypt
        else ctypes.windll.crypt32.CryptProtectData
    )
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.windll.kernel32.LocalFree(target.data)


class State:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS receipts(id TEXT PRIMARY KEY, received REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS prompts(id TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS outputs(filename TEXT, subfolder TEXT, type TEXT,
                    PRIMARY KEY(filename,subfolder,type));
                CREATE TABLE IF NOT EXISTS classes(name TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS definitions(class_type TEXT PRIMARY KEY, graph TEXT NOT NULL);
            """)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.root / "journal.sqlite3", timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def load_pairing(self) -> dict | None:
        path = self.root / "pairing.dpapi"
        return json.loads(protect(path.read_bytes(), decrypt=True)) if path.exists() else None

    def save_pairing(self, value: dict) -> None:
        temporary = self.root / "pairing.dpapi.tmp"
        temporary.write_bytes(protect(json.dumps(value).encode()))
        os.replace(temporary, self.root / "pairing.dpapi")

    def clear_pairing(self) -> None:
        (self.root / "pairing.dpapi").unlink(missing_ok=True)
        with self.db() as db:
            for table in ("prompts", "outputs", "classes", "receipts", "definitions"):
                db.execute(f"DELETE FROM {table}")

    def add_classes(self, names) -> None:
        with self.db() as db:
            db.executemany("INSERT OR IGNORE INTO classes VALUES (?)", [(name,) for name in names])

    def classes(self) -> list[str]:
        with self.db() as db:
            return [row[0] for row in db.execute("SELECT name FROM classes")]

    def remember_references(self, graph: dict) -> None:
        with self.db() as db:
            for class_type in {node["class_type"] for node in graph.values()}:
                row = db.execute(
                    "SELECT graph FROM definitions WHERE class_type=?", (class_type,)
                ).fetchone()
                refs = json.loads(row[0]) if row else {}
                for node in graph.values():
                    if node["class_type"] == class_type:
                        for name, value in node.get("inputs", {}).items():
                            if isinstance(value, str) and len(value) <= 1024:
                                values = refs.setdefault(name, [])
                                if value not in values:
                                    values.append(value)
                db.execute(
                    "INSERT OR REPLACE INTO definitions VALUES (?,?)",
                    (class_type, json.dumps(refs)),
                )

    def reference_graph(self) -> dict:
        graph = {}
        with self.db() as db:
            for class_type, payload in db.execute("SELECT class_type,graph FROM definitions"):
                for name, values in json.loads(payload).items():
                    for value in values:
                        graph[str(len(graph))] = {"class_type": class_type, "inputs": {name: value}}
        return graph

    def owns_prompt(self, prompt_id: str) -> bool:
        with self.db() as db:
            return (
                db.execute("SELECT 1 FROM prompts WHERE id=?", (prompt_id,)).fetchone() is not None
            )

    def own_history_outputs(self, history: dict) -> None:
        with self.db() as db:
            for entry in history.values():
                for output in entry.get("outputs", {}).values():
                    for values in output.values():
                        if isinstance(values, list):
                            for item in values:
                                if isinstance(item, dict) and isinstance(item.get("filename"), str):
                                    db.execute(
                                        "INSERT OR IGNORE INTO outputs VALUES (?,?,?)",
                                        (
                                            item["filename"],
                                            item.get("subfolder", ""),
                                            item.get("type", "output"),
                                        ),
                                    )

    def owns_output(self, filename: str, subfolder: str, kind: str) -> bool:
        with self.db() as db:
            return (
                db.execute(
                    "SELECT 1 FROM outputs WHERE filename=? AND subfolder=? AND type=?",
                    (filename, subfolder, kind),
                ).fetchone()
                is not None
            )

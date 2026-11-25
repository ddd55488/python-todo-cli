"""数据层：任务模型、JSON 读写、筛选与统计。

与 todo.py（命令行版）共用同一份 tasks.json：
命令行旧格式只有 title / done，这里读取时自动补全缺失字段，
写回时保留扩展字段，所以两个版本可以混着用。
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

PRIORITIES = ("high", "mid", "low")
PRIORITY_LABEL = {"high": "高", "mid": "中", "low": "低"}
PRIORITY_ORDER = {"high": 0, "mid": 1, "low": 2}
DEFAULT_CATEGORY = "默认"


def app_dir() -> Path:
    """程序所在目录：源码运行看 .py 位置，打包后看 exe 位置。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def _writable(folder: Path) -> bool:
    try:
        probe = folder / ".write_probe"
        probe.write_text("1", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def default_data_file() -> Path:
    """优先把 tasks.json 放在程序旁边（便携）；目录不可写时退回 AppData。"""
    base = app_dir()
    if _writable(base):
        return base / "tasks.json"
    fallback = Path(os.environ.get("APPDATA") or Path.home()) / "PythonTodo"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback / "tasks.json"


@dataclass
class Task:
    title: str
    done: bool = False
    priority: str = "mid"
    due: str = ""                      # ISO 日期 yyyy-mm-dd，空表示没有截止日
    category: str = DEFAULT_CATEGORY
    created: str = ""
    tid: str = ""

    def __post_init__(self):
        if not self.created:
            self.created = datetime.now().isoformat(timespec="microseconds")
        if not self.tid:
            self.tid = uuid.uuid4().hex[:12]
        if self.priority not in PRIORITY_ORDER:
            self.priority = "mid"
        if not self.category:
            self.category = DEFAULT_CATEGORY

    @property
    def due_date(self):
        try:
            return date.fromisoformat(self.due) if self.due else None
        except ValueError:
            return None

    def days_left(self):
        moment = self.due_date
        return None if moment is None else (moment - date.today()).days

    def is_overdue(self) -> bool:
        if self.done:
            return False
        left = self.days_left()
        return left is not None and left < 0

    def is_today(self) -> bool:
        return not self.done and self.days_left() == 0

    def due_text(self) -> str:
        left = self.days_left()
        if left is None:
            return ""
        if self.done:
            return self.due
        if left < 0:
            return f"逾期 {abs(left)} 天"
        if left == 0:
            return "今天到期"
        if left == 1:
            return "明天到期"
        return f"{left} 天后"

    def to_dict(self) -> dict:
        return {
            "id": self.tid,
            "title": self.title,
            "done": bool(self.done),
            "priority": self.priority,
            "due": self.due,
            "category": self.category,
            "created": self.created,
        }

    @classmethod
    def from_dict(cls, raw) -> "Task":
        title = str(raw.get("title", "")).strip()
        if not title:
            raise ValueError("任务标题不能为空")
        due = raw.get("due") or ""
        try:
            date.fromisoformat(due)
        except (ValueError, TypeError):
            due = ""
        return cls(
            title=title,
            done=raw.get("done") is True,
            priority=str(raw.get("priority") or "mid"),
            due=due,
            category=str(raw.get("category") or DEFAULT_CATEGORY).strip(),
            created=str(raw.get("created") or ""),
            tid=str(raw.get("id") or ""),
        )


class TaskStore:
    """任务集合：负责读写文件，并对界面提供筛选、统计和增删改。"""

    def __init__(self, path=None):
        self.path = Path(path) if path else default_data_file()
        self.tasks: list[Task] = []
        self.error = ""
        self.load()

    # ---------- 读写 ----------
    def load(self):
        self.tasks = []
        self.error = ""
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.error = f"读取失败：{exc}"
            return
        if not isinstance(raw, list):
            self.error = "tasks.json 顶层应该是列表"
            return
        for item in raw:
            try:
                self.tasks.append(Task.from_dict(item))
            except (ValueError, AttributeError, TypeError):
                continue

    def save(self) -> bool:
        temporary = self.path.with_suffix(".json.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps([t.to_dict() for t in self.tasks], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(self.path)
            self.error = ""
            return True
        except OSError as exc:
            self.error = f"保存失败：{exc}"
            return False

    # ---------- 增删改 ----------
    def add(self, title, priority="mid", due="", category=DEFAULT_CATEGORY) -> bool:
        self.tasks.append(Task(title=title.strip(), priority=priority,
                               due=due, category=category.strip() or DEFAULT_CATEGORY))
        return self.save()

    def update(self, tid, title, priority, due, category) -> bool:
        for task in self.tasks:
            if task.tid == tid:
                task.title = title.strip()
                task.priority = priority
                task.due = due
                task.category = category.strip() or DEFAULT_CATEGORY
                return self.save()
        return False

    def toggle(self, tid) -> bool:
        for task in self.tasks:
            if task.tid == tid:
                task.done = not task.done
                return self.save()
        return False

    def delete(self, tid):
        """删除并返回 (任务, 原位置)，便于撤销。"""
        for index, task in enumerate(self.tasks):
            if task.tid == tid:
                self.tasks.pop(index)
                self.save()
                return task, index
        return None, -1

    def restore(self, task, index) -> bool:
        self.tasks.insert(max(0, min(index, len(self.tasks))), task)
        return self.save()

    def clear_done(self) -> int:
        keep = [t for t in self.tasks if not t.done]
        removed = len(self.tasks) - len(keep)
        if removed:
            self.tasks = keep
            self.save()
        return removed

    def get(self, tid):
        for task in self.tasks:
            if task.tid == tid:
                return task
        return None

    # ---------- 查询 ----------
    def query(self, view="all", category=None, keyword="", sort="default"):
        items = list(self.tasks)
        today = date.today()
        if view == "active":
            items = [t for t in items if not t.done]
        elif view == "done":
            items = [t for t in items if t.done]
        elif view == "today":
            items = [t for t in items if not t.done and t.due_date == today]
        elif view == "overdue":
            items = [t for t in items if t.is_overdue()]

        if category:
            items = [t for t in items if t.category == category]

        key = keyword.strip().lower()
        if key:
            items = [t for t in items
                     if key in t.title.lower() or key in t.category.lower()]

        if sort == "priority":
            items.sort(key=lambda t: (t.done, PRIORITY_ORDER.get(t.priority, 1), t.created))
        elif sort == "due":
            items.sort(key=lambda t: (t.done,
                                      1 if t.due_date is None else 0,
                                      t.due_date.toordinal() if t.due_date else 0))
        elif sort == "title":
            items.sort(key=lambda t: t.title.lower())
        else:
            items.sort(key=lambda t: t.created, reverse=True)
        return items

    def counts(self) -> dict:
        today = date.today()
        return {
            "all": len(self.tasks),
            "active": sum(1 for t in self.tasks if not t.done),
            "done": sum(1 for t in self.tasks if t.done),
            "today": sum(1 for t in self.tasks if not t.done and t.due_date == today),
            "overdue": sum(1 for t in self.tasks if t.is_overdue()),
        }

    def categories(self) -> dict:
        """分类 -> 数量，按数量从多到少。"""
        counter = {}
        for task in self.tasks:
            counter[task.category] = counter.get(task.category, 0) + 1
        return dict(sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])))

    def completion_rate(self) -> float:
        if not self.tasks:
            return 0.0
        return sum(1 for t in self.tasks if t.done) / len(self.tasks)

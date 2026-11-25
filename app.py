"""桌面版待办清单 —— Tkinter 图形界面。

运行：py app.py
ai生成的前端

界面结构：
    左侧栏   视图筛选 / 分类筛选 / 完成率
    顶部     搜索框 + 排序方式
    中间     任务卡片列表（双击编辑，右键菜单，悬停显示删除）
    对话框   新建 / 编辑任务
"""

from __future__ import annotations

import sys
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox

from todo_core import DEFAULT_CATEGORY, PRIORITY_LABEL, TaskStore

# ---------------------------------------------------------------- 主题色
BG = "#0f1115"          # 窗口底色
SIDEBAR = "#141720"     # 侧栏
CARD = "#1a1e27"        # 卡片
CARD_HOVER = "#222a39"  # 卡片悬停
BORDER = "#262d3a"      # 描边
TEXT = "#e7eaf0"        # 主文字
MUTED = "#8b94a7"       # 次要文字
DIM = "#5b6376"         # 已完成文字
ACCENT = "#5b8cff"      # 强调色
ACCENT_DARK = "#3f6fe0"
ACCENT_SOFT = "#1b2438"  # 强调色浅底
CHIP = "#1c212c"         # 小按钮底色
RED = "#f87171"
AMBER = "#fbbf24"
GREEN = "#4ade80"

PRIORITY_COLOR = {"high": RED, "mid": AMBER, "low": GREEN}

VIEWS = [
    ("all", "全部任务"),
    ("active", "进行中"),
    ("done", "已完成"),
    ("today", "今天到期"),
    ("overdue", "已逾期"),
]

SORTS = [("default", "最新"), ("priority", "优先级"),
         ("due", "截止日"), ("title", "标题")]


# ---------------------------------------------------------------- 工具函数
def rect_points(x1, y1, x2, y2, radius):
    """圆角矩形的 16 个控制点（配合 smooth=True 得到圆角）。"""
    r = min(radius, abs(x2 - x1) / 2, abs(y2 - y1) / 2)
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


def round_rect(canvas, x1, y1, x2, y2, radius, **kwargs):
    """用平滑多边形画一个圆角矩形（Tk 没有原生圆角）。"""
    return canvas.create_polygon(rect_points(x1, y1, x2, y2, radius),
                                 smooth=True, **kwargs)


def pick_font_family(root) -> str:
    families = set(tkfont.families(root))
    for name in ("Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC",
                 "Segoe UI", "SimHei"):
        if name in families:
            return name
    return "TkDefaultFont"


def parse_due(text: str) -> str:
    """把用户输入整理成 ISO 日期；空字符串表示没有截止日。"""
    text = text.strip().replace("/", "-").replace(".", "-")
    if not text:
        return ""
    return date.fromisoformat(text).isoformat()


# ---------------------------------------------------------------- 基础控件
class RoundButton(tk.Canvas):
    """圆角按钮，颜色完全可控。"""

    def __init__(self, master, text, command=None, *, width=None, height=38,
                 fill=ACCENT, hover=ACCENT_DARK, fg="#ffffff", font=None,
                 radius=10, parent_bg=BG):
        text_width = font.measure(text) if font else len(text) * 12
        box_width = width or text_width + 40
        super().__init__(master, width=box_width, height=height, bg=parent_bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.command = command
        self.fill = fill
        self.hover = hover
        self.shape = round_rect(self, 1, 1, box_width - 1, height - 1, radius,
                                fill=fill, outline="")
        self.create_text(box_width / 2, height / 2, text=text, fill=fg, font=font)
        self.bind("<Enter>", lambda e: self.itemconfigure(self.shape, fill=self.hover))
        self.bind("<Leave>", lambda e: self.itemconfigure(self.shape, fill=self.fill))
        self.bind("<Button-1>", self._on_click)

    def _on_click(self, _event):
        if self.command:
            self.command()


class Chip(tk.Label):
    """小号可选标签，用于排序方式、优先级、快捷日期。"""

    def __init__(self, master, text, command=None, *, selected=False,
                 parent_bg=BG, base_bg=None, font=None, padx=12, pady=5):
        super().__init__(master, text=text, font=font, padx=padx, pady=pady,
                         cursor="hand2", bd=0)
        self.command = command
        self.selected = selected
        self.parent_bg = parent_bg
        self.base_bg = base_bg or parent_bg
        self.paint()
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", lambda e: self.paint())

    def _on_click(self, _event):
        if self.command:
            self.command(self)

    def _on_enter(self, _event):
        if not self.selected:
            self.configure(bg=CARD_HOVER)

    def paint(self):
        if self.selected:
            self.configure(bg=ACCENT_SOFT, fg=ACCENT)
        else:
            self.configure(bg=self.base_bg, fg=MUTED)

    def set_selected(self, value: bool):
        self.selected = value
        self.paint()


class PlaceholderEntry(tk.Entry):
    """带灰色提示文字的输入框。"""

    def __init__(self, master, placeholder="", **kwargs):
        super().__init__(master, **kwargs)
        self.placeholder = placeholder
        self._showing = False
        self.bind("<FocusIn>", self._focus_in, add="+")
        self.bind("<FocusOut>", self._focus_out, add="+")
        self._show()

    def _show(self):
        if not super().get():
            self._showing = True
            self.configure(fg=DIM)
            self.insert(0, self.placeholder)

    def _focus_in(self, _event=None):
        if self._showing and super().get() == self.placeholder:
            self.delete(0, "end")
            self.configure(fg=TEXT)
            self._showing = False

    def _focus_out(self, _event=None):
        if not super().get():
            self._show()

    def text(self) -> str:
        return "" if self._showing else super().get()

    def set_text(self, value):
        """写入真实内容：先撤掉占位符，避免和已有内容粘在一起。"""
        self.delete(0, "end")
        self._showing = False
        self.configure(fg=TEXT)
        if value:
            self.insert(0, value)
        elif self.focus_get() is not self:
            self._show()

    def clear(self):
        self.delete(0, "end")
        self.configure(fg=TEXT)
        self._showing = False


class SlimScrollbar(tk.Canvas):
    """细滚动条：只画一根圆角滑块，避开 ttk 自带的箭头和凹槽。"""

    def __init__(self, master, command, width=7):
        super().__init__(master, width=width, bg=BG, highlightthickness=0,
                         bd=0, cursor="hand2")
        self.command = command
        self.first = 0.0
        self.last = 1.0
        self._origin = None
        self._origin_first = 0.0
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", lambda e: self._draw(hover=True))
        self.bind("<Leave>", lambda e: self._draw())
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._move)
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "_origin", None))

    def set(self, first, last):
        self.first, self.last = float(first), float(last)
        self._draw()

    def _draw(self, hover=False):
        self.delete("all")
        height = self.winfo_height()
        width = self.winfo_width()
        if height <= 2 or self.last - self.first >= 0.999:
            return                      # 一屏能放下就不显示滑块
        top = self.first * height
        bottom = top + max(30.0, (self.last - self.first) * height)
        bottom = min(bottom, height)
        round_rect(self, 1, top + 1, width - 1, bottom - 1, 3,
                   fill="#3b4659" if hover else "#2c3546", outline="")

    def _press(self, event):
        self._origin = event.y
        self._origin_first = self.first

    def _move(self, event):
        if self._origin is None:
            return
        height = max(1, self.winfo_height())
        self.command("moveto", self._origin_first + (event.y - self._origin) / height)


class SideItem(tk.Frame):
    """侧栏里的一行：名称 + 数量，可选中。"""

    def __init__(self, master, text, count, selected, command, font_body, font_small):
        super().__init__(master, bg=ACCENT_SOFT if selected else SIDEBAR,
                         cursor="hand2", height=34)
        self.selected = selected
        self.command = command

        self.marker = tk.Frame(self, bg=ACCENT if selected else SIDEBAR, width=2)
        self.marker.pack(side="left", fill="y")

        self.name = tk.Label(self, text=text, font=font_body, anchor="w",
                             bg=ACCENT_SOFT if selected else SIDEBAR,
                             fg=ACCENT if selected else TEXT)
        self.name.pack(side="left", fill="x", expand=True, padx=(12, 6), pady=7)

        self.badge = tk.Label(self, text=str(count) if count else "", font=font_small,
                              bg=ACCENT_SOFT if selected else SIDEBAR,
                              fg=ACCENT if selected else DIM)
        self.badge.pack(side="right", padx=(0, 12))

        for widget in (self, self.name, self.badge):
            widget.bind("<Button-1>", self._on_click)
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)

    def _on_click(self, _event):
        self.command()

    def _paint(self, color):
        self.configure(bg=color)
        self.name.configure(bg=color)
        self.badge.configure(bg=color)

    def _on_enter(self, _event):
        if not self.selected:
            self._paint(CARD_HOVER)

    def _on_leave(self, _event):
        if not self.selected:
            self._paint(SIDEBAR)


# ---------------------------------------------------------------- 任务卡片
class TaskRow(tk.Frame):
    def __init__(self, master, task, app):
        super().__init__(master, bg=CARD, cursor="hand2")
        self.task = task
        self.app = app
        self._hover = False

        bar_color = "#2b3342" if task.done else PRIORITY_COLOR.get(task.priority, AMBER)
        self.bar = tk.Frame(self, bg=bar_color, width=3)
        self.bar.pack(side="left", fill="y")

        self.body = tk.Frame(self, bg=CARD)
        self.body.pack(side="left", fill="both", expand=True, padx=(12, 10), pady=10)
        self.body.columnconfigure(1, weight=1)

        self.box = tk.Canvas(self.body, width=20, height=20, bg=CARD,
                             highlightthickness=0, bd=0, cursor="hand2")
        self.box.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 11))
        self._draw_box()

        title_font = app.f_title_done if task.done else app.f_title
        self.title_lbl = tk.Label(self.body, text=task.title, font=title_font,
                                  bg=CARD, fg=DIM if task.done else TEXT, anchor="w")
        self.title_lbl.grid(row=0, column=1, sticky="ew")

        meta_bg = CARD
        self.meta = tk.Frame(self.body, bg=meta_bg)
        self.meta.grid(row=1, column=1, sticky="w", pady=(3, 0))

        dot = PRIORITY_COLOR.get(task.priority, AMBER)
        if task.done:
            dot = DIM
        self.dot = tk.Label(self.meta, text="●", font=app.f_dot, bg=meta_bg, fg=dot)
        self.dot.pack(side="left", padx=(0, 5))

        self.meta_lbl = tk.Label(
            self.meta, text=f"{PRIORITY_LABEL.get(task.priority, '中')} · {task.category}",
            font=app.f_small, bg=meta_bg, fg=DIM if task.done else MUTED)
        self.meta_lbl.pack(side="left")

        due = task.due_text()
        due_color = MUTED
        if not task.done:
            if task.is_overdue():
                due_color = RED
            elif task.is_today():
                due_color = AMBER
        self.due_lbl = tk.Label(self.meta, text=f"  ·  {due}" if due else "",
                                font=app.f_small, bg=meta_bg,
                                fg=DIM if task.done else due_color)
        self.due_lbl.pack(side="left")

        self.actions = tk.Frame(self.body, bg=CARD)
        self.actions.grid(row=0, column=2, rowspan=2, sticky="e")
        self.del_lbl = tk.Label(self.actions, text="×", font=app.f_x, bg=CARD,
                                fg=CARD, cursor="hand2", padx=6)
        self.del_lbl.pack()

        self._bind_tree(self)
        self.del_lbl.bind("<Button-1>", lambda e: self.app.delete_task(self.task))
        self.box.bind("<Button-1>", lambda e: self.app.toggle_task(self.task))
        self.body.bind("<Configure>", self._on_resize)

        self._menu = tk.Menu(self, tearoff=0, bg=CARD, fg=TEXT, bd=0,
                             activebackground=ACCENT_SOFT, activeforeground=TEXT,
                             activeborderwidth=0)
        self._menu.add_command(label="编辑任务", command=lambda: self.app.edit_task(self.task))
        self._menu.add_command(
            label="标记为未完成" if task.done else "标记为已完成",
            command=lambda: self.app.toggle_task(self.task))
        self._menu.add_separator()
        self._menu.add_command(label="删除", command=lambda: self.app.delete_task(self.task))

    # ---------- 绘制 ----------
    def _draw_box(self):
        self.box.delete("all")
        if self.task.done:
            self.box.create_oval(2, 2, 18, 18, fill=ACCENT, outline="")
            self.box.create_line(6, 10, 9, 13.5, 14, 6.5, fill="#ffffff",
                                 width=2, capstyle="round", joinstyle="round")
        else:
            color = ACCENT if self._hover else "#3b4353"
            self.box.create_oval(2, 2, 18, 18, fill="", outline=color, width=1.6)

    def _paint(self, color):
        for widget in (self, self.body, self.title_lbl, self.meta, self.dot,
                       self.meta_lbl, self.due_lbl, self.actions, self.del_lbl):
            widget.configure(bg=color)
        self.box.configure(bg=color)
        self._draw_box()

    def _bind_tree(self, widget):
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<Button-3>", self._popup, add="+")
        if widget is not self.box and widget is not self.del_lbl:
            widget.bind("<Double-Button-1>",
                        lambda e: self.app.edit_task(self.task), add="+")
        for child in widget.winfo_children():
            self._bind_tree(child)

    def _on_enter(self, _event=None):
        self._set_hover(True)

    def _on_leave(self, _event=None):
        self.after(20, self._check_leave)

    def _check_leave(self):
        """鼠标可能只是移到了子控件上，需要确认是否真的离开了整张卡片。"""
        try:
            x, y = self.winfo_pointerxy()
            widget = self.winfo_containing(x, y)
        except (KeyError, tk.TclError):
            widget = None
        inside = False
        while widget is not None:
            if widget is self:
                inside = True
                break
            widget = getattr(widget, "master", None)
        if not inside:
            self._set_hover(False)

    def _set_hover(self, value):
        if self._hover == value:
            return
        self._hover = value
        self._paint(CARD_HOVER if value else CARD)
        self.del_lbl.configure(fg=MUTED if value else CARD)

    def _popup(self, event):
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu.grab_release()

    def _on_resize(self, event):
        width = max(160, event.width - 130)
        if getattr(self, "_wrap", None) != width:
            self._wrap = width
            self.title_lbl.configure(wraplength=width)


# ---------------------------------------------------------------- 新建/编辑对话框
class TaskDialog(tk.Toplevel):
    def __init__(self, master, store: TaskStore, task=None, on_save=None):
        super().__init__(master)
        self.app = master
        self.store = store
        self.task = task
        self.on_save = on_save
        self.result = None

        self.title("编辑任务" if task else "新建任务")
        self.configure(bg=BG, padx=0, pady=0)
        self.resizable(False, False)
        self.transient(master)

        self.priority = task.priority if task else "mid"
        self._build()
        self._center()
        apply_dark_titlebar(self)

        self.grab_set()
        self.title_entry.focus_set()
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Control-Return>", lambda e: self._save())
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    # ---------- 界面 ----------
    def _build(self):
        wrap = tk.Frame(self, bg=BG)
        wrap.pack(fill="both", expand=True, padx=26, pady=22)
        tk.Frame(wrap, bg=BG, width=440, height=1).pack()   # 只用来撑出宽度

        tk.Label(wrap, text="任务内容", font=self.app.f_small, bg=BG, fg=MUTED,
                 anchor="w").pack(fill="x")
        self.title_entry = PlaceholderEntry(
            wrap, "简单描述要做什么",
            font=self.app.f_body, bg=CARD, fg=TEXT, insertbackground=ACCENT,
            relief="flat", bd=0, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=ACCENT,
            selectbackground=ACCENT_SOFT, selectforeground=TEXT)
        self.title_entry.pack(fill="x", ipady=7, pady=(6, 16))
        self.title_entry.bind("<Return>", lambda e: self._save())
        if self.task:
            self.title_entry.set_text(self.task.title)

        tk.Label(wrap, text="优先级", font=self.app.f_small, bg=BG, fg=MUTED,
                 anchor="w").pack(fill="x")
        row = tk.Frame(wrap, bg=BG)
        row.pack(fill="x", pady=(6, 16))
        self.priority_chips = {}
        for key in ("high", "mid", "low"):
            chip = Chip(row, PRIORITY_LABEL[key], self._pick_priority,
                        selected=(key == self.priority), parent_bg=BG,
                        base_bg=CHIP, font=self.app.f_small)
            chip.key = key
            chip.pack(side="left", padx=(0, 8))
            self.priority_chips[key] = chip

        tk.Label(wrap, text="截止日期", font=self.app.f_small, bg=BG, fg=MUTED,
                 anchor="w").pack(fill="x")
        self.due_entry = PlaceholderEntry(
            wrap, "YYYY-MM-DD，可留空",
            font=self.app.f_body, bg=CARD, fg=TEXT, insertbackground=ACCENT,
            relief="flat", bd=0, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=ACCENT,
            selectbackground=ACCENT_SOFT, selectforeground=TEXT)
        self.due_entry.pack(fill="x", ipady=7, pady=(6, 8))
        if self.task and self.task.due:
            self.due_entry.set_text(self.task.due)

        quick = tk.Frame(wrap, bg=BG)
        quick.pack(fill="x", pady=(0, 16))
        today = date.today()
        for label, value in (("今天", today.isoformat()),
                             ("明天", date.fromordinal(today.toordinal() + 1).isoformat()),
                             ("清除", "")):
            chip = Chip(quick, label, lambda c, v=value: self._pick_due(v),
                        parent_bg=BG, base_bg=CHIP, font=self.app.f_small,
                        padx=10, pady=4)
            chip.pack(side="left", padx=(0, 8))

        tk.Label(wrap, text="分类", font=self.app.f_small, bg=BG, fg=MUTED,
                 anchor="w").pack(fill="x")
        self.cat_entry = PlaceholderEntry(
            wrap, DEFAULT_CATEGORY,
            font=self.app.f_body, bg=CARD, fg=TEXT, insertbackground=ACCENT,
            relief="flat", bd=0, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=ACCENT,
            selectbackground=ACCENT_SOFT, selectforeground=TEXT)
        self.cat_entry.pack(fill="x", ipady=7, pady=(6, 8))
        if self.task and self.task.category != DEFAULT_CATEGORY:
            self.cat_entry.set_text(self.task.category)

        cats = [name for name in self.store.categories() if name != DEFAULT_CATEGORY][:5]
        if cats:
            chips = tk.Frame(wrap, bg=BG)
            chips.pack(fill="x", pady=(0, 6))
            for name in cats:
                chip = Chip(chips, name, lambda c, v=name: self._pick_cat(v),
                            parent_bg=BG, base_bg=CHIP, font=self.app.f_small,
                            padx=9, pady=3)
                chip.pack(side="left", padx=(0, 6))

        self.hint = tk.Label(wrap, text="", font=self.app.f_small, bg=BG, fg=RED,
                             anchor="w")
        self.hint.pack(fill="x", pady=(2, 2))

        buttons = tk.Frame(wrap, bg=BG)
        buttons.pack(fill="x", pady=(4, 0))
        RoundButton(buttons, "保存", self._save, width=104, height=38,
                    font=self.app.f_btn, parent_bg=BG).pack(side="right")
        RoundButton(buttons, "取消", self.destroy, width=88, height=38,
                    fill="#232a38", hover="#2c3444", fg=MUTED,
                    font=self.app.f_btn, parent_bg=BG).pack(side="right", padx=(0, 10))

    def _center(self):
        self.update_idletasks()
        width = max(492, self.winfo_reqwidth())
        height = self.winfo_reqheight()
        parent = self.master
        x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
        y = parent.winfo_rooty() + max(40, (parent.winfo_height() - height) // 3)
        self.geometry(f"{width}x{height}+{x}+{y}")

    # ---------- 交互 ----------
    def _pick_priority(self, chip):
        self.priority = chip.key
        for key, item in self.priority_chips.items():
            item.set_selected(key == chip.key)

    def _pick_due(self, value):
        self.due_entry.clear()
        if value:
            self.due_entry.insert(0, value)

    def _pick_cat(self, value):
        self.cat_entry.clear()
        self.cat_entry.insert(0, value)

    def _save(self):
        title = self.title_entry.text().strip()
        if not title:
            self.hint.configure(text="任务内容不能为空")
            self.title_entry.focus_set()
            return
        try:
            due = parse_due(self.due_entry.text())
        except ValueError:
            self.hint.configure(text="日期格式应为 2026-11-26")
            self.due_entry.focus_set()
            return
        category = self.cat_entry.text().strip() or DEFAULT_CATEGORY
        self.result = {"title": title, "priority": self.priority,
                       "due": due, "category": category}
        if self.on_save:
            self.on_save(self.result)
        self.destroy()


# ---------------------------------------------------------------- 主窗口
class TodoApp(tk.Tk):
    def __init__(self, store: TaskStore | None = None):
        super().__init__()
        self.store = store or TaskStore()
        self.view = "all"
        self.category = None
        self.sort = "default"
        self.keyword = ""
        self._search_job = None
        self._toast = None
        self._undo = None
        self._scroll_top = True

        self.title("待办清单")
        width, height = 1080, 720
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{width}x{height}+{(screen_w - width) // 2}+{(screen_h - height) // 2}")
        self.minsize(900, 580)
        self.configure(bg=BG)
        self._set_icon()

        self.font_family = pick_font_family(self)
        self._build_fonts()
        self._build_layout()
        self._bind_keys()
        self.refresh()
        self.after(30, lambda: apply_dark_titlebar(self))

        if self.store.error:
            self.after(400, lambda: self.toast(self.store.error, error=True))

    # ---------- 初始化 ----------
    def _set_icon(self):
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
        icon = base / "icon.ico"
        if icon.exists():
            try:
                self.iconbitmap(str(icon))
            except tk.TclError:
                pass

    def _build_fonts(self):
        family = self.font_family
        self.f_brand = tkfont.Font(family=family, size=13, weight="bold")
        self.f_section = tkfont.Font(family=family, size=9, weight="bold")
        self.f_title = tkfont.Font(family=family, size=11)
        self.f_title_done = tkfont.Font(family=family, size=11, overstrike=1)
        self.f_body = tkfont.Font(family=family, size=10)
        self.f_small = tkfont.Font(family=family, size=9)
        self.f_dot = tkfont.Font(family=family, size=7)
        self.f_x = tkfont.Font(family=family, size=13, weight="bold")
        self.f_btn = tkfont.Font(family=family, size=10, weight="bold")
        self.f_stat = tkfont.Font(family=family, size=20, weight="bold")

    def _build_layout(self):
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()

    def _build_sidebar(self):
        side = tk.Frame(self, bg=SIDEBAR, width=238)
        side.grid(row=0, column=0, sticky="ns")
        side.grid_propagate(False)
        side.pack_propagate(False)

        brand = tk.Frame(side, bg=SIDEBAR)
        brand.pack(fill="x", padx=20, pady=(20, 16))
        logo = tk.Canvas(brand, width=28, height=28, bg=SIDEBAR,
                         highlightthickness=0, bd=0)
        logo.pack(side="left")
        round_rect(logo, 1, 1, 27, 27, 8, fill=ACCENT, outline="")
        logo.create_line(8, 14, 12, 19, 20, 9, fill="#ffffff", width=2.4,
                         capstyle="round", joinstyle="round")
        tk.Label(brand, text="待办清单", font=self.f_brand, bg=SIDEBAR,
                 fg=TEXT).pack(side="left", padx=(10, 0))

        RoundButton(side, "＋  新建任务", self.new_task, width=198, height=38,
                    font=self.f_btn, parent_bg=SIDEBAR).pack(padx=20, pady=(0, 22))

        self.view_box = tk.Frame(side, bg=SIDEBAR)
        self.view_box.pack(fill="x")

        self.cat_box = tk.Frame(side, bg=SIDEBAR)
        self.cat_box.pack(fill="x", pady=(18, 0))

        bottom = tk.Frame(side, bg=SIDEBAR)
        bottom.pack(side="bottom", fill="x", padx=20, pady=18)

        self.progress = tk.Canvas(bottom, width=198, height=6, bg=SIDEBAR,
                                  highlightthickness=0, bd=0)
        self.progress.pack(fill="x")
        round_rect(self.progress, 0, 0, 198, 6, 3, fill="#2b3444", outline="")
        self.progress_bar = round_rect(self.progress, 0, 0, 0, 6, 3,
                                       fill=ACCENT, outline="")
        self.progress_text = tk.Label(bottom, text="", font=self.f_small,
                                      bg=SIDEBAR, fg=MUTED, anchor="w")
        self.progress_text.pack(fill="x", pady=(8, 10))

        path_lbl = tk.Label(bottom, text="打开数据目录", font=self.f_small,
                            bg=SIDEBAR, fg=DIM, anchor="w", cursor="hand2")
        path_lbl.pack(fill="x")
        path_lbl.bind("<Button-1>", lambda e: self.open_data_dir())
        path_lbl.bind("<Enter>", lambda e: path_lbl.configure(fg=ACCENT))
        path_lbl.bind("<Leave>", lambda e: path_lbl.configure(fg=DIM))

    def _build_main(self):
        main = tk.Frame(self, bg=BG)
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        header = tk.Frame(main, bg=BG)
        header.grid(row=0, column=0, sticky="ew", padx=26, pady=(20, 14))
        header.columnconfigure(0, weight=1)

        search_wrap = tk.Frame(header, bg=CARD, highlightthickness=1,
                               highlightbackground=BORDER, highlightcolor=BORDER)
        search_wrap.grid(row=0, column=0, sticky="ew")
        self.search_entry = PlaceholderEntry(
            search_wrap, "搜索任务标题或分类…", font=self.f_body, bg=CARD,
            fg=TEXT, insertbackground=ACCENT, relief="flat", bd=0,
            highlightthickness=0, selectbackground=ACCENT_SOFT,
            selectforeground=TEXT)
        self.search_entry.pack(fill="x", ipady=7, padx=12, pady=1)
        self.search_entry.bind("<KeyRelease>", self._on_search_key)
        self.search_entry.bind("<Escape>", lambda e: self.clear_search())
        self.search_entry.bind("<FocusIn>", lambda e: search_wrap.configure(
            highlightbackground=ACCENT))
        self.search_entry.bind("<FocusOut>", lambda e: search_wrap.configure(
            highlightbackground=BORDER))

        sort_box = tk.Frame(header, bg=BG)
        sort_box.grid(row=0, column=1, sticky="e", padx=(16, 0))
        tk.Label(sort_box, text="排序", font=self.f_small, bg=BG,
                 fg=DIM).pack(side="left", padx=(0, 6))
        self.sort_chips = {}
        for key, label in SORTS:
            chip = Chip(sort_box, label, self._pick_sort, selected=(key == self.sort),
                        parent_bg=BG, base_bg=CHIP, font=self.f_small, padx=9, pady=4)
            chip.key = key
            chip.pack(side="left", padx=(0, 4))
            self.sort_chips[key] = chip

        list_wrap = tk.Frame(main, bg=BG)
        list_wrap.grid(row=1, column=0, sticky="nsew", padx=(26, 16))
        list_wrap.columnconfigure(0, weight=1)
        list_wrap.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(list_wrap, bg=BG, highlightthickness=0, bd=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = SlimScrollbar(list_wrap, self.canvas.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns", padx=(6, 0))
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.inner = tk.Frame(self.canvas, bg=BG)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind_all("<MouseWheel>", self._on_wheel, add="+")

        footer = tk.Frame(main, bg=BG)
        footer.grid(row=2, column=0, sticky="ew", padx=26, pady=(10, 14))
        tk.Label(footer, text="双击编辑 · 右键更多 · Ctrl+N 新建 · Ctrl+F 搜索 · Ctrl+Z 撤销删除",
                 font=self.f_small, bg=BG, fg=DIM, anchor="w").pack(side="left")
        self.count_lbl = tk.Label(footer, text="", font=self.f_small, bg=BG, fg=DIM)
        self.count_lbl.pack(side="right")

    def _bind_keys(self):
        self.bind("<Control-n>", lambda e: self.new_task())
        self.bind("<Control-f>", lambda e: self.search_entry.focus_set())
        self.bind("<Control-z>", lambda e: self.undo_delete())

    # ---------- 滚动 ----------
    def _on_inner_configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    def _on_wheel(self, event):
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget is self.canvas:
                self.canvas.yview_scroll(int(-event.delta / 120), "units")
                return
            widget = getattr(widget, "master", None)

    # ---------- 渲染 ----------
    def refresh(self):
        self._render_views()
        self._render_categories()
        self._render_list()
        self._render_progress()

    def _render_views(self):
        for child in self.view_box.winfo_children():
            child.destroy()
        tk.Label(self.view_box, text="视图", font=self.f_section, bg=SIDEBAR,
                 fg=DIM, anchor="w").pack(fill="x", padx=20, pady=(0, 4))
        counts = self.store.counts()
        for key, label in VIEWS:
            SideItem(self.view_box, label, counts.get(key, 0), self.view == key,
                     lambda k=key: self._pick_view(k), self.f_body, self.f_small
                     ).pack(fill="x")

    def _render_categories(self):
        for child in self.cat_box.winfo_children():
            child.destroy()
        tk.Label(self.cat_box, text="分类", font=self.f_section, bg=SIDEBAR,
                 fg=DIM, anchor="w").pack(fill="x", padx=20, pady=(0, 4))
        SideItem(self.cat_box, "全部分类", len(self.store.tasks),
                 self.category is None, lambda: self._pick_category(None),
                 self.f_body, self.f_small).pack(fill="x")
        for name, count in self.store.categories().items():
            SideItem(self.cat_box, name, count, self.category == name,
                     lambda n=name: self._pick_category(n),
                     self.f_body, self.f_small).pack(fill="x")

    def _render_list(self):
        # 切换筛选时回到顶部，单纯增删改时保持原来的滚动位置
        fraction = 0.0 if self._scroll_top else self.canvas.yview()[0]
        self._scroll_top = False
        for child in self.inner.winfo_children():
            child.destroy()
        items = self.store.query(self.view, self.category, self.keyword, self.sort)
        if not items:
            self._empty_state()
        else:
            for task in items:
                TaskRow(self.inner, task, self).pack(fill="x", pady=(0, 8))
        self.canvas.update_idletasks()
        self.canvas.yview_moveto(fraction)
        total = len(self.store.tasks)
        self.count_lbl.configure(text=f"当前 {len(items)} 条 · 共 {total} 条")

    def _empty_state(self):
        box = tk.Frame(self.inner, bg=BG)
        box.pack(fill="both", expand=True, pady=40)
        center = tk.Frame(box, bg=BG)
        center.pack(expand=True)          # 让提示在列表区域里垂直居中
        tk.Label(center, text="这里还没有任务", font=self.f_title, bg=BG,
                 fg=MUTED).pack()
        tk.Label(center, text="点击左侧「＋ 新建任务」开始记录", font=self.f_small,
                 bg=BG, fg=DIM).pack(pady=(6, 0))

    def _render_progress(self):
        rate = self.store.completion_rate()
        length = max(6.0, rate * 198)
        self.progress.coords(self.progress_bar, *rect_points(0, 0, length, 6, 3))
        self.progress.itemconfigure(self.progress_bar, fill=ACCENT)
        counts = self.store.counts()
        self.progress_text.configure(
            text=f"完成率 {rate * 100:.0f}%    {counts['done']}/{counts['all']}")

    # ---------- 筛选交互 ----------
    def _pick_view(self, key):
        self.view = key
        self._scroll_top = True
        self.refresh()

    def _pick_category(self, name):
        self.category = name
        self._scroll_top = True
        self.refresh()

    def _pick_sort(self, chip):
        self.sort = chip.key
        for key, item in self.sort_chips.items():
            item.set_selected(key == chip.key)
        self._scroll_top = True
        self._render_list()

    def _on_search_key(self, _event):
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(140, self._apply_search)

    def _apply_search(self):
        self._search_job = None
        keyword = self.search_entry.text().strip()
        if keyword != self.keyword:
            self.keyword = keyword
            self._scroll_top = True
            self._render_list()

    def clear_search(self):
        self.search_entry.clear()
        self.keyword = ""
        self._scroll_top = True
        self.focus_set()
        self._render_list()

    # ---------- 任务操作 ----------
    def new_task(self):
        TaskDialog(self, self.store, None, on_save=self._create_task)

    def _create_task(self, data):
        if self.store.add(**data):
            self.refresh()
            self.toast("已添加")
        else:
            self.toast(self.store.error, error=True)

    def edit_task(self, task):
        current = self.store.get(task.tid) or task
        TaskDialog(self, self.store, current,
                   on_save=lambda data: self._update_task(current, data))

    def _update_task(self, task, data):
        if self.store.update(task.tid, **data):
            self.refresh()
            self.toast("已更新")
        else:
            self.toast(self.store.error, error=True)

    def toggle_task(self, task):
        self.store.toggle(task.tid)
        self.refresh()

    def delete_task(self, task):
        removed, index = self.store.delete(task.tid)
        if removed is None:
            return
        self._undo = (removed, index)
        self.refresh()
        self.toast(f"已删除「{removed.title[:12]}」", action="撤销",
                   action_cb=self.undo_delete)

    def undo_delete(self):
        if not self._undo:
            return
        task, index = self._undo
        self._undo = None
        self.store.restore(task, index)
        self.refresh()
        self.toast("已恢复")

    def open_data_dir(self):
        import os
        try:
            os.startfile(self.store.path.parent)
        except OSError:
            messagebox.showinfo("数据位置", str(self.store.path), parent=self)

    # ---------- 提示条 ----------
    def toast(self, text, *, action=None, action_cb=None, error=False):
        if self._toast is not None:
            self._toast.destroy()
        bar = tk.Frame(self, bg="#3a2028" if error else "#252e40")
        tk.Label(bar, text=text, font=self.f_small, bg=bar["bg"],
                 fg=RED if error else TEXT, padx=16, pady=9).pack(side="left")
        if action:
            act = tk.Label(bar, text=action, font=self.f_small, bg=bar["bg"],
                           fg=ACCENT, padx=12, pady=9, cursor="hand2")
            act.pack(side="left")
            act.bind("<Button-1>",
                     lambda e: (action_cb() if action_cb else None, self._hide_toast()))
        bar.place(relx=0.5, rely=1.0, anchor="s", y=-24)
        self._toast = bar
        self.after(2600, lambda target=bar: self._hide_toast(target))

    def _hide_toast(self, target=None):
        if self._toast is None:
            return
        if target is not None and target is not self._toast:
            return          # 定时器属于已经过期的提示条，不要误删新的
        self._toast.destroy()
        self._toast = None


def enable_dpi_awareness():
    """Windows 高分屏下避免字体发虚。"""
    if sys.platform != "win32":
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def apply_dark_titlebar(window):
    """让 Windows 自带的标题栏也变成深色，和界面统一。"""
    if sys.platform != "win32":
        return
    import ctypes
    try:
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1)
        for attribute in (20, 19):        # 20 是 Win10 20H1+，19 是老版本
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
    except Exception:
        pass


def main():
    enable_dpi_awareness()
    app = TodoApp()
    app.mainloop()


if __name__ == "__main__":
    main()

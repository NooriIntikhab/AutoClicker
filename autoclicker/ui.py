"""Small window for choosing click sets, speed, and play/pause."""

from __future__ import annotations

import sys
import time
import tkinter as tk
from pathlib import Path

from autoclicker.engine import ClickEngine
from autoclicker.model import (
    SLOT_COUNT,
    ClickPoint,
    Settings,
    SetupSession,
    contains_point,
    format_hotkey,
    format_speed,
    gap_from_slider,
    is_valid_hotkey,
    order_text,
    slider_from_gap,
)

BG = "#17181c"
SURFACE = "#23252b"
SURFACE_2 = "#2e3138"
BORDER = "#0c0d10"
TEXT = "#f4f5f7"
MUTED = "#9aa0aa"
ACCENT = "#6d5efc"
ACCENT_HOVER = "#7c6efd"
GREEN = "#2f9e44"
GREEN_HOVER = "#37b24d"
AMBER = "#e8890c"
AMBER_HOVER = "#f59f00"
DANGER_HOVER = "#c92a2a"
DISABLED = "#2a2c33"
DISABLED_TEXT = "#6d717a"
TRACK = "#3a3d46"
KNOB = "#ffffff"


def choose_font(root: tk.Misc) -> str:
    families = set(tkfont_families(root))
    for name in ("Segoe UI", "Ubuntu", "Cantarell", "DejaVu Sans", "Liberation Sans"):
        if name in families:
            return name
    return "TkDefaultFont"


def tkfont_families(root: tk.Misc) -> tuple[str, ...]:
    import tkinter.font as tkfont

    return tkfont.families(root)


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "assets" / name


class FlatButton:
    """Label button so the colors stay the same on Windows and Linux."""

    def __init__(self, parent, text, command, font, bg, fg, hover, pady=8):
        self.command = command
        self.enabled = True
        self.bg = bg
        self.hover = hover
        self.fg = fg
        self.frame = tk.Frame(parent, bg=bg, cursor="hand2", highlightthickness=0, bd=0)
        self.label = tk.Label(
            self.frame,
            text=text,
            bg=bg,
            fg=fg,
            font=font,
            pady=pady,
            cursor="hand2",
            highlightthickness=0,
            bd=0,
        )
        self.label.pack(fill="x")
        for widget in (self.frame, self.label):
            widget.bind("<Button-1>", self._click)
            widget.bind("<Enter>", self._enter)
            widget.bind("<Leave>", self._leave)

    def _click(self, _event=None):
        if self.enabled and self.command is not None:
            self.command()

    def invoke(self) -> None:
        self._click()

    def pack(self, **kwargs) -> None:
        self.frame.pack(**kwargs)

    def grid(self, **kwargs) -> None:
        self.frame.grid(**kwargs)

    def destroy(self) -> None:
        self.frame.destroy()

    def set_style(self, *, text=None, bg=None, hover=None, fg=None, enabled=None) -> None:
        if text is not None:
            self.label.configure(text=text)
        if bg is not None:
            self.bg = bg
        if hover is not None:
            self.hover = hover
        if fg is not None:
            self.fg = fg
        if enabled is not None:
            self.enabled = enabled
        cursor = "hand2" if self.enabled else "arrow"
        self.frame.configure(bg=self.bg, cursor=cursor)
        self.label.configure(bg=self.bg, fg=self.fg, cursor=cursor)

    def text(self) -> str:
        return str(self.label.cget("text"))

    def _enter(self, _event) -> None:
        if self.enabled:
            self.frame.configure(bg=self.hover)
            self.label.configure(bg=self.hover)

    def _leave(self, _event) -> None:
        self.frame.configure(bg=self.bg)
        self.label.configure(bg=self.bg)


class SpeedBar(tk.Canvas):
    """Draggable bar. The right side is faster."""

    def __init__(self, parent, variable: tk.DoubleVar, command, **kwargs):
        super().__init__(
            parent,
            height=28,
            bg=BG,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            **kwargs,
        )
        self.variable = variable
        self.command = command
        self._dragging = False
        self.bind("<Configure>", lambda _event: self.redraw())
        self.bind("<Button-1>", self._on_pointer)
        self.bind("<B1-Motion>", self._on_pointer)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<MouseWheel>", self._on_wheel)
        self.bind("<Button-4>", lambda _event: self._nudge(0.04))
        self.bind("<Button-5>", lambda _event: self._nudge(-0.04))
        self.variable.trace_add("write", lambda *_args: self.redraw())

    def redraw(self) -> None:
        self.delete("all")
        width = self.winfo_width()
        height = self.winfo_height()
        if width < 20:
            return
        pad = 10
        center_y = height // 2
        position = min(1.0, max(0.0, float(self.variable.get())))
        knob_x = pad + position * (width - 2 * pad)
        self.create_line(pad, center_y, width - pad, center_y, fill=TRACK, width=6, capstyle="round")
        self.create_line(pad, center_y, knob_x, center_y, fill=ACCENT, width=6, capstyle="round")
        radius = 8
        self.create_oval(
            knob_x - radius,
            center_y - radius,
            knob_x + radius,
            center_y + radius,
            fill=KNOB,
            outline=ACCENT,
            width=2,
        )

    def _value_at(self, x: int) -> float:
        pad = 10
        width = max(1, self.winfo_width() - 2 * pad)
        return min(1.0, max(0.0, (x - pad) / width))

    def _on_pointer(self, event) -> None:
        self._dragging = True
        value = self._value_at(event.x)
        self.variable.set(value)
        if self.command is not None:
            self.command(value)

    def _on_release(self, _event) -> None:
        self._dragging = False
        if self.command is not None:
            self.command(float(self.variable.get()))

    def _on_wheel(self, event) -> None:
        delta = getattr(event, "delta", 0)
        self._nudge(0.04 if delta > 0 else -0.04)

    def _nudge(self, amount: float) -> None:
        value = min(1.0, max(0.0, float(self.variable.get()) + amount))
        self.variable.set(value)
        if self.command is not None:
            self.command(value)


class AutoClickerApp:
    def __init__(self, root: tk.Tk, settings: Settings, mouse, hotkeys, capture, save_settings):
        self.root = root
        self.settings = settings
        self.mouse = mouse
        self.hotkeys = hotkeys
        self.capture = capture
        self._save = save_settings
        self.engine = ClickEngine(
            mouse,
            self._points_for_engine,
            self._interval_for_engine,
            self._on_engine_event,
            should_yield=self._user_wants_the_pointer,
        )
        self._window_bounds: tuple[int, int, int, int] | None = None
        self._last_seen: tuple[int, int] | None = None
        self._moved_at = 0.0
        self.font = choose_font(root)
        self._busy = False
        self._rebinding = False
        self._closing = False
        self._banner_active = False
        self._chromeless = False
        self._minimizing = False
        self._saw_iconic = False
        self._home_geometry = ""
        self._last_toggle = 0.0
        self._save_after: str | None = None
        self._pending_status: str | None = None
        self._user_cancelled = False
        self._confirm_result = False
        self._capture_token = 0
        self._accepting_clicks = False
        self._captured: ClickPoint | None = None
        self._setup_cancelled = False
        self._wake = tk.IntVar(master=root, value=0)
        self._count_wake = tk.IntVar(master=root, value=0)
        self._count_waiting = False
        self._count_active = False
        self._count_panel: tk.Frame | None = None
        self.count_buttons: list[FlatButton] | None = None
        self.count_next: FlatButton | None = None
        self.confirm_accept: FlatButton | None = None
        self.confirm_retry: FlatButton | None = None
        self._count_dialog: tk.Toplevel | None = None
        self._confirm_dialog: tk.Toplevel | None = None
        self._count_choice = 1
        self._count_result: int | None = None
        self.edit_buttons: list[FlatButton] = []
        self._icon_image = None
        self._build()
        self.apply_hotkey()
        self.refresh()
        self._place_initial()
        self.root.after(200, self._watch_window_state)
        self.root.after(80, self._cache_window_bounds)
        if sys.platform == "win32":
            self.root.after(30, self._ensure_taskbar)

    def run(self) -> None:
        self.root.mainloop()

    def _build(self) -> None:
        root = self.root
        root.title("AutoClicker")
        root.configure(bg=BORDER)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._load_icon()
        # A drawn title bar keeps minimize and close inside the small window.
        root.overrideredirect(True)
        self._chromeless = True

        self._shell = tk.Frame(root, bg=BG, highlightthickness=0, bd=0)
        self._shell.pack(fill="both", expand=True, padx=1, pady=1)

        self._header = tk.Frame(self._shell, bg=BG, height=40)
        self._header.pack(fill="x")
        self._header.pack_propagate(False)
        self._title = tk.Label(
            self._header,
            text="AutoClicker",
            bg=BG,
            fg=TEXT,
            font=(self.font, 12, "bold"),
        )
        self._title.pack(side="left", padx=14)
        self.close_button = self._title_control("×", self.close, DANGER_HOVER)
        self.minimize_button = self._title_control("–", self.minimize_window, SURFACE_2)
        for widget in (self._header, self._title):
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)

        self._body = tk.Frame(self._shell, bg=BG)
        self._body.pack(fill="both", expand=True, padx=16, pady=(4, 14))

        self.play_button = FlatButton(
            self._body,
            "Play",
            self.toggle_play,
            (self.font, 13, "bold"),
            GREEN,
            TEXT,
            GREEN_HOVER,
            pady=12,
        )
        self.play_button.pack(fill="x", pady=(8, 10))

        key_row = tk.Frame(self._body, bg=BG)
        key_row.pack(fill="x")
        tk.Label(
            key_row,
            text="Play / pause key",
            bg=BG,
            fg=MUTED,
            font=(self.font, 10),
        ).pack(side="left")
        self.hotkey_value = tk.Label(
            key_row,
            text=format_hotkey(self.settings.hotkey),
            bg=SURFACE,
            fg=TEXT,
            font=(self.font, 10, "bold"),
            padx=10,
            pady=4,
        )
        self.hotkey_value.pack(side="left", padx=8)
        self.hotkey_button = FlatButton(
            key_row,
            "Change",
            self.on_hotkey_button,
            (self.font, 10, "bold"),
            SURFACE_2,
            TEXT,
            "#3a3d46",
            pady=4,
        )
        self.hotkey_button.pack(side="right")

        self.hint_label = tk.Label(
            self._body,
            text="This key keeps working while the window is minimized.",
            bg=BG,
            fg=MUTED,
            font=(self.font, 9),
            anchor="w",
        )
        self.hint_label.pack(fill="x", pady=(6, 14))

        self._section(self._body, "Sets").pack(fill="x", pady=(0, 6))
        self.slot_row = tk.Frame(self._body, bg=BG)
        self.slot_row.pack(fill="x")
        self.slot_buttons: list[FlatButton] = []
        self.slot_marks: list[tk.Frame] = []
        for index in range(SLOT_COUNT):
            self.slot_row.grid_columnconfigure(index, weight=1, uniform="sets")
            cell = tk.Frame(self.slot_row, bg=BG)
            cell.grid(row=0, column=index, sticky="ew", padx=3)
            button = FlatButton(
                cell,
                str(index + 1),
                lambda i=index: self.on_slot_clicked(i),
                (self.font, 13, "bold"),
                SURFACE,
                TEXT,
                SURFACE_2,
                pady=8,
            )
            button.pack(fill="x")
            mark = tk.Frame(cell, bg=BG, height=3)
            mark.pack(fill="x", pady=(5, 0))
            mark.pack_propagate(False)
            self.slot_buttons.append(button)
            self.slot_marks.append(mark)
        self.slot_caption = tk.Label(
            self._body,
            text="",
            bg=BG,
            fg=MUTED,
            font=(self.font, 10),
            anchor="w",
        )
        self.slot_caption.pack(fill="x", pady=(8, 12))

        self._section(self._body, "Clicks").pack(fill="x", pady=(0, 4))
        self.order_label = tk.Label(
            self._body,
            text="",
            bg=BG,
            fg=TEXT,
            font=(self.font, 10),
            anchor="w",
            justify="left",
        )
        self.order_label.pack(fill="x", pady=(0, 6))
        self.points_box = tk.Frame(self._body, bg=BG)
        self.points_box.pack(fill="x")
        self.setup_button = FlatButton(
            self._body,
            "Set up clicks",
            self.run_setup,
            (self.font, 11, "bold"),
            ACCENT,
            TEXT,
            ACCENT_HOVER,
            pady=10,
        )
        self.setup_button.pack(fill="x", pady=(10, 14))

        speed_header = tk.Frame(self._body, bg=BG)
        speed_header.pack(fill="x")
        self._section(speed_header, "Speed").pack(side="left")
        self.speed_value = tk.Label(
            speed_header,
            text=format_speed(self.settings.interval),
            bg=BG,
            fg=TEXT,
            font=(self.font, 10, "bold"),
        )
        self.speed_value.pack(side="right")
        speed_ends = tk.Frame(self._body, bg=BG)
        speed_ends.pack(fill="x", pady=(4, 0))
        tk.Label(speed_ends, text="Slow", bg=BG, fg=MUTED, font=(self.font, 9)).pack(side="left")
        tk.Label(speed_ends, text="Fast", bg=BG, fg=MUTED, font=(self.font, 9)).pack(side="right")
        self.speed_var = tk.DoubleVar(value=slider_from_gap(self.settings.interval))
        self.speed_bar = SpeedBar(self._body, self.speed_var, self.on_speed, width=360)
        self.speed_bar.pack(fill="x")

        self.status_label = tk.Label(
            self._body,
            text="Paused",
            bg=SURFACE,
            fg=TEXT,
            font=(self.font, 10),
            anchor="w",
            padx=10,
            pady=8,
        )
        self.status_label.pack(fill="x", pady=(12, 0))

        self._banner = tk.Frame(self._shell, bg=BG)
        banner_top = tk.Frame(self._banner, bg=BG)
        banner_top.pack(fill="x", padx=16, pady=(14, 0))
        self._banner_title = tk.Label(
            banner_top,
            text="",
            bg=BG,
            fg=TEXT,
            font=(self.font, 13, "bold"),
            anchor="w",
        )
        self._banner_title.pack(side="left", fill="x", expand=True)
        self.banner_cancel = FlatButton(
            banner_top,
            "Cancel",
            self.cancel_setup,
            (self.font, 10, "bold"),
            SURFACE_2,
            TEXT,
            "#3a3d46",
            pady=4,
        )
        self.banner_cancel.pack(side="right")
        self._banner_detail = tk.Label(
            self._banner,
            text="",
            bg=BG,
            fg=MUTED,
            font=(self.font, 10),
            anchor="w",
            justify="left",
            wraplength=460,
        )
        self._banner_detail.pack(fill="x", padx=16, pady=(6, 14))

    def _title_control(self, text: str, command, hover: str) -> FlatButton:
        button = FlatButton(
            self._header,
            text,
            command,
            (self.font, 14),
            BG,
            TEXT,
            hover,
            pady=6,
        )
        button.frame.pack(side="right", fill="y")
        button.label.configure(padx=14)
        return button

    def _section(self, parent, text: str) -> tk.Label:
        return tk.Label(
            parent,
            text=text.upper(),
            bg=BG,
            fg=MUTED,
            font=(self.font, 9, "bold"),
            anchor="w",
        )

    def _load_icon(self) -> None:
        path = resource_path("icon.png")
        if not path.exists():
            return
        try:
            self._icon_image = tk.PhotoImage(file=str(path))
            self.root.iconphoto(True, self._icon_image)
        except tk.TclError:
            self._icon_image = None

    def _place_initial(self) -> None:
        self.root.update_idletasks()
        width = 400
        height = max(self._shell.winfo_reqheight() + 2, 520)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.speed_bar.redraw()

    def _fit_height(self) -> None:
        if self._banner_active or self._count_active or self._closing:
            return
        self.root.update_idletasks()
        width = 400
        height = self._shell.winfo_reqheight() + 2
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def refresh(self) -> None:
        slot = self.settings.active_slot
        for index, button in enumerate(self.slot_buttons):
            selected = index == slot
            button.set_style(
                bg=ACCENT if selected else SURFACE,
                hover=ACCENT_HOVER if selected else SURFACE_2,
                fg=TEXT,
                enabled=not self._interactions_locked(),
            )
            self.slot_marks[index].configure(bg=ACCENT if selected else BG)
        self.slot_caption.configure(text=f"Set {slot + 1} is in use")
        points = self.settings.slots[slot].points
        self.order_label.configure(text=order_text(len(points)))
        self._rebuild_points(points)
        empty = not points
        self.setup_button.set_style(
            text="Set up clicks" if empty else "Set up again",
            bg=ACCENT if empty else SURFACE_2,
            hover=ACCENT_HOVER if empty else "#3a3d46",
            fg=TEXT,
            enabled=not self._interactions_locked(),
        )
        self.hotkey_value.configure(text=format_hotkey(self.settings.hotkey))
        self.hotkey_button.set_style(
            text="Cancel" if self._rebinding else "Change",
            enabled=not self._busy,
        )
        self.speed_var.set(slider_from_gap(self.settings.interval))
        self.speed_value.configure(text=format_speed(self.settings.interval))
        self._sync_play_button()
        minimize_enabled = not self._busy and not self._banner_active
        self.minimize_button.set_style(
            bg=BG,
            hover=SURFACE_2 if minimize_enabled else BG,
            fg=TEXT if minimize_enabled else DISABLED_TEXT,
            enabled=minimize_enabled,
        )
        if not self.engine.is_running and not self._rebinding:
            self._set_status(f"Paused · set {slot + 1}")
        self._fit_height()

    def _rebuild_points(self, points: list[ClickPoint]) -> None:
        self.edit_buttons = []
        for child in self.points_box.winfo_children():
            child.destroy()
        if not points:
            tk.Label(
                self.points_box,
                text="Choose how many spots to click, then click each spot on your screen.",
                bg=BG,
                fg=MUTED,
                font=(self.font, 10),
                wraplength=350,
                justify="left",
                anchor="w",
            ).pack(fill="x", pady=(0, 4))
            return
        locked = self._interactions_locked()
        for index, point in enumerate(points):
            row = tk.Frame(self.points_box, bg=SURFACE)
            row.pack(fill="x", pady=3)
            tk.Label(
                row,
                text=str(index + 1),
                bg=SURFACE,
                fg=ACCENT,
                font=(self.font, 11, "bold"),
                width=2,
            ).pack(side="left", padx=(10, 4), pady=6)
            tk.Label(
                row,
                text=f"{point.x}, {point.y}",
                bg=SURFACE,
                fg=TEXT,
                font=(self.font, 10),
                anchor="w",
            ).pack(side="left", fill="x", expand=True)
            edit = FlatButton(
                row,
                "Edit",
                lambda i=index: self.edit_point(i),
                (self.font, 10, "bold"),
                SURFACE,
                ACCENT,
                SURFACE_2,
                pady=4,
            )
            edit.label.configure(padx=8)
            edit.set_style(enabled=not locked)
            edit.pack(side="right", padx=6, pady=4)
            self.edit_buttons.append(edit)

    def _sync_play_button(self) -> None:
        running = self.engine.is_running
        has_points = bool(self.settings.active_points())
        locked = self._interactions_locked()
        if running and not locked:
            text, bg, hover, fg = "Pause", AMBER, AMBER_HOVER, "#1a1b1e"
        elif has_points and not locked:
            text, bg, hover, fg = "Play", GREEN, GREEN_HOVER, TEXT
        else:
            text, bg, hover, fg = "Play", DISABLED, DISABLED, DISABLED_TEXT
        self.play_button.set_style(text=text, bg=bg, hover=hover, fg=fg, enabled=not locked)

    def _interactions_locked(self) -> bool:
        return self._busy or self._rebinding

    def _set_status(self, text: str) -> None:
        if not self._closing:
            self.status_label.configure(text=text)

    def _cache_window_bounds(self) -> None:
        if self._closing:
            return
        self._window_bounds = _widget_bounds(self.root)
        try:
            self.root.after(80, self._cache_window_bounds)
        except tk.TclError:
            pass

    def _user_wants_the_pointer(self) -> bool:
        """True while the user is aiming at this window or moving the mouse."""

        try:
            pos = self.mouse.position()
        except Exception:
            return False
        now = time.monotonic()
        bounds = self._window_bounds
        over_window = bounds is not None and contains_point(pos[0], pos[1], bounds, pad=20)
        if over_window:
            return True
        last = getattr(self.mouse, "last_click", None)
        moved = last is not None and (abs(pos[0] - last[0]) > 18 or abs(pos[1] - last[1]) > 18)
        if not moved:
            self._last_seen = pos
            return False
        if pos != self._last_seen:
            self._last_seen = pos
            self._moved_at = now
        return now - self._moved_at < 0.3

    def _points_for_engine(self):
        return self.settings.active_points()

    def _interval_for_engine(self) -> float:
        return self.settings.interval

    def _on_engine_event(self, kind: str, **payload) -> None:
        if self._closing:
            return

        def apply() -> None:
            if self._closing:
                return
            self._apply_engine_event(kind, payload)

        try:
            self.root.after(0, apply)
        except tk.TclError:
            pass

    def _apply_engine_event(self, kind: str, payload: dict) -> None:
        slot = self.settings.active_slot + 1
        if kind == "started":
            self._set_status(f"Clicking set {slot}")
        elif kind == "click":
            self._set_status(
                f"Clicking set {slot} · spot {payload['index'] + 1} of {payload['count']}"
            )
        elif kind == "empty":
            self._pending_status = "Set up clicks for this set first."
        elif kind == "error":
            self._pending_status = payload.get("message") or "Could not click."
        elif kind == "stopped":
            message = self._pending_status or f"Paused · set {slot}"
            self._pending_status = None
            self._set_status(message)
        self._sync_play_button()

    def toggle_play(self) -> None:
        if self._interactions_locked() or self._closing:
            return
        now = time.monotonic()
        if now - self._last_toggle < 0.25:
            return
        self._last_toggle = now
        if self.engine.is_running:
            self.engine.stop()
            self._sync_play_button()
            return
        if not self.settings.active_points():
            self._set_status("Set up clicks for this set first.")
            self._sync_play_button()
            return
        self.engine.start()
        self._sync_play_button()

    def on_slot_clicked(self, index: int) -> None:
        if self._interactions_locked():
            return
        self.settings.active_slot = index
        self.persist()
        self.refresh()
        if self.engine.is_running:
            self._set_status(f"Clicking set {index + 1}")
        if not self.settings.slots[index].points:
            if self.engine.is_running:
                self.engine.stop()
            self.run_setup()

    def on_speed(self, position: float) -> None:
        self.settings.interval = gap_from_slider(position)
        self.speed_value.configure(text=format_speed(self.settings.interval))
        if self._save_after is not None:
            self.root.after_cancel(self._save_after)
        self._save_after = self.root.after(200, self.persist)

    def on_hotkey_button(self) -> None:
        if self._busy:
            return
        if self._rebinding:
            self.cancel_rebind()
        else:
            self.start_rebind()

    def start_rebind(self) -> None:
        if self._interactions_locked():
            return
        self._rebinding = True
        try:
            self.hotkeys.clear_hotkey()
        except Exception as exc:
            print(f"AutoClicker could not pause the hotkey: {exc}", file=sys.stderr)
        self.refresh()
        self._set_status("Press a key. Esc cancels.")
        try:
            self.hotkeys.capture_next_key(
                lambda spec: self.root.after(0, lambda: self._finish_rebind(spec))
            )
        except Exception as exc:
            print(f"AutoClicker could not listen for a key: {exc}", file=sys.stderr)
            self._finish_rebind(None)
            self._set_status("Could not listen for a new key.")

    def cancel_rebind(self) -> None:
        try:
            self.hotkeys.cancel_capture()
        except Exception:
            pass
        self._finish_rebind(None)

    def _finish_rebind(self, spec: str | None) -> None:
        if not self._rebinding or self._closing:
            return
        self._rebinding = False
        chosen = spec if spec and is_valid_hotkey(spec) else None
        if chosen is not None:
            self.settings.hotkey = chosen
            self.persist()
        self.apply_hotkey()
        self.refresh()
        if chosen is not None:
            self._set_status(f"Play / pause is now {format_hotkey(chosen)}.")

    def apply_hotkey(self) -> None:
        if self._closing:
            return
        try:
            self.hotkeys.set_hotkey(self.settings.hotkey, self._hotkey_pressed)
        except Exception as exc:
            print(f"AutoClicker hotkey failed: {exc}", file=sys.stderr)
            if self.settings.hotkey != "<f6>":
                self.settings.hotkey = "<f6>"
                self.persist()
                try:
                    self.hotkeys.set_hotkey("<f6>", self._hotkey_pressed)
                except Exception:
                    self._set_status("Could not listen for the play / pause key.")

    def _hotkey_pressed(self) -> None:
        if self._closing:
            return
        try:
            self.root.after(0, self.toggle_play)
        except tk.TclError:
            pass

    def run_setup(self) -> None:
        if self._busy or self._closing:
            return
        slot_index = self.settings.active_slot
        existing = len(self.settings.slots[slot_index].points)
        self._busy = True
        self._user_cancelled = False
        if self.engine.is_running:
            self.engine.stop()
        self.refresh()
        saved_message = None
        try:
            count = self.ask_count(slot_index, existing)
            if count is None:
                return
            session = SetupSession(count)
            if self._capture_session(session):
                self.settings.slots[slot_index].points = list(session.points)
                self.persist()
                saved_message = f"Saved {len(session.points)} clicks in set {slot_index + 1}"
        finally:
            self._accepting_clicks = False
            try:
                self.capture.disarm()
            except Exception:
                pass
            self._destroy_dialog("_confirm_dialog")
            self._leave_banner()
            self._busy = False
            if not self._closing:
                self.refresh()
                if saved_message:
                    self._set_status(saved_message)

    def edit_point(self, index: int) -> None:
        if self._busy or self._closing:
            return
        slot = self.settings.slots[self.settings.active_slot]
        if index < 0 or index >= len(slot.points):
            return
        self._busy = True
        self._user_cancelled = False
        if self.engine.is_running:
            self.engine.stop()
        self.refresh()
        saved_message = None
        try:
            while not self._closing and not self._user_cancelled:
                point = self._capture_point(
                    f"New spot for click {index + 1}",
                    "Click the new place on your screen. Drag this window if it covers the spot. Esc cancels.",
                )
                if point is None:
                    return
                if self._confirm_point(f"Click {index + 1}", point):
                    points = list(slot.points)
                    points[index] = point
                    slot.points = points
                    self.persist()
                    saved_message = f"Updated click {index + 1}"
                    return
        finally:
            self._accepting_clicks = False
            try:
                self.capture.disarm()
            except Exception:
                pass
            self._destroy_dialog("_confirm_dialog")
            self._leave_banner()
            self._busy = False
            if not self._closing:
                self.refresh()
                if saved_message:
                    self._set_status(saved_message)

    def cancel_setup(self) -> None:
        if self._closing or not self._busy:
            return
        self._user_cancelled = True
        self._complete_capture(self._capture_token, cancel=True)
        self._cancel_count()
        if self._confirm_dialog is not None:
            self._close_confirm(False)

    def ask_count(self, slot_index: int, existing: int) -> int | None:
        """Ask inside the main window so the prompt is not a second overlapping card."""

        self._count_choice = existing if 1 <= existing <= 5 else 1
        self._count_result = None
        self._count_waiting = True
        panel = tk.Frame(self._shell, bg=BG)
        self._count_panel = panel
        inner = tk.Frame(panel, bg=BG)
        inner.pack(fill="both", expand=True, padx=18, pady=(8, 18))
        tk.Label(
            inner,
            text=f"Set {slot_index + 1}",
            bg=BG,
            fg=ACCENT,
            font=(self.font, 10, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            inner,
            text="How many clicks in a row?",
            bg=BG,
            fg=TEXT,
            font=(self.font, 14, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(4, 4))
        tk.Label(
            inner,
            text="Pick up to 5. They run in order, then start again at the first.",
            bg=BG,
            fg=MUTED,
            font=(self.font, 10),
            wraplength=340,
            justify="left",
            anchor="w",
        ).pack(fill="x")
        if existing:
            tk.Label(
                inner,
                text="Finishing this replaces the clicks already in this set.",
                bg=BG,
                fg=MUTED,
                font=(self.font, 10),
                wraplength=340,
                justify="left",
                anchor="w",
            ).pack(fill="x", pady=(4, 0))
        row = tk.Frame(inner, bg=BG)
        row.pack(fill="x", pady=(14, 16))
        self.count_buttons = []
        for number in range(1, 6):
            row.grid_columnconfigure(number - 1, weight=1, uniform="count")
            button = FlatButton(
                row,
                str(number),
                lambda n=number: self._choose_count(n),
                (self.font, 13, "bold"),
                SURFACE,
                TEXT,
                SURFACE_2,
                pady=8,
            )
            button.grid(row=0, column=number - 1, sticky="ew", padx=3)
            self.count_buttons.append(button)
        self._paint_count_choices()
        actions = tk.Frame(inner, bg=BG)
        actions.pack(fill="x")
        cancel = FlatButton(
            actions,
            "Cancel",
            self._cancel_count,
            (self.font, 11, "bold"),
            SURFACE_2,
            TEXT,
            "#3a3d46",
            pady=8,
        )
        cancel.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.count_next = FlatButton(
            actions,
            "Next",
            self._accept_count,
            (self.font, 11, "bold"),
            ACCENT,
            TEXT,
            ACCENT_HOVER,
            pady=8,
        )
        self.count_next.pack(side="right", fill="x", expand=True, padx=(6, 0))
        self._bind_count_keys()
        self._show_count_panel(panel)
        self.root.wait_variable(self._count_wake)
        self.count_buttons = None
        self.count_next = None
        self._count_panel = None
        self.root.after_idle(panel.destroy)
        if self._count_result is None and not self._banner_active:
            self._restore_main()
        return self._count_result

    def _choose_count(self, number: int) -> None:
        self._count_choice = number
        self._paint_count_choices()

    def _paint_count_choices(self) -> None:
        if not self.count_buttons:
            return
        for number, button in enumerate(self.count_buttons, start=1):
            selected = number == self._count_choice
            button.set_style(
                bg=ACCENT if selected else SURFACE,
                hover=ACCENT_HOVER if selected else SURFACE_2,
                fg=TEXT,
            )

    def _accept_count(self) -> None:
        if not self._count_waiting:
            return
        self._count_result = self._count_choice
        self._finish_count_wait()

    def _cancel_count(self) -> None:
        if not self._count_waiting:
            return
        self._count_result = None
        self._finish_count_wait()

    def _finish_count_wait(self) -> None:
        self._count_waiting = False
        self._count_active = False
        self._unbind_count_keys()
        panel = self._count_panel
        if panel is not None:
            try:
                panel.pack_forget()
            except tk.TclError:
                pass
        self._wake_count()

    def _show_count_panel(self, panel: tk.Frame) -> None:
        if not self._home_geometry:
            self._home_geometry = self.root.geometry()
        self._count_active = True
        self._body.pack_forget()
        panel.pack(fill="both", expand=True)
        self.root.update_idletasks()
        width = 400
        height = self._shell.winfo_reqheight() + 2
        self.root.geometry(f"{width}x{height}+{self.root.winfo_x()}+{self.root.winfo_y()}")

    def _bind_count_keys(self) -> None:
        self.root.bind("<Escape>", lambda _event: self._cancel_count())
        self.root.bind("<Return>", lambda _event: self._accept_count())
        for number in range(1, 6):
            self.root.bind(str(number), lambda _event, n=number: self._choose_count(n))

    def _unbind_count_keys(self) -> None:
        for sequence in ("<Escape>", "<Return>", "1", "2", "3", "4", "5"):
            try:
                self.root.unbind(sequence)
            except tk.TclError:
                pass

    def _wake_count(self) -> None:
        try:
            self._count_wake.set(int(self._count_wake.get()) + 1)
        except tk.TclError:
            pass

    def _restore_main(self) -> None:
        self._count_active = False
        self._banner_active = False
        try:
            self._banner.pack_forget()
        except tk.TclError:
            pass
        if self._count_panel is not None:
            try:
                self._count_panel.pack_forget()
            except tk.TclError:
                pass
        try:
            if not self._body.winfo_ismapped():
                self._body.pack(fill="both", expand=True, padx=16, pady=(4, 14))
        except tk.TclError:
            return
        try:
            self.root.attributes("-topmost", False)
        except tk.TclError:
            pass
        if self._home_geometry:
            self.root.geometry(self._home_geometry)
        self._home_geometry = ""

    def _capture_session(self, session: SetupSession) -> bool:
        while not session.done and not self._closing and not self._user_cancelled:
            point = self._capture_point(
                f"Click spot {session.index} of {session.count}",
                "Click the place on your screen for this spot. Drag this window if it covers it. Esc cancels.",
            )
            if point is None:
                return False
            session.offer(point.x, point.y)
            if self._confirm_point(f"Click {session.index} of {session.count}", point):
                session.accept()
            else:
                session.reject()
        return session.done

    def _capture_point(self, title: str, detail: str) -> ClickPoint | None:
        self._capture_token += 1
        token = self._capture_token
        self._accepting_clicks = True
        self._captured = None
        self._setup_cancelled = False
        self._enter_banner(title, detail)
        try:
            self._arm_capture(token)
        except Exception as exc:
            print(f"AutoClicker could not capture a click: {exc}", file=sys.stderr)
            self._set_status("Could not watch the mouse. Check input permissions.")
            self._accepting_clicks = False
            return None
        self.root.wait_variable(self._wake)
        try:
            self.capture.disarm()
        except Exception:
            pass
        if self._closing or self._setup_cancelled or self._captured is None:
            return None
        return self._captured

    def _arm_capture(self, token: int) -> None:
        def on_click(x: int, y: int) -> None:
            self.root.after(0, lambda: self._on_screen_click(token, x, y))

        def on_cancel() -> None:
            self.root.after(0, lambda: self._complete_capture(token, cancel=True))

        self.capture.arm(on_click, on_cancel)

    def _on_screen_click(self, token: int, x: int, y: int) -> None:
        if token != self._capture_token or not self._accepting_clicks:
            return
        if self._click_hits_app(x, y):
            try:
                self._arm_capture(token)
            except Exception:
                self._complete_capture(token, cancel=True)
            return
        self._complete_capture(token, point=ClickPoint(int(x), int(y)))

    def _complete_capture(self, token: int, point: ClickPoint | None = None, cancel: bool = False) -> None:
        if token != self._capture_token:
            return
        self._capture_token += 1
        self._accepting_clicks = False
        if cancel or point is None:
            self._setup_cancelled = True
            self._captured = None
        else:
            self._captured = point
        self._wake_wait()

    def _confirm_point(self, title: str, point: ClickPoint) -> bool:
        self._confirm_result = False
        dialog = tk.Toplevel(self.root)
        self._confirm_dialog = dialog
        dialog.title("Confirm click")
        dialog.configure(bg="#3a3d46")
        dialog.overrideredirect(True)
        dialog.attributes("-topmost", True)
        shell = tk.Frame(dialog, bg=BG)
        shell.pack(fill="both", expand=True, padx=1, pady=1)
        inner = tk.Frame(shell, bg=BG)
        inner.pack(fill="both", expand=True, padx=18, pady=16)
        tk.Label(
            inner,
            text="Use this spot?",
            bg=BG,
            fg=TEXT,
            font=(self.font, 14, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            inner,
            text=title,
            bg=BG,
            fg=MUTED,
            font=(self.font, 10),
            anchor="w",
        ).pack(fill="x", pady=(2, 8))
        tk.Label(
            inner,
            text=f"X {point.x}      Y {point.y}",
            bg=SURFACE,
            fg=TEXT,
            font=(self.font, 12, "bold"),
            padx=10,
            pady=8,
        ).pack(fill="x")
        actions = tk.Frame(inner, bg=BG)
        actions.pack(fill="x", pady=(14, 0))
        self.confirm_retry = FlatButton(
            actions,
            "Pick again",
            lambda: self._close_confirm(False),
            (self.font, 11, "bold"),
            SURFACE_2,
            TEXT,
            "#3a3d46",
            pady=8,
        )
        self.confirm_retry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.confirm_accept = FlatButton(
            actions,
            "Use this spot",
            lambda: self._close_confirm(True),
            (self.font, 11, "bold"),
            ACCENT,
            TEXT,
            ACCENT_HOVER,
            pady=8,
        )
        self.confirm_accept.pack(side="right", fill="x", expand=True, padx=(6, 0))
        dialog.bind("<Escape>", lambda _event: self._close_confirm(False))
        dialog.bind("<Return>", lambda _event: self._close_confirm(True))
        dialog.update_idletasks()
        width = max(320, dialog.winfo_reqwidth())
        height = dialog.winfo_reqheight()
        self._place_near(dialog, point.x, point.y, width, height)
        dialog.lift()
        self._focus_dialog(dialog)
        self.root.wait_window(dialog)
        accepted = bool(self._confirm_result)
        self.confirm_accept = None
        self.confirm_retry = None
        self._confirm_dialog = None
        return accepted

    def _close_confirm(self, accepted: bool) -> None:
        self._confirm_result = accepted
        self.confirm_accept = None
        self.confirm_retry = None
        self._destroy_dialog("_confirm_dialog")

    def _enter_banner(self, title: str, detail: str) -> None:
        if not self._banner_active:
            if not self._home_geometry:
                self._home_geometry = self.root.geometry()
            self._banner_active = True
            self._body.pack_forget()
            if self._count_panel is not None:
                self._count_panel.pack_forget()
            self._banner.pack(fill="both", expand=True)
        self._banner_title.configure(text=title)
        self._banner_detail.configure(text=detail)
        self.root.update_idletasks()
        width = 520
        height = max(132, self._shell.winfo_reqheight() + 2)
        x = max(0, (self.root.winfo_screenwidth() - width) // 2)
        self.root.geometry(f"{width}x{height}+{x}+24")
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.minimize_button.set_style(enabled=False, fg=DISABLED_TEXT, hover=BG, bg=BG)
        self.root.update_idletasks()

    def _leave_banner(self) -> None:
        if not self._banner_active and not self._count_active:
            return
        self._restore_main()

    def _click_hits_app(self, x: int, y: int) -> bool:
        bounds = _widget_bounds(self.root)
        return bounds is not None and contains_point(x, y, bounds, pad=8)

    def _center(self, window: tk.Toplevel, width: int, height: int) -> None:
        if self.root.winfo_viewable():
            x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - width) // 2)
            y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - height) // 2)
        else:
            x = max(0, (window.winfo_screenwidth() - width) // 2)
            y = max(0, (window.winfo_screenheight() - height) // 2)
        window.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

    def _place_near(self, window: tk.Toplevel, x: int, y: int, width: int, height: int) -> None:
        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()
        pos_x = x + 16
        pos_y = y + 16
        if pos_x + width > screen_w:
            pos_x = max(0, x - width - 16)
        if pos_y + height > screen_h:
            pos_y = max(0, y - height - 16)
        window.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

    def _destroy_dialog(self, attr: str) -> None:
        dialog = getattr(self, attr)
        setattr(self, attr, None)
        if dialog is None:
            return
        try:
            dialog.grab_release()
        except tk.TclError:
            pass
        try:
            dialog.destroy()
        except tk.TclError:
            pass

    def _focus_dialog(self, dialog: tk.Toplevel) -> None:
        try:
            dialog.focus_force()
        except tk.TclError:
            pass
        try:
            dialog.grab_set()
        except tk.TclError:
            pass

    def _wake_wait(self) -> None:
        try:
            self._wake.set(int(self._wake.get()) + 1)
        except tk.TclError:
            pass

    def minimize_window(self) -> None:
        if self._busy or self._banner_active or self._closing:
            return
        # A borderless window ignores iconify until it is withdrawn and handed
        # back to the window manager. Clicks keep running after that.
        self._minimizing = True
        self._chromeless = False
        self._saw_iconic = False
        try:
            self.root.withdraw()
            self.root.overrideredirect(False)
            self.root.update()
            self.root.deiconify()
            self.root.update()
            self.root.iconify()
            self.root.update()
        except tk.TclError:
            self._chromeless = True
            try:
                self.root.overrideredirect(True)
                self.root.deiconify()
            except tk.TclError:
                pass
        self._minimizing = False

    def _watch_window_state(self) -> None:
        if self._closing:
            return
        try:
            state = str(self.root.state())
        except tk.TclError:
            return
        if state == "iconic":
            self._saw_iconic = True
        elif (
            state == "normal"
            and self._saw_iconic
            and not self._chromeless
            and not self._banner_active
            and not self._minimizing
        ):
            self._restore_borderless()
        try:
            self.root.after(200, self._watch_window_state)
        except tk.TclError:
            pass

    def _restore_borderless(self) -> None:
        try:
            geometry = self.root.geometry()
            self.root.withdraw()
            self.root.overrideredirect(True)
            self.root.geometry(geometry)
            self.root.update_idletasks()
            self.root.deiconify()
            self._chromeless = True
            self._saw_iconic = False
        except tk.TclError:
            pass

    def _ensure_taskbar(self) -> None:
        if sys.platform != "win32" or self._closing:
            return
        import ctypes

        try:
            self.root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            style = (style & ~0x00000080) | 0x00040000
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)
        except Exception:
            return

    def _start_drag(self, event) -> None:
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()

    def _drag(self, event) -> None:
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def persist(self) -> None:
        self._save_after = None
        try:
            self._save(self.settings)
        except OSError as exc:
            print(f"AutoClicker could not save settings: {exc}", file=sys.stderr)
            self._set_status("Could not save settings on this PC.")

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._setup_cancelled = True
        self._accepting_clicks = False
        self._capture_token += 1
        try:
            self.capture.disarm()
        except Exception:
            pass
        try:
            self.hotkeys.cancel_capture()
        except Exception:
            pass
        try:
            self.hotkeys.clear_hotkey()
        except Exception:
            pass
        try:
            self.engine.stop()
        except Exception:
            pass
        self.persist()
        self._count_waiting = False
        self._wake_count()
        self._wake_wait()
        self._destroy_dialog("_count_dialog")
        self._destroy_dialog("_confirm_dialog")
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def _widget_bounds(widget: tk.Misc) -> tuple[int, int, int, int] | None:
    try:
        if not int(widget.winfo_viewable()):
            return None
        widget.update_idletasks()
        return (
            int(widget.winfo_rootx()),
            int(widget.winfo_rooty()),
            int(widget.winfo_width()),
            int(widget.winfo_height()),
        )
    except tk.TclError:
        return None

"""Responsive Tkinter dashboard for the traffic-monitoring pipeline."""

import datetime
import math
import tkinter as tk
from tkinter import ttk

import cv2
from PIL import Image, ImageOps, ImageTk


# Control-room palette
BG = "#080b12"
SURFACE = "#101622"
CARD = "#151d2b"
CARD_ALT = "#1a2434"
BORDER = "#273449"
TEXT = "#edf3fb"
MUTED = "#8997aa"
CYAN = "#21d4c2"
CYAN_DARK = "#123b3b"
GREEN = "#45dc8c"
AMBER = "#ffbd59"
RED = "#ff5d6c"
RED_DARK = "#3c2029"
FONT = "DejaVu Sans"


class Panel(tk.Frame):
    """Bordered dashboard card with a consistent title bar."""

    def __init__(self, master, title, accent=CYAN, **kwargs):
        super().__init__(
            master, bg=CARD, bd=0, highlightthickness=1,
            highlightbackground=BORDER, **kwargs
        )
        self.header = tk.Frame(self, bg=CARD, height=38)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_propagate(False)
        self.marker = tk.Frame(self.header, bg=accent, width=3)
        self.marker.pack(side="left", fill="y")
        self.title = tk.Label(
            self.header, text=title, bg=CARD, fg=TEXT,
            font=(FONT, 10, "bold"), anchor="w"
        )
        self.title.pack(side="left", padx=11)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)


class MetricCard(tk.Frame):
    def __init__(self, master, label, color):
        super().__init__(
            master, bg=CARD_ALT, bd=0, highlightthickness=1,
            highlightbackground=BORDER
        )
        self.value = tk.Label(
            self, text="0", bg=CARD_ALT, fg=color,
            font=(FONT, 22, "bold")
        )
        self.value.pack(pady=(9, 0))
        self.caption = tk.Label(
            self, text=label.upper(), bg=CARD_ALT, fg=MUTED,
            font=(FONT, 8, "bold")
        )
        self.caption.pack(pady=(0, 8))

    def set(self, value):
        self.value.configure(text=str(value))

    def set_compact(self, compact):
        self.value.configure(font=(FONT, 17 if compact else 22, "bold"))
        self.caption.configure(font=(FONT, 7 if compact else 8, "bold"))


class SpeedGauge(tk.Canvas):
    """Responsive speed gauge redrawn only when its value or size changes."""

    def __init__(self, master, **kwargs):
        super().__init__(master, bg=CARD, bd=0, highlightthickness=0, **kwargs)
        self.speed = 0
        self.limit = 50
        self.bind("<Configure>", self._redraw)

    def set_speed(self, speed, limit=50):
        speed = float(speed or 0)
        if speed != self.speed or limit != self.limit:
            self.speed, self.limit = speed, limit
            self._redraw()

    def _redraw(self, _event=None):
        width = max(self.winfo_width(), 120)
        height = max(self.winfo_height(), 95)
        size = min(width - 16, (height - 12) * 1.75)
        if size <= 20:
            return

        self.delete("all")
        cx, cy = width / 2, height * 0.72
        radius = min(size / 2, cy - 8)
        box = (cx - radius, cy - radius, cx + radius, cy + radius)
        self.create_arc(*box, start=0, extent=180, style="arc", width=11, outline=BORDER)
        self.create_arc(*box, start=0, extent=77, style="arc", width=11, outline=GREEN)
        self.create_arc(*box, start=77, extent=50, style="arc", width=11, outline=AMBER)
        self.create_arc(*box, start=127, extent=53, style="arc", width=11, outline=RED)

        ratio = min(max(self.speed / 140, 0), 1)
        angle = math.radians(180 - ratio * 180)
        needle_r = radius - 18
        nx = cx + needle_r * math.cos(angle)
        ny = cy - needle_r * math.sin(angle)
        color = RED if self.speed > self.limit else CYAN
        self.create_line(cx, cy, nx, ny, fill=color, width=4)
        self.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, fill=color, outline="")
        self.create_text(
            cx, cy + 23, text=f"{self.speed:g}", fill=TEXT,
            font=(FONT, 17, "bold")
        )
        self.create_text(cx, cy + 42, text="km/h", fill=MUTED, font=(FONT, 8))


class Dashboard:
    """Responsive UI. Public methods remain compatible with the old dashboard."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("TrafficOps | AI Monitoring")
        self.root.configure(bg=BG)

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(1600, max(900, screen_w - 70))
        height = min(950, max(620, screen_h - 100))
        self.root.geometry(f"{width}x{height}")
        # Never request a minimum larger than the user's usable display.
        self.root.minsize(min(900, screen_w), min(620, screen_h))

        self.running = True
        self.vehicle_rows = {}
        self.total_count = 0
        self.overspeed_ids = set()
        self._photo = None
        self._last_frame_rgb = None
        self._last_render_size = (0, 0)
        self._frame_dirty = False
        self._resize_job = None
        self._compact = None

        self._configure_style()
        self._build_header()
        self._build_content()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<q>", lambda _event: self.close())
        self.root.bind("<Q>", lambda _event: self.close())
        self.root.bind("<Configure>", self._schedule_responsive_update)
        self._tick_clock()
        self.root.after_idle(self._apply_responsive_layout)

    def _configure_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Traffic.Treeview", background=CARD, fieldbackground=CARD,
            foreground=TEXT, rowheight=29, borderwidth=0, font=(FONT, 9)
        )
        style.configure(
            "Traffic.Treeview.Heading", background=CARD_ALT, foreground=CYAN,
            relief="flat", padding=(6, 8), font=(FONT, 9, "bold")
        )
        style.map(
            "Traffic.Treeview", background=[("selected", CYAN_DARK)],
            foreground=[("selected", TEXT)]
        )
        style.configure(
            "Traffic.Vertical.TScrollbar", background=CARD_ALT,
            troughcolor=SURFACE, bordercolor=SURFACE, arrowcolor=MUTED
        )
        style.configure(
            "Traffic.Horizontal.TScrollbar", background=CARD_ALT,
            troughcolor=SURFACE, bordercolor=SURFACE, arrowcolor=MUTED
        )

    def _build_header(self):
        self.header = tk.Frame(self.root, bg=SURFACE, height=66)
        self.header.pack(side="top", fill="x")
        self.header.pack_propagate(False)

        brand = tk.Frame(self.header, bg=SURFACE)
        brand.pack(side="left", fill="y", padx=18)
        tk.Label(brand, text="●", bg=SURFACE, fg=CYAN, font=(FONT, 16)).pack(side="left")
        brand_text = tk.Frame(brand, bg=SURFACE)
        brand_text.pack(side="left", padx=9)
        self.title_label = tk.Label(
            brand_text, text="TRAFFICOPS", bg=SURFACE, fg=TEXT,
            font=(FONT, 16, "bold"), anchor="w"
        )
        self.title_label.pack(anchor="w")
        self.subtitle_label = tk.Label(
            brand_text, text="AI traffic intelligence and violation monitoring",
            bg=SURFACE, fg=MUTED, font=(FONT, 8), anchor="w"
        )
        self.subtitle_label.pack(anchor="w")

        status = tk.Frame(self.header, bg=SURFACE)
        status.pack(side="right", fill="y", padx=18)
        self.clock_label = tk.Label(
            status, text="", bg=SURFACE, fg=TEXT, font=(FONT, 10, "bold")
        )
        self.clock_label.pack(side="right")
        self.live_label = tk.Label(
            status, text="●  LIVE", bg=SURFACE, fg=GREEN, font=(FONT, 9, "bold")
        )
        self.live_label.pack(side="right", padx=(0, 18))

    def _build_content(self):
        self.content = tk.Frame(self.root, bg=BG)
        self.content.pack(fill="both", expand=True, padx=14, pady=14)
        self.content.grid_columnconfigure(0, weight=1, minsize=360)
        self.content.grid_columnconfigure(1, weight=0, minsize=310)
        self.content.grid_rowconfigure(0, weight=3, minsize=300)
        self.content.grid_rowconfigure(1, weight=2, minsize=180)

        self.video_panel = Panel(self.content, "CAMERA 01  /  LIVE FEED")
        self.video_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.video_viewport = tk.Frame(self.video_panel, bg="black")
        self.video_viewport.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.video_viewport.grid_propagate(False)
        self.video_label = tk.Label(
            self.video_viewport, text="Waiting for camera feed…", bg="black",
            fg=MUTED, font=(FONT, 10)
        )
        self.video_label.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.video_viewport.bind("<Configure>", self._video_viewport_changed)

        self.sidebar = tk.Frame(self.content, bg=BG, width=340)
        self.sidebar.grid(row=0, column=1, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure((0, 1), weight=1)
        self.sidebar.grid_rowconfigure(2, weight=1)

        self.total_card = MetricCard(self.sidebar, "Vehicles", CYAN)
        self.total_card.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=(0, 10))
        self.over_card = MetricCard(self.sidebar, "Overspeed", RED)
        self.over_card.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=(0, 10))

        self.gauge_panel = Panel(self.sidebar, "CURRENT SPEED")
        self.gauge_panel.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        self.gauge = SpeedGauge(self.gauge_panel, height=150)
        self.gauge.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 5))

        self.detail_panel = Panel(self.sidebar, "ACTIVE VEHICLE")
        self.detail_panel.grid(row=2, column=0, columnspan=2, sticky="nsew")
        detail_body = tk.Frame(self.detail_panel, bg=CARD)
        detail_body.grid(row=1, column=0, sticky="nsew", padx=13, pady=(0, 12))
        detail_body.grid_columnconfigure(0, weight=1)
        detail_body.grid_rowconfigure(0, weight=1)
        self.info_label = tk.Label(
            detail_body, text="No vehicle detected yet", bg=CARD, fg=MUTED,
            justify="left", anchor="nw", font=(FONT, 9)
        )
        self.info_label.grid(row=0, column=0, sticky="nsew")
        self.status_banner = tk.Label(
            detail_body, text="AWAITING DATA", bg=CARD_ALT, fg=MUTED,
            font=(FONT, 9, "bold"), pady=7
        )
        self.status_banner.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        self.table_panel = Panel(self.content, "DETECTION HISTORY")
        self.table_panel.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        table_wrap = tk.Frame(self.table_panel, bg=CARD)
        table_wrap.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        table_wrap.grid_columnconfigure(0, weight=1)
        table_wrap.grid_rowconfigure(0, weight=1)

        columns = ("ID", "TYPE", "PLATE", "SPEED", "LIMIT", "STATUS", "TIME")
        self.table = ttk.Treeview(
            table_wrap, columns=columns, show="headings", height=6,
            style="Traffic.Treeview"
        )
        for column in columns:
            self.table.heading(column, text=column)
            self.table.column(column, width=100, minwidth=70, anchor="center", stretch=True)
        self.table.column("ID", width=70, minwidth=55)
        self.table.column("TYPE", width=115)
        self.table.column("PLATE", width=145)
        self.table.column("STATUS", width=130)

        vertical = ttk.Scrollbar(
            table_wrap, orient="vertical", command=self.table.yview,
            style="Traffic.Vertical.TScrollbar"
        )
        horizontal = ttk.Scrollbar(
            table_wrap, orient="horizontal", command=self.table.xview,
            style="Traffic.Horizontal.TScrollbar"
        )
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.table.tag_configure("overspeed", foreground=RED)
        self.table.tag_configure("normal", foreground=GREEN)

    def _tick_clock(self):
        if not self.running:
            return
        now = datetime.datetime.now()
        self.clock_label.configure(text=now.strftime("%H:%M:%S   %d %b %Y"))
        self.root.after(1000, self._tick_clock)

    def _schedule_responsive_update(self, event):
        if event.widget is not self.root or not self.running:
            return
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(100, self._apply_responsive_layout)

    def _apply_responsive_layout(self):
        if not self.running:
            return
        self._resize_job = None
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        compact = width < 1450 or height < 850

        sidebar_width = 310 if compact else 350
        self.sidebar.configure(width=sidebar_width)
        self.content.grid_columnconfigure(1, minsize=sidebar_width)
        self.header.configure(height=58 if compact else 66)
        self.title_label.configure(font=(FONT, 13 if compact else 16, "bold"))
        self.subtitle_label.configure(font=(FONT, 7 if compact else 8))
        self.clock_label.configure(font=(FONT, 9 if compact else 10, "bold"))
        self.total_card.set_compact(compact)
        self.over_card.set_compact(compact)
        self.gauge.configure(height=105 if compact else 150)
        self.table.configure(height=4 if compact else 7)
        ttk.Style(self.root).configure(
            "Traffic.Treeview", rowheight=25 if compact else 30,
            font=(FONT, 8 if compact else 9)
        )
        self._compact = compact
        self._render_last_frame(force=True)

    def _video_viewport_changed(self, _event=None):
        if self._resize_job is None and self.running:
            self._resize_job = self.root.after(80, self._finish_video_resize)

    def _finish_video_resize(self):
        self._resize_job = None
        self._render_last_frame(force=True)

    def _render_last_frame(self, force=False):
        if self._last_frame_rgb is None or not self.running:
            return
        width = max(self.video_viewport.winfo_width(), 2)
        height = max(self.video_viewport.winfo_height(), 2)
        size = (width, height)
        if not force and not self._frame_dirty and size == self._last_render_size:
            return

        source = Image.fromarray(self._last_frame_rgb)
        fitted = ImageOps.contain(source, size, Image.Resampling.BILINEAR)
        canvas = Image.new("RGB", size, "black")
        canvas.paste(fitted, ((width - fitted.width) // 2, (height - fitted.height) // 2))
        self._photo = ImageTk.PhotoImage(canvas)
        self.video_label.configure(image=self._photo, text="")
        self._last_render_size = size
        self._frame_dirty = False

    # Public API retained for src/main.py.
    def update_video(self, frame):
        if not self.running or frame is None:
            return
        self._last_frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self._frame_dirty = True
        self._render_last_frame()

    def update_vehicle(self, vehicle_id, vehicle_type, plate, speed, limit, status):
        if not self.running:
            return
        is_over = status == "OVERSPEED"
        self.info_label.configure(
            text=(f"Vehicle ID     {vehicle_id}\n"
                  f"Type           {vehicle_type}\n"
                  f"Plate          {plate}\n"
                  f"Speed          {speed} km/h\n"
                  f"Limit          {limit} km/h"),
            fg=TEXT
        )
        if is_over:
            self.status_banner.configure(text="⚠  OVERSPEED VIOLATION", bg=RED_DARK, fg=RED)
            self.overspeed_ids.add(vehicle_id)
        else:
            self.status_banner.configure(text="✓  WITHIN SPEED LIMIT", bg=CYAN_DARK, fg=GREEN)

        if vehicle_id not in self.vehicle_rows:
            self.total_count += 1
            self.total_card.set(self.total_count)
        self.over_card.set(len(self.overspeed_ids))
        self.gauge.set_speed(speed, limit)

        values = (
            vehicle_id, vehicle_type, plate, f"{speed} km/h", f"{limit} km/h",
            status, datetime.datetime.now().strftime("%H:%M:%S")
        )
        tag = "overspeed" if is_over else "normal"
        if vehicle_id in self.vehicle_rows:
            self.table.item(self.vehicle_rows[vehicle_id], values=values, tags=(tag,))
        else:
            row = self.table.insert("", 0, values=values, tags=(tag,))
            self.vehicle_rows[vehicle_id] = row

    def update(self):
        if not self.running:
            return False
        try:
            self.root.update_idletasks()
            self.root.update()
            return True
        except tk.TclError:
            self.running = False
            return False

    def close(self):
        """Signal the processing loop to stop and close the window safely."""
        if not self.running:
            return
        self.running = False
        if self._resize_job:
            try:
                self.root.after_cancel(self._resize_job)
            except tk.TclError:
                pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass


if __name__ == "__main__":
    # Lightweight UI preview without loading YOLO.
    import random
    import numpy as np

    dashboard = Dashboard()
    frame_number = 0

    while dashboard.running:
        frame_number += 1
        frame = np.full((540, 960, 3), (25, 30, 40), dtype=np.uint8)
        cv2.rectangle(frame, (0, 210), (960, 540), (48, 53, 63), -1)
        x = (frame_number * 5) % 1080 - 100
        cv2.rectangle(frame, (x, 310), (x + 100, 355), (190, 190, 35), -1)
        dashboard.update_video(frame)
        if frame_number % 30 == 0:
            speed = random.randint(30, 105)
            dashboard.update_vehicle(
                frame_number // 30, "Car", "BA 12 PA 1234", speed, 50,
                "OVERSPEED" if speed > 50 else "NORMAL"
            )
        dashboard.update()

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw
import cv2
import math
import datetime


# ---------------------------------------------------------------------------
#  COLOR PALETTE  (dark, "control room" style)
# ---------------------------------------------------------------------------
BG_MAIN      = "#0b0e14"
BG_PANEL     = "#131722"
BG_CARD      = "#1b2030"
BG_CARD_HI   = "#212840"
BORDER       = "#2a3145"
ACCENT       = "#00e0c6"     # teal accent
ACCENT_DIM   = "#0d8f80"
DANGER       = "#ff4d5e"
DANGER_DIM   = "#402028"
SUCCESS      = "#3ddc84"
SUCCESS_DIM  = "#173023"
WARN         = "#ffb84d"
TEXT_MAIN    = "#e8ecf4"
TEXT_DIM     = "#8a92a8"
FONT_FAMILY  = "Segoe UI"


class RoundedCard(tk.Frame):
    """A simple 'card' frame with a border and padding, used to group content."""
    def __init__(self, master, title=None, accent=ACCENT, **kwargs):
        super().__init__(master, bg=BG_CARD, highlightbackground=BORDER,
                          highlightthickness=1, bd=0, **kwargs)
        if title:
            head = tk.Frame(self, bg=BG_CARD)
            head.pack(fill="x", padx=14, pady=(12, 0))
            tk.Frame(head, bg=accent, width=4, height=16).pack(side="left", padx=(0, 8))
            tk.Label(head, text=title, font=(FONT_FAMILY, 11, "bold"),
                      bg=BG_CARD, fg=TEXT_MAIN).pack(side="left")


class StatChip(tk.Frame):
    """Small KPI chip: big number + caption."""
    def __init__(self, master, caption, value="0", color=ACCENT, **kwargs):
        super().__init__(master, bg=BG_CARD_HI, highlightbackground=BORDER,
                          highlightthickness=1, **kwargs)
        self.value_lbl = tk.Label(self, text=value, font=(FONT_FAMILY, 22, "bold"),
                                    bg=BG_CARD_HI, fg=color)
        self.value_lbl.pack(pady=(12, 0))
        tk.Label(self, text=caption.upper(), font=(FONT_FAMILY, 9),
                 bg=BG_CARD_HI, fg=TEXT_DIM).pack(pady=(0, 10))

    def set(self, value):
        self.value_lbl.config(text=str(value))


class SpeedGauge(tk.Canvas):
    """A semi-circular speedometer drawn with canvas arcs."""
    def __init__(self, master, size=210, max_speed=140, **kwargs):
        super().__init__(master, width=size, height=size * 0.65 + 30,
                          bg=BG_CARD, highlightthickness=0, **kwargs)
        self.size = size
        self.max_speed = max_speed
        self._draw_static()
        self.needle = None
        self.text_id = None
        self.set_speed(0, limit=60)

    def _draw_static(self):
        s = self.size
        pad = 10
        self.create_arc(pad, pad, s - pad, s - pad, start=0, extent=180,
                         style="arc", width=16, outline="#2a3145")
        # colored zones
        self.create_arc(pad, pad, s - pad, s - pad, start=0, extent=90,
                         style="arc", width=16, outline=SUCCESS)
        self.create_arc(pad, pad, s - pad, s - pad, start=90, extent=55,
                         style="arc", width=16, outline=WARN)
        self.create_arc(pad, pad, s - pad, s - pad, start=145, extent=35,
                         style="arc", width=16, outline=DANGER)

    def set_speed(self, speed, limit=60):
        s = self.size
        cx, cy = s / 2, s / 2
        ratio = max(0, min(1, speed / self.max_speed))
        angle = 180 - ratio * 180  # 180deg (left) -> 0deg (right)
        rad = math.radians(angle)
        r = s / 2 - 30
        x = cx + r * math.cos(rad)
        y = cy - r * math.sin(rad)

        if self.needle:
            self.delete(self.needle)
            self.delete(self.hub)
            self.delete(self.text_id)
            self.delete(self.cap_id)

        color = DANGER if speed > limit else ACCENT
        self.needle = self.create_line(cx, cy, x, y, width=4, fill=color, capstyle="round")
        self.hub = self.create_oval(cx - 7, cy - 7, cx + 7, cy + 7, fill=color, outline="")
        self.text_id = self.create_text(cx, cy + 30, text=f"{speed}", fill=TEXT_MAIN,
                                          font=(FONT_FAMILY, 20, "bold"))
        self.cap_id = self.create_text(cx, cy + 52, text="km/h", fill=TEXT_DIM,
                                         font=(FONT_FAMILY, 9))


class Dashboard:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AI Traffic Monitoring System")
        self.root.geometry("1680x950")
        self.root.configure(bg=BG_MAIN)
        self.root.minsize(1280, 760)

        self.vehicle_rows = {}
        self.total_count = 0
        self.overspeed_count = 0
        self.speed_sum = 0
        self.speed_n = 0

        self._build_style()
        self._build_header()
        self._build_body()
        self._tick_clock()

    # ------------------------------------------------------------------
    # STYLE
    # ------------------------------------------------------------------
    def _build_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Treeview",
                        background=BG_CARD,
                        fieldbackground=BG_CARD,
                        foreground=TEXT_MAIN,
                        rowheight=32,
                        borderwidth=0,
                        font=(FONT_FAMILY, 10))
        style.configure("Treeview.Heading",
                        background=BG_CARD_HI,
                        foreground=ACCENT,
                        relief="flat",
                        font=(FONT_FAMILY, 10, "bold"))
        style.map("Treeview.Heading", background=[("active", BG_CARD_HI)])
        style.map("Treeview", background=[("selected", ACCENT_DIM)],
                  foreground=[("selected", TEXT_MAIN)])
        style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    # ------------------------------------------------------------------
    # HEADER
    # ------------------------------------------------------------------
    def _build_header(self):
        header = tk.Frame(self.root, bg=BG_PANEL, height=70)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        left = tk.Frame(header, bg=BG_PANEL)
        left.pack(side="left", padx=20)

        tk.Label(left, text="\u25CF", font=(FONT_FAMILY, 16), bg=BG_PANEL,
                 fg=ACCENT).pack(side="left", padx=(0, 8))

        title_box = tk.Frame(left, bg=BG_PANEL)
        title_box.pack(side="left")
        tk.Label(title_box, text="AI TRAFFIC MONITORING DASHBOARD",
                 font=(FONT_FAMILY, 17, "bold"), bg=BG_PANEL, fg=TEXT_MAIN
                 ).pack(anchor="w")
        tk.Label(title_box, text="Real-time vehicle detection · speed estimation · violation tracking",
                 font=(FONT_FAMILY, 9), bg=BG_PANEL, fg=TEXT_DIM).pack(anchor="w")

        right = tk.Frame(header, bg=BG_PANEL)
        right.pack(side="right", padx=20)

        self.status_dot = tk.Label(right, text="\u25CF", font=(FONT_FAMILY, 12),
                                    bg=BG_PANEL, fg=SUCCESS)
        self.status_dot.pack(side="left", padx=(0, 6))
        tk.Label(right, text="LIVE", font=(FONT_FAMILY, 10, "bold"),
                 bg=BG_PANEL, fg=SUCCESS).pack(side="left", padx=(0, 20))

        self.clock_lbl = tk.Label(right, text="", font=(FONT_FAMILY, 13, "bold"),
                                    bg=BG_PANEL, fg=TEXT_MAIN)
        self.clock_lbl.pack(side="left")

    def _tick_clock(self):
        now = datetime.datetime.now()
        self.clock_lbl.config(text=now.strftime("%H:%M:%S   %d %b %Y"))
        self.root.after(1000, self._tick_clock)

    # ------------------------------------------------------------------
    # BODY
    # ------------------------------------------------------------------
    def _build_body(self):
        body = tk.Frame(self.root, bg=BG_MAIN)
        body.pack(fill="both", expand=True, padx=16, pady=16)

        top = tk.Frame(body, bg=BG_MAIN)
        top.pack(fill="both", expand=True)

        # ---------------- VIDEO CARD (left) ----------------
        video_card = RoundedCard(top, title="CAMERA FEED — CAM 01")
        video_card.pack(side="left", fill="both", expand=True, padx=(0, 12))

        video_wrap = tk.Frame(video_card, bg="black", highlightbackground=BORDER,
                               highlightthickness=1)
        video_wrap.pack(padx=14, pady=14, fill="both", expand=True)

        self.video_label = tk.Label(video_wrap, bg="black",
                                     text="Waiting for camera feed…",
                                     fg=TEXT_DIM, font=(FONT_FAMILY, 12))
        self.video_label.pack(fill="both", expand=True)

        # ---------------- SIDE PANEL (right) ----------------
        side = tk.Frame(top, bg=BG_MAIN, width=380)
        side.pack(side="right", fill="y")
        side.pack_propagate(False)

        # KPI chips row
        kpi_row = tk.Frame(side, bg=BG_MAIN)
        kpi_row.pack(fill="x", pady=(0, 12))
        self.chip_total = StatChip(kpi_row, "Vehicles", "0", ACCENT)
        self.chip_total.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.chip_over = StatChip(kpi_row, "Overspeed", "0", DANGER)
        self.chip_over.pack(side="left", fill="x", expand=True, padx=(6, 0))

        # Gauge card
        gauge_card = RoundedCard(side, title="CURRENT SPEED")
        gauge_card.pack(fill="x", pady=(0, 12))
        self.gauge = SpeedGauge(gauge_card)
        self.gauge.pack(pady=(6, 10))

        # Vehicle detail card
        detail_card = RoundedCard(side, title="VEHICLE DETAIL")
        detail_card.pack(fill="both", expand=True)

        self.info_label = tk.Label(
            detail_card,
            text="No vehicle detected yet.",
            font=(FONT_FAMILY, 11),
            bg=BG_CARD,
            fg=TEXT_DIM,
            justify="left",
            anchor="nw"
        )
        self.info_label.pack(fill="both", expand=True, padx=16, pady=12)

        self.status_banner = tk.Label(
            detail_card, text="", font=(FONT_FAMILY, 11, "bold"),
            bg=BG_CARD, fg=TEXT_MAIN, pady=8
        )
        self.status_banner.pack(fill="x", padx=14, pady=(0, 14))

        # ---------------- TABLE CARD (bottom) ----------------
        table_card = RoundedCard(body, title="DETECTION LOG")
        table_card.pack(fill="both", expand=False, pady=(16, 0))

        columns = ("ID", "TYPE", "PLATE", "SPEED", "LIMIT", "STATUS", "TIME")
        self.table = ttk.Treeview(table_card, columns=columns, show="headings", height=10)

        widths = {"ID": 80, "TYPE": 140, "PLATE": 160, "SPEED": 120,
                  "LIMIT": 120, "STATUS": 140, "TIME": 140}
        for col in columns:
            self.table.heading(col, text=col)
            self.table.column(col, width=widths.get(col, 120), anchor="center")

        vsb = ttk.Scrollbar(table_card, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=vsb.set)

        self.table.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=14)
        vsb.pack(side="right", fill="y", pady=14, padx=(0, 14))

        self.table.tag_configure("OVER", foreground=DANGER)
        self.table.tag_configure("NORMAL", foreground=SUCCESS)
        self.table.tag_configure("oddrow", background=BG_CARD)
        self.table.tag_configure("evenrow", background=BG_CARD_HI)

    # ------------------------------------------------------------------
    # PUBLIC API (same signatures as the original Dashboard)
    # ------------------------------------------------------------------
    def update_video(self, frame):
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame)

        w = self.video_label.winfo_width() or 900
        h = self.video_label.winfo_height() or 550
        img = img.resize((max(w, 100), max(h, 100)))
        img = ImageTk.PhotoImage(img)

        self.video_label.config(image=img, text="")
        self.video_label.image = img

    def update_vehicle(self, vehicle_id, vehicle_type, plate, speed, limit, status):
        is_over = status == "OVERSPEED"

        # ---- side detail panel ----
        self.info_label.config(
            text=(
                f"ID           :  {vehicle_id}\n"
                f"Type         :  {vehicle_type}\n"
                f"Plate        :  {plate}\n"
                f"Speed        :  {speed} km/hr\n"
                f"Speed Limit  :  {limit} km/hr\n"
            ),
            fg=TEXT_MAIN
        )

        if is_over:
            self.status_banner.config(text="⚠  OVERSPEED VIOLATION", bg=DANGER_DIM, fg=DANGER)
        else:
            self.status_banner.config(text="✓  WITHIN SPEED LIMIT", bg=SUCCESS_DIM, fg=SUCCESS)

        # ---- gauge ----
        self.gauge.set_speed(speed, limit)

        # ---- KPI chips ----
        if vehicle_id not in self.vehicle_rows:
            self.total_count += 1
            self.chip_total.set(self.total_count)
        if is_over:
            self.overspeed_count += 1
            self.chip_over.set(self.overspeed_count)

        # ---- table ----
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        values = (vehicle_id, vehicle_type, plate, f"{speed} km/hr",
                  f"{limit} km/hr", status, time_str)

        tag = "OVER" if is_over else "NORMAL"
        stripe = "evenrow" if len(self.vehicle_rows) % 2 == 0 else "oddrow"

        if vehicle_id not in self.vehicle_rows:
            row = self.table.insert("", 0, values=values, tags=(tag, stripe))
            self.vehicle_rows[vehicle_id] = row
        else:
            row = self.vehicle_rows[vehicle_id]
            self.table.item(row, values=values, tags=(tag, stripe))

    def update(self):
        self.root.update()


# ---------------------------------------------------------------------------
#  DEMO / STANDALONE RUNNER
#  (Lets you preview the UI immediately without any real detection pipeline.
#   Feeds a synthetic "road" frame + fake vehicle data. Safe to delete this
#   block once you wire in your real detection + speed-estimation code.)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import random
    import numpy as np

    dash = Dashboard()

    demo_types = ["Car", "Bus", "Truck", "Motorbike"]
    demo_state = {"frame_i": 0, "veh_i": 0}

    def synthetic_frame(i):
        img = Image.new("RGB", (960, 540), (30, 34, 44))
        draw = ImageDraw.Draw(img)
        # road
        draw.rectangle([0, 200, 960, 540], fill=(45, 48, 58))
        for x in range(-40, 960, 80):
            offset = (i * 6) % 80
            draw.rectangle([x + offset, 360, x + offset + 40, 372], fill=(200, 200, 60))
        # a moving "car"
        cx = (i * 5) % 1100 - 100
        draw.rectangle([cx, 300, cx + 90, 340], fill=(0, 200, 180))
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    def demo_loop():
        demo_state["frame_i"] += 1
        dash.update_video(synthetic_frame(demo_state["frame_i"]))

        if demo_state["frame_i"] % 25 == 0:
            demo_state["veh_i"] += 1
            vid = demo_state["veh_i"]
            speed = random.randint(35, 110)
            limit = 60
            status = "OVERSPEED" if speed > limit else "NORMAL"
            dash.update_vehicle(
                vehicle_id=f"V{vid:03d}",
                vehicle_type=random.choice(demo_types),
                plate=f"BA {random.randint(10,99)} PA {random.randint(1000,9999)}",
                speed=speed,
                limit=limit,
                status=status
            )

        dash.root.after(40, demo_loop)

    demo_loop()
    dash.root.mainloop()
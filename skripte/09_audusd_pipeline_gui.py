#!/usr/bin/env python3
"""
Phase 5: Graphical Pipeline Interface for AUDUSD M5 (09_audusd_pipeline_gui.py)
--------------------------------------------------------------------------------
A modern, dark-themed Tkinter desktop application to visualize
the ML training pipeline for the AUDUSD M5 robot, displaying model accuracies,
classification reports, 23 feature sets, and interactive confusion matrices.
Allows triggering model training asynchronously with a live console log.
"""

import os
import sys
import json
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# Configuration & Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METRICS_PATH = os.path.join(BASE_DIR, "data", "model_metrics.json")
TRAIN_SCRIPT_PATH = os.path.join(BASE_DIR, "skripte", "02_train_gatekeeper.py")

# Modern UI Color Palette
BG_DARK = "#121212"      # Main window background
BG_SIDEBAR = "#181818"   # Sidebar background
BG_CARD = "#1f1f1f"      # Card background
FG_LIGHT = "#ffffff"     # Primary text
FG_MUTED = "#999999"     # Muted text
COLOR_ACCENT = "#d4af37" # Gold/Yellow accent
COLOR_GREEN = "#2ecc71"  # Success/Train indicators
COLOR_RED = "#e74c3c"    # Stop/Alerts
COLOR_BLUE = "#3498db"   # Info/Active states
BORDER_COLOR = "#2a2a2a" # Grid/Card borders


class ModernButton(tk.Button):
    """A polished, flat Tkinter button with hover effects."""
    def __init__(self, master, hover_bg=COLOR_ACCENT, hover_fg="#121212", **kwargs):
        self.normal_bg = kwargs.get("bg", "#2a2a2a")
        self.normal_fg = kwargs.get("fg", FG_LIGHT)
        self.hover_bg = hover_bg
        self.hover_fg = hover_fg
        
        kwargs.update({
            "relief": "flat",
            "activebackground": hover_bg,
            "activeforeground": hover_fg,
            "cursor": "hand2"
        })
        super().__init__(master, **kwargs)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def on_enter(self, e):
        self.config(bg=self.hover_bg, fg=self.hover_fg)

    def on_leave(self, e):
        self.config(bg=self.normal_bg, fg=self.normal_fg)


class TrafficLightCanvas(tk.Canvas):
    """A vertical traffic light visualization using 4 circles (Red, Orange, Yellow, Green)."""
    def __init__(self, master, **kwargs):
        kwargs.setdefault("width", 50)
        kwargs.setdefault("height", 150)
        kwargs.setdefault("bg", BG_CARD)
        kwargs.setdefault("highlightthickness", 0)
        super().__init__(master, **kwargs)
        self.draw_housing()
        
    def draw_housing(self):
        # Draw the black traffic light housing
        self.create_round_rect(5, 5, 45, 145, radius=10, fill="#181818", outline=BORDER_COLOR, width=2)
        # Draw four empty sockets: Red, Orange, Yellow, Green
        self.red_circle = self.create_oval(14, 11, 36, 33, fill="#251010", outline="#1a0c0c")
        self.orange_circle = self.create_oval(14, 43, 36, 65, fill="#251a10", outline="#1a110c")
        self.yellow_circle = self.create_oval(14, 75, 36, 97, fill="#252510", outline="#1a1a0c")
        self.green_circle = self.create_oval(14, 107, 36, 129, fill="#102510", outline="#0c1a0c")

    def create_round_rect(self, x1, y1, x2, y2, radius=10, **kwargs):
        points = [x1+radius, y1,
                  x1+radius, y1,
                  x2-radius, y1,
                  x2-radius, y1,
                  x2, y1,
                  x2, y1+radius,
                  x2, y1+radius,
                  x2, y2-radius,
                  x2, y2-radius,
                  x2, y2,
                  x2-radius, y2,
                  x2-radius, y2,
                  x1+radius, y2,
                  x1+radius, y2,
                  x1, y2,
                  x1, y2-radius,
                  x1, y2-radius,
                  x1, y1+radius,
                  x1, y1+radius,
                  x1, y1]
        return self.create_polygon(points, **kwargs, smooth=True)

    def set_state(self, color):
        # Reset all lights to dim state
        self.itemconfigure(self.red_circle, fill="#251010", outline="#1a0c0c")
        self.itemconfigure(self.orange_circle, fill="#251a10", outline="#1a110c")
        self.itemconfigure(self.yellow_circle, fill="#252510", outline="#1a1a0c")
        self.itemconfigure(self.green_circle, fill="#102510", outline="#0c1a0c")
        
        if color == "red":
            self.itemconfigure(self.red_circle, fill="#ff4d4d", outline="#ff9999")
        elif color == "orange":
            self.itemconfigure(self.orange_circle, fill="#ff851b", outline="#ffb366")
        elif color == "yellow":
            self.itemconfigure(self.yellow_circle, fill="#ffdc00", outline="#fff07f")
        elif color == "green":
            self.itemconfigure(self.green_circle, fill="#2ecc71", outline="#a3e4d7")


class MLPipelineGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AUDUSD M5 Trading Bot - ML Pipeline Dashboard")
        self.root.geometry("1100x750")
        self.root.configure(bg=BG_DARK)
        self.root.resizable(True, True)
        
        # Grid layout weights
        self.root.grid_columnconfigure(0, weight=0, minsize=260)  # Sidebar
        self.root.grid_columnconfigure(1, weight=1)              # Main Content
        self.root.grid_rowconfigure(0, weight=1)
        
        self.is_training = False
        self.metrics = None
        
        self.setup_styles()
        self.build_sidebar()
        self.build_main_content()
        self.load_metrics_data()
        
    def setup_styles(self):
        """Configure styles for ttk components to blend with the dark theme."""
        style = ttk.Style()
        style.theme_use("clam")
        
        # Scrollbar design
        style.configure("Vertical.TScrollbar", 
                        gripcount=0,
                        background=BG_SIDEBAR, 
                        troughcolor=BG_DARK, 
                        bordercolor=BG_DARK, 
                        arrowcolor=FG_MUTED)
        style.map("Vertical.TScrollbar",
                  background=[('pressed', COLOR_ACCENT), ('active', "#333333")])

    def build_sidebar(self):
        """Builds the left navigation and parameter bar."""
        sidebar = tk.Frame(self.root, bg=BG_SIDEBAR, width=260, bd=0, highlightthickness=1, highlightbackground=BORDER_COLOR)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        sidebar.grid_propagate(False)
        
        # Header / Logo
        lbl_logo = tk.Label(sidebar, text="KIAUDUSDRobot 📈", bg=BG_SIDEBAR, fg=COLOR_ACCENT, font=("Segoe UI", 16, "bold"))
        lbl_logo.pack(anchor="w", padx=20, pady=(25, 5))
        
        lbl_sub = tk.Label(sidebar, text="ONNX ML pipeline execution", bg=BG_SIDEBAR, fg=FG_MUTED, font=("Segoe UI", 9, "italic"))
        lbl_sub.pack(anchor="w", padx=20, pady=(0, 20))
        
        # Divider line
        div = tk.Frame(sidebar, bg=BORDER_COLOR, height=1)
        div.pack(fill="x", padx=20, pady=10)
        
        # Status Card
        self.card_status = tk.Frame(sidebar, bg=BG_CARD, bd=0, highlightthickness=1, highlightbackground=BORDER_COLOR)
        self.card_status.pack(fill="x", padx=20, pady=10)
        
        lbl_status_title = tk.Label(self.card_status, text="PIPELINE STATUS:", bg=BG_CARD, fg=FG_MUTED, font=("Segoe UI", 8, "bold"))
        lbl_status_title.pack(anchor="w", padx=15, pady=(10, 2))
        
        self.lbl_status_val = tk.Label(self.card_status, text="Idle (Bereit)", bg=BG_CARD, fg=COLOR_GREEN, font=("Segoe UI", 12, "bold"))
        self.lbl_status_val.pack(anchor="w", padx=15, pady=(0, 10))
        
        # Lern-Qualität Card (Ampel)
        self.card_quality = tk.Frame(sidebar, bg=BG_CARD, bd=0, highlightthickness=1, highlightbackground=BORDER_COLOR)
        self.card_quality.pack(fill="x", padx=20, pady=5)
        
        lbl_quality_title = tk.Label(self.card_quality, text="PRÄZISION (SAFE-TRADES):", bg=BG_CARD, fg=FG_MUTED, font=("Segoe UI", 8, "bold"))
        lbl_quality_title.pack(anchor="w", padx=15, pady=(10, 2))
        
        q_frame = tk.Frame(self.card_quality, bg=BG_CARD)
        q_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        self.traffic_light = TrafficLightCanvas(q_frame, bg=BG_CARD)
        self.traffic_light.pack(side="left")
        
        q_text_frame = tk.Frame(q_frame, bg=BG_CARD)
        q_text_frame.pack(side="left", fill="both", expand=True, padx=(10, 0))
        
        lbl_p_title = tk.Label(q_text_frame, text="Test-Präzision:", bg=BG_CARD, fg=FG_MUTED, font=("Segoe UI", 8))
        lbl_p_title.pack(anchor="w")
        
        self.lbl_qual_percent = tk.Label(q_text_frame, text="--%", bg=BG_CARD, fg=FG_LIGHT, font=("Segoe UI", 12, "bold"))
        self.lbl_qual_percent.pack(anchor="w", pady=(0, 5))
        
        lbl_s_title = tk.Label(q_text_frame, text="Bewertung:", bg=BG_CARD, fg=FG_MUTED, font=("Segoe UI", 8))
        lbl_s_title.pack(anchor="w")
        
        self.lbl_qual_status = tk.Label(q_text_frame, text="Keine Daten", bg=BG_CARD, fg=FG_MUTED, font=("Segoe UI", 9, "bold"))
        self.lbl_qual_status.pack(anchor="w")
        
        # Parameters Summary list
        self.param_frame = tk.Frame(sidebar, bg=BG_SIDEBAR)
        self.param_frame.pack(fill="x", padx=20, pady=15)
        
        # Spacer
        spacer = tk.Label(sidebar, bg=BG_SIDEBAR)
        spacer.pack(fill="both", expand=True)
        
        # Action Button
        self.btn_train = ModernButton(
            sidebar, 
            text="🚀 Modell neu anlernen", 
            bg=COLOR_ACCENT, 
            fg="#121212", 
            hover_bg="#f39c12",
            hover_fg="#ffffff",
            font=("Segoe UI", 11, "bold"),
            height=2,
            command=self.start_training_thread
        )
        self.btn_train.pack(fill="x", padx=20, pady=(0, 25))

    def add_param_val(self, label_text, val_text):
        """Adds a neat label-value pair to the sidebar."""
        f = tk.Frame(self.param_frame, bg=BG_SIDEBAR)
        f.pack(fill="x", pady=4)
        lbl = tk.Label(f, text=label_text, bg=BG_SIDEBAR, fg=FG_MUTED, font=("Segoe UI", 9))
        lbl.pack(side="left")
        val = tk.Label(f, text=val_text, bg=BG_SIDEBAR, fg=FG_LIGHT, font=("Segoe UI", 9, "bold"))
        val.pack(side="right")

    def add_detail_box(self, parent, col, label, value):
        """Helper to render a key-value detail box inside the forest details area."""
        box = tk.Frame(parent, bg=BG_CARD, padx=10, pady=5)
        box.grid(row=0, column=col, sticky="nsew", padx=3)
        
        lbl_l = tk.Label(box, text=label.upper(), bg=BG_CARD, fg=FG_MUTED, font=("Segoe UI", 10, "bold"))
        lbl_l.pack(anchor="w")
        
        lbl_v = tk.Label(box, text=value, bg=BG_CARD, fg=COLOR_ACCENT, font=("Segoe UI", 14, "bold"))
        lbl_v.pack(anchor="w", pady=(2, 0))

    def build_main_content(self):
        """Builds the tabbed panel in the right area."""
        self.main_container = tk.Frame(self.root, bg=BG_DARK, padx=25, pady=25)
        self.main_container.grid(row=0, column=1, sticky="nsew")
        
        self.main_container.grid_rowconfigure(0, weight=0) # Tabs Header
        self.main_container.grid_rowconfigure(1, weight=1) # Tab Content Frame
        self.main_container.grid_columnconfigure(0, weight=1)
        
        # Tabs Button Bar (Custom Modern Styling)
        self.tabs_bar = tk.Frame(self.main_container, bg=BG_DARK)
        self.tabs_bar.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        
        self.tab_buttons = {}
        self.tab_frames = {}
        
        tabs_config = [
            ("metrics", "📊 Modell-Metriken"),
            ("features", "⚙️ Features (23)"),
            ("confusion", "🏁 Konfusionsmatrix"),
            ("console", "🖥️ Live-Konsole Log")
        ]
        
        for index, (tab_id, tab_title) in enumerate(tabs_config):
            # Button styling
            btn = tk.Button(
                self.tabs_bar, 
                text=tab_title, 
                bg=BG_CARD, 
                fg=FG_MUTED, 
                activebackground=BG_DARK, 
                activeforeground=FG_LIGHT,
                font=("Segoe UI", 10, "bold"),
                relief="flat", 
                bd=0, 
                padx=15, 
                pady=8,
                cursor="hand2",
                command=lambda tid=tab_id: self.switch_tab(tid)
            )
            btn.pack(side="left", padx=(0, 8))
            self.tab_buttons[tab_id] = btn
            
            # Content Frame for each tab
            frame = tk.Frame(self.main_container, bg=BG_DARK)
            self.tab_frames[tab_id] = frame
            
        # Default Active Tab
        self.active_tab = "metrics"
        self.switch_tab("metrics")

    def switch_tab(self, target_tab):
        """Hides current tab frame and packs the selected one with active styles."""
        if hasattr(self, 'active_tab') and self.active_tab:
            self.tab_frames[self.active_tab].grid_forget()
            self.tab_buttons[self.active_tab].config(bg=BG_CARD, fg=FG_MUTED, highlightthickness=0)
            
        self.active_tab = target_tab
        self.tab_frames[target_tab].grid(row=1, column=0, sticky="nsew")
        self.tab_buttons[target_tab].config(bg=COLOR_BLUE, fg="#ffffff")
        
        self.render_tab_content(target_tab)

    def load_metrics_data(self):
        """Loads model_metrics.json file and updates layout values."""
        if os.path.exists(METRICS_PATH):
            try:
                with open(METRICS_PATH, "r", encoding="utf-8") as f:
                    self.metrics = json.load(f)
            except Exception as e:
                self.metrics = None
                print(f"Error loading metrics JSON: {e}")
        else:
            self.metrics = None
            
        self.refresh_parameters()

    def refresh_parameters(self):
        """Refreshes the sidebar parameter values dynamically based on loaded metrics."""
        for widget in self.param_frame.winfo_children():
            widget.destroy()
            
        self.add_param_val("Instrument:", "AUDUSD")
        self.add_param_val("Timeframe:", "M5")
        
        if self.metrics and "algorithm" in self.metrics:
            algo = self.metrics["algorithm"]
            params = algo.get("parameters", {})
            self.add_param_val("Lernalgo:", algo.get("name", "Random Forest"))
            self.add_param_val("Schätzer (Bäume):", str(params.get("n_estimators", 100)))
            self.add_param_val("Max. Tiefe:", str(params.get("max_depth", 6)))
        else:
            self.add_param_val("Lernalgo:", "Random Forest (ONNX)")
            
        feat_count = self.metrics.get("feature_count", 23) if self.metrics else 23
        self.add_param_val("Features:", f"{feat_count} Features active")
        self.add_param_val("Targets:", "2 Classes (Dangerous, Safe)")
        
        if self.metrics and "dataset_size" in self.metrics:
            ds = self.metrics["dataset_size"]
            self.add_param_val("Gesamt-Signale:", f"{ds.get('total', 0):,}".replace(",", "."))
            self.add_param_val("Training-Set:", f"{ds.get('train', 0):,}".replace(",", "."))
            self.add_param_val("Test-Set:", f"{ds.get('test', 0):,}".replace(",", "."))
            
        # Update traffic light & quality status using Test Precision of Safe Trades (Class 1)
        test_prec = 0.0
        if self.metrics and "classification_reports" in self.metrics:
            test_prec = self.metrics["classification_reports"].get("test", {}).get("1", {}).get("precision", 0.0)
            
        if test_prec > 0.0:
            percent_str = f"{test_prec * 100:.2f}%"
            self.lbl_qual_percent.config(text=percent_str)
            
            # Baseline precision is 83.86%. Anything above is positive learning.
            if test_prec >= 0.855:
                self.traffic_light.set_state("green")
                self.lbl_qual_status.config(text="Grün\n(Ausgezeichnet)", fg="#2ecc71")
            elif test_prec >= 0.840:
                self.traffic_light.set_state("yellow")
                self.lbl_qual_status.config(text="Gelb\n(Gut)", fg="#ffdc00")
            elif test_prec >= 0.820:
                self.traffic_light.set_state("orange")
                self.lbl_qual_status.config(text="Orange\n(Schwach)", fg="#ff851b")
            else:
                self.traffic_light.set_state("red")
                self.lbl_qual_status.config(text="Rot\n(Ungenügend)", fg="#ff4d4d")
        else:
            self.lbl_qual_percent.config(text="--%")
            self.lbl_qual_status.config(text="Keine Daten", fg=FG_MUTED)
            self.traffic_light.set_state("gray")
            
        if "features" in self.tab_buttons:
            self.tab_buttons["features"].config(text=f"⚙️ Features ({feat_count})")

    def render_tab_content(self, tab_id):
        """Renders specific widgets in selected tab frames."""
        frame = self.tab_frames[tab_id]
        
        for widget in frame.winfo_children():
            widget.destroy()
            
        if self.metrics is None and tab_id != "console":
            lbl_no_data = tk.Label(
                frame, 
                text="Keine Modelldaten gefunden.\nBitte klicke auf 'Modell neu anlernen', um das Training zu starten.", 
                bg=BG_DARK, 
                fg=FG_MUTED, 
                font=("Segoe UI", 12, "bold")
            )
            lbl_no_data.pack(expand=True)
            return

        if tab_id == "metrics":
            self.render_metrics_tab(frame)
        elif tab_id == "features":
            self.render_features_tab(frame)
        elif tab_id == "confusion":
            self.render_confusion_tab(frame)
        elif tab_id == "console":
            self.render_console_tab(frame)

    def render_metrics_tab(self, frame):
        """Renders the general dashboard view with split sets performance cards."""
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_columnconfigure(2, weight=1)
        
        # Top title frame with title and info button
        title_frame = tk.Frame(frame, bg=BG_DARK)
        title_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 15))
        
        lbl_title = tk.Label(title_frame, text="Modell-Genauigkeit (Accuracy) & Präzision", bg=BG_DARK, fg=FG_LIGHT, font=("Segoe UI", 14, "bold"))
        lbl_title.pack(side="left")
        
        btn_data_info = tk.Button(
            title_frame, 
            text=" ℹ Daten-Details & Beispiele ", 
            bg=BG_CARD, 
            fg=COLOR_ACCENT, 
            activebackground=BG_DARK, 
            activeforeground=FG_LIGHT,
            font=("Segoe UI", 10, "bold"),
            relief="flat", 
            bd=0, 
            cursor="hand2",
            padx=10,
            pady=4,
            command=self.show_dataset_info
        )
        btn_data_info.pack(side="left", padx=(15, 0))
        
        # Accuracy cards
        accs = self.metrics.get("accuracies", {})
        report_train = self.metrics.get("classification_reports", {}).get("train", {})
        report_test = self.metrics.get("classification_reports", {}).get("test", {})
        safe_precision = report_test.get("1", {}).get("precision", 0.0)
        
        # Load dataset sizes and class counts
        dataset_size = self.metrics.get("dataset_size", {})
        train_samples = dataset_size.get("train", 0)
        test_samples = dataset_size.get("test", 0)
        
        train_0 = int(report_train.get("0", {}).get("support", 0))
        train_1 = int(report_train.get("1", {}).get("support", 0))
        test_0 = int(report_test.get("0", {}).get("support", 0))
        test_1 = int(report_test.get("1", {}).get("support", 0))
        
        splits = [
            ("Trainings-Daten In-Sample (82%)", accs.get("train", 0.0), COLOR_GREEN),
            ("Test-Daten Out-of-Sample (18%)", accs.get("test", 0.0), COLOR_ACCENT),
            ("Präzision Safe-Trades (Klasse 1)", safe_precision, COLOR_BLUE)
        ]
        
        for idx, (title, score, color) in enumerate(splits):
            card = tk.Frame(frame, bg=BG_CARD, bd=0, highlightthickness=1, highlightbackground=BORDER_COLOR, padx=15, pady=20)
            card.grid(row=1, column=idx, sticky="nsew", padx=5)
            
            lbl_t = tk.Label(card, text=title.upper(), bg=BG_CARD, fg=FG_MUTED, font=("Segoe UI", 8, "bold"))
            lbl_t.pack(anchor="w", pady=(0, 5))
            
            lbl_val = tk.Label(card, text=f"{score*100:.2f}%", bg=BG_CARD, fg=color, font=("Segoe UI", 24, "bold"))
            lbl_val.pack(anchor="w", pady=(0, 5))
            
            # Progress bar simulation
            p_bar_bg = tk.Frame(card, bg=BORDER_COLOR, height=6)
            p_bar_bg.pack(fill="x", pady=(10, 0))
            p_bar_fg = tk.Frame(p_bar_bg, bg=color, height=6, width=int(score * 180))
            p_bar_fg.pack(side="left")
            
            # Details label showing exact samples count
            details_text = ""
            if idx == 0:
                details_text = f"Beispiele: {train_samples:,} (Sicher: {train_1:,} | Gefährlich: {train_0:,})".replace(",", ".")
            elif idx == 1:
                details_text = f"Beispiele: {test_samples:,} (Sicher: {test_1:,} | Gefährlich: {test_0:,})".replace(",", ".")
            elif idx == 2:
                if test_samples > 0:
                    details_text = f"Blockiert: {test_0:,} von {test_samples:,} Signalen ({test_0/test_samples*100:.1f}%)".replace(",", ".")
                else:
                    details_text = "Keine Testdaten vorhanden"
            
            lbl_details = tk.Label(card, text=details_text, bg=BG_CARD, fg=FG_MUTED, font=("Segoe UI", 9, "italic"))
            lbl_details.pack(anchor="w", pady=(8, 0))
            
        # Detailed Reports Table below cards
        feat_count = self.metrics.get("feature_count", 23) if self.metrics else 23
        lbl_table_t = tk.Label(frame, text=f"Detaillierter Testset-Klassifizierungsbericht ({feat_count} Features)", bg=BG_DARK, fg=FG_LIGHT, font=("Segoe UI", 14, "bold"))
        lbl_table_t.grid(row=2, column=0, columnspan=3, sticky="w", pady=(25, 10))
        
        table_frame = tk.Frame(frame, bg=BG_CARD, bd=0, highlightthickness=1, highlightbackground=BORDER_COLOR)
        table_frame.grid(row=3, column=0, columnspan=3, sticky="nsew")
        
        # Grid layout for table headers
        headers = ["Klasse (Einstieg)", "Precision (Genauigkeit)", "Recall (Trefferquote)", "F1-Score", "Support (Anzahl)"]
        for col_idx, header in enumerate(headers):
            lbl_h = tk.Label(table_frame, text=header, bg=BORDER_COLOR, fg=FG_LIGHT, font=("Segoe UI", 11, "bold"), padx=10, pady=8)
            lbl_h.grid(row=0, column=col_idx, sticky="ew")
            table_frame.grid_columnconfigure(col_idx, weight=1)
            
        report_data = self.metrics.get("classification_reports", {}).get("test", {})
        classes_map = {
            "0": "Gefährlich / Blockiert (0)",
            "1": "Sicher / Erlaubt (1)"
        }
        
        row_idx = 1
        for k, name in classes_map.items():
            if k in report_data:
                item = report_data[k]
                bg_col = BG_CARD if row_idx % 2 == 0 else "#252525"
                
                tk.Label(table_frame, text=name, bg=bg_col, fg=COLOR_ACCENT if k != "0" else FG_LIGHT, font=("Segoe UI", 11, "bold"), pady=6).grid(row=row_idx, column=0, sticky="ew")
                tk.Label(table_frame, text=f"{item['precision']*100:.1f}%", bg=bg_col, fg=FG_LIGHT, font=("Segoe UI", 11), pady=6).grid(row=row_idx, column=1, sticky="ew")
                tk.Label(table_frame, text=f"{item['recall']*100:.1f}%", bg=bg_col, fg=FG_LIGHT, font=("Segoe UI", 11), pady=6).grid(row=row_idx, column=2, sticky="ew")
                tk.Label(table_frame, text=f"{item['f1-score']*100:.1f}%", bg=bg_col, fg=FG_LIGHT, font=("Segoe UI", 11), pady=6).grid(row=row_idx, column=3, sticky="ew")
                tk.Label(table_frame, text=str(int(item['support'])), bg=bg_col, fg=FG_MUTED, font=("Segoe UI", 11), pady=6).grid(row=row_idx, column=4, sticky="ew")
                row_idx += 1
                
        # Forest structural details card below table
        if "forest_details" in self.metrics:
            details = self.metrics["forest_details"]
            
            lbl_forest_t = tk.Label(frame, text="Struktur des gelernten Random Forest (Wald-Größe)", bg=BG_DARK, fg=FG_LIGHT, font=("Segoe UI", 14, "bold"))
            lbl_forest_t.grid(row=4, column=0, columnspan=3, sticky="w", pady=(25, 10))
            
            forest_frame = tk.Frame(frame, bg=BG_CARD, bd=0, highlightthickness=1, highlightbackground=BORDER_COLOR, padx=15, pady=12)
            forest_frame.grid(row=5, column=0, columnspan=3, sticky="ew")
            
            # Subgrid inside forest details
            forest_frame.grid_columnconfigure(0, weight=1)
            forest_frame.grid_columnconfigure(1, weight=1)
            forest_frame.grid_columnconfigure(2, weight=1)
            forest_frame.grid_columnconfigure(3, weight=1)
            forest_frame.grid_columnconfigure(4, weight=1)
            
            # Details:
            self.add_detail_box(forest_frame, 0, "Bäume (Trees)", str(details.get("n_estimators", 100)))
            self.add_detail_box(forest_frame, 1, "Entscheidungsknoten", f"{details.get('total_nodes', 0):,}")
            self.add_detail_box(forest_frame, 2, "Ø Baum-Tiefe", f"{details.get('avg_actual_depth', 0.0):.1f}")
            train_sec = self.metrics.get("algorithm", {}).get("training_time_seconds", 0.0)
            self.add_detail_box(forest_frame, 3, "Trainings-Dauer", f"{train_sec:.2f}s")
            onnx_kb = details.get("onnx_size_bytes", 0) / 1024.0
            self.add_detail_box(forest_frame, 4, "ONNX Dateigröße", f"{onnx_kb:.1f} KB")

    def render_features_tab(self, frame):
        """Displays list of features mapping inside the ONNX model, ranked by importance."""
        lbl_title = tk.Label(frame, text="Feature-Bedeutung (Feature Importance Ranking)", bg=BG_DARK, fg=FG_LIGHT, font=("Segoe UI", 14, "bold"))
        lbl_title.pack(anchor="w", pady=(0, 10))
        
        desc_text = "Der Random Forest bewertet die Wichtigkeit jedes Features für die Vorhersage. Die Features sind hier nach ihrer Relevanz sortiert:"
        desc_label = tk.Label(frame, text=desc_text, bg=BG_DARK, fg=FG_MUTED, wraplength=750, justify="left", font=("Segoe UI", 10))
        desc_label.pack(anchor="w", pady=(0, 15))
        
        # Create a container frame for canvas and scrollbar
        container = tk.Frame(frame, bg=BG_DARK)
        container.pack(fill="both", expand=True)
        
        # Canvas and Scrollbar setup
        canvas = tk.Canvas(container, bg=BG_DARK, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        
        # Inner frame to hold all feature cards
        scrollable_frame = tk.Frame(canvas, bg=BG_DARK)
        
        # Bind configure event to update scroll region
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )
        
        # Create canvas window
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        # Resize scrollable_frame width to match canvas width dynamically
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(canvas_window, width=e.width))
        
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Safe mousewheel binding only when cursor is inside the canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            
        def _bind_to_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            
        def _unbind_from_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
            
        canvas.bind('<Enter>', _bind_to_mousewheel)
        canvas.bind('<Leave>', _unbind_from_mousewheel)
        
        # Cleanup binding when canvas is destroyed
        canvas.bind('<Destroy>', lambda e: canvas.unbind_all("<MouseWheel>"))
        
        # Grid frame for features list inside the scrollable frame
        grid_frame = tk.Frame(scrollable_frame, bg=BG_DARK)
        grid_frame.pack(fill="both", expand=True)
        
        feature_descriptions = {
            "is_buy": "Signal-Richtung (1 = Buy, 0 = Sell)",
            "dist_ema250_h4": "Abstand zum H4 EMA(250) Trendfilter (in Punkten)",
            "rsi_m5": "RSI 14 Momentum-Oszillator auf M5-Ebene",
            "rsi_m15": "RSI 14 Momentum-Oszillator auf M15-Ebene",
            "rsi_h1": "RSI 14 Momentum-Oszillator auf H1-Ebene",
            "adx_h1": "ADX 14 Trendstärke-Oszillator auf H1-Ebene",
            "efficiency_ratio_h1": "Kaufmans Efficiency Ratio (Rauschen vs. Trend) auf H1",
            "atr_ratio_m15": "Relative M15 Volatilität (ATR 14 / Ø ATR 30)",
            "atr_ratio_h1": "Relative H1 Volatilität (ATR 14 / Ø ATR 30)",
            "spread_points": "Aktueller Broker-Spread in Punkten",
            "sin_hour": "Zyklische Stunde des Tages (Sinus-Komponente)",
            "cos_hour": "Zyklische Stunde des Tages (Kosinus-Komponente)",
            "sin_day": "Zyklischer Wochentag (Sinus-Komponente)",
            "cos_day": "Zyklischer Wochentag (Kosinus-Komponente)",
            "dist_env_up": "Kurs-Abstand zum oberen Envelope (H1, 14, 0.133) in Punkten",
            "dist_env_down": "Kurs-Abstand zum unteren Envelope (H1, 20, 0.299) in Punkten",
            "macd_h1": "MACD Hauptlinie (12, 26, 9) auf H1-Ebene",
            "macd_sig_h1": "MACD Signallinie (12, 26, 9) auf H1-Ebene",
            "macd_hist_h1": "MACD Histogramm (Differenz Haupt- und Signallinie) auf H1",
            "stoch_k_m15": "Stochastic %K Oszillator (14, 3, 3) auf M15-Ebene",
            "stoch_d_m15": "Stochastic %D Oszillator-Signallinie (14, 3, 3) auf M15-Ebene",
            "cci_h1": "Commodity Channel Index (14, PRICE_TYPICAL) auf H1-Ebene",
            "ema50_ema200_dist_h1": "Distanz zwischen H1 EMA(50) und H1 EMA(200) (in Punkten)",
            "vix_close": "Aktueller Schlusskurs des VIX Volatilitätsindexes (Markt-Angstindikator)",
            "rsi_us500_h1": "RSI 14 Momentum-Oszillator auf H1 von US500 (S&P 500 Marktstimmung)",
            "rsi_xauusd_h1": "RSI 14 Momentum-Oszillator auf H1 von XAUUSD (Gold Safe-Haven-Nachfrage)",
            "minutes_to_usd_news": "Verbleibende Minuten bis zum nächsten wichtigen USD-Wirtschaftstermin",
            "minutes_to_aud_news": "Verbleibende Minuten bis zum nächsten wichtigen AUD-Wirtschaftstermin",
            "dxy_close": "Aktueller Kurs des US-Dollar-Index (DXY)",
            "rsi_dxy_h1": "RSI 14 auf H1-Ebene des US-Dollar-Index (DXY)",
            "rsi_audjpy_h1": "RSI 14 auf H1-Ebene von AUDJPY (Risiko-Sentiment)",
            "rsi_euraud_h1": "RSI 14 auf H1-Ebene von EURAUD (Euro/Aussie-Verhältnis)",
            "rsi_gbpaud_h1": "RSI 14 auf H1-Ebene von GBPAUD (Pfund/Aussie-Verhältnis)",
            "rsi_usdjpy_h1": "RSI 14 auf H1-Ebene von USDJPY (Dollar-Stärke vs. Yen)",
            "is_asian_session": "Asiatische Handels-Session (Broker 22:00 - 08:00)",
            "is_london_session": "Londoner Handels-Session (Broker 08:00 - 16:00)",
            "is_ny_session": "New Yorker Handels-Session (Broker 13:00 - 21:00)",
            "consec_bars_m5": "Aufeinanderfolgende completed M5-Balken gleicher Richtung",
            "vol_ratio_m5": "Verhältnis von M5 Tick-Volumen zum SMA(20) Volumen",
            "rsi_h4": "RSI 14 Momentum-Oszillator auf H4-Ebene von AUDUSD",
            "rsi_d1": "RSI 14 Momentum-Oszillator auf Daily-Ebene (D1) von AUDUSD",
            "dist_sma200_h1": "Kurs-Abstand zum H1 SMA(200) in Punkten",
            "dist_sma200_h4": "Kurs-Abstand zum H4 SMA(200) in Punkten",
            "bb_width_h1": "Relative Breite des Bollinger-Bandes (20, 2) auf H1",
            "bb_width_h4": "Relative Breite des Bollinger-Bandes (20, 2) auf H4",
            "dist_bb_upper_h1": "Kurs-Abstand zum oberen Bollinger-Band auf H1",
            "dist_bb_lower_h1": "Kurs-Abstand zum unteren Bollinger-Band auf H1",
            "dist_bb_upper_h4": "Kurs-Abstand zum oberen Bollinger-Band auf H4",
            "dist_bb_lower_h4": "Kurs-Abstand zum unteren Bollinger-Band auf H4"
        }
        
        feat_imp = self.metrics.get("feature_importances", [])
        
        if not feat_imp:
            features_list = self.metrics.get("features", [])
            feat_imp = [{"name": f, "importance": 1.0 / len(features_list) if features_list else 0.0} for f in features_list]
            
        # Draw 2 columns of features
        half = (len(feat_imp) + 1) // 2
        for col in range(2):
            col_frame = tk.Frame(grid_frame, bg=BG_DARK)
            col_frame.pack(side="left", fill="both", expand=True, padx=10)
            
            start = col * half
            end = min(start + half, len(feat_imp))
            
            for idx in range(start, end):
                item = feat_imp[idx]
                f_name = item["name"]
                importance = item["importance"]
                rank = idx + 1
                
                card = tk.Frame(col_frame, bg=BG_CARD, bd=0, highlightthickness=1, highlightbackground=BORDER_COLOR, pady=12, padx=15)
                card.pack(fill="x", pady=6)
                
                # Header row: Rank and Name
                header_f = tk.Frame(card, bg=BG_CARD)
                header_f.pack(fill="x")
                
                lbl_rank = tk.Label(header_f, text=f"#{rank:02d}", bg=BG_CARD, fg=COLOR_ACCENT, font=("Segoe UI", 12, "bold"))
                lbl_rank.pack(side="left")
                
                lbl_n = tk.Label(header_f, text=f" {f_name}", bg=BG_CARD, fg=FG_LIGHT, font=("Consolas", 12, "bold"))
                lbl_n.pack(side="left")

                # Info Button [i]
                btn_info = tk.Button(
                    header_f, 
                    text="ℹ", 
                    bg=BG_CARD, 
                    fg=COLOR_ACCENT, 
                    activebackground=BG_CARD, 
                    activeforeground=FG_LIGHT,
                    font=("Segoe UI", 11, "bold"),
                    relief="flat",
                    bd=0,
                    cursor="hand2",
                    padx=5,
                    command=lambda name=f_name: self.show_feature_explanation(name)
                )
                btn_info.pack(side="left", padx=(8, 0))
                
                lbl_imp_val = tk.Label(header_f, text=f"{importance*100:.2f}%", bg=BG_CARD, fg=COLOR_BLUE, font=("Segoe UI", 11, "bold"))
                lbl_imp_val.pack(side="right")
                
                # Description
                desc = feature_descriptions.get(f_name, "AUDUSD Modell Feature")
                lbl_d = tk.Label(card, text=desc, bg=BG_CARD, fg=FG_MUTED, font=("Segoe UI", 11), justify="left", anchor="w", wraplength=350)
                lbl_d.pack(fill="x", pady=(4, 6))
                
                # Horizontal Bar representing importance
                p_bar_bg = tk.Frame(card, bg=BORDER_COLOR, height=6)
                p_bar_bg.pack(fill="x")
                color = COLOR_GREEN if rank <= 4 else (COLOR_BLUE if rank <= 10 else FG_MUTED)
                max_imp = feat_imp[0]["importance"] if feat_imp else 1.0
                rel_width = int((importance / max_imp) * 200) if max_imp > 0 else 0
                p_bar_fg = tk.Frame(p_bar_bg, bg=color, height=6, width=max(1, rel_width))
                p_bar_fg.pack(side="left")

    def show_feature_explanation(self, name):
        """Shows a detailed explanation of the indicator in a styled dark-themed window."""
        explanations = {
            "is_buy": {
                "title": "Signal-Richtung (is_buy)",
                "desc": "Dieses Feature gibt die Handelsrichtung der aktuellen Envelope-Durchbruchskerze an.\n\n"
                        "Wert 1.0 steht für ein BUY-Signal (Preis bricht das untere Envelope-Band).\n"
                        "Wert 0.0 steht für ein SELL-Signal (Preis bricht das obere Envelope-Band).\n\n"
                        "Warum es wichtig ist: Mean-Reversion-Muster verhalten sich bei Aufwärts- und Abwärtsbewegungen oft asymmetrisch."
            },
            "dist_ema250_h4": {
                "title": "EMA(250) H4 Distanz (dist_ema250_h4)",
                "desc": "Der Abstand des M5-Schlusskurses zum exponentiell gleitenden Durchschnitt (EMA) über 250 Perioden auf H4-Ebene (in Punkten).\n\n"
                        "Bedeutung: Filtert den übergeordneten Keltner-/Trendkanal auf H4. Ein hoher positiver Abstand signalisiert einen starken Aufwärtstrend, "
                        "während ein hoher negativer Abstand einen starken Abwärtstrend anzeigt.\n\n"
                        "Warum es wichtig ist: Verhindert Einstiege gegen extrem starke übergeordnete Trends."
            },
            "rsi_m5": {
                "title": "RSI 14 M5 (rsi_m5)",
                "desc": "Relative Strength Index (RSI) mit einer Periode von 14 auf dem M5-Timeframe.\n\n"
                        "Bedeutung: Oszilliert zwischen 0 und 100. Werte über 70 deuten auf überkaufte Bedingungen hin, "
                        "Werte unter 30 auf überverkaufte Bedingungen auf M5-Ebene.\n\n"
                        "Warum es wichtig ist: Zeigt kurzfristiges Momentum an, das unmittelbar vor dem Durchbruch herrscht."
            },
            "rsi_m15": {
                "title": "RSI 14 M15 (rsi_m15)",
                "desc": "Relative Strength Index (RSI) mit einer Periode von 14 auf dem M15-Timeframe (in der Extraktion als Periode 21 implementiert).\n\n"
                        "Bedeutung: Misst die relative Stärke auf dem mittleren Timeframe. Hilft, mittelfristige Erschöpfungen zu erkennen.\n\n"
                        "Warum es wichtig ist: Bietet ein breiteres Bild über den Zustand des Vermögenswerts als der M5 RSI."
            },
            "rsi_h1": {
                "title": "RSI 14 H1 (rsi_h1)",
                "desc": "Relative Strength Index (RSI) mit einer Periode von 14 auf dem H1-Timeframe.\n\n"
                        "Bedeutung: Zeigt überkaufte/überverkaufte Zonen auf H1. Äußerst nützlich für die übergeordnete Zyklusbestimmung.\n\n"
                        "Warum es wichtig ist: Starke Trends auf H1 weisen darauf hin, dass Ausbrüche oft weiterlaufen anstatt direkt zu drehen."
            },
            "adx_h1": {
                "title": "ADX 14 H1 (adx_h1)",
                "desc": "Average Directional Movement Index (ADX) mit Periode 14 auf dem H1-Timeframe.\n\n"
                        "Bedeutung: Misst die Stärke des übergeordneten Trends, unabhängig von dessen Richtung. Werte über 25 "
                        "signalisieren einen starken Trend, Werte unter 20 deuten auf einen Seitwärtsmarkt hin.\n\n"
                        "Warum es wichtig ist: Wenn der ADX hoch ist, sind Ausbrüche aus den Envelopes oft Fortsetzungssignale (gefährlich für Grid) statt Umkehrsignale."
            },
            "efficiency_ratio_h1": {
                "title": "Kaufman's Efficiency Ratio H1 (efficiency_ratio_h1)",
                "desc": "Kaufmans Effizienz-Ratio (ER) über 10 Perioden auf dem H1-Timeframe.\n\n"
                        "Bedeutung: Berechnet als das Verhältnis von gerichteter Preisbewegung zu Summe aller absoluten Preisbewegungen. "
                        "ER = 1.0 bedeutet einen vollkommen glatten Trend ohne Rauschen; ER = 0.0 bedeutet pures Rauschen ohne Netto-Bewegung.\n\n"
                        "Warum es wichtig ist: Schützt das Grid vor Einstiegen in hocheffiziente, geradlinige Trendausbrüche."
            },
            "atr_ratio_m15": {
                "title": "ATR Ratio M15 (atr_ratio_m15)",
                "desc": "Verhältnis der aktuellen Average True Range (ATR 10) zum gleitenden Durchschnitt der ATR über 30 Perioden auf M15.\n\n"
                        "Bedeutung: Misst die relative Volatilitätsausdehnung. Ein Wert > 1.0 zeigt eine Ausdehnung der Volatilität, "
                        "Wert < 1.0 zeigt eine Beruhigung an.\n\n"
                        "Warum es wichtig ist: Volatilitätsspitzen deuten oft auf News oder impulsive Ausbrüche hin, die schwer zu fangen sind."
            },
            "atr_ratio_h1": {
                "title": "ATR Ratio H1 (atr_ratio_h1)",
                "desc": "Verhältnis der aktuellen Average True Range (ATR 14) zum gleitenden Durchschnitt der ATR über 30 Perioden auf H1.\n\n"
                        "Bedeutung: Ähnlich wie auf M15, misst jedoch die längerfristige Volatilitätsdynamik auf H1.\n\n"
                        "Warum es wichtig ist: Hilft dem Modell zu unterscheiden, ob ein Durchbruch bei normalem Rauschen oder unter extremen Marktbedingungen stattfindet."
            },
            "spread_points": {
                "title": "Spread in Punkten (spread_points)",
                "desc": "Der aktuelle Spread (Differenz zwischen Ask und Bid) in Broker-Punkten beim Eintreffen des Signals.\n\n"
                        "Bedeutung: Spiegelt die Handelskosten und die Marktliquidität wider.\n\n"
                        "Warum es wichtig ist: Hohe Spreads treten bei News-Events oder schlechter Liquidität auf, was das Verlustrisiko erhöht."
            },
            "sin_hour": {
                "title": "Zyklische Stunde - Sinus (sin_hour)",
                "desc": "Sinus-Transformation der Stunde (0-23) der Signalzeit.\n\n"
                        "Bedeutung: Wandelt die Tageszeit in ein kontinuierliches, zyklisches Signal um. Stellt die zeitliche Nähe zum Tagesverlauf dar.\n\n"
                        "Warum es wichtig ist: Ermöglicht dem Modell das Lernen tageszeitspezifischer Verhaltensmuster (z.B. Asien-Session vs. London-Eröffnung)."
            },
            "cos_hour": {
                "title": "Zyklische Stunde - Kosinus (cos_hour)",
                "desc": "Kosinus-Transformation der Stunde (0-23) der Signalzeit.\n\n"
                        "Bedeutung: Ergänzt die Sinus-Transformation, um jede Stunde des Tages eindeutig im 2D-Raum darzustellen (Stunde 23 liegt direkt neben Stunde 0).\n\n"
                        "Warum es wichtig ist: Unverzichtbar für Machine-Learning-Algorithmen, um zeitliche Distanzen korrekt zu erfassen."
            },
            "sin_day": {
                "title": "Zyklischer Wochentag - Sinus (sin_day)",
                "desc": "Sinus-Transformation des Wochentags (1=Montag bis 7=Sonntag).\n\n"
                        "Bedeutung: Bildet den Wochentag zyklisch ab, um den Verlauf der Handelswoche darzustellen.\n\n"
                        "Warum es wichtig ist: Märkte verhalten sich montags (Markteröffnung) oder freitags (Wochenendschließung) oft anders als mitten in der Woche."
            },
            "cos_day": {
                "title": "Zyklischer Wochentag - Kosinus (cos_day)",
                "desc": "Kosinus-Transformation des Wochentags.\n\n"
                        "Bedeutung: Arbeitet mit dem Sinus-Wochentag zusammen, um einen kontinuierlichen Wochenzyklus zu garantieren.\n\n"
                        "Warum es wichtig ist: Schützt das Modell vor abrupten Grenzwerten zwischen Sonntag und Montag."
            },
            "dist_env_up": {
                "title": "Abstand zum oberen Envelope (dist_env_up)",
                "desc": "Der Abstand des M5-Schlusskurses zum oberen H1-Envelope-Band (Periode 14, Abweichung 0.133) in Punkten.\n\n"
                        "Bedeutung: Misst die Überschreitung des oberen Kanals. Bei einem Sell-Signal ist dieser Wert positiv (bricht nach oben aus).\n\n"
                        "Warum es wichtig ist: Je weiter der Preis über das Band schießt, desto überdehnter ist die Bewegung, aber auch desto stärker das Ausbruchsmomentum."
            },
            "dist_env_down": {
                "title": "Abstand zum unteren Envelope (dist_env_down)",
                "desc": "Der Abstand des M5-Schlusskurses zum unteren H1-Envelope-Band (Periode 20, Abweichung 0.299) in Punkten.\n\n"
                        "Bedeutung: Misst die Unterschreitung des unteren Kanals. Bei einem Buy-Signal ist dieser Wert negativ (bricht nach unten aus).\n\n"
                        "Warum es wichtig ist: Gibt Aufschluss über die Aggressivität des Abwärtsausbruchs."
            },
            "macd_h1": {
                "title": "MACD Hauptlinie H1 (macd_h1)",
                "desc": "Der Wert der Moving Average Convergence Divergence (MACD) Hauptlinie (12, 26) auf H1-Ebene.\n\n"
                        "Bedeutung: Misst die Differenz zwischen dem 12-Perioden- und dem 26-Perioden-EMA. Positive Werte zeigen Aufwärtstrendstärke, negative Abwärtstrendstärke.\n\n"
                        "Warum es wichtig ist: Hilft bei der Klassifizierung der übergeordneten Trendstärke."
            },
            "macd_sig_h1": {
                "title": "MACD Signallinie H1 (macd_sig_h1)",
                "desc": "Der Wert der MACD-Signallinie (9-Perioden-SMA der Hauptlinie) auf H1-Ebene.\n\n"
                        "Bedeutung: Glättet den MACD-Wert, um Trendwendepunkte zu bestimmen.\n\n"
                        "Warum es wichtig ist: Dient als Referenz für die Bestimmung von Impulsänderungen auf H1."
            },
            "macd_hist_h1": {
                "title": "MACD Histogramm H1 (macd_hist_h1)",
                "desc": "Die Differenz zwischen der MACD-Hauptlinie und der Signallinie auf H1-Ebene.\n\n"
                        "Bedeutung: Zeigt die Beschleunigung oder Verlangsamung des momentanen Trends. Ein steigendes Histogramm zeigt zunehmendes Kaufmomentum, ein fallendes zunehmendes Verkaufsmomentum.\n\n"
                        "Warum es wichtig ist: Große Histogramm-Werte deuten auf impulsive Ausbruchsbewegungen hin, bei denen Kontra-Trend-Einstiege riskant sind."
            },
            "stoch_k_m15": {
                "title": "Stochastic %K M15 (stoch_k_m15)",
                "desc": "Die %K-Linie des Stochastic-Oszillators (14, 3, 3) auf dem M15-Timeframe.\n\n"
                        "Bedeutung: Vergleicht den Schlusskurs mit der Preisspanne über 14 Perioden. Liegt zwischen 0 und 100. Werte nahe 100 zeigen, dass der Kurs nahe dem Hoch schließt, Werte nahe 0 zeigen Schlusskurse am Tief.\n\n"
                        "Warum es wichtig ist: Liefert überverkaufte/überkaufte Signale auf mittlerer Zeitebene."
            },
            "stoch_d_m15": {
                "title": "Stochastic %D M15 (stoch_d_m15)",
                "desc": "Die %D-Signallinie (3-Perioden-SMA der %K-Linie) auf M15.\n\n"
                        "Bedeutung: Glättet die %K-Linie zur Signalgenerierung.\n\n"
                        "Warum es wichtig ist: Kreuzungen von %K und %D signalisieren lokale Erschöpfungspunkte im M15-Trend."
            },
            "cci_h1": {
                "title": "CCI H1 (cci_h1)",
                "desc": "Commodity Channel Index (14, PRICE_TYPICAL) auf dem H1-Timeframe.\n\n"
                        "Bedeutung: Ein Oszillator, der die Abweichung des Kurses von seinem gleitenden Durchschnitt misst. Werte über +100 signalisieren starke Überdehnung nach oben, Werte unter -100 nach unten.\n\n"
                        "Warum es wichtig ist: Sehr starke CCI-Auslenkungen (z.B. > +200) deuten auf unaufhaltsame Trend-Impulse hin, bei denen das Grid leicht überfordert werden kann."
            },
            "ema50_ema200_dist_h1": {
                "title": "EMA(50)/EMA(200) H1 Distanz (ema50_ema200_dist_h1)",
                "desc": "Der Abstand zwischen dem 50-Perioden-EMA und dem 200-Perioden-EMA auf H1-Ebene (in Punkten).\n\n"
                        "Bedeutung: Klassischer Indikator für langfristige Trendphasen (Golden Cross / Death Cross) sowie deren Ausdehnung.\n\n"
                        "Warum es wichtig ist: Große Distanzen weisen auf weit fortgeschrittene Trends hin, bei denen Gegenbewegungen überfällig sein können."
            },
            "vix_close": {
                "title": "VIX Schlusskurs (vix_close)",
                "desc": "Der aktuelle Schlusskurs des CBOE Volatilitätsindex (VIX).\n\n"
                        "Bedeutung: Der VIX misst die implizite Volatilität von S&P 500-Optionen und gilt als das Angstbarometer des globalen Finanzmarktes. Ein niedriger Wert zeigt Sorglosigkeit, während ein hoher Wert Angst signalisiert.\n\n"
                        "Warum es wichtig ist: Extrem hohe VIX-Werte (>25-30) weisen auf unruhige globale Märkte hin. In solchen Phasen sind klassische Mean-Reversion-Muster bei Währungen weniger verlässlich und das Grid-Risiko ist deutlich erhöht."
            },
            "rsi_us500_h1": {
                "title": "US500 H1 RSI (rsi_us500_h1)",
                "desc": "Der Relative Strength Index (RSI 14) auf dem H1-Chart des US500 (S&P 500 Index).\n\n"
                        "Bedeutung: Zeigt die überkaufte/überverkaufte Lage am US-Aktienmarkt.\n\n"
                        "Warum es wichtig ist: Starke Bewegungen am Aktienmarkt (Risk-on/Risk-off-Stimmungen) erzeugen oft signifikante Kapitalverschiebungen in sichere Häfen (US-Dollar) oder risikoreichere Währungen (Australischer Dollar). Dies hilft, die Dynamik von AUDUSD-Ausbrüchen besser einzuschätzen."
            },
            "rsi_xauusd_h1": {
                "title": "Gold H1 RSI (rsi_xauusd_h1)",
                "desc": "Der Relative Strength Index (RSI 14) auf dem H1-Chart von Gold (XAUUSD).\n\n"
                        "Bedeutung: Bestimmt die Dynamik des Goldpreises auf H1.\n\n"
                        "Warum es wichtig ist: Gold gilt als der ultimative sichere Hafen bei geopolitischen oder ökonomischen Spannungen. Zudem hat Australien als großer Rohstoffexporteur eine enge Korrelation zu Edelmetallen. Ein steigender Goldpreis (hoher RSI) stützt tendenziell den AUD."
            },
            "minutes_to_usd_news": {
                "title": "USD News Countdown (minutes_to_usd_news)",
                "desc": "Die verbleibende Zeit in Minuten bis zum nächsten USD-Wirtschaftskalenderereignis von mittlerer bis hoher Relevanz.\n\n"
                        "Bedeutung: Ein zeitlicher Abstandshalter zu News-Veröffentlichungen. Werte nahe Null weisen auf kurz bevorstehende Veröffentlichungen hin.\n\n"
                        "Warum es wichtig ist: Kurz vor News-Events (z. B. Zinsentscheide, NFP) kommt es oft zu unberechenbarer Volatilität und ausbleibender Liquidität, in denen das Modell Trades blockieren sollte."
            },
            "minutes_to_aud_news": {
                "title": "AUD News Countdown (minutes_to_aud_news)",
                "desc": "Die verbleibende Zeit in Minuten bis zum nächsten AUD-Wirtschaftskalenderereignis von mittlerer bis hoher Relevanz.\n\n"
                        "Bedeutung: Zeigt die Nähe zu australischen Notenbankentscheidungen oder Konjunkturdaten an.\n\n"
                        "Warum es wichtig ist: Ähnlich wie bei USD-News schützt dies das Grid vor unkontrollierten Slippage- oder Spread-Phasen rund um australische Wirtschaftsdaten."
            },
            "dxy_close": {
                "title": "DXY Schlusskurs (dxy_close)",
                "desc": "Der aktuelle Kurs des US-Dollar-Index (DXY).\n\n"
                        "Bedeutung: Der DXY misst den Wert des US-Dollars im Vergleich zu einem Korb aus sechs Hauptwährungen.\n\n"
                        "Warum es wichtig ist: Ein steigender DXY deutet auf eine generelle Stärke des US-Dollars hin, was typischerweise Abwärtsdruck auf AUDUSD ausübt."
            },
            "rsi_dxy_h1": {
                "title": "DXY H1 RSI (rsi_dxy_h1)",
                "desc": "Der Relative Strength Index (RSI 14) auf dem H1-Chart des US-Dollar-Index (DXY).\n\n"
                        "Bedeutung: Zeigt die überkaufte oder überverkaufte Dynamik der globalen Leitwährung.\n\n"
                        "Warum es wichtig ist: Hilft dem Modell zu erkennen, ob die globale Dollar-Stärke bereits überdehnt ist und eine Korrektur anstehen könnte."
            },
            "rsi_audjpy_h1": {
                "title": "AUDJPY H1 RSI (rsi_audjpy_h1)",
                "desc": "Der Relative Strength Index (RSI 14) auf dem H1-Chart von AUDJPY.\n\n"
                        "Bedeutung: AUDJPY gilt als das klassische Barometer für Risiko-Sentiment (Risk-on / Risk-off) im Devisenmarkt.\n\n"
                        "Warum es wichtig ist: Ein hoher RSI bei AUDJPY zeigt starke Risk-on-Stimmung (Aktienkäufe, Carry-Trades), was den AUD stützt. Ein fallender RSI weist auf Flucht in Sicherheit hin."
            },
            "rsi_euraud_h1": {
                "title": "EURAUD H1 RSI (rsi_euraud_h1)",
                "desc": "Der Relative Strength Index (RSI 14) auf dem H1-Chart von EURAUD.\n\n"
                        "Bedeutung: Zeigt die Stärke des Euros gegenüber dem australischen Dollar.\n\n"
                        "Warum es wichtig ist: EURAUD verhält sich oft gegenläufig zu AUDUSD. Ein überkaufter EURAUD (hoher RSI) signalisiert Schwäche im AUD, die sich auf AUDUSD auswirken kann."
            },
            "rsi_gbpaud_h1": {
                "title": "GBPAUD H1 RSI (rsi_gbpaud_h1)",
                "desc": "Der Relative Strength Index (RSI 14) auf dem H1-Chart von GBPAUD.\n\n"
                        "Bedeutung: Zeigt die Dynamik von GBP gegenüber AUD.\n\n"
                        "Warum es wichtig ist: Zusammen mit EURAUD hilft dieser Oszillator dem Modell, europäisch-australische Währungsverschiebungen als Kontext zu erfassen."
            },
            "rsi_usdjpy_h1": {
                "title": "USDJPY H1 RSI (rsi_usdjpy_h1)",
                "desc": "Der Relative Strength Index (RSI 14) auf dem H1-Chart von USDJPY.\n\n"
                        "Bedeutung: Zeigt die relative Stärke des Dollars gegenüber dem Yen.\n\n"
                        "Warum es wichtig ist: USDJPY spiegelt stark die Zinsdifferenz zwischen den USA und Japan wider. Ein Anstieg deutet auf breite Nachfrage nach US-Renditen hin."
            },
            "is_asian_session": {
                "title": "Asian Session (is_asian_session)",
                "desc": "Binaeres Flag (1.0 = aktiv, 0.0 = inaktiv) fuer die asiatische Handels-Session (Broker-Zeit 22:00 - 08:00).\n\n"
                        "Bedeutung: Asiatische Stunden zeichnen sich meist durch niedriges Volumen und Seitwaertsphasen aus.\n\n"
                        "Warum es wichtig ist: Grid-Systeme koennen hier freigiebiger handeln, da Trenddurchbrueche seltener sind."
            },
            "is_london_session": {
                "title": "London Session (is_london_session)",
                "desc": "Binaeres Flag fuer die europaeische Handels-Session (Broker-Zeit 08:00 - 16:00).\n\n"
                        "Bedeutung: Das europaeische Geschaeft bringt viel Liquiditaet und oft den ersten starken Trend des Tages.\n\n"
                        "Warum es wichtig ist: Warnung fuer unruhige Trendstarts."
            },
            "is_ny_session": {
                "title": "New York Session (is_ny_session)",
                "desc": "Binaeres Flag fuer die US Handels-Session (Broker-Zeit 13:00 - 21:00).\n\n"
                        "Bedeutung: Hohe Volatilitaet durch US-Daten und Ueberschneidung mit London.\n\n"
                        "Warum es wichtig ist: Risikoreichste Session des Tages."
            },
            "consec_bars_m5": {
                "title": "Consecutive Bars M5 (consec_bars_m5)",
                "desc": "Anzahl aufeinanderfolgender M5-Kerzen mit derselben Richtung (positive Werte fuer gruene/bullische Kerzen, negative fuer rote/baerische Kerzen).\n\n"
                        "Bedeutung: Zaehlt die Trendlaenge auf M5 ohne nennenswerte Pause.\n\n"
                        "Warum es wichtig ist: Je laenger ein Impuls ohne Konsolidierung laeuft, desto gefaehrlicher wird ein direkter Grid-Einstieg."
            },
            "vol_ratio_m5": {
                "title": "Volume Ratio M5 (vol_ratio_m5)",
                "desc": "Verhaeltnis des aktuellen Tick-Volumens zum Durchschnittsvolumen der letzten 20 Kerzen auf M5.\n\n"
                        "Bedeutung: Zeigt an, ob ein Ausbruch von viel Volumen (institutionelles Geld) getragen wird.\n\n"
                        "Warum es wichtig ist: Sehr hohe Ratios (>2.0) deuten auf echte Ausbrueche hin (hohe Gefahr), kleine Ratios auf Fehlausbrueche."
            },
            "rsi_h4": {
                "title": "AUDUSD H4 RSI (rsi_h4)",
                "desc": "Der Relative Strength Index (RSI 14) auf dem H4-Chart von AUDUSD.\n\n"
                        "Bedeutung: Zeigt die mittelfristige Erschoepfung des Kurses an.\n\n"
                        "Warum es wichtig ist: Filtert Fehlausbrueche bei stark ueberdehnten H4-Zyklen."
            },
            "rsi_d1": {
                "title": "AUDUSD Daily RSI (rsi_d1)",
                "desc": "Der Relative Strength Index (RSI 14) auf dem Daily-Chart (D1) von AUDUSD.\n\n"
                        "Bedeutung: Zeigt den uebergeordneten, langfristigen Erschoepfungszustand an.\n\n"
                        "Warum es wichtig ist: Wenn der Daily RSI im Extrembereich liegt (z. B. >70 oder <30), droht bei Ausbruechen ein starker Trendlauf."
            },
            "dist_sma200_h1": {
                "title": "SMA(200) H1 Distanz (dist_sma200_h1)",
                "desc": "Kursabstand des aktuellen M5-Preises zum H1 SMA(200) in Broker-Punkten.\n\n"
                        "Bedeutung: Der SMA(200) ist eine sehr starke institutionelle Unterstuetzungs- und Widerstandslinie.\n\n"
                        "Warum es wichtig ist: Je weiter der Kurs entfernt ist, desto staerker ist die Tendenz zur Rueckkehr zum Mittelwert."
            },
            "dist_sma200_h4": {
                "title": "SMA(200) H4 Distanz (dist_sma200_h4)",
                "desc": "Kursabstand des aktuellen M5-Preises zum H4 SMA(200) in Broker-Punkten.\n\n"
                        "Bedeutung: Zeigt den Abstand zum uebergeordneten H4 gleitenden Durchschnitt.\n\n"
                        "Warum es wichtig ist: Verhindert Einstiege weit abseits der langfristigen Mittelwerte."
            },
            "bb_width_h1": {
                "title": "Bollinger Band Width H1 (bb_width_h1)",
                "desc": "Die relative Bandbreite der Bollinger Baender (20, 2) auf H1.\n\n"
                        "Bedeutung: Berechnet als (Upper - Lower) / Middle. Kleine Werte deuten auf einen Squeeze (Seitwaertsphase) hin.\n\n"
                        "Warum es wichtig ist: Aus Squeezes brechen Kurse oft mit enormer Wucht aus (Breakout-Gefahr)."
            },
            "bb_width_h4": {
                "title": "Bollinger Band Width H4 (bb_width_h4)",
                "desc": "Die relative Bandbreite der Bollinger Baender (20, 2) auf H4.\n\n"
                        "Bedeutung: Zeigt mittelfristige Volatilitaetskontraktionen an.\n\n"
                        "Warum es wichtig ist: Signalisiert laengere Phasen der Marktberuhigung oder bevorstehende Grossbewegungen."
            },
            "dist_bb_upper_h1": {
                "title": "Abstand zum oberen BB H1 (dist_bb_upper_h1)",
                "desc": "Kursabstand zum oberen Bollinger Band (20, 2) auf H1 (in Punkten).\n\n"
                        "Bedeutung: Positive Werte bedeuten einen Ausbruch ueber das Band.\n\n"
                        "Warum es wichtig ist: Identifiziert extreme Abweichungen auf H1."
            },
            "dist_bb_lower_h1": {
                "title": "Abstand zum unteren BB H1 (dist_bb_lower_h1)",
                "desc": "Kursabstand zum unteren Bollinger Band (20, 2) auf H1 (in Punkten).\n\n"
                        "Bedeutung: Negative Werte deuten auf einen Ausbruch nach unten hin.\n\n"
                        "Warum es wichtig ist: Hilft bei der Beurteilung von Buy-Signalen auf H1."
            },
            "dist_bb_upper_h4": {
                "title": "Abstand zum oberen BB H4 (dist_bb_upper_h4)",
                "desc": "Kursabstand zum oberen Bollinger Band (20, 2) auf H4 (in Punkten).\n\n"
                        "Bedeutung: Zeigt, wie weit der Preis ueber das H4 Band gestiegen ist.\n\n"
                        "Warum es wichtig ist: Schützt das Grid bei massiven H4-Trendausbruechen."
            },
            "dist_bb_lower_h4": {
                "title": "Abstand zum unteren BB H4 (dist_bb_lower_h4)",
                "desc": "Kursabstand zum unteren Bollinger Band (20, 2) auf H4 (in Punkten).\n\n"
                        "Bedeutung: Zeigt extreme Ausbrueche nach unten auf H4.\n\n"
                        "Warum es wichtig ist: Filtert hochriskante Selloffs."
            }
        }
        
        # Create a custom popup window
        info_win = tk.Toplevel(self.root)
        info_win.title("Feature Details")
        info_win.geometry("580x420")
        info_win.configure(bg=BG_CARD)
        info_win.transient(self.root)
        info_win.grab_set()
        info_win.resizable(False, False)
        
        info = explanations.get(name, {
            "title": f"Feature: {name}",
            "desc": "Keine Beschreibung verfügbar."
        })
        
        # Title Label
        lbl_title = tk.Label(
            info_win, 
            text=info["title"], 
            bg=BG_CARD, 
            fg=COLOR_ACCENT, 
            font=("Segoe UI", 14, "bold"),
            wraplength=520,
            justify="left"
        )
        lbl_title.pack(anchor="w", padx=25, pady=(25, 15))
        
        # Separator
        sep = tk.Frame(info_win, bg=BORDER_COLOR, height=1)
        sep.pack(fill="x", padx=25, pady=0)
        
        # Description Text (with custom scrollable text or label)
        txt_frame = tk.Frame(info_win, bg=BG_CARD)
        txt_frame.pack(fill="both", expand=True, padx=25, pady=15)
        
        txt_desc = scrolledtext.ScrolledText(
            txt_frame, 
            bg=BG_CARD, 
            fg=FG_LIGHT, 
            insertbackground=FG_LIGHT,
            font=("Segoe UI", 11),
            bd=0,
            highlightthickness=0,
            wrap="word"
        )
        txt_desc.pack(fill="both", expand=True)
        txt_desc.insert(tk.END, info["desc"])
        txt_desc.configure(state="disabled")
        
        # Close Button
        btn_close = ModernButton(
            info_win,
            text="Schließen",
            bg=BORDER_COLOR,
            fg=FG_LIGHT,
            hover_bg=COLOR_BLUE,
            hover_fg="#ffffff",
            font=("Segoe UI", 10, "bold"),
            width=12,
            height=1,
            command=info_win.destroy
        )
        btn_close.pack(anchor="e", padx=25, pady=(0, 20))

    def show_dataset_info(self):
        """Shows a detailed explanation of the training/testing dataset and examples."""
        info_win = tk.Toplevel(self.root)
        info_win.title("Informationen zu den Trainings- und Testdaten")
        info_win.geometry("620x520")
        info_win.configure(bg=BG_CARD)
        info_win.transient(self.root)
        info_win.grab_set()
        info_win.resizable(False, False)
        
        lbl_title = tk.Label(
            info_win, 
            text="Daten-Details & Trainings-Beispiele", 
            bg=BG_CARD, 
            fg=COLOR_ACCENT, 
            font=("Segoe UI", 14, "bold")
        )
        lbl_title.pack(anchor="w", padx=25, pady=(25, 15))
        
        sep = tk.Frame(info_win, bg=BORDER_COLOR, height=1)
        sep.pack(fill="x", padx=25, pady=0)
        
        txt_frame = tk.Frame(info_win, bg=BG_CARD)
        txt_frame.pack(fill="both", expand=True, padx=25, pady=15)
        
        txt_desc = scrolledtext.ScrolledText(
            txt_frame, 
            bg=BG_CARD, 
            fg=FG_LIGHT, 
            insertbackground=FG_LIGHT,
            font=("Segoe UI", 11),
            bd=0,
            highlightthickness=0,
            wrap="word"
        )
        txt_desc.pack(fill="both", expand=True)
        
        # Retrieve stats from self.metrics
        total_samples = 0
        train_samples = 0
        test_samples = 0
        train_0 = 0
        train_1 = 0
        test_0 = 0
        test_1 = 0
        
        if self.metrics:
            ds = self.metrics.get("dataset_size", {})
            total_samples = ds.get("total", 0)
            train_samples = ds.get("train", 0)
            test_samples = ds.get("test", 0)
            
            report_train = self.metrics.get("classification_reports", {}).get("train", {})
            report_test = self.metrics.get("classification_reports", {}).get("test", {})
            
            train_0 = int(report_train.get("0", {}).get("support", 0))
            train_1 = int(report_train.get("1", {}).get("support", 0))
            test_0 = int(report_test.get("0", {}).get("support", 0))
            test_1 = int(report_test.get("1", {}).get("support", 0))
            
        desc_text = (
            "Wie entstehen diese Beispiele?\n"
            "------------------------------\n"
            "Die Datenbasis wird aus den historischen M5-Chart-Daten der letzten Jahre generiert. "
            "Immer wenn das Grid-System ein Signal für einen potenziellen Trade erhalten hätte (z.B. Durchbruch der Envelope-Bänder), "
            "wird ein historisches Beispiel aufgezeichnet. Zu jedem Beispiel werden alle 49 technischen und zyklischen Indikatoren extrahiert.\n\n"
            
            "Klassifizierung (Targets / Label):\n"
            "---------------------------------\n"
            "- Klasse 0 (Gefährlich / Blockiert): Der Einstieg führte zu einem hohen Drawdown oder Verlust des Grids (Gefahrenzone).\n"
            "- Klasse 1 (Sicher / Erlaubt): Der Einstieg verlief sicher und erreichte das Take-Profit-Ziel ohne kritischen Drawdown.\n\n"
            
            "Verwendete Beispiele im aktuellen Modell:\n"
            "----------------------------------------\n"
            f"• Gesamt-Beispiele in der Datenbank: {total_samples:,}\n"
            f"• Trainings-Set (In-Sample, 82%): {train_samples:,} Beispiele\n"
            f"  - Klasse 1 (Sicher): {train_1:,} ({train_1/max(1, train_samples)*100:.1f}%)\n"
            f"  - Klasse 0 (Gefährlich): {train_0:,} ({train_0/max(1, train_samples)*100:.1f}%)\n"
            f"• Test-Set (Out-of-Sample, 18%): {test_samples:,} Beispiele\n"
            f"  - Klasse 1 (Sicher): {test_1:,} ({test_1/max(1, test_samples)*100:.1f}%)\n"
            f"  - Klasse 0 (Gefährlich): {test_0:,} ({test_0/max(1, test_samples)*100:.1f}%)\n\n"
            
            "In-Sample vs. Out-of-Sample:\n"
            "---------------------------\n"
            "• Trainings-Daten (In-Sample): Mit diesen Beispielen lernt der Random Forest die Muster. "
            "Das Modell versucht, Entscheidungsregeln zu finden, um die Klassen optimal zu trennen. Die Genauigkeit hier zeigt, wie gut das Modell die Trainingsdaten gelernt hat.\n"
            "• Test-Daten (Out-of-Sample): Diese Daten wurden dem Modell beim Lernen komplett vorenthalten. "
            "Die Genauigkeit hier zeigt die echte Leistungsfähigkeit bei unbekannten Marktbedingungen. Sie schützt vor Overfitting (Auswendiglernen) und ist die Grundlage für die Ampel-Qualitätsbewertung."
        ).replace(",", ".")
        
        txt_desc.insert(tk.END, desc_text)
        txt_desc.configure(state="disabled")
        
        btn_close = ModernButton(
            info_win,
            text="Schließen",
            bg=BORDER_COLOR,
            fg=FG_LIGHT,
            hover_bg=COLOR_BLUE,
            hover_fg="#ffffff",
            font=("Segoe UI", 10, "bold"),
            width=12,
            height=1,
            command=info_win.destroy
        )
        btn_close.pack(anchor="e", padx=25, pady=(0, 20))

    def render_confusion_tab(self, frame):
        """Draws a custom heatmap visualization of the test confusion matrix (2x2 binary classification)."""
        lbl_title = tk.Label(frame, text="Klassifizierungs-Konfusionsmatrix (Testdaten)", bg=BG_DARK, fg=FG_LIGHT, font=("Segoe UI", 14, "bold"))
        lbl_title.pack(anchor="w", pady=(0, 10))
        
        desc = tk.Label(frame, text="Zeigt die tatsächlichen (Actual) Klassen gegen die vom Modell vorhergesagten (Predicted) Klassen.", bg=BG_DARK, fg=FG_MUTED, font=("Segoe UI", 10))
        desc.pack(anchor="w", pady=(0, 15))
        
        cm = self.metrics.get("confusion_matrices", {}).get("test", [])
        if not cm or len(cm) != 2:
            lbl_err = tk.Label(frame, text="Fehlerhafte Konfusionsmatrix-Daten (Benötigt 2x2 Matrix).", bg=BG_DARK, fg=COLOR_RED, font=("Segoe UI", 11, "bold"))
            lbl_err.pack(pady=20)
            return
            
        canvas_width = 500
        canvas_height = 420
        canvas = tk.Canvas(frame, width=canvas_width, height=canvas_height, bg=BG_DARK, highlightthickness=0)
        canvas.pack(pady=10)
        
        # Grid constants
        offset_x = 150  # Left label spacer
        offset_y = 70   # Top label spacer
        cell_size = 140
        
        labels = ["DANGEROUS (0)", "SAFE (1)"]
        row_totals = [sum(row) for row in cm]
        
        for i in range(2):
            # Row labels (Actual)
            canvas.create_text(offset_x - 15, offset_y + (i * cell_size) + (cell_size / 2),
                               text=labels[i], fill=FG_LIGHT, font=("Segoe UI", 10, "bold"), anchor="e")
            # Column labels (Predicted)
            canvas.create_text(offset_x + (i * cell_size) + (cell_size / 2), offset_y - 15,
                               text=labels[i], fill=FG_LIGHT, font=("Segoe UI", 10, "bold"), anchor="s")
                               
        # Main Actual / Predicted titles
        canvas.create_text(offset_x + (1.0 * cell_size), offset_y - 40,
                           text="VORHERGESAGT (PREDICTED)", fill=COLOR_ACCENT, font=("Segoe UI", 12, "bold"))
                           
        canvas.create_text(25, offset_y + (1.0 * cell_size),
                           text="TATSAECHLICH\n(ACTUAL)", fill=COLOR_ACCENT, font=("Segoe UI", 12, "bold"), justify="center", angle=90)
        
        # Draw Cells
        for r in range(2):
            for c in range(2):
                val = cm[r][c]
                total = row_totals[r] if row_totals[r] > 0 else 1
                ratio = val / total
                
                # Main diagonal is true hits (Green), others are misses (Red/Muted)
                if r == c:
                    color_intensity = int(50 + (ratio * 150))
                    hex_color = f"#00{color_intensity:02x}00"
                    text_color = "#ffffff"
                else:
                    color_intensity = int(30 + (ratio * 100))
                    hex_color = f"#{color_intensity:02x}1a1a"
                    text_color = FG_MUTED
                    
                x1 = offset_x + (c * cell_size)
                y1 = offset_y + (r * cell_size)
                x2 = x1 + cell_size
                y2 = y1 + cell_size
                
                canvas.create_rectangle(x1, y1, x2, y2, fill=hex_color, outline=BORDER_COLOR, width=1)
                
                # Value and percentage
                canvas.create_text(x1 + (cell_size / 2), y1 + (cell_size / 2) - 12,
                                   text=f"{val:,}", fill=text_color, font=("Consolas", 16, "bold"))
                
                canvas.create_text(x1 + (cell_size / 2), y1 + (cell_size / 2) + 14,
                                   text=f"{ratio*100:.1f}%", fill=COLOR_ACCENT if r == c else FG_MUTED, font=("Segoe UI", 10))

    def render_console_tab(self, frame):
        """Displays scrolling text area showing subprocess training logs."""
        lbl_title = tk.Label(frame, text="Subprozess Trainings-Logs (Live-Konsole)", bg=BG_DARK, fg=FG_LIGHT, font=("Segoe UI", 14, "bold"))
        lbl_title.pack(anchor="w", pady=(0, 10))
        
        self.txt_console = scrolledtext.ScrolledText(
            frame, 
            bg="#0c0c0c", 
            fg="#00ff00", 
            insertbackground="#ffffff",
            font=("Consolas", 9),
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR
        )
        self.txt_console.pack(fill="both", expand=True, pady=5)
        
        self.txt_console.insert(tk.END, "=== AUDUSD M5 EA Pipeline Console Ready ===\n")
        self.txt_console.insert(tk.END, "Klicke links auf 'Modell neu anlernen', um das Training zu starten und die Ausgabe hier live zu sehen.\n")
        self.txt_console.configure(state="disabled")

    def log_to_console(self, text):
        """Appends output text to the console scrollarea in a thread-safe manner."""
        if not hasattr(self, 'txt_console') or not self.txt_console.winfo_exists():
            return
            
        self.txt_console.configure(state="normal")
        self.txt_console.insert(tk.END, text)
        self.txt_console.see(tk.END)
        self.txt_console.configure(state="disabled")

    def start_training_thread(self):
        """Triggers model training script on a background worker thread."""
        if self.is_training:
            messagebox.showwarning("Training läuft", "Es läuft bereits ein Trainings-Prozess. Bitte warte, bis dieser beendet ist.")
            return
            
        self.is_training = True
        self.btn_train.config(state="disabled", bg=BG_CARD)
        self.lbl_status_val.config(text="Modell lernt...", fg=COLOR_BLUE)
        
        self.switch_tab("console")
        self.txt_console.configure(state="normal")
        self.txt_console.delete("1.0", tk.END)
        self.txt_console.configure(state="disabled")
        
        t = threading.Thread(target=self.run_training_process, daemon=True)
        t.start()

    def run_training_process(self):
        """Executes 02_train_gatekeeper.py via subprocess and reads output line by line."""
        self.log_to_console("Starte Trainings-Subprozess...\n")
        self.log_to_console(f"Script: {TRAIN_SCRIPT_PATH}\n\n")
        
        try:
            cmd = [sys.executable, TRAIN_SCRIPT_PATH]
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True, 
                bufsize=1,
                cwd=BASE_DIR
            )
            
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                self.root.after(0, self.log_to_console, line)
                
            process.wait()
            exit_code = process.returncode
            
            self.root.after(0, self.finalize_training, exit_code)
            
        except Exception as e:
            self.root.after(0, self.log_to_console, f"\nCRITICAL ERROR: {str(e)}\n")
            self.root.after(0, self.finalize_training, -1)

    def finalize_training(self, exit_code):
        """Refreshes layouts, metrics, and updates status labels in GUI."""
        self.is_training = False
        self.btn_train.config(state="normal", bg=COLOR_ACCENT)
        
        if exit_code == 0:
            self.lbl_status_val.config(text="Idle (Bereit)", fg=COLOR_GREEN)
            self.log_to_console("\n=== TRAINING ERFOLGREICH BEENDET ===\n")
            self.load_metrics_data()
            self.switch_tab("metrics")
            messagebox.showinfo("Erfolg", "Das Modell wurde erfolgreich trainiert und gatekeeper.onnx aktualisiert!")
        else:
            self.lbl_status_val.config(text="Fehler!", fg=COLOR_RED)
            self.log_to_console(f"\n=== FEHLER BEIM TRAINING: EXIT-CODE {exit_code} ===\n")
            messagebox.showerror("Fehler", f"Das Modell-Training ist mit dem Fehler-Code {exit_code} abgebrochen. Siehe Logs in der Live-Konsole.")


def main():
    root = tk.Tk()
    app = MLPipelineGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

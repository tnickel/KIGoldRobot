#!/usr/bin/env python3
"""
Phase 5: Graphical Pipeline Interface (04_pipeline_gui.py)
----------------------------------------------------------
A modern, dark-themed Tkinter desktop application to visualize
the ML training pipeline, displaying model accuracies, classification
reports, feature sets, and interactive confusion matrices.
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
TRAIN_SCRIPT_PATH = os.path.join(BASE_DIR, "python_scripts", "02_train_model.py")

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


class MLPipelineGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Gold ONNX Trading Bot - ML Pipeline Dashboard")
        self.root.geometry("1100x700")
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
        lbl_logo = tk.Label(sidebar, text="KIGoldRobot 📈", bg=BG_SIDEBAR, fg=COLOR_ACCENT, font=("Segoe UI", 18, "bold"))
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
        
        # Parameters Summary list
        self.param_frame = tk.Frame(sidebar, bg=BG_SIDEBAR)
        self.param_frame.pack(fill="x", padx=20, pady=15)
        
        # Spacer
        spacer = tk.Label(sidebar, bg=BG_SIDEBAR)
        spacer.pack(fill="both", expand=True)
        
        # Action Buttons
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
        box.grid(row=0, column=col, sticky="nsew")
        
        lbl_l = tk.Label(box, text=label.upper(), bg=BG_CARD, fg=FG_MUTED, font=("Segoe UI", 8, "bold"))
        lbl_l.pack(anchor="w")
        
        lbl_v = tk.Label(box, text=value, bg=BG_CARD, fg=COLOR_ACCENT, font=("Segoe UI", 12, "bold"))
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
            ("features", "⚙️ Features (16)"),
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
        # Unpack current frame
        if hasattr(self, 'active_tab') and self.active_tab:
            self.tab_frames[self.active_tab].grid_forget()
            self.tab_buttons[self.active_tab].config(bg=BG_CARD, fg=FG_MUTED, highlightthickness=0)
            
        self.active_tab = target_tab
        
        # Pack target frame
        self.tab_frames[target_tab].grid(row=1, column=0, sticky="nsew")
        self.tab_buttons[target_tab].config(bg=COLOR_BLUE, fg="#ffffff")
        
        # Populate tabs if data exists
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
            
        self.add_param_val("Instrument:", "XAUUSD (Gold)")
        self.add_param_val("Timeframe:", "M30")
        
        if self.metrics and "algorithm" in self.metrics:
            algo = self.metrics["algorithm"]
            params = algo.get("parameters", {})
            self.add_param_val("Lernalgo:", algo.get("name", "Random Forest"))
            self.add_param_val("Schätzer (Bäume):", str(params.get("n_estimators", 150)))
            self.add_param_val("Max. Tiefe:", str(params.get("max_depth", 6)))
        else:
            self.add_param_val("Lernalgo:", "Random Forest (ONNX)")
            
        feat_count = self.metrics.get("feature_count", 16) if self.metrics else 16
        self.add_param_val("Features:", f"{feat_count} Features active")
        self.add_param_val("Targets:", "3 Classes (-1, 0, 1)")

            
    def render_tab_content(self, tab_id):
        """Renders specific widgets in selected tab frames."""
        frame = self.tab_frames[tab_id]
        
        # Clear frame children first to redraw fresh
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
        
        # Top title
        lbl_title = tk.Label(frame, text="Modell-Genauigkeit (Accuracy)", bg=BG_DARK, fg=FG_LIGHT, font=("Segoe UI", 14, "bold"))
        lbl_title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 15))
        
        # Accuracy cards
        accs = self.metrics.get("accuracies", {})
        splits = [
            ("Trainings-Daten (70%)", accs.get("train", 0.0), COLOR_GREEN),
            ("Validierungs-Daten (15%)", accs.get("val", 0.0), COLOR_BLUE),
            ("Test-Daten (15% Out-of-Sample)", accs.get("test", 0.0), COLOR_ACCENT)
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
            
        # Detailed Reports Table below cards
        lbl_table_t = tk.Label(frame, text="Detaillierter Testset-Klassifizierungsbericht", bg=BG_DARK, fg=FG_LIGHT, font=("Segoe UI", 12, "bold"))
        lbl_table_t.grid(row=2, column=0, columnspan=3, sticky="w", pady=(25, 10))
        
        table_frame = tk.Frame(frame, bg=BG_CARD, bd=0, highlightthickness=1, highlightbackground=BORDER_COLOR)
        table_frame.grid(row=3, column=0, columnspan=3, sticky="nsew")
        
        # Grid layout for table headers
        headers = ["Klasse (Richtung)", "Precision (Genauigkeit)", "Recall (Trefferquote)", "F1-Score", "Support (Anzahl)"]
        for col_idx, header in enumerate(headers):
            lbl_h = tk.Label(table_frame, text=header, bg=BORDER_COLOR, fg=FG_LIGHT, font=("Segoe UI", 9, "bold"), padx=10, pady=8)
            lbl_h.grid(row=0, column=col_idx, sticky="ew")
            table_frame.grid_columnconfigure(col_idx, weight=1)
            
        report_data = self.metrics.get("classification_reports", {}).get("test", {})
        classes_map = {
            "-1": "Verkauf (-1)",
            "0": "Neutral / Hold (0)",
            "1": "Kauf (1)"
        }
        
        row_idx = 1
        for k, name in classes_map.items():
            if k in report_data:
                item = report_data[k]
                bg_col = BG_CARD if row_idx % 2 == 0 else "#252525"
                
                tk.Label(table_frame, text=name, bg=bg_col, fg=COLOR_ACCENT if k != "0" else FG_LIGHT, font=("Segoe UI", 9, "bold"), pady=6).grid(row=row_idx, column=0, sticky="ew")
                tk.Label(table_frame, text=f"{item['precision']*100:.1f}%", bg=bg_col, fg=FG_LIGHT, font=("Segoe UI", 9), pady=6).grid(row=row_idx, column=1, sticky="ew")
                tk.Label(table_frame, text=f"{item['recall']*100:.1f}%", bg=bg_col, fg=FG_LIGHT, font=("Segoe UI", 9), pady=6).grid(row=row_idx, column=2, sticky="ew")
                tk.Label(table_frame, text=f"{item['f1-score']*100:.1f}%", bg=bg_col, fg=FG_LIGHT, font=("Segoe UI", 9), pady=6).grid(row=row_idx, column=3, sticky="ew")
                tk.Label(table_frame, text=str(int(item['support'])), bg=bg_col, fg=FG_MUTED, font=("Segoe UI", 9), pady=6).grid(row=row_idx, column=4, sticky="ew")
                row_idx += 1
                
        # Forest structural details card below table
        if "forest_details" in self.metrics:
            details = self.metrics["forest_details"]
            
            lbl_forest_t = tk.Label(frame, text="Struktur des gelernten Random Forest (Wald-Größe)", bg=BG_DARK, fg=FG_LIGHT, font=("Segoe UI", 12, "bold"))
            lbl_forest_t.grid(row=4, column=0, columnspan=3, sticky="w", pady=(25, 10))
            
            forest_frame = tk.Frame(frame, bg=BG_CARD, bd=0, highlightthickness=1, highlightbackground=BORDER_COLOR, padx=15, pady=12)
            forest_frame.grid(row=5, column=0, columnspan=3, sticky="ew")
            
            # Subgrid inside forest details
            forest_frame.grid_columnconfigure(0, weight=1)
            forest_frame.grid_columnconfigure(1, weight=1)
            forest_frame.grid_columnconfigure(2, weight=1)
            forest_frame.grid_columnconfigure(3, weight=1)
            
            # Details:
            # 1. Total trees
            self.add_detail_box(forest_frame, 0, "Bäume gesamt (Trees)", str(details.get("n_estimators", 150)))
            # 2. Total nodes
            self.add_detail_box(forest_frame, 1, "Knoten gesamt (Nodes)", f"{details.get('total_nodes', 0):,}")
            # 3. Avg nodes
            self.add_detail_box(forest_frame, 2, "Ø Knoten pro Baum", f"{details.get('avg_nodes_per_tree', 0.0):.1f}")
            # 4. ONNX size
            onnx_kb = details.get("onnx_size_bytes", 0) / 1024.0
            self.add_detail_box(forest_frame, 3, "ONNX Dateigröße", f"{onnx_kb:.1f} KB")


    def render_features_tab(self, frame):
        """Displays list of 16 features mapping inside the ONNX model."""
        lbl_title = tk.Label(frame, text="ONNX-Modell Eingangsfeatures (Eingabevektor: 16 Dimensionen)", bg=BG_DARK, fg=FG_LIGHT, font=("Segoe UI", 14, "bold"))
        lbl_title.pack(anchor="w", pady=(0, 15))
        
        desc_label = tk.Label(frame, text="Diese 16 Features werden bei jeder neuen M30-Kerze live in MT5 kopiert, ATR-normalisiert und in die eingebettete model.onnx-Ressource eingespeist:", bg=BG_DARK, fg=FG_MUTED, wraplength=750, justify="left", font=("Segoe UI", 10))
        desc_label.pack(anchor="w", pady=(0, 15))
        
        # Grid frame for features list
        grid_frame = tk.Frame(frame, bg=BG_DARK)
        grid_frame.pack(fill="both", expand=True)
        
        features_list = self.metrics.get("features", [])
        
        feature_descriptions = {
            "atr": "Average True Range (14) - Gold Volatilität",
            "rsi": "Relative Strength Index (14) - Gold Momentum",
            "dist_ema20": "Abstand Gold Close zur EMA(20) (ATR-normalisiert)",
            "dist_ema50": "Abstand Gold Close zur EMA(50) (ATR-normalisiert)",
            "dist_sma200": "Abstand Gold Close zur SMA(200) (ATR-normalisiert)",
            "macd_diff_norm": "MACD-Signal-Differenz (ATR-normalisiert)",
            "body_size_norm": "Körpergröße der Kerze (ATR-normalisiert)",
            "upper_shadow_norm": "Obere Kerzenschatten-Größe (ATR-normalisiert)",
            "lower_shadow_norm": "Untere Kerzenschatten-Größe (ATR-normalisiert)",
            "tick_volume_ratio": "Kerzen-Tick-Volumen relativ zum 20er Durchschnitt",
            "dxy_dist_ema20": "Dollar Index (DXY) Close-EMA(20) Abstand",
            "vix_close": "Rohwert des Volatilitätsindex (VIX Close)",
            "sin_hour": "Zyklische Stunde des Tages (Sinus-Komponente)",
            "cos_hour": "Zyklische Stunde des Tages (Cosinus-Komponente)",
            "sin_day": "Zyklischer Wochentag (Sinus-Komponente)",
            "cos_day": "Zyklischer Wochentag (Cosinus-Komponente)"
        }
        
        # Draw 2 columns of 8 features each
        half = (len(features_list) + 1) // 2
        for col in range(2):
            col_frame = tk.Frame(grid_frame, bg=BG_DARK)
            col_frame.pack(side="left", fill="both", expand=True, padx=10)
            
            start = col * half
            end = min(start + half, len(features_list))
            
            for idx in range(start, end):
                f_name = features_list[idx]
                card = tk.Frame(col_frame, bg=BG_CARD, bd=0, highlightthickness=1, highlightbackground=BORDER_COLOR, pady=10, padx=15)
                card.pack(fill="x", pady=5)
                
                lbl_num = tk.Label(card, text=f"INPUT [{idx:02d}]:", bg=BG_CARD, fg=COLOR_ACCENT, font=("Consolas", 9, "bold"))
                lbl_num.pack(anchor="w")
                
                lbl_n = tk.Label(card, text=f_name, bg=BG_CARD, fg=FG_LIGHT, font=("Consolas", 10, "bold"))
                lbl_n.pack(anchor="w")
                
                desc = feature_descriptions.get(f_name, "Gold Modell Feature")
                lbl_d = tk.Label(card, text=desc, bg=BG_CARD, fg=FG_MUTED, font=("Segoe UI", 8))
                lbl_d.pack(anchor="w", pady=(2, 0))

    def render_confusion_tab(self, frame):
        """Draws a custom heatmap visualization of the test confusion matrix."""
        lbl_title = tk.Label(frame, text="Klassifizierungs-Konfusionsmatrix (Testdaten)", bg=BG_DARK, fg=FG_LIGHT, font=("Segoe UI", 14, "bold"))
        lbl_title.pack(anchor="w", pady=(0, 10))
        
        desc = tk.Label(frame, text="Zeigt die tatsächlichen (Actual) Richtungen gegen die vom Modell vorhergesagten (Predicted) Richtungen.", bg=BG_DARK, fg=FG_MUTED, font=("Segoe UI", 10))
        desc.pack(anchor="w", pady=(0, 15))
        
        cm = self.metrics.get("confusion_matrices", {}).get("test", [])
        if not cm or len(cm) != 3:
            lbl_err = tk.Label(frame, text="Fehlerhafte Konfusionsmatrix-Daten.", bg=BG_DARK, fg=COLOR_RED, font=("Segoe UI", 11, "bold"))
            lbl_err.pack(pady=20)
            return
            
        canvas_width = 500
        canvas_height = 420
        canvas = tk.Canvas(frame, width=canvas_width, height=canvas_height, bg=BG_DARK, highlightthickness=0)
        canvas.pack(pady=10)
        
        # Grid constants
        offset_x = 120  # Left label spacer
        offset_y = 50   # Top label spacer
        cell_size = 95
        
        labels = ["VERKAUF (-1)", "NEUTRAL (0)", "KAUF (1)"]
        
        # Compute row totals for percentage intensity shading
        row_totals = [sum(row) for row in cm]
        
        # Draw Labels and Grid
        for i in range(3):
            # Row labels (Actual)
            canvas.create_text(offset_x - 15, offset_y + (i * cell_size) + (cell_size / 2),
                               text=labels[i], fill=FG_LIGHT, font=("Segoe UI", 9, "bold"), anchor="e")
            # Column labels (Predicted)
            canvas.create_text(offset_x + (i * cell_size) + (cell_size / 2), offset_y - 15,
                               text=labels[i], fill=FG_LIGHT, font=("Segoe UI", 9, "bold"), anchor="s")
                               
        # Main Actual / Predicted titles
        canvas.create_text(offset_x + (1.5 * cell_size), offset_y - 35,
                           text="VORHERGESAGT (PREDICTED)", fill=COLOR_ACCENT, font=("Segoe UI", 11, "bold"))
                           
        # Vertical Actual title needs rotation, drawing character by character as a fallback
        canvas.create_text(15, offset_y + (1.5 * cell_size),
                           text="TATSAECHLICH\n(ACTUAL)", fill=COLOR_ACCENT, font=("Segoe UI", 11, "bold"), justify="center", angle=90)
        
        # Draw Cells
        for r in range(3):
            for c in range(3):
                val = cm[r][c]
                total = row_totals[r] if row_totals[r] > 0 else 1
                ratio = val / total
                
                # Shading color based on match/miss
                # Main diagonal is true hits (Green), others are misses (Red/Muted)
                if r == c:
                    # Scale green intensity
                    color_intensity = int(50 + (ratio * 150))
                    hex_color = f"#00{color_intensity:02x}00"
                    text_color = "#ffffff"
                else:
                    # Misses
                    color_intensity = int(30 + (ratio * 100))
                    hex_color = f"#{color_intensity:02x}1a1a"
                    text_color = FG_MUTED
                    
                x1 = offset_x + (c * cell_size)
                y1 = offset_y + (r * cell_size)
                x2 = x1 + cell_size
                y2 = y1 + cell_size
                
                # Draw cell box
                canvas.create_rectangle(x1, y1, x2, y2, fill=hex_color, outline=BORDER_COLOR, width=1)
                
                # Draw numeric value
                canvas.create_text(x1 + (cell_size / 2), y1 + (cell_size / 2) - 10,
                                   text=f"{val}", fill=text_color, font=("Consolas", 14, "bold"))
                
                # Draw percentage
                canvas.create_text(x1 + (cell_size / 2), y1 + (cell_size / 2) + 12,
                                   text=f"{ratio*100:.1f}%", fill=COLOR_ACCENT if r == c else FG_MUTED, font=("Segoe UI", 8))

    def render_console_tab(self, frame):
        """Displays scrolling text area showing subprocess training logs."""
        lbl_title = tk.Label(frame, text="Subprozess Trainings-Logs (Live-Konsole)", bg=BG_DARK, fg=FG_LIGHT, font=("Segoe UI", 14, "bold"))
        lbl_title.pack(anchor="w", pady=(0, 10))
        
        # ScrolledText console view
        self.txt_console = scrolledtext.ScrolledText(
            frame, 
            bg="#0c0c0c", 
            fg="#00ff00", # Classic Matrix Green
            insertbackground="#ffffff",
            font=("Consolas", 9),
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR
        )
        self.txt_console.pack(fill="both", expand=True, pady=5)
        
        # Load previous compile log if exists, else welcome
        self.txt_console.insert(tk.END, "=== Gold ONNX Robot Pipeline Console Ready ===\n")
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
        
        # Switch to console tab immediately
        self.switch_tab("console")
        self.txt_console.configure(state="normal")
        self.txt_console.delete("1.0", tk.END)
        self.txt_console.configure(state="disabled")
        
        # Spawn thread
        t = threading.Thread(target=self.run_training_process, daemon=True)
        t.start()

    def run_training_process(self):
        """Executes 02_train_model.py via subprocess and reads output line by line."""
        self.log_to_console("Starte Trainings-Subprozess...\n")
        self.log_to_console(f"Script: {TRAIN_SCRIPT_PATH}\n\n")
        
        try:
            # Execute python script
            cmd = [sys.executable, TRAIN_SCRIPT_PATH]
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True, 
                bufsize=1,
                cwd=BASE_DIR
            )
            
            # Read stdout line by line
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                # Schedule log update to run in main Tkinter thread
                self.root.after(0, self.log_to_console, line)
                
            process.wait()
            exit_code = process.returncode
            
            # Finalize execution in main thread
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
            # Reload fresh metrics
            self.load_metrics_data()
            self.switch_tab("metrics")
            messagebox.showinfo("Erfolg", "Das Modell wurde erfolgreich trainiert und model.onnx aktualisiert!")
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

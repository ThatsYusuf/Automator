import customtkinter as ctk
from tkinter import messagebox, simpledialog
import threading
import time
import json
import os
import random
import logging
import sys
from pynput import mouse, keyboard


#  LOGGING CONFIGURATION
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("desktop_automation.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class AutomationStudio(ctk.CTk):
    def __init__(self):
        super().__init__()
        logging.info("Initialising")

        self.title("Automater")
        self.geometry("780x640")
        self.resizable(False, False)

        # Config States
        self.macro_events = []
        self.saved_macros = {}
        self.is_recording = False
        self.is_playing = False
        self.is_spammer_active = False
        self.start_time = None
        self.save_file = "automation_profiles.json"

        # Telemetry State Trackers
        self.total_actions_dispatched = 0
        self.automation_start_timestamp = 0.0
        self.is_telemetry_loop_running = False

        # Interactive UI Register Holds
        self.listening_target = None
        self.current_active_tab = "macro"

        # Combo Key State Tracking Engine
        self.currently_pressed_keys = set()
        self.temp_combo_buffer = set()

        self.load_profiles_from_disk()

        # Listeners
        self.mouse_listener = None
        self.keyboard_listener = None
        self.global_keybind_listener = None

        self.setup_ui()
        self.start_global_keybind_monitor()
        self.switch_tab("macro")
        logging.info("Application context fully loaded and operational.")

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        #
        # Sidebar Controls
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color="#121218")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1)

        brand = ctk.CTkLabel(self.sidebar, text="Automater 67",
                             font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color="#A78BFA")
        brand.grid(row=0, column=0, padx=20, pady=25)

        self.nav_macro_btn = ctk.CTkButton(self.sidebar, text="🎥 Macro Recorder", fg_color="transparent",
                                           text_color="#94A3B8", hover_color="#1E1E28", anchor="w",
                                           command=lambda: self.switch_tab("macro"))
        self.nav_macro_btn.grid(row=1, column=0, padx=15, pady=5, sticky="ew")

        self.nav_spammer_btn = ctk.CTkButton(self.sidebar, text="⚡ Autoclicker", fg_color="transparent",
                                             text_color="#94A3B8", hover_color="#1E1E28", anchor="w",
                                             command=lambda: self.switch_tab("spammer"))
        self.nav_spammer_btn.grid(row=2, column=0, padx=15, pady=5, sticky="ew")

        self.nav_profiles_btn = ctk.CTkButton(self.sidebar, text="📁 Save Files", fg_color="transparent",
                                              text_color="#94A3B8", hover_color="#1E1E28", anchor="w",
                                              command=lambda: self.switch_tab("profiles"))
        self.nav_profiles_btn.grid(row=3, column=0, padx=15, pady=5, sticky="ew")

        self.keybinds_enabled_var = ctk.BooleanVar(value=True)
        self.keybinds_switch = ctk.CTkSwitch(
            self.sidebar,
            text="Enable Global Keybinds",
            variable=self.keybinds_enabled_var,
            progress_color="#A78BFA",
            text_color="#94A3B8",
            font=ctk.CTkFont(size=11, weight="normal"),
            command=self.on_keybinds_switch_toggle
        )
        self.keybinds_switch.grid(row=5, column=0, padx=20, pady=(10, 25), sticky="w")


        # Main Cont
        self.container = ctk.CTkFrame(self, corner_radius=0, fg_color="#0B0B0E")
        self.container.grid(row=0, column=1, sticky="nsew", padx=25, pady=20)
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        vcmd = (self.register(self.validate_numeric), '%P')


        # Macro Tab
        self.tab_macro = ctk.CTkFrame(self.container, fg_color="transparent")
        macro_ctrls = ctk.CTkFrame(self.tab_macro, fg_color="#121218", border_width=1, border_color="#1E1E28")
        macro_ctrls.pack(fill="x", pady=(0, 15), ipady=10)

        ctk.CTkLabel(macro_ctrls, text="Macro PANEL", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#64748B").pack(anchor="w", padx=15, pady=10)

        m_btn_row = ctk.CTkFrame(macro_ctrls, fg_color="transparent")
        m_btn_row.pack(fill="x", padx=15)

        self.record_btn = ctk.CTkButton(m_btn_row, text="🔴 Record", fg_color="#EF4444", hover_color="#DC2626",
                                        text_color="#FFFFFF", text_color_disabled="#94A3B8",
                                        font=ctk.CTkFont(weight="bold"), command=self.toggle_recording)
        self.record_btn.pack(side="left", expand=True, fill="x", padx=4)

        self.play_btn = ctk.CTkButton(m_btn_row, text="▶ Play", fg_color="#3B82F6", hover_color="#2563EB",
                                      text_color="#FFFFFF", text_color_disabled="#4B5563",
                                      font=ctk.CTkFont(weight="bold"), state="disabled", command=self.start_playback)
        self.play_btn.pack(side="left", expand=True, fill="x", padx=4)

        self.clear_btn = ctk.CTkButton(m_btn_row, text="🗑 Purge", fg_color="#374151", hover_color="#4B5563",
                                       text_color="#FFFFFF", text_color_disabled="#4B5563",
                                       font=ctk.CTkFont(weight="bold"), state="disabled", command=self.clear_macro)
        self.clear_btn.pack(side="left", expand=True, fill="x", padx=4)

        tweaks_row = ctk.CTkFrame(macro_ctrls, fg_color="transparent")
        tweaks_row.pack(fill="x", padx=15, pady=(15, 5))

        ctk.CTkLabel(tweaks_row, text="Loops (0=∞):", text_color="#94A3B8").pack(side="left", padx=5)
        self.loop_entry = ctk.CTkEntry(tweaks_row, width=50, fg_color="#1E1E28", border_color="#2B2B3A",
                                       text_color="#FFFFFF", justify="center", validate="key", validatecommand=vcmd)
        self.loop_entry.insert(0, "1")
        self.loop_entry.pack(side="left", padx=5)

        ctk.CTkLabel(tweaks_row, text="Keybind:", text_color="#94A3B8").pack(side="left", padx=(15, 5))

        self.macro_keybind_btn = ctk.CTkButton(tweaks_row, text="ctrl+f4", width=95, fg_color="#1E293B",
                                               hover_color="#334155", text_color="#FFFFFF", border_width=1,
                                               border_color="#334155", font=ctk.CTkFont(weight="bold"))
        self.macro_keybind_btn.bind("<Button-1>",
                                    lambda e: self.activate_key_listener(self.macro_keybind_btn, e, default_bg="#1E293B"))
        self.macro_keybind_btn.pack(side="left", padx=5)

        self.human_macro_var = ctk.BooleanVar(value=True)
        self.human_macro_cb = ctk.CTkCheckBox(tweaks_row, text="Interval Variance",
                                              variable=self.human_macro_var, text_color="#94A3B8",
                                              font=ctk.CTkFont(size=12))
        self.human_macro_cb.pack(side="right", padx=10)

        ctk.CTkLabel(self.tab_macro, text="LIVE RECORDED TIMELINE (Click items to delete)",
                     font=ctk.CTkFont(size=11, weight="bold"), text_color="#64748B").pack(anchor="w", pady=(5, 5))
        self.timeline_frame = ctk.CTkScrollableFrame(self.tab_macro, fg_color="#121218", border_width=1,
                                                     border_color="#1E1E28")
        self.timeline_frame.pack(fill="both", expand=True)


        # Autoclicker Tab
        self.tab_spammer = ctk.CTkFrame(self.container, fg_color="transparent")
        spam_card = ctk.CTkFrame(self.tab_spammer, fg_color="#121218", border_width=1, border_color="#1E1E28")
        spam_card.pack(fill="x", ipady=15)

        ctk.CTkLabel(spam_card, text="SPAM CONFIGURATION", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#64748B").pack(anchor="w", padx=20, pady=15)

        grid_wrap = ctk.CTkFrame(spam_card, fg_color="transparent")
        grid_wrap.pack(fill="x", padx=20)
        grid_wrap.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(grid_wrap, text="Target Key / Click:", text_color="#94A3B8").grid(row=0, column=0, sticky="w",
                                                                                       pady=6)

        self.target_key_btn = ctk.CTkButton(grid_wrap, text="LeftClick", fg_color="#2E1065", hover_color="#4C1D95",
                                            text_color="#FFFFFF",
                                            border_width=1, border_color="#4C1D95", font=ctk.CTkFont(weight="bold"))
        self.target_key_btn.bind("<Button-1>",
                                 lambda e: self.activate_key_listener(self.target_key_btn, e, default_bg="#2E1065"))
        self.target_key_btn.bind("<Button-3>",
                                 lambda e: self.activate_key_listener(self.target_key_btn, e, default_bg="#2E1065"))
        self.target_key_btn.grid(row=0, column=1, sticky="ew", pady=6)

        ctk.CTkLabel(grid_wrap, text="Delay Interval (seconds):", text_color="#94A3B8").grid(row=1, column=0,
                                                                                             sticky="w", pady=6)
        self.interval_entry = ctk.CTkEntry(grid_wrap, fg_color="#1E1E28", border_color="#2B2B3A", text_color="#FFFFFF",
                                           justify="center")
        self.interval_entry.insert(0, "0.05")
        self.interval_entry.grid(row=1, column=1, sticky="ew", pady=6)

        ctk.CTkLabel(grid_wrap, text="Activation Mode:", text_color="#94A3B8").grid(row=2, column=0, sticky="w", pady=6)
        self.spam_mode_menu = ctk.CTkOptionMenu(grid_wrap, values=["Toggle Mode", "Hold Mode"], fg_color="#1E1E28",
                                                text_color="#FFFFFF", button_color="#2B2B3A")
        self.spam_mode_menu.grid(row=2, column=1, sticky="ew", pady=6)

        ctk.CTkLabel(grid_wrap, text="Toggle Keybind Bind:", text_color="#94A3B8").grid(row=3, column=0, sticky="w",
                                                                                       pady=6)

        self.spammer_keybind_btn = ctk.CTkButton(grid_wrap, text="ctrl+f3", fg_color="#1E1B4B", hover_color="#312E81",
                                                text_color="#FFFFFF",
                                                border_width=1, border_color="#312E81", font=ctk.CTkFont(weight="bold"))
        self.spammer_keybind_btn.bind("<Button-1>", lambda e: self.activate_key_listener(self.spammer_keybind_btn, e,
                                                                                        default_bg="#1E1B4B"))
        self.spammer_keybind_btn.grid(row=3, column=1, sticky="ew", pady=6)

        self.human_spam_var = ctk.BooleanVar(value=False)
        self.human_spam_cb = ctk.CTkCheckBox(spam_card, text="Enable Jitter Variance ",
                                             variable=self.human_spam_var, text_color="#94A3B8")
        self.human_spam_cb.pack(pady=20, padx=20, anchor="w")

        self.spammer_status_label = ctk.CTkLabel(self.tab_spammer, text="AUTOMATION MODULE INACTIVE",
                                                 font=ctk.CTkFont(size=13, weight="bold"), text_color="#EF4444")
        self.spammer_status_label.pack(pady=40)


        # Saves Tab
        self.tab_profiles = ctk.CTkFrame(self.container, fg_color="transparent")
        prof_card = ctk.CTkFrame(self.tab_profiles, fg_color="#121218", border_width=1, border_color="#1E1E28")
        prof_card.pack(fill="x", ipady=20)

        ctk.CTkLabel(prof_card, text="Saved Configurations", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#64748B").pack(anchor="w", padx=20, pady=15)

        self.profile_var = ctk.StringVar(value="Select Save File")
        self.profile_menu = ctk.CTkOptionMenu(prof_card, variable=self.profile_var, values=self.get_profile_list(),
                                              command=self.load_selected_profile, fg_color="#1E1E28",
                                              text_color="#FFFFFF", button_color="#2B2B3A")
        self.profile_menu.pack(fill="x", padx=20, pady=10)

        p_btn_row = ctk.CTkFrame(prof_card, fg_color="transparent")
        p_btn_row.pack(fill="x", padx=16, pady=10)

        self.save_btn = ctk.CTkButton(
            p_btn_row,
            text="💾 Save",
            fg_color="#10B981",
            hover_color="#059669",
            text_color="#FFFFFF",
            text_color_disabled="#1F2937",
            font=ctk.CTkFont(weight="bold"),
            state="disabled",
            command=self.save_macro_prompt
        )
        self.save_btn.pack(fill="x", expand=True, padx=4)


        #Dashboard Panel
        self.telemetry_strip = ctk.CTkFrame(self.container, fg_color="#121218", border_width=1, border_color="#1E1E28",
                                            height=40)
        self.telemetry_strip.pack(fill="x", side="bottom", pady=(10, 0))
        self.telemetry_strip.pack_propagate(False)

        self.lbl_dispatched = ctk.CTkLabel(self.telemetry_strip, text="Actions Dispatched: 0",
                                           font=ctk.CTkFont(size=12, family="Courier"), text_color="#34D399")
        self.lbl_dispatched.pack(side="left", padx=20)

        self.lbl_runtime = ctk.CTkLabel(self.telemetry_strip, text="Active Runtime: 0.00s",
                                        font=ctk.CTkFont(size=12, family="Courier"), text_color="#60A5FA")
        self.lbl_runtime.pack(side="right", padx=20)

        #Window Overlay
        self.modal_overlay = ctk.CTkFrame(self, fg_color="#060608", corner_radius=0)
        modal_card = ctk.CTkFrame(self.modal_overlay, fg_color="#121218", border_width=1, border_color="#1E1E28",
                                  width=340, height=200)
        modal_card.place(relx=0.5, rely=0.4, anchor="center")
        modal_card.pack_propagate(False)

        ctk.CTkLabel(modal_card, text="COMMIT DESKTOP WORKFLOW TO DISK", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#64748B").pack(anchor="w", padx=20, pady=(15, 5))
        self.modal_entry = ctk.CTkEntry(modal_card, fg_color="#1E1E28", border_color="#2B2B3A", text_color="#FFFFFF",
                                        placeholder_text="e.g., DataEntry_Template")
        self.modal_entry.pack(fill="x", padx=20, pady=15)

        m_btn_row = ctk.CTkFrame(modal_card, fg_color="transparent")
        m_btn_row.pack(fill="x", padx=16)
        ctk.CTkButton(m_btn_row, text="Cancel", fg_color="#374151", text_color="#FFFFFF",
                      command=self.close_save_modal).pack(side="left",
                                                          expand=True,
                                                          fill="x",
                                                          padx=4)
        ctk.CTkButton(m_btn_row, text="Confirm", fg_color="#10B981", text_color="#FFFFFF",
                      command=self.confirm_save_modal).pack(side="right",
                                                            expand=True,
                                                            fill="x",
                                                            padx=4)
        self.modal_entry.bind("<Return>", lambda e: self.confirm_save_modal())

    def switch_tab(self, destination):
        self.current_active_tab = destination
        tabs = {"macro": self.tab_macro, "spammer": self.tab_spammer, "profiles": self.tab_profiles}
        btns = {"macro": self.nav_macro_btn, "spammer": self.nav_spammer_btn, "profiles": self.nav_profiles_btn}
        for k, view in tabs.items():
            if k == destination:
                view.pack(fill="both", expand=True)
                btns[k].configure(fg_color="#1E1E28", text_color="#FFFFFF")
            else:
                view.pack_forget()
                btns[k].configure(fg_color="transparent", text_color="#94A3B8")

    def validate_numeric(self, P):
        return P == "" or P.isdigit()

    def on_keybinds_switch_toggle(self):
        if self.keybinds_enabled_var.get():
            logging.info("System keyboard event interception links enabled.")
        else:
            logging.warning("System keybind temporarily decoupled.")
            self.stop_spammer()
            self.is_playing = False

    def rebuild_timeline_view(self):
        for item in self.timeline_frame.winfo_children(): item.destroy()
        if not self.macro_events:
            ctk.CTkLabel(self.timeline_frame,
                         text="Empty execution sequence. Press record to generate telemetry actions.",
                         text_color="#475569", font=ctk.CTkFont(slant="italic")).pack(pady=40)
            return
        for idx, (timestamp, event, note) in enumerate(self.macro_events):
            row = ctk.CTkFrame(self.timeline_frame, fg_color="#1E1E28", height=32)
            row.pack(fill="x", pady=2, padx=5)
            row.pack_propagate(False)
            ctk.CTkLabel(row, text=f"⏱ [{timestamp:.2f}s]  ➔  Type: {event.upper()} ({note})", text_color="#94A3B8",
                         font=ctk.CTkFont(size=12)).pack(side="left", padx=10)
            ctk.CTkButton(row, text="✕", width=24, height=24, fg_color="transparent", hover_color="#EF4444",
                          text_color="#64748B", command=lambda i=idx: self.delete_timeline_step(i)).pack(side="right",
                                                                                                         padx=6, pady=4)

    def delete_timeline_step(self, index):
        if 0 <= index < len(self.macro_events):
            removed = self.macro_events.pop(index)
            logging.info(f"Step index purged from runtime sequence buffer: {removed}")
            self.rebuild_timeline_view()
            self.set_ui_states("normal")

    def activate_key_listener(self, widget, event, default_bg):
        if getattr(widget, "is_listening", False):
            if event.num == 1:
                widget.configure(text="LeftClick")
            elif event.num == 3:
                widget.configure(text="RightClick")
            widget.is_listening = False
            self.listening_target = None
            widget.configure(fg_color=default_bg)
            return

        if self.listening_target and self.listening_target != widget:
            self.listening_target.configure(fg_color=getattr(self.listening_target, "default_color_tag", "#1E1E28"))
            self.listening_target.is_listening = False

        self.listening_target = widget
        widget.is_listening = True
        widget.default_color_tag = default_bg
        self.temp_combo_buffer.clear()

        widget.configure(text="[ Listening input combo... ]", fg_color="#451A20")

    def start_global_keybind_monitor(self):
        def clean_key_string(key):
            if hasattr(key, 'char') and key.char is not None:
                val = str(key.char).lower().strip()
                return val if val not in ["", "none", "[]", "<>"] else ""
            if hasattr(key, 'name') and key.name is not None:
                n = str(key.name).lower().strip()
                if "ctrl" in n: return "ctrl"
                if "shift" in n: return "shift"
                if "alt" in n: return "alt"
                return n if n not in ["", "none", "[]", "<>"] else ""

            raw = str(key).replace("Key.", "").strip("'").lower().strip()
            if raw in ["", "[]", "<>", "none"]:
                return ""
            return raw

        def sanitize_ui_string(tokens_list):
            clean_list = []
            for token in tokens_list:
                t = str(token).replace("[]", "").replace("<>", "").strip("+").strip()
                if t and t not in ["", "none", "[]"]:
                    clean_list.append(t)

            clean_list = sorted(list(set(clean_list)))
            output = "+".join(clean_list).strip("+")
            while "++" in output:
                output = output.replace("++", "+")
            return output

        def on_press(key):
            k_str = clean_key_string(key)
            if not k_str: return
            self.currently_pressed_keys.add(k_str)

            panic_combo = {"ctrl", "alt", "shift", "p"}
            if panic_combo.issubset(self.currently_pressed_keys):
                logging.critical("System terminate sequence intercepted. Executing clean hard crash fallback.")
                os._exit(1)

            if key == keyboard.Key.esc:
                logging.info("Hardware break condition recognized via global ESC register.")
                self.is_playing = False
                if self.is_recording:
                    self.after(0, self.stop_recording)
                else:
                    self.after(0, self.stop_spammer)
                    self.after(0, self.finish_playback)
                return

            if not self.keybinds_enabled_var.get():
                return

            if self.listening_target:
                self.temp_combo_buffer.add(k_str)
                combo_display = sanitize_ui_string(self.temp_combo_buffer)

                if combo_display and combo_display != "[]":
                    self.listening_target.configure(text=combo_display)
                return

            macro_trigger_set = set(self.macro_keybind_btn.cget("text").split("+"))
            spammer_trigger_set = set(self.spammer_keybind_btn.cget("text").split("+"))

            if macro_trigger_set.issubset(self.currently_pressed_keys):
                if self.is_recording:
                    self.after(0, self.stop_recording)
                elif not self.is_playing:
                    self.after(0, self.start_playback)
                else:
                    self.is_playing = False

            if spammer_trigger_set.issubset(self.currently_pressed_keys) and not self.is_recording:
                if self.spam_mode_menu.get() == "Toggle Mode":
                    if not self.is_spammer_active:
                        self.after(0, self.start_spammer)
                    else:
                        self.after(0, self.stop_spammer)
                elif self.spam_mode_menu.get() == "Hold Mode" and not self.is_spammer_active:
                    self.after(0, self.start_spammer)

        def on_release(key):
            k_str = clean_key_string(key)
            if self.listening_target:
                raw_text = self.listening_target.cget("text")
                final_text = sanitize_ui_string(raw_text.split("+"))
                if not final_text or final_text == "[]":
                    final_text = k_str if k_str else "f4"
                self.listening_target.configure(text=final_text, fg_color=self.listening_target.default_color_tag)
                self.listening_target.is_listening = False
                self.listening_target = None
                self.temp_combo_buffer.clear()
                logging.info("Input tracking keybind assigned completely.")
                return

            if self.is_spammer_active and self.spam_mode_menu.get() == "Hold Mode":
                spammer_trigger_set = set(self.spammer_keybind_btn.cget("text").split("+"))
                if k_str in spammer_trigger_set:
                    self.after(0, self.stop_spammer)

            if k_str in self.currently_pressed_keys:
                self.currently_pressed_keys.remove(k_str)

        self.global_keybind_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self.global_keybind_listener.start()

    def _trigger_telemetry_monitoring(self):
        if self.is_telemetry_loop_running: return
        self.is_telemetry_loop_running = True
        self.automation_start_timestamp = time.time()
        self._telemetry_refresh_cycle()

    def _telemetry_refresh_cycle(self):
        if not self.is_playing and not self.is_spammer_active:
            self.is_telemetry_loop_running = False
            self.lbl_runtime.configure(text="Active Runtime: 0.00s")
            return

        elapsed = time.time() - self.automation_start_timestamp
        self.lbl_dispatched.configure(text=f"Actions Dispatched: {self.total_actions_dispatched}")
        self.lbl_runtime.configure(text=f"Active Runtime: {elapsed:.2f}s")
        self.after(50, self._telemetry_refresh_cycle)

    def toggle_recording(self):
        if not self.is_recording:
            logging.info("Starting hardware monitoring hooks. Recording workflow execution trace...")
            self.macro_events.clear()
            self.is_recording = True
            self.start_time = time.time()
            self.record_btn.configure(text="⏹ Stop", fg_color="#374151")
            self.set_ui_states("disabled")
            self.mouse_listener = mouse.Listener(on_click=self.on_click)
            self.keyboard_listener = keyboard.Listener(on_press=self.on_recorded_key)
            self.mouse_listener.start()
            self.keyboard_listener.start()
        else:
            self.stop_recording()

    def stop_recording(self):
        if self.is_recording:
            self.is_recording = False
            if self.mouse_listener: self.mouse_listener.stop()
            if self.keyboard_listener: self.keyboard_listener.stop()

            macro_trigger_set = set(self.macro_keybind_btn.cget("text").split("+"))
            clean_events = []
            for ev in self.macro_events:
                if ev[1] == "Key Press" and (ev[2] in macro_trigger_set or ev[2] == "Key.esc"):
                    continue
                clean_events.append(ev)
            self.macro_events = clean_events

            logging.info(f"Workflow sequence recorded. Captured traces total: {len(self.macro_events)}")
            self.record_btn.configure(text="🔴 Record", fg_color="#EF4444")
            self.rebuild_timeline_view()
            self.set_ui_states("normal")

    def on_click(self, x, y, button, pressed):
        if self.is_recording:
            elapsed = time.time() - self.start_time
            state = "Down" if pressed else "Up"
            self.macro_events.append((elapsed, f"Mouse {state}", f"{button.name} @ {x},{y}"))
            self.after(0, self.rebuild_timeline_view)

    def on_recorded_key(self, key):
        if key == keyboard.Key.esc: return False
        if self.is_recording:
            elapsed = time.time() - self.start_time
            k_str = key.char if hasattr(key, 'char') and key.char else f"Key.{key.name}"
            self.macro_events.append((elapsed, "Key Press", k_str))
            self.after(0, self.rebuild_timeline_view)

    def start_playback(self):
        if not self.macro_events or self.is_playing: return
        try:
            self.target_loops = int(self.loop_entry.get() or 1)
        except ValueError:
            logging.error("Failed executing workflow playback. Looping configuration mismatch.")
            return

        logging.info("Initializing asynchronous thread loop play drive.")
        self.is_playing = True
        self.total_actions_dispatched = 0
        self._trigger_telemetry_monitoring()
        self.set_ui_states("disabled")
        threading.Thread(target=self.playback_loop_manager, daemon=True).start()

    def playback_loop_manager(self):
        m_ctrl = mouse.Controller()
        k_ctrl = keyboard.Controller()
        loop_count = 0
        while self.is_playing:
            if self.target_loops != 0 and loop_count >= self.target_loops: break
            loop_count += 1
            last_time = 0.0
            for elapsed, ev_type, details in self.macro_events:
                if not self.is_playing: break
                delay = elapsed - last_time
                if self.human_macro_var.get():
                    delay += random.uniform(-0.008, 0.008)
                time.sleep(max(0, delay))
                last_time = elapsed
                try:
                    if "Mouse" in ev_type:
                        coords = details.split("@")[1].strip().split(",")
                        m_ctrl.position = (int(coords[0]), int(coords[1]))
                        btn = mouse.Button[details.split("@")[0].strip()]
                        if "Down" in ev_type:
                            m_ctrl.press(btn)
                        else:
                            m_ctrl.release(btn)
                    elif "Key" in ev_type:
                        if details.startswith("Key."):
                            k = getattr(keyboard.Key, details.split(".")[1])
                        else:
                            k = details
                        k_ctrl.press(k)
                        k_ctrl.release(k)
                    self.total_actions_dispatched += 1
                except Exception as ex:
                    logging.debug(f"Hardware virtualization exception context: {ex}")
            time.sleep(0.02)
        self.after(0, self.finish_playback)

    def finish_playback(self):
        self.is_playing = False
        logging.info("Workflow tracking execution path completed successfully.")
        self.set_ui_states("normal")

    def start_spammer(self):
        try:
            self.click_interval = float(self.interval_entry.get())
            if self.click_interval <= 0: return
        except ValueError:
            logging.error("Continuous driver error: delay execution missing parameters.")
            return
        self.raw_target_key = self.target_key_btn.cget("text").strip()
        if self.raw_target_key.startswith("["): return

        logging.info(f"Spawning background thread... Continuous macro generator target: {self.raw_target_key}")
        self.is_spammer_active = True
        self.total_actions_dispatched = 0
        self._trigger_telemetry_monitoring()
        self.spammer_status_label.configure(text="AUTOMATION MODULE ACTIVE", text_color="#4ADE80")
        threading.Thread(target=self.spammer_core_loop, daemon=True).start()

    def stop_spammer(self):
        if self.is_spammer_active:
            self.is_spammer_active = False
            logging.info("Continuous desktop generator thread decoupled safely.")
            self.spammer_status_label.configure(text="AUTOMATION MODULE INACTIVE", text_color="#EF4444")

    def spammer_core_loop(self):
        from pynput.mouse import Controller as MouseCtrl, Button
        from pynput.keyboard import Controller as KbdCtrl, Key

        m_ctrl = MouseCtrl()
        k_ctrl = KbdCtrl()

        key_to_send = self.raw_target_key
        is_mouse = key_to_send.lower() in ["leftclick", "rightclick"]

        special_key = None
        if not is_mouse and key_to_send.lower() in ["space", "enter", "shift", "ctrl", "alt", "tab"]:
            special_key = getattr(Key, key_to_send.lower())

        while self.is_spammer_active:
            try:
                if is_mouse:
                    btn = Button.left if key_to_send.lower() == "leftclick" else Button.right
                    m_ctrl.press(btn)
                    time.sleep(0.002)
                    m_ctrl.release(btn)
                else:
                    target = special_key if special_key else key_to_send
                    k_ctrl.press(target)
                    time.sleep(0.002)
                    k_ctrl.release(target)

                self.total_actions_dispatched += 1

                interval = self.click_interval
                if self.human_spam_var.get():
                    interval += random.uniform(-0.005, 0.005)

                time.sleep(max(0.001, interval))
            except Exception as e:
                logging.error(f"Error in continuous core execution thread loop: {e}")
                break

        self.after(0, self.stop_spammer)

    def save_macro_prompt(self):
        if not self.macro_events: return
        self.modal_entry.delete(0, 'end')
        self.modal_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.modal_entry.focus_set()

    def confirm_save_modal(self):
        name = self.modal_entry.get().strip()
        if name:
            self.saved_macros[name] = self.macro_events.copy()
            self.save_profiles_to_disk()
            self.refresh_profile_menu()
            self.profile_var.set(name)
            logging.info(f"Successfully recorded asset workspace configuration mapping: {name}")
            self.close_save_modal()
        else:
            messagebox.showwarning("Validation Error", "Profile deployment title cannot be left blank.")

    def close_save_modal(self):
        self.modal_overlay.place_forget()

    def load_selected_profile(self, name):
        if name in self.saved_macros:
            self.macro_events = self.saved_macros[name].copy()
            logging.info(f"Loaded active automation mapping sequence target: {name}")
            self.rebuild_timeline_view()
            self.set_ui_states("normal")

    def save_profiles_to_disk(self):
        try:
            with open(self.save_file, "w") as f:
                json.dump(self.saved_macros, f)
        except Exception as e:
            logging.error(f"Write failure: {e}")

    def load_profiles_from_disk(self):
        if os.path.exists(self.save_file):
            try:
                with open(self.save_file, "r") as f:
                    self.saved_macros = json.load(f)
            except Exception as e:
                logging.error(f"Read failure: {e}")

    def refresh_profile_menu(self):
        self.profile_menu.configure(values=self.get_profile_list())

    def get_profile_list(self):
        return list(self.saved_macros.keys()) if self.saved_macros else ["No Profiles Found"]

    def set_ui_states(self, state):
        self.play_btn.configure(state=state if self.macro_events else "disabled")
        self.clear_btn.configure(state=state if self.macro_events else "disabled")
        self.save_btn.configure(state=state if self.macro_events else "disabled")

    def clear_macro(self):
        self.macro_events.clear()
        self.profile_var.set("Select Configuration Profile")
        self.rebuild_timeline_view()
        self.set_ui_states("disabled")
        logging.info("Volatile runtime macro history event buffer wiped clean.")


if __name__ == "__main__":
    app = AutomationStudio()
    app.mainloop()
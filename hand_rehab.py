import cv2
import mediapipe as mp
import math
import time
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

# --- Design Constants ---
COLOR_BG = "#0f172a"          # Slate 900
COLOR_CARD = "#1e293b"        # Slate 800
COLOR_ACCENT = "#38bdf8"      # Sky 400
COLOR_SUCCESS = "#4ade80"     # Green 400
COLOR_ERROR = "#f87171"       # Red 400
COLOR_TEXT = "#f1f5f9"        # Slate 100
COLOR_TEXT_DIM = "#94a3b8"    # Slate 400
FONT_MAIN = ("Segoe UI", 12)
FONT_BOLD = ("Segoe UI", 14, "bold")

class HandRehabApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hand Rehab Tracker Pro")
        self.root.geometry("1100x750")
        self.root.configure(bg=COLOR_BG)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # --- State Variables ---
        self.is_running = False
        self.reps = 0
        self.rep_times = []
        self.rep_start_time = None
        self.session_start_time = None
        self.total_time = 0.0
        
        # State Machine: 
        # 0: Waiting for full open
        # 1: Hand is open, waiting for full close
        # 2: Hand is closed, waiting for full open to complete rep
        self.exercise_state = 0 
        
        self.feedback = "Position hand to start"
        self.feedback_color = COLOR_TEXT
        
        # --- MediaPipe Setup ---
        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils
        self.hands = self.mp_hands.Hands(
            max_num_hands=1,
            min_detection_confidence=0.8,
            min_tracking_confidence=0.8
        )
        self.cap = None
        
        self.setup_ui()
        
    def setup_ui(self):
        # Layout
        self.main_container = tk.Frame(self.root, bg=COLOR_BG)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        # Video
        self.left_frame = tk.Frame(self.main_container, bg=COLOR_BG)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.video_container = tk.Frame(self.left_frame, bg=COLOR_CARD, highlightthickness=1, highlightbackground=COLOR_ACCENT)
        self.video_container.pack(fill=tk.BOTH, expand=True)
        
        self.video_label = tk.Label(self.video_container, bg=COLOR_CARD)
        self.video_label.pack(fill=tk.BOTH, expand=True)
        
        self.lbl_feedback = tk.Label(self.left_frame, text=self.feedback, font=FONT_BOLD, bg=COLOR_BG, fg=COLOR_TEXT, pady=20)
        self.lbl_feedback.pack()

        # Stats Sidebar
        self.right_frame = tk.Frame(self.main_container, bg=COLOR_BG, width=320)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(30, 0))
        self.right_frame.pack_propagate(False)

        # Rep Counter Card
        rep_card = tk.Frame(self.right_frame, bg=COLOR_CARD, pady=20)
        rep_card.pack(fill=tk.X)
        tk.Label(rep_card, text="TOTAL REPETITIONS", font=("Segoe UI", 10, "bold"), bg=COLOR_CARD, fg=COLOR_ACCENT).pack()
        self.lbl_reps = tk.Label(rep_card, text="0", font=("Segoe UI", 64, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT)
        self.lbl_reps.pack()

        # Timer & Stats
        stats_frame = tk.Frame(self.right_frame, bg=COLOR_BG, pady=10)
        stats_frame.pack(fill=tk.X)
        
        self.lbl_time = self.create_stat_label(stats_frame, "SESSION TIME", "0.0s")
        self.lbl_avg = self.create_stat_label(stats_frame, "AVG SPEED", "0.0s")

        # History
        tk.Label(self.right_frame, text="LAST REPS", font=("Segoe UI", 9, "bold"), bg=COLOR_BG, fg=COLOR_TEXT_DIM).pack(anchor="w", pady=(20, 5))
        self.history_listbox = tk.Listbox(self.right_frame, font=("Segoe UI", 10), bg=COLOR_CARD, fg=COLOR_TEXT, 
                                        borderwidth=0, highlightthickness=0, height=8)
        self.history_listbox.pack(fill=tk.X)

        # Buttons
        btn_frame = tk.Frame(self.right_frame, bg=COLOR_BG, pady=20)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.btn_start = tk.Button(btn_frame, text="START TRACKING", font=FONT_BOLD, bg=COLOR_SUCCESS, fg=COLOR_BG, 
                                   command=self.start_tracking, relief=tk.FLAT, pady=10)
        self.btn_start.pack(fill=tk.X, pady=5)

        self.btn_stop = tk.Button(btn_frame, text="STOP", font=FONT_BOLD, bg=COLOR_ERROR, fg=COLOR_BG, 
                                  command=self.stop_tracking, relief=tk.FLAT, state=tk.DISABLED, pady=10)
        self.btn_stop.pack(fill=tk.X, pady=5)

    def create_stat_label(self, parent, text, val):
        f = tk.Frame(parent, bg=COLOR_CARD, pady=10, padx=15)
        f.pack(fill=tk.X, pady=5)
        tk.Label(f, text=text, font=("Segoe UI", 8, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT_DIM).pack(anchor="w")
        label = tk.Label(f, text=val, font=("Segoe UI", 16, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT)
        label.pack(anchor="w")
        return label

    def start_tracking(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            messagebox.showerror("Error", "No camera detected.")
            return
        self.is_running = True
        self.session_start_time = time.time()
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.update_frame()
        
    def stop_tracking(self):
        self.is_running = False
        if self.cap: self.cap.release()
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.video_label.config(image="")
        
    def update_frame(self):
        if not self.is_running: return
        ret, frame = self.cap.read()
        if not ret: 
            self.root.after(10, self.update_frame)
            return

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb)
        
        current_pose = "NONE"
        if results.multi_hand_landmarks:
            lm = results.multi_hand_landmarks[0]
            self.mp_draw.draw_landmarks(frame, lm, self.mp_hands.HAND_CONNECTIONS)
            
            # --- STRICT DETECTION LOGIC ---
            # Check 4 fingers (Index, Middle, Ring, Pinky)
            # Tip (8,12,16,20) vs MCP (5,9,13,17) vs Wrist (0)
            fingers_extended = []
            for tip, mcp in [(8,5), (12,9), (16,13), (20,17)]:
                tip_y = lm.landmark[tip].y
                mcp_y = lm.landmark[mcp].y
                # In OpenCV coordinates, Y increases downward. 
                # Extended finger: tip is significantly higher (lower Y) than mcp
                fingers_extended.append(tip_y < mcp_y - 0.05) 

            # Check Thumb
            # Thumb tip (4) vs Thumb MCP (2) distance from Pinky MCP (17)
            t_tip = lm.landmark[4]
            t_mcp = lm.landmark[2]
            p_mcp = lm.landmark[17]
            dist_tip = math.hypot(t_tip.x - p_mcp.x, t_tip.y - p_mcp.y)
            dist_mcp = math.hypot(t_mcp.x - p_mcp.x, t_mcp.y - p_mcp.y)
            thumb_extended = dist_tip > dist_mcp + 0.03
            
            count = sum(fingers_extended) + (1 if thumb_extended else 0)
            
            if count == 5: current_pose = "OPEN"
            elif count <= 1: current_pose = "CLOSED"
            else: current_pose = "PARTIAL"
            
            self.process_state_machine(current_pose)
        else:
            self.feedback = "Detecting hand..."
            self.feedback_color = COLOR_TEXT_DIM

        # UI Update
        self.render_ui(frame)
        self.root.after(10, self.update_frame)

    def process_state_machine(self, pose):
        # Logic: 0 (Init) -> 1 (Open) -> 2 (Closed) -> 1 (Open - Rep++)
        
        if self.exercise_state == 0:
            if pose == "OPEN":
                self.exercise_state = 1
                self.feedback = "Fully Open. Now close your fist."
                self.feedback_color = COLOR_ACCENT
            else:
                self.feedback = "Please open your hand fully"
                self.feedback_color = COLOR_TEXT_DIM
        
        elif self.exercise_state == 1:
            if pose == "CLOSED":
                self.exercise_state = 2
                self.feedback = "Excellent! Now open back up."
                self.feedback_color = COLOR_SUCCESS
                if not self.rep_start_time:
                    self.rep_start_time = time.time()
            elif pose == "PARTIAL":
                # Do nothing, just waiting for full close
                pass
            
        elif self.exercise_state == 2:
            if pose == "OPEN":
                # COMPLETED REP
                self.reps += 1
                if self.rep_start_time:
                    dt = time.time() - self.rep_start_time
                    self.rep_times.append(dt)
                    self.history_listbox.insert(0, f" Rep {self.reps} - {dt:.1f}s")
                    self.rep_start_time = None
                
                self.exercise_state = 1 # Back to waiting for next close
                self.feedback = "Rep Counted! ✅ Close again."
                self.feedback_color = COLOR_SUCCESS
            elif pose == "PARTIAL":
                 # Use feedback to tell user they aren't open enough yet
                 self.feedback = "Open hand COMPLETELY..."
                 self.feedback_color = COLOR_ACCENT

    def render_ui(self, frame):
        frame = cv2.resize(frame, (640, 480))
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        imgtk = ImageTk.PhotoImage(image=img)
        self.video_label.imgtk = imgtk
        self.video_label.configure(image=imgtk)
        
        self.lbl_reps.config(text=str(self.reps))
        self.lbl_feedback.config(text=self.feedback, fg=self.feedback_color)
        
        if self.session_start_time:
            self.total_time = time.time() - self.session_start_time
            self.lbl_time.config(text=f"{self.total_time:.1f}s")
            
        avg = sum(self.rep_times) / len(self.rep_times) if self.rep_times else 0.0
        self.lbl_avg.config(text=f"{avg:.1f}s")

    def on_close(self):
        self.is_running = False
        if self.cap: self.cap.release()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    HandRehabApp(root)
    root.mainloop()

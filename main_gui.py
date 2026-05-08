import re
import tkinter as tk
from tkinter import ttk, messagebox

# ╔══════════════════════════════════════════════════════╗
#  ALGORITHMS LOGIC
# ╚══════════════════════════════════════════════════════╝
def run_round_robin(processes, quantum):
    procs = [{'pid': p['pid'], 'arrival': p['arrival'], 'burst': p['burst'], 'remaining': p['burst'], 'start_time': -1, 'finish': 0} for p in processes]
    procs.sort(key=lambda x: (x['arrival'], x['pid']))
    queue, gantt, queue_states, time, done, n, visited = [], [], [], 0, 0, len(procs), [False] * len(procs)

    for i, p in enumerate(procs):
        if p['arrival'] <= time: queue.append(i); visited[i] = True

    while done < n:
        if not queue:
            time = min(p['arrival'] for i, p in enumerate(procs) if not visited[i])
            for i, p in enumerate(procs):
                if not visited[i] and p['arrival'] <= time: queue.append(i); visited[i] = True
            continue

        idx = queue.pop(0)
        p = procs[idx]
        if p['start_time'] == -1: p['start_time'] = time
        run_time = min(quantum, p['remaining'])

        # snapshot ready queue BEFORE running
        queue_states.append({
            'at_time': time,
            'running': p['pid'],
            'waiting': [procs[i]['pid'] for i in queue],
        })

        gantt.append({'pid': p['pid'], 'start': time, 'end': time + run_time})
        time += run_time
        p['remaining'] -= run_time

        for i, proc in enumerate(procs):
            if not visited[i] and proc['arrival'] <= time: queue.append(i); visited[i] = True

        if p['remaining'] == 0: p['finish'] = time; done += 1
        else: queue.append(idx)

    total_wt = total_tat = total_rt = 0
    results = []
    for p in procs:
        tat, wt, rt = p['finish'] - p['arrival'], (p['finish'] - p['arrival']) - p['burst'], p['start_time'] - p['arrival']
        total_wt += wt; total_tat += tat; total_rt += rt
        results.append({'pid': p['pid'], 'arrival': p['arrival'], 'burst': p['burst'], 'wt': wt, 'tat': tat, 'rt': rt})

    return gantt, results, {'avg_wt': round(total_wt/n, 2), 'avg_tat': round(total_tat/n, 2), 'avg_rt': round(total_rt/n, 2)}, queue_states

def run_srtf(processes):
    n = len(processes)
    remaining = [p['burst'] for p in processes]
    start_t = [-1] * n
    finish_t = [0] * n
    t = 0
    completed = 0
    gantt = []
    current = -1
    queue_states = []

    while completed < n:
        idx = -1
        min_time = float('inf')
        # List of ready (arrived and not completed) processes for ready queue
        ready_list = []
        for i in range(n):
            if processes[i]['arrival'] <= t and remaining[i] > 0:
                ready_list.append((remaining[i], i))

        # Order ready queue by remaining time, breaking ties with arrival time, then PID
        ready_list_sorted = sorted(
            ready_list,
            key=lambda x: (x[0], processes[x[1]]['arrival'], processes[x[1]]['pid'])
        )
 

        # Build the ready queue state snapshot for this time step (before running)
        if idx == -1 and ready_list_sorted:
            srtf_waiting = [processes[i]['pid'] for _, i in ready_list_sorted]
        else:
            srtf_waiting = [processes[i]['pid'] for _, i in ready_list_sorted if i != idx]

        # Pick the process with the smallest remaining time (if any)
        if ready_list_sorted:
            min_time, idx = ready_list_sorted[0]
        else:
            # Still add an empty ready queue state when CPU idle
            queue_states.append({
                "at_time": t,
                "running": "—",
                "waiting": [],
            })
            t += 1
            continue

        # Add ready queue snapshot: running is processes[idx]['pid'], waiting is ready queue minus running
        queue_states.append({
            "at_time": t,
            "running": processes[idx]['pid'],
            "waiting": [processes[i]['pid'] for _, i in ready_list_sorted if i != idx],
        })

        if start_t[idx] == -1:
            start_t[idx] = t

        if current != idx:
            gantt.append({'pid': processes[idx]['pid'], 'start': t, 'end': t + 1})
            current = idx
        else:
            gantt[-1]['end'] += 1

        remaining[idx] -= 1
        t += 1
        if remaining[idx] == 0:
            finish_t[idx] = t
            completed += 1

    total_wt = total_tat = total_rt = 0
    results = []
    for i in range(n):
        tat = finish_t[i] - processes[i]['arrival']
        wt = (finish_t[i] - processes[i]['arrival']) - processes[i]['burst']
        rt = start_t[i] - processes[i]['arrival']
        total_wt += wt
        total_tat += tat
        total_rt += rt
        results.append({'pid': processes[i]['pid'], 'arrival': processes[i]['arrival'], 'burst': processes[i]['burst'], 'wt': wt, 'tat': tat, 'rt': rt})

    return gantt, results, {'avg_wt': round(total_wt/n, 2), 'avg_tat': round(total_tat/n, 2), 'avg_rt': round(total_rt/n, 2)}, queue_states

# ╔══════════════════════════════════════════════════════╗
#  COMPRESSED GUI & STRICT VALIDATION
# ╚══════════════════════════════════════════════════════╝
class SchedulerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("C2 — Round Robin vs SRTF")
        self.root.geometry("720x900")
        self.processes = []
        self.sections = {} # Stores references dynamically
        
        # IDInitialized to '1'
        self.pid_var = tk.StringVar(value="1")
        
        # Scroll Setup
        self.main_canvas = tk.Canvas(self.root)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.scroll_frame = tk.Frame(self.main_canvas)
        self.main_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.scrollbar.pack(side="right", fill="y")
        self.main_canvas.pack(side="left", fill="both", expand=True)
        self.main_canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.scroll_frame.bind("<Configure>", lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all")))
        self.main_canvas.bind("<Configure>", lambda e: self.main_canvas.itemconfig(self.main_canvas.find_withtag("all")[0], width=e.width))
        self.main_canvas.bind_all("<MouseWheel>", lambda e: self.main_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        self._build_ui()

    def _build_ui(self):
        # Initialize ttk.Style with customizations as requested
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'), background='#E0E0E0')
        style.configure('Treeview', rowheight=25, font=('Segoe UI', 10))

        sf = self.scroll_frame

        inp = tk.LabelFrame(sf, text=" Input ", font=("Segoe UI", 11, "bold"))
        inp.pack(fill="x", padx=10, pady=10)
        self.entries = {}

        #  Next Process ID and Time Quantum, side by side
        tk.Label(inp, text="Next Process ID:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", padx=8, pady=5)
        pid_entry = tk.Entry(inp, textvariable=self.pid_var, state="disabled", width=12, disabledforeground="black")
        pid_entry.grid(row=0, column=1, sticky="w", padx=8, pady=5)

        tk.Label(inp, text="Time Quantum").grid(row=0, column=2, padx=8, pady=5)
        e_quantum = tk.Entry(inp, width=12)
        e_quantum.grid(row=0, column=3, padx=8, pady=5)
        self.entries["quantum"] = e_quantum

        tk.Label(inp, text="Arrival Time").grid(row=1, column=0, padx=8, pady=3)
        tk.Label(inp, text="Burst Time").grid(row=1, column=1, padx=8, pady=3)
        e_arrival = tk.Entry(inp, width=12)
        e_arrival.grid(row=2, column=0, padx=8, pady=3)
        self.entries["arrival"] = e_arrival

        e_burst = tk.Entry(inp, width=12)
        e_burst.grid(row=2, column=1, padx=8, pady=3)
        self.entries["burst"] = e_burst

        # Buttons
        bf = tk.Frame(sf)
        bf.pack(pady=5)
        for txt, cmd, color in [
            ("➕ Add Process", self._add_process, "#4CAF50"),
            ("🗑 Clear All", self._clear_all, "#f44336"),
            ("▶ Run Both", self._run, "#2196F3")
        ]:
            tk.Button(
                bf, 
                text=txt, 
                command=cmd, 
                bg=color, 
                fg="white", 
                width=14, 
                relief='flat',
                cursor='hand2',
                font=('Segoe UI', 10, 'bold')
            ).pack(side="left", padx=5, ipady=3)
       

        # Tables & Sections Builder
        self.proc_table = self._make_table(sf, " Processes ", ("PID", "Arrival", "Burst"), 4)

        for name, key, color in [("Round Robin", "rr", "#2196F3"), ("SRTF", "srtf", "#9C27B0")]:
            lf = tk.LabelFrame(sf, text=f" {name} ", font=("Segoe UI", 11, "bold"), fg=color)
            lf.pack(fill="x", padx=10, pady=10)
            cv = tk.Canvas(lf, width=650, height=70, bg="#F8F9FA", highlightthickness=0)
            cv.pack(pady=5)
            tbl = self._make_table(lf, None, ("PID", "Arrival", "Burst", "WT", "TAT", "RT"), 5)
            lbls = self._make_avg_row(lf)
            rq_tbl = None
            if key == "rr":
                rq_frame = tk.LabelFrame(lf, text="RR Ready Queue", font=("Segoe UI", 10, "bold"))
                rq_frame.pack(fill="x", padx=5, pady=3)
                rq_tbl = ttk.Treeview(rq_frame, columns=("At Time", "Running", "Waiting"), show="headings", height=4)
                rq_tbl.heading("At Time", text="At Time")
                rq_tbl.heading("Running", text="▶ Running")
                rq_tbl.heading("Waiting", text="⏳ Ready Queue")
                rq_tbl.column("At Time", width=80,  anchor="center")
                rq_tbl.column("Running", width=100, anchor="center")
                rq_tbl.column("Waiting", width=440, anchor="w")
                rq_tbl.pack(fill="x", padx=5, pady=3)
            self.sections[key] = {'canvas': cv, 'table': tbl, 'lbls': lbls, 'rq': rq_tbl}

        # For SRTF ready queue, add a new label frame below the SRTF metrics & table.
        # Insert after SRTF self.sections entry is created
        srtf_sec = self.sections['srtf']
        srtf_lf = srtf_sec['table'].master.master  # label frame for SRTF (the immediate containing label frame)
        rq_srtf_frame = tk.LabelFrame(srtf_lf, text="SRTF Ready Queue", font=("Segoe UI", 10, "bold"))
        rq_srtf_frame.pack(fill="x", padx=5, pady=3)
        rq_srtf_tbl = ttk.Treeview(rq_srtf_frame, columns=("At Time", "Running", "Waiting"), show="headings", height=4)
        rq_srtf_tbl.heading("At Time", text="At Time")
        rq_srtf_tbl.heading("Running", text="▶ Running")
        rq_srtf_tbl.heading("Waiting", text="⏳ Ready Queue")
        rq_srtf_tbl.column("At Time", width=80,  anchor="center")
        rq_srtf_tbl.column("Running", width=100, anchor="center")
        rq_srtf_tbl.column("Waiting", width=440, anchor="w")
        rq_srtf_tbl.pack(fill="x", padx=5, pady=3)
        self.sections['srtf']['rq'] = rq_srtf_tbl

        # Comparison
        cmp = tk.LabelFrame(sf, text=" Comparison Summary ", font=("Arial", 10, "bold"), fg="#F44336")
        cmp.pack(fill="x", padx=10, pady=10)  # pady changed to 10
        self.cmp_table = ttk.Treeview(cmp, columns=("Metric", "Round Robin", "SRTF"), show="headings", height=3)
        for c in ("Metric", "Round Robin", "SRTF"):
            self.cmp_table.heading(c, text=c)
            self.cmp_table.column(c, width=200, anchor="center")
        self.cmp_table.pack(pady=5)

        # Conclusion
        conc = tk.LabelFrame(sf, text=" Conclusion ", font=("Arial", 10, "bold"), fg="#795548")
        conc.pack(fill="x", padx=10, pady=10)  # pady changed to 10
        self.conc_txt = tk.Text(
            conc,
            width=80,
            height=8,
            font=("Arial", 9),
            state="disabled",
            bg="#F8F9FA",
            wrap="word",
            relief="flat"
        )
        self.conc_txt.pack(pady=10, padx=10)

    def _make_table(self, parent, title, cols, height):
        if title:
            parent = tk.LabelFrame(parent, text=title, font=("Arial", 10, "bold"))
            parent.pack(fill="x", padx=10, pady=5)
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=height)
        for c in cols: tree.heading(c, text=c); tree.column(c, width=100, anchor="center")
        tree.pack(pady=5)
        return tree

    def _make_avg_row(self, parent):
        frame = tk.Frame(parent); frame.pack(anchor="w", padx=10, pady=5)
        lbls = {}
        for i, (text, key, color) in enumerate([("Avg WT:", 'wt', "#2196F3"), ("Avg TAT:", 'tat', "#4CAF50"), ("Avg RT:", 'rt', "#FF9800")]):
            tk.Label(frame, text=text, font=("Arial", 10)).grid(row=0, column=i*2, padx=5)
            lbls[key] = tk.Label(frame, text="—", font=("Arial", 10, "bold"), fg=color)
            lbls[key].grid(row=0, column=i*2+1, padx=5)
        return lbls

    # ── Strict Validation & Add ────────────────────────────────
    def _add_process(self):
        # 1. get arrival and burst time
        arr = self.entries["arrival"].get().strip()
        brst = self.entries["burst"].get().strip()
        
        # Create ID automatically based on the number of processes + 1
        pid = str(len(self.processes) + 1)
        
        errors = []

        # 3. validate arrival and burst time
        if not arr or not brst: errors.append("- Missing required fields.")
        if arr and (not arr.isdigit() or int(arr) < 0): errors.append("- Arrival Time must be a valid positive number or 0.")
        if brst and (not brst.isdigit() or int(brst) <= 0): errors.append("- Burst Time must be a valid number > 0.")

        if errors:
            messagebox.showerror("Validation Errors", "Please fix the following issues:\n" + "\n".join(errors))
            return

        # 4. add process to the list
        self.processes.append({"pid": pid, "arrival": int(arr), "burst": int(brst)})
        self.proc_table.insert("", "end", values=(pid, arr, brst))
        
        # 5. Empty cells after adding
        for k in ("arrival", "burst"): self.entries[k].delete(0, tk.END)

        self.pid_var.set(str(len(self.processes) + 1))

    # ── Strict Quantum Validation & Run ────────────────────────
    def _run(self):
        if not self.processes: return messagebox.showwarning("Warning", "Add at least one process.")
        q_str = self.entries["quantum"].get().strip()
        
        if not q_str or not q_str.isdigit() or int(q_str) <= 0:
            return messagebox.showerror("Validation Error", "Time Quantum must be a valid number > 0.")
        
        quantum = int(q_str)
        rr_g, rr_r, rr_a, rr_qs = run_round_robin(self.processes, quantum)
        sr_g, sr_r, sr_a, sr_qs = run_srtf(self.processes)

        self._populate(self.sections['rr'],   rr_g, rr_r, rr_a, rr_qs)
        self._populate(self.sections['srtf'], sr_g, sr_r, sr_a, sr_qs)
        
        # Populate Comparison
        self.cmp_table.delete(*self.cmp_table.get_children())
        for lbl, k in [("Avg Waiting Time", 'avg_wt'), ("Avg Turnaround Time", 'avg_tat'), ("Avg Response Time", 'avg_rt')]:
            self.cmp_table.insert("", "end", values=(lbl, rr_a[k], sr_a[k]))
            
        self._generate_conclusion(rr_a, sr_a, rr_r, sr_r, quantum)

    def _populate(self, sec, gantt, res, avg, queue_states=None):
        sec['canvas'].delete("all")
        for row in sec['table'].get_children(): sec['table'].delete(row)
        for r in res: sec['table'].insert("", "end", values=(r["pid"], r["arrival"], r["burst"], r["wt"], r["tat"], r["rt"]))
        for k in ('wt', 'tat', 'rt'): sec['lbls'][k].config(text=str(avg[f'avg_{k}']))

        # Fill Ready Queue
        if sec['rq'] is not None:
            for row in sec['rq'].get_children(): sec['rq'].delete(row)
            if queue_states:
                for state in queue_states:
                    waiting_str = " → ".join(state['waiting']) if state['waiting'] else "—"
                    sec['rq'].insert("", "end", values=(f"t = {state['at_time']}", state['running'], waiting_str))
        
        # Draw Gantt
        if not gantt: return
        tt, CW, XO, colors = gantt[-1]["end"], 640, 5, ["#4FC3F7","#81C784","#FFB74D","#E57373","#BA68C8"]
        cmap = {p: colors[i % len(colors)] for i, p in enumerate(dict.fromkeys(s["pid"] for s in gantt))}
        for s in gantt:
            x1, x2 = XO + (s["start"]/tt)*CW, XO + (s["end"]/tt)*CW
            sec['canvas'].create_rectangle(x1, 5, x2, 45, fill=cmap[s["pid"]], outline="white", width=2)
            sec['canvas'].create_text((x1+x2)/2, 25, text=s["pid"], font=("Arial", 9, "bold"))
            sec['canvas'].create_text(x1, 57, text=str(s["start"]), font=("Arial", 8))
        sec['canvas'].create_text(XO+CW, 57, text=str(tt), font=("Arial", 8))

    def _generate_conclusion(self, rr_a, sr_a, rr_r, sr_r, q):
        def cmp(r, s, m): return f"RR better on {m}." if r < s else f"SRTF better on {m}." if s < r else f"Equal on {m}."
        
        rr_rng = max(x['wt'] for x in rr_r) - min(x['wt'] for x in rr_r)
        sr_rng = max(x['wt'] for x in sr_r) - min(x['wt'] for x in sr_r)
        fairness = "RR was fairer (smaller WT range)." if rr_rng <= sr_rng else "SRTF had a smaller WT range here."
        
        txt = (
            "1. Performance:\n"
            f" • {cmp(rr_a['avg_wt'], sr_a['avg_wt'], 'Avg WT')}\n"
            f" • {cmp(rr_a['avg_tat'], sr_a['avg_tat'], 'Avg TAT')}\n"
            f" • {cmp(rr_a['avg_rt'], sr_a['avg_rt'], 'Avg RT')}\n"
            f"2. Fairness: {fairness}\n"
            "3. Efficiency: SRTF is generally better at minimizing idle time.\n"
            f"4. Quantum: Q={q} affected RR's responsiveness vs context switch overhead."
        )
        
        self.conc_txt.config(state="normal")
        self.conc_txt.delete("1.0", tk.END)
        self.conc_txt.insert(tk.END, txt)
        self.conc_txt.config(state="disabled")

    def _clear_all(self):
        self.processes.clear()
        for k in self.entries: self.entries[k].delete(0, tk.END)
        self.pid_var.set("1")  # Resetting PID variable to '1'
        for tbl in [self.proc_table, self.sections['rr']['table'], self.sections['srtf']['table'], self.cmp_table]:
            for row in tbl.get_children(): tbl.delete(row)
        if self.sections['rr']['rq'] is not None:
            for row in self.sections['rr']['rq'].get_children(): self.sections['rr']['rq'].delete(row)
        if self.sections['srtf']['rq'] is not None:
            for row in self.sections['srtf']['rq'].get_children(): self.sections['srtf']['rq'].delete(row)
        for sec in self.sections.values():
            sec['canvas'].delete("all")
            for lbl in sec['lbls'].values(): lbl.config(text="—")
        self.conc_txt.config(state="normal"); self.conc_txt.delete("1.0", tk.END); self.conc_txt.config(state="disabled")
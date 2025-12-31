import re
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser
import configparser
import datetime
import threading
import queue
import os

# -------- THEMES --------
LIGHT = {
    "bg": "#f5f5f5",
    "fg": "#000000",
    "btn_bg": "#ffffff",
    "btn_fg": "#000000",
    "accent": "#0078d7",
    "status": "#333333",
    "entry_bg": "#ffffff",
    "list_bg": "#ffffff",
    "list_fg": "#000000",
    "select_bg": "#0078d7"
}

class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tooltip, text=self.text, background="yellow", relief="solid", borderwidth=1, padx=5, pady=3)
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

class InstagramUnfollowApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Instagram Unfollow Tool")
        self.root.geometry("600x800")
        self.root.resizable(True, True)
        
        self.theme = LIGHT
        self.followers_file = None
        self.following_file = None
        self.whitelist_file = None
        self.all_results = []
        self.followers = set()
        self.following = set()
        self.whitelist = set()
        self.mode = tk.StringVar(value="Unfollowers")
        self.use_regex = tk.BooleanVar(value=False)
        
        self.config = configparser.ConfigParser()
        self.config_file = "config.ini"
        self.load_config()
        
        self.queue = queue.Queue()
        
        self.setup_ui()
        self.apply_theme()
        self.setup_keyboard_shortcuts()
        
    def load_config(self):
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
            if "Paths" in self.config:
                self.followers_file = self.config["Paths"].get("followers", None)
                self.following_file = self.config["Paths"].get("following", None)
                self.whitelist_file = self.config["Paths"].get("whitelist", None)
        
    def save_config(self):
        self.config["Paths"] = {
            "followers": self.followers_file or "",
            "following": self.following_file or "",
            "whitelist": self.whitelist_file or ""
        }
        with open(self.config_file, "w") as f:
            self.config.write(f)
        
    def setup_ui(self):
        # Menu Bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
        
        # Main Frame
        self.main_frame = ttk.Frame(self.root, padding=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        self.title_label = ttk.Label(self.main_frame, text="Instagram Unfollow Tool", font=("Arial", 18, "bold"))
        self.title_label.pack(pady=10)
        
        # Mode Selection
        mode_frame = ttk.Frame(self.main_frame)
        mode_frame.pack(pady=5)
        
        ttk.Radiobutton(mode_frame, text="Unfollowers", variable=self.mode, value="Unfollowers").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="Fans", variable=self.mode, value="Fans").pack(side=tk.LEFT, padx=5)
        
        # File Selection Frame
        file_frame = ttk.LabelFrame(self.main_frame, text="Select Files", padding=10)
        file_frame.pack(fill=tk.X, pady=10)
        
        # Followers
        followers_btn_frame = ttk.Frame(file_frame)
        followers_btn_frame.pack(fill=tk.X, pady=5)
        
        self.btn_followers = ttk.Button(followers_btn_frame, text="Select Followers File", command=self.select_followers)
        self.btn_followers.pack(side=tk.LEFT)
        Tooltip(self.btn_followers, "Select HTML or JSON file for followers")
        
        self.followers_label = ttk.Label(followers_btn_frame, text=self.followers_file.split("/")[-1] if self.followers_file else "No file selected", padding=(10, 0))
        self.followers_label.pack(side=tk.LEFT)
        
        # Following
        following_btn_frame = ttk.Frame(file_frame)
        following_btn_frame.pack(fill=tk.X, pady=5)
        
        self.btn_following = ttk.Button(following_btn_frame, text="Select Following File", command=self.select_following)
        self.btn_following.pack(side=tk.LEFT)
        Tooltip(self.btn_following, "Select HTML or JSON file for following")
        
        self.following_label = ttk.Label(following_btn_frame, text=self.following_file.split("/")[-1] if self.following_file else "No file selected", padding=(10, 0))
        self.following_label.pack(side=tk.LEFT)
        
        # Whitelist
        whitelist_btn_frame = ttk.Frame(file_frame)
        whitelist_btn_frame.pack(fill=tk.X, pady=5)
        
        self.btn_whitelist = ttk.Button(whitelist_btn_frame, text="Select Whitelist TXT", command=self.select_whitelist)
        self.btn_whitelist.pack(side=tk.LEFT)
        Tooltip(self.btn_whitelist, "Optional: TXT file with usernames to exclude (one per line)")
        
        self.whitelist_label = ttk.Label(whitelist_btn_frame, text=self.whitelist_file.split("/")[-1] if self.whitelist_file else "No file selected", padding=(10, 0))
        self.whitelist_label.pack(side=tk.LEFT)
        
        # Compare Button
        self.btn_compare = ttk.Button(self.main_frame, text="Compare", command=self.compare_threaded)
        self.btn_compare.pack(pady=10)
        Tooltip(self.btn_compare, "Compare files and find unfollowers or fans")
        
        # Progress Bar
        self.progress = ttk.Progressbar(self.main_frame, mode="indeterminate")
        self.progress.pack(pady=5, fill=tk.X)
        self.progress.pack_forget()  # Hide initially
        
        # Stats Frame
        self.stats_frame = ttk.LabelFrame(self.main_frame, text="Statistics", padding=10)
        self.stats_frame.pack(fill=tk.X, pady=10)
        
        self.stats_labels = {
            "followers": ttk.Label(self.stats_frame, text="Followers: 0"),
            "following": ttk.Label(self.stats_frame, text="Following: 0"),
            "mutuals": ttk.Label(self.stats_frame, text="Mutuals: 0"),
            "results": ttk.Label(self.stats_frame, text="Results: 0")
        }
        for label in self.stats_labels.values():
            label.pack(anchor="w")
        
        # Search
        search_frame = ttk.Frame(self.main_frame)
        search_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=5)
        
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.search_users)
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.regex_check = ttk.Checkbutton(search_frame, text="Regex", variable=self.use_regex)
        self.regex_check.pack(side=tk.LEFT, padx=5)
        Tooltip(self.regex_check, "Use regular expression for search")
        
        # Count Label (integrated in stats)
        
        # Listbox with Scrollbar
        list_frame = ttk.Frame(self.main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.listbox_scroll = ttk.Scrollbar(list_frame)
        self.listbox_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox = tk.Listbox(list_frame, font=("Consolas", 12), yscrollcommand=self.listbox_scroll.set, selectmode=tk.EXTENDED)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox_scroll.config(command=self.listbox.yview)
        self.listbox.bind("<Double-Button-1>", self.open_profile)
        
        # Actions
        actions_frame = ttk.Frame(self.main_frame)
        actions_frame.pack(fill=tk.X, pady=5)
        
        self.btn_copy = ttk.Button(actions_frame, text="Copy Selected", command=self.copy_username)
        self.btn_copy.pack(side=tk.LEFT, padx=5)
        Tooltip(self.btn_copy, "Copy selected username(s) to clipboard")
        
        self.btn_export = ttk.Button(actions_frame, text="Export to TXT/CSV", command=self.export_results)
        self.btn_export.pack(side=tk.LEFT, padx=5)
        Tooltip(self.btn_export, "Export results to TXT or CSV")
        
        # Status Bar
        self.status_bar = ttk.Label(self.main_frame, text="Ready", relief=tk.SUNKEN, anchor="w", padding=5)
        self.status_bar.pack(fill=tk.X, pady=5)
        
    def apply_theme(self):
        style = ttk.Style()
        style.theme_use('default')
        
        # Configure styles
        style.configure("TFrame", background=self.theme["bg"])
        style.configure("TLabel", background=self.theme["bg"], foreground=self.theme["fg"])
        style.configure("TButton", background=self.theme["btn_bg"], foreground=self.theme["btn_fg"])
        style.configure("TEntry", fieldbackground=self.theme["entry_bg"], foreground=self.theme["fg"])
        style.configure("TLabelFrame", background=self.theme["bg"], foreground=self.theme["fg"])
        style.configure("TLabelFrame.Label", background=self.theme["bg"], foreground=self.theme["fg"])
        
        self.root.configure(bg=self.theme["bg"])
        
        self.listbox.configure(bg=self.theme["list_bg"], fg=self.theme["list_fg"],
                               selectbackground=self.theme["accent"], selectforeground=self.theme["btn_fg"])
        
        self.status_bar.configure(background=self.theme["btn_bg"], foreground=self.theme["status"])
        
    def setup_keyboard_shortcuts(self):
        self.root.bind("<Control-o>", lambda e: self.select_followers())
        self.root.bind("<Control-Shift-O>", lambda e: self.select_following())
        self.root.bind("<Control-r>", lambda e: self.compare_threaded())
        self.root.bind("<Control-c>", lambda e: self.copy_username())
        self.root.bind("<Control-e>", lambda e: self.export_results())
        
    def show_about(self):
        messagebox.showinfo("About", "Instagram Unfollow Tool\nVersion 1.1\n\nA professional tool to find users you follow who don't follow you back, or vice versa.\nSupports HTML and JSON from Instagram data export.\n\nCreated with Tkinter.")
        
    def select_followers(self):
        initialdir = os.path.dirname(self.followers_file) if self.followers_file else "."
        self.followers_file = filedialog.askopenfilename(title="Select Followers File", initialdir=initialdir, filetypes=[("HTML/JSON files", "*.html *.json")])
        if self.followers_file:
            self.followers_label.config(text=self.followers_file.split("/")[-1])
            self.status_bar.config(text="Followers file selected")
            self.save_config()
            
    def select_following(self):
        initialdir = os.path.dirname(self.following_file) if self.following_file else "."
        self.following_file = filedialog.askopenfilename(title="Select Following File", initialdir=initialdir, filetypes=[("HTML/JSON files", "*.html *.json")])
        if self.following_file:
            self.following_label.config(text=self.following_file.split("/")[-1])
            self.status_bar.config(text="Following file selected")
            self.save_config()
            
    def select_whitelist(self):
        initialdir = os.path.dirname(self.whitelist_file) if self.whitelist_file else "."
        self.whitelist_file = filedialog.askopenfilename(title="Select Whitelist TXT", initialdir=initialdir, filetypes=[("TXT files", "*.txt")])
        if self.whitelist_file:
            self.whitelist_label.config(text=self.whitelist_file.split("/")[-1])
            self.status_bar.config(text="Whitelist file selected")
            self.load_whitelist()
            self.save_config()
            
    def load_whitelist(self):
        if self.whitelist_file:
            try:
                with open(self.whitelist_file, "r", encoding="utf-8") as f:
                    self.whitelist = {line.strip() for line in f if line.strip()}
                self.status_bar.config(text=f"Loaded {len(self.whitelist)} whitelist users")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load whitelist: {str(e)}")
                self.whitelist = set()
        
    def extract_usernames(self, path, is_followers=True):
        try:
            if path.endswith(".json"):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    usernames = {item["string_list_data"][0]["value"] for item in data if "string_list_data" in item and item["string_list_data"]}
                elif "relationships_following" in data:
                    usernames = {item["string_list_data"][0]["value"] for item in data["relationships_following"] if "string_list_data" in item and item["string_list_data"]}
                elif "relationships_followers" in data:
                    usernames = {item["string_list_data"][0]["value"] for item in data["relationships_followers"] if "string_list_data" in item and item["string_list_data"]}
                else:
                    raise ValueError("Unknown JSON structure")
            else:  # HTML
                with open(path, "r", encoding="utf-8") as f:
                    html = f.read()
                usernames = set(re.findall(r'href="https://www.instagram.com/(?:_u/)?([^"/]+)"', html))
            return usernames
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file {path}: {str(e)}")
            return set()
        
    def compare_threaded(self):
        if not self.followers_file or not self.following_file:
            messagebox.showwarning("Missing Files", "Please select both Followers and Following files.")
            return
        
        self.status_bar.config(text="Comparing...")
        self.progress.pack()
        self.progress.start()
        
        thread = threading.Thread(target=self.compare_worker)
        thread.start()
        self.root.after(100, self.check_queue)
        
    def compare_worker(self):
        self.followers = self.extract_usernames(self.followers_file, is_followers=True)
        self.following = self.extract_usernames(self.following_file, is_followers=False)
        
        if self.mode.get() == "Unfollowers":
            diff = self.following - self.followers
        else:
            diff = self.followers - self.following
        
        diff -= self.whitelist
        
        self.all_results = sorted(diff)
        
        self.queue.put("done")
        
    def check_queue(self):
        try:
            msg = self.queue.get_nowait()
            if msg == "done":
                self.update_stats()
                self.update_list(self.all_results)
                self.auto_save()
                self.status_bar.config(text=f"Comparison complete — {len(self.all_results)} results found")
                self.progress.stop()
                self.progress.pack_forget()
        except queue.Empty:
            self.root.after(100, self.check_queue)
        
    def update_stats(self):
        mutuals = len(self.followers & self.following)
        self.stats_labels["followers"].config(text=f"Followers: {len(self.followers)}")
        self.stats_labels["following"].config(text=f"Following: {len(self.following)}")
        self.stats_labels["mutuals"].config(text=f"Mutuals: {mutuals}")
        self.stats_labels["results"].config(text=f"{self.mode.get()}: {len(self.all_results)}")
        
    def update_list(self, data):
        self.listbox.delete(0, tk.END)
        for u in data:
            self.listbox.insert(tk.END, u)
        
    def search_users(self, *args):
        query = self.search_var.get().lower()
        if not query:
            filtered = self.all_results
        else:
            if self.use_regex.get():
                try:
                    pattern = re.compile(query)
                    filtered = [u for u in self.all_results if pattern.search(u.lower())]
                except re.error:
                    filtered = []
                    self.status_bar.config(text="Invalid regex")
                    return
            else:
                filtered = [u for u in self.all_results if query in u.lower()]
        self.update_list(filtered)
        self.status_bar.config(text=f"Search complete — {len(filtered)} result(s)")
        
    def copy_username(self):
        try:
            selected = self.listbox.curselection()
            if selected:
                usernames = [self.listbox.get(idx) for idx in selected]
                text = "\n".join(usernames)
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
                self.status_bar.config(text=f"Copied {len(usernames)} username(s)")
            else:
                self.status_bar.config(text="No username selected")
        except Exception as e:
            self.status_bar.config(text="Error copying username")
            
    def open_profile(self, event):
        try:
            selected = self.listbox.curselection()
            if selected:
                username = self.listbox.get(selected[0])  # Open first selected
                webbrowser.open(f"https://www.instagram.com/{username}/")
        except:
            pass
        
    def export_results(self):
        if not self.all_results:
            messagebox.showwarning("No Results", "No results to export. Please compare files first.")
            return
        
        filetypes = [("Text files", "*.txt"), ("CSV files", "*.csv")]
        file_path = filedialog.asksaveasfilename(title="Save Results", defaultextension=".txt", filetypes=filetypes)
        if file_path:
            try:
                if file_path.endswith(".csv"):
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write("Username\n")
                        for u in self.all_results:
                            f.write(f"{u}\n")
                else:
                    with open(file_path, "w", encoding="utf-8") as f:
                        for u in self.all_results:
                            f.write(u + "\n")
                self.status_bar.config(text=f"Exported to {file_path.split('/')[-1]}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export: {str(e)}")
    
    def auto_save(self):
        if self.all_results:
            mode_lower = self.mode.get().lower()
            today = datetime.date.today().isoformat()
            file_name = f"{mode_lower}_{today}.txt"
            with open(file_name, "w", encoding="utf-8") as f:
                for u in self.all_results:
                    f.write(u + "\n")
            self.status_bar.config(text=f"Auto-saved to {file_name}")

if __name__ == "__main__":
    root = tk.Tk()
    app = InstagramUnfollowApp(root)
    root.mainloop()
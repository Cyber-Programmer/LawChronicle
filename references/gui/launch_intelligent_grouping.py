"""
Intelligent Grouping Launcher

A launcher script that allows users to choose between different intelligent grouping tools:
1. Full Intelligent Grouping GUI - Complete context-aware analysis
2. Constitutional Amendment Detector - Focused on constitutional amendments
3. Exit

This provides a simple way to access all the intelligent grouping functionality.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import subprocess

class IntelligentGroupingLauncher:
    """Launcher for intelligent grouping tools"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Intelligent Grouping Tools Launcher")
        self.root.geometry("500x400")
        self.root.configure(bg='#f0f0f0')
        
        # Center the window
        self.center_window()
        
        # Initialize UI
        self.init_ui()
    
    def center_window(self):
        """Center the window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def init_ui(self):
        """Initialize the user interface"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="🧠 Intelligent Grouping Tools", 
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # Description
        desc_label = ttk.Label(main_frame, 
                              text="Choose a tool to launch intelligent, context-aware statute grouping:",
                              font=('Arial', 10))
        desc_label.pack(pady=(0, 30))
        
        # Tool selection frame
        tools_frame = ttk.LabelFrame(main_frame, text="Available Tools", padding="20")
        tools_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Tool 1: Full Intelligent Grouping
        tool1_frame = ttk.Frame(tools_frame)
        tool1_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(tool1_frame, text="🔧 Full Intelligent Grouping", 
                 font=('Arial', 12, 'bold')).pack(anchor=tk.W)
        ttk.Label(tool1_frame, 
                 text="Complete context-aware analysis with constitutional detection, legal lineage, and intelligent grouping",
                 font=('Arial', 9)).pack(anchor=tk.W, pady=(0, 5))
        
        ttk.Button(tool1_frame, text="Launch Full Tool", 
                  command=self.launch_full_tool,
                  style='Accent.TButton').pack(anchor=tk.W)
        
        # Tool 2: Constitutional Amendment Detector
        tool2_frame = ttk.Frame(tools_frame)
        tool2_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(tool2_frame, text="📜 Constitutional Amendment Detector", 
                 font=('Arial', 12, 'bold')).pack(anchor=tk.W)
        ttk.Label(tool2_frame, 
                 text="Focused tool for detecting and analyzing constitutional amendments and building amendment chains",
                 font=('Arial', 9)).pack(anchor=tk.W, pady=(0, 5))
        
        ttk.Button(tool2_frame, text="Launch Amendment Detector", 
                  command=self.launch_amendment_detector,
                  style='Accent.TButton').pack(anchor=tk.W)
        
        # Configuration info
        config_frame = ttk.LabelFrame(main_frame, text="Configuration", padding="15")
        config_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(config_frame, 
                 text="Make sure to configure your Azure OpenAI credentials in 'config_intelligent_grouping.json'",
                 font=('Arial', 9)).pack()
        
        ttk.Button(config_frame, text="Edit Configuration", 
                  command=self.edit_configuration).pack(pady=(10, 0))
        
        # Exit button
        ttk.Button(main_frame, text="Exit", 
                  command=self.root.quit,
                  style='Danger.TButton').pack(pady=(20, 0))
    
    def launch_full_tool(self):
        """Launch the full intelligent grouping tool"""
        try:
            script_path = os.path.join(os.path.dirname(__file__), "intelligent_grouping_gui.py")
            if os.path.exists(script_path):
                # Launch in new process
                subprocess.Popen([sys.executable, script_path])
                messagebox.showinfo("Success", "Full Intelligent Grouping Tool launched successfully!")
            else:
                messagebox.showerror("Error", f"Script not found: {script_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch tool: {e}")
    
    def launch_amendment_detector(self):
        """Launch the constitutional amendment detector"""
        try:
            script_path = os.path.join(os.path.dirname(__file__), "constitutional_amendment_detector_gui.py")
            if os.path.exists(script_path):
                # Launch in new process
                subprocess.Popen([sys.executable, script_path])
                messagebox.showinfo("Success", "Constitutional Amendment Detector launched successfully!")
            else:
                messagebox.showerror("Error", f"Script not found: {script_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch tool: {e}")
    
    def edit_configuration(self):
        """Open configuration file for editing"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), "config_intelligent_grouping.json")
            if os.path.exists(config_path):
                # Try to open with default text editor
                if sys.platform == "win32":
                    os.startfile(config_path)
                elif sys.platform == "darwin":
                    subprocess.run(["open", config_path])
                else:
                    subprocess.run(["xdg-open", config_path])
                
                messagebox.showinfo("Success", "Configuration file opened for editing")
            else:
                messagebox.showerror("Error", f"Configuration file not found: {config_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open configuration: {e}")

def main():
    """Main entry point"""
    root = tk.Tk()
    
    # Configure styles
    style = ttk.Style()
    style.configure('Accent.TButton', background='#0078d4', foreground='white')
    style.configure('Danger.TButton', background='#d83b01', foreground='white')
    
    app = IntelligentGroupingLauncher(root)
    root.mainloop()

if __name__ == "__main__":
    main()

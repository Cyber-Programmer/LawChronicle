"""
Constitutional Amendment Detector GUI

A focused GUI application for detecting and analyzing constitutional amendments
in Pakistani legal documents. This tool specifically identifies constitutional
amendment relationships and chains.

Features:
- Constitutional amendment detection
- Amendment chain visualization
- Confidence scoring
- Export capabilities
- Interactive validation
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Optional
from collections import defaultdict

# Add parent directory to path for utils imports
parent_dir = os.path.join(os.path.dirname(__file__), '..')
sys.path.append(parent_dir)

# Azure OpenAI imports
try:
    from openai import AzureOpenAI
    AZURE_AVAILABLE = True
except ImportError:
    AzureOpenAI = None
    AZURE_AVAILABLE = False

class ConstitutionalAmendmentDetector:
    """Detects constitutional amendments using GPT analysis"""
    
    def __init__(self, gpt_client, config: Dict):
        self.gpt_client = gpt_client
        self.config = config
        
    def detect_constitutional_amendment(self, statute: Dict) -> Dict:
        """Detect if statute is a constitutional amendment"""
        prompt = f"""
        You are a Pakistani constitutional law expert with 25+ years experience.
        
        Analyze if this statute is a constitutional amendment:
        
        Statute Name: {statute.get('Statute_Name', '')}
        Province: {statute.get('Province', '')}
        Preamble: {statute.get('Preamble', '')[:500]}...
        
        Determine:
        1. Is this a constitutional amendment? (Yes/No)
        2. What constitutional article/section does it modify?
        3. What amendment number is this?
        4. What is the relationship type?
        5. Confidence level (0-100%)
        
        Respond in this exact JSON format:
        {{
            "is_constitutional": true/false,
            "constitutional_base": "Constitution of Pakistan",
            "amendment_number": "18th",
            "amendment_type": "amendment/repeal/addition",
            "target_articles": ["Article 51", "Article 59"],
            "confidence": 95
        }}
        """
        
        try:
            response = self.gpt_client.chat.completions.create(
                model=self.config["azure_openai"]["model"],
                messages=[
                    {"role": "system", "content": "You are a Pakistani constitutional law expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config["azure_openai"]["temperature"],
                max_tokens=self.config["azure_openai"]["max_tokens"]
            )
            result = json.loads(response.choices[0].message.content)
            return result
        except Exception as e:
            print(f"Error detecting constitutional amendment: {e}")
            return self._get_fallback_analysis(statute)
    
    def _get_fallback_analysis(self, statute: Dict) -> Dict:
        """Fallback analysis when GPT fails"""
        name = statute.get('Statute_Name', '').lower()
        if 'constitution' in name and ('amendment' in name or 'order' in name):
            return {
                "is_constitutional": True,
                "constitutional_base": "Constitution of Pakistan",
                "amendment_number": "unknown",
                "amendment_type": "amendment",
                "target_articles": [],
                "confidence": 60
            }
        return {
            "is_constitutional": False,
            "constitutional_base": None,
            "amendment_number": None,
            "amendment_type": None,
            "target_articles": [],
            "confidence": 50
        }

class ConstitutionalAmendmentDetectorGUI:
    """GUI for constitutional amendment detection"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Constitutional Amendment Detector")
        
        # Load configuration
        self.config = self.load_config()
        
        # Initialize components
        self.init_components()
        self.init_ui()
        
        # Data storage
        self.statutes = []
        self.constitutional_amendments = []
        self.amendment_chains = {}
        
    def load_config(self) -> Dict:
        """Load configuration from file"""
        config_file = "gui/config_intelligent_grouping.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading config: {e}")
        
        # Default configuration
        return {
            "mongo_uri": "mongodb://localhost:27017",
            "source_db": "Batched-Statutes",
            "source_collection": "statute",
            "azure_openai": {
                "api_key": "",
                "endpoint": "",
                "model": "gpt-4o",
                "temperature": 0.1,
                "max_tokens": 1000
            }
        }
    
    def init_components(self):
        """Initialize core components"""
        # Initialize Azure OpenAI client
        if AZURE_AVAILABLE and self.config.get("azure_openai", {}).get("api_key"):
            self.gpt_client = AzureOpenAI(
                api_key=self.config["azure_openai"]["api_key"],
                api_version=self.config["azure_openai"]["api_version"],
                azure_endpoint=self.config["azure_openai"]["endpoint"]
            )
        else:
            self.gpt_client = None
            print("⚠️ Azure OpenAI not available")
        
        # Initialize detector
        if self.gpt_client:
            self.detector = ConstitutionalAmendmentDetector(self.gpt_client, self.config)
        else:
            self.detector = None
        
        # Initialize MongoDB connection
        try:
            from pymongo import MongoClient
            self.mongo_client = MongoClient(self.config["mongo_uri"])
            self.db = self.mongo_client[self.config["source_db"]]
            self.collection = self.db[self.config["source_collection"]]
            print("✅ MongoDB connection established")
        except Exception as e:
            print(f"❌ MongoDB connection failed: {e}")
            self.mongo_client = None
    
    def init_ui(self):
        """Initialize the user interface"""
        # Configure window
        self.root.geometry("1200x800")
        self.root.configure(bg='#f0f0f0')
        
        # Create main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create control panel
        self.create_control_panel(main_container)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # Create tabs
        self.create_detection_tab()
        self.create_amendment_chains_tab()
        self.create_statistics_tab()
        
        # Create status bar
        self.create_status_bar(main_container)
    
    def create_control_panel(self, parent):
        """Create the control panel"""
        control_frame = ttk.LabelFrame(parent, text="Control Panel", padding=10)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Database controls
        db_frame = ttk.Frame(control_frame)
        db_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(db_frame, text="Source DB:").pack(side=tk.LEFT)
        self.source_db_var = tk.StringVar(value=self.config["source_db"])
        ttk.Entry(db_frame, textvariable=self.source_db_var, width=20).pack(side=tk.LEFT, padx=(5, 10))
        
        ttk.Label(db_frame, text="Collection:").pack(side=tk.LEFT)
        self.source_coll_var = tk.StringVar(value=self.config["source_collection"])
        ttk.Entry(db_frame, textvariable=self.source_coll_var, width=20).pack(side=tk.LEFT, padx=(5, 10))
        
        ttk.Button(db_frame, text="Load Statutes", command=self.load_statutes).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(db_frame, text="Refresh", command=self.refresh_data).pack(side=tk.LEFT, padx=(5, 0))
        
        # Detection controls
        detection_frame = ttk.Frame(control_frame)
        detection_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(detection_frame, text="Detection:").pack(side=tk.LEFT)
        ttk.Button(detection_frame, text="Start Detection", command=self.start_detection).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Button(detection_frame, text="Analyze Selected", command=self.analyze_selected).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Button(detection_frame, text="Build Amendment Chains", command=self.build_amendment_chains).pack(side=tk.LEFT, padx=(5, 5))
        
        # Export controls
        export_frame = ttk.Frame(control_frame)
        export_frame.pack(fill=tk.X)
        
        ttk.Label(export_frame, text="Export:").pack(side=tk.LEFT)
        ttk.Button(export_frame, text="Export Amendments", command=self.export_amendments).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Button(export_frame, text="Export Chains", command=self.export_chains).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Button(export_frame, text="Export Report", command=self.export_report).pack(side=tk.LEFT, padx=(5, 5))
    
    def create_detection_tab(self):
        """Create the detection tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Amendment Detection")
        
        # Create split view
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - Statute list
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        
        ttk.Label(left_frame, text="Statutes", font=('Arial', 12, 'bold')).pack(pady=5)
        
        # Statute listbox
        self.statute_listbox = tk.Listbox(left_frame, selectmode=tk.SINGLE)
        self.statute_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.statute_listbox.bind('<<ListboxSelect>>', self.on_statute_select)
        
        # Right panel - Detection results
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)
        
        ttk.Label(right_frame, text="Constitutional Amendment Detection", font=('Arial', 12, 'bold')).pack(pady=5)
        
        # Detection results display
        self.detection_text = scrolledtext.ScrolledText(right_frame, height=20, width=60)
        self.detection_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Detection controls
        control_frame = ttk.Frame(right_frame)
        control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(control_frame, text="Detect Amendment", 
                  command=self.detect_selected_amendment).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Clear", 
                  command=lambda: self.detection_text.delete(1.0, tk.END)).pack(side=tk.LEFT, padx=5)
    
    def create_amendment_chains_tab(self):
        """Create the amendment chains tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Amendment Chains")
        
        # Amendment chains treeview
        columns = ('Chain ID', 'Base Constitution', 'Amendments', 'Latest Amendment', 'Status')
        self.chains_tree = ttk.Treeview(tab, columns=columns, show='headings')
        
        for col in columns:
            self.chains_tree.heading(col, text=col)
            self.chains_tree.column(col, width=150)
        
        self.chains_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Chain controls
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(control_frame, text="View Chain Details", 
                  command=self.view_chain_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Export Chain", 
                  command=self.export_selected_chain).pack(side=tk.LEFT, padx=5)
    
    def create_statistics_tab(self):
        """Create the statistics tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Statistics")
        
        # Statistics display
        self.stats_text = scrolledtext.ScrolledText(tab, height=20, width=80)
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Refresh button
        ttk.Button(tab, text="Refresh Statistics", 
                  command=self.refresh_statistics).pack(pady=5)
    
    def create_status_bar(self, parent):
        """Create the status bar"""
        self.status_bar = ttk.Label(parent, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, pady=(10, 0))
    
    def load_statutes(self):
        """Load statutes from database"""
        if not self.mongo_client:
            messagebox.showerror("Error", "MongoDB connection not available")
            return
        
        try:
            self.status_bar.config(text="Loading statutes...")
            self.root.update()
            
            # Load statutes
            self.statutes = list(self.collection.find({}))
            
            # Update display
            self.update_statutes_display()
            
            self.status_bar.config(text=f"Loaded {len(self.statutes)} statutes")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load statutes: {e}")
            self.status_bar.config(text="Error loading statutes")
    
    def update_statutes_display(self):
        """Update the statutes listbox"""
        self.statute_listbox.delete(0, tk.END)
        for statute in self.statutes:
            name = statute.get('Statute_Name', 'Unknown')
            self.statute_listbox.insert(tk.END, name)
    
    def on_statute_select(self, event):
        """Handle statute selection"""
        selection = self.statute_listbox.curselection()
        if selection:
            index = selection[0]
            statute = self.statutes[index]
            self.display_statute_info(statute)
    
    def display_statute_info(self, statute):
        """Display basic statute information"""
        info = f"""Statute Information:
Name: {statute.get('Statute_Name', 'Unknown')}
Province: {statute.get('Province', 'Unknown')}
Date: {statute.get('Date', 'Unknown')}
Type: {statute.get('Statute_Type', 'Unknown')}

Preamble Preview:
{statute.get('Preamble', 'No preamble available')[:300]}...
"""
        self.detection_text.delete(1.0, tk.END)
        self.detection_text.insert(1.0, info)
    
    def start_detection(self):
        """Start constitutional amendment detection for all statutes"""
        if not self.statutes:
            messagebox.showwarning("Warning", "No statutes loaded")
            return
        
        if not self.detector:
            messagebox.showerror("Error", "Amendment detector not available")
            return
        
        # Start detection in background thread
        import threading
        thread = threading.Thread(target=self._run_detection)
        thread.daemon = True
        thread.start()
    
    def _run_detection(self):
        """Run detection in background"""
        try:
            self.status_bar.config(text="Running constitutional amendment detection...")
            
            total = len(self.statutes)
            self.constitutional_amendments = []
            
            for i, statute in enumerate(self.statutes):
                # Update progress
                self.status_bar.config(text=f"Analyzing statute {i+1}/{total}")
                self.root.update()
                
                # Detect constitutional amendment
                result = self.detector.detect_constitutional_amendment(statute)
                
                if result.get('is_constitutional', False):
                    amendment_info = {
                        'statute_id': str(statute.get('_id', '')),
                        'statute_name': statute.get('Statute_Name', ''),
                        'detection_result': result,
                        'statute_data': statute
                    }
                    self.constitutional_amendments.append(amendment_info)
                
                # Small delay to prevent overwhelming the API
                import time
                time.sleep(0.1)
            
            self.status_bar.config(text(f"Detection completed: {len(self.constitutional_amendments)} constitutional amendments found")
            
        except Exception as e:
            self.status_bar.config(text=f"Error: {e}")
    
    def analyze_selected(self):
        """Analyze selected statute for constitutional amendment"""
        selection = self.statute_listbox.curselection()
        if selection:
            index = selection[0]
            statute = self.statutes[index]
            
            if self.detector:
                result = self.detector.detect_constitutional_amendment(statute)
                
                display_text = f"""Constitutional Amendment Detection Result:

Statute: {statute.get('Statute_Name', 'Unknown')}

Analysis Result:
{json.dumps(result, indent=2)}

Interpretation:
- Is Constitutional Amendment: {'Yes' if result.get('is_constitutional') else 'No'}
- Constitutional Base: {result.get('constitutional_base', 'N/A')}
- Amendment Number: {result.get('amendment_number', 'N/A')}
- Amendment Type: {result.get('amendment_type', 'N/A')}
- Target Articles: {', '.join(result.get('target_articles', []))}
- Confidence: {result.get('confidence', 0)}%
"""
                
                self.detection_text.delete(1.0, tk.END)
                self.detection_text.insert(1.0, display_text)
    
    def detect_selected_amendment(self):
        """Detect amendment for selected statute"""
        self.analyze_selected()
    
    def build_amendment_chains(self):
        """Build amendment chains from detected amendments"""
        if not self.constitutional_amendments:
            messagebox.showwarning("Warning", "No constitutional amendments detected")
            return
        
        try:
            self.status_bar.config(text="Building amendment chains...")
            
            # Group amendments by constitutional base
            chains = defaultdict(list)
            for amendment in self.constitutional_amendments:
                base = amendment['detection_result'].get('constitutional_base', 'Unknown')
                chains[base].append(amendment)
            
            # Sort each chain by amendment number
            for base, amendments in chains.items():
                # Try to sort by amendment number
                try:
                    amendments.sort(key=lambda x: self._extract_amendment_number(
                        x['detection_result'].get('amendment_number', '0')
                    ))
                except:
                    pass  # Keep original order if sorting fails
            
            self.amendment_chains = dict(chains)
            
            # Update chains display
            self.update_chains_display()
            
            self.status_bar.config(text(f"Built {len(self.amendment_chains)} amendment chains")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to build chains: {e}")
            self.status_bar.config(text="Error building chains")
    
    def _extract_amendment_number(self, amendment_str: str) -> int:
        """Extract numeric amendment number from string"""
        if not amendment_str or amendment_str == 'unknown':
            return 0
        
        # Try to extract number from strings like "18th", "21st", etc.
        import re
        match = re.search(r'(\d+)', amendment_str)
        if match:
            return int(match.group(1))
        return 0
    
    def update_chains_display(self):
        """Update the chains treeview"""
        # Clear existing items
        for item in self.chains_tree.get_children():
            self.chains_tree.delete(item)
        
        # Add chains
        for i, (base, amendments) in enumerate(self.amendment_chains.items()):
            latest = amendments[-1] if amendments else {}
            self.chains_tree.insert('', 'end', values=(
                f"chain_{i}",
                base,
                len(amendments),
                latest.get('detection_result', {}).get('amendment_number', 'N/A'),
                'Active'
            ))
    
    def view_chain_details(self):
        """View details of selected chain"""
        selection = self.chains_tree.selection()
        if selection:
            # Implementation for viewing chain details
            pass
    
    def export_amendments(self):
        """Export constitutional amendments"""
        if not self.constitutional_amendments:
            messagebox.showwarning("Warning", "No amendments to export")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                export_data = {
                    'export_timestamp': datetime.now().isoformat(),
                    'total_amendments': len(self.constitutional_amendments),
                    'amendments': self.constitutional_amendments
                }
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
                
                messagebox.showinfo("Success", f"Amendments exported to {filename}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {e}")
    
    def export_chains(self):
        """Export amendment chains"""
        if not self.amendment_chains:
            messagebox.showwarning("Warning", "No chains to export")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                export_data = {
                    'export_timestamp': datetime.now().isoformat(),
                    'total_chains': len(self.amendment_chains),
                    'chains': self.amendment_chains
                }
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
                
                messagebox.showinfo("Success", f"Chains exported to {filename}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {e}")
    
    def export_report(self):
        """Export comprehensive report"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                report = self._generate_report()
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(report)
                
                messagebox.showinfo("Success", f"Report exported to {filename}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export report: {e}")
    
    def _generate_report(self) -> str:
        """Generate comprehensive report"""
        report = f"""# Constitutional Amendment Detection Report

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary
- Total Statutes Analyzed: {len(self.statutes)}
- Constitutional Amendments Detected: {len(self.constitutional_amendments)}
- Amendment Chains Built: {len(self.amendment_chains)}

## Constitutional Amendments
"""
        
        for amendment in self.constitutional_amendments:
            result = amendment['detection_result']
            report += f"- **{amendment['statute_name']}**\n"
            report += f"  - Amendment Number: {result.get('amendment_number', 'Unknown')}\n"
            report += f"  - Type: {result.get('amendment_type', 'Unknown')}\n"
            report += f"  - Target Articles: {', '.join(result.get('target_articles', []))}\n"
            report += f"  - Confidence: {result.get('confidence', 0)}%\n\n"
        
        report += "\n## Amendment Chains\n"
        for base, amendments in self.amendment_chains.items():
            report += f"- **{base}**: {len(amendments)} amendments\n"
            for amendment in amendments:
                result = amendment['detection_result']
                report += f"  - {result.get('amendment_number', 'Unknown')}: {amendment['statute_name']}\n"
        
        return report
    
    def refresh_data(self):
        """Refresh data from database"""
        self.load_statutes()
    
    def refresh_statistics(self):
        """Refresh statistics display"""
        stats = self._calculate_statistics()
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(1.0, stats)
    
    def _calculate_statistics(self) -> str:
        """Calculate and return statistics"""
        stats = f"""Constitutional Amendment Detection Statistics
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Data Overview:
- Total Statutes: {len(self.statutes)}
- Constitutional Amendments Detected: {len(self.constitutional_amendments)}
- Amendment Chains Built: {len(self.amendment_chains)}

Amendment Analysis:
- Amendment Types: {len(set(a['detection_result'].get('amendment_type') for a in self.constitutional_amendments))}
- Average Confidence Score: {sum(a['detection_result'].get('confidence', 0) for a in self.constitutional_amendments) / len(self.constitutional_amendments) if self.constitutional_amendments else 0:.1f}%

Chain Analysis:
"""
        
        if self.amendment_chains:
            for base, amendments in self.amendment_chains.items():
                stats += f"- {base}: {len(amendments)} amendments\n"
                if amendments:
                    latest = amendments[-1]
                    stats += f"  - Latest: {latest['detection_result'].get('amendment_number', 'Unknown')}\n"
        
        return stats
    
    def export_selected_chain(self):
        """Export selected chain"""
        selection = self.chains_tree.selection()
        if selection:
            # Implementation for exporting selected chain
            pass

def main():
    """Main entry point"""
    root = tk.Tk()
    app = ConstitutionalAmendmentDetectorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

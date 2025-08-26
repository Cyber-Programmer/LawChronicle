"""
Intelligent Grouping GUI - Context-Aware Statute & Section Grouping

A comprehensive GUI application for intelligent, context-aware statute grouping that:
- Detects constitutional amendment relationships
- Analyzes legal lineage and context
- Uses conditional GPT prompting for different legal contexts
- Preserves amendment chains and legal relationships
- Provides interactive analysis and validation

Features:
- Constitutional amendment detection
- Legal lineage analysis
- Amendment relationship mapping
- Context-aware grouping decisions
- Interactive validation and override
- Real-time progress monitoring
- Comprehensive export options
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import numpy as np
from pymongo import MongoClient
import json
import os
import sys
import re
import threading
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict, Counter
from dataclasses import dataclass
import time
from rapidfuzz import process, fuzz
from difflib import SequenceMatcher

# Add parent directory to path for utils imports
parent_dir = os.path.join(os.path.dirname(__file__), '..')
sys.path.append(parent_dir)

# Import GPT optimization utilities
try:
    from utils.gpt_cache import gpt_cache
    from utils.gpt_rate_limiter import rate_limited_gpt_call
    from utils.gpt_prompt_optimizer import optimize_gpt_prompt
    from utils.gpt_monitor import gpt_monitor
    GPT_UTILS_AVAILABLE = True
    print("✅ GPT optimization utilities imported successfully")
except ImportError as e:
    GPT_UTILS_AVAILABLE = False
    print(f"⚠️ Warning: GPT optimization utilities not available: {e}")

# Import intelligent preprocessor
try:
    from intelligent_preprocessor import IntelligentPreprocessor, PreprocessingResult
    PREPROCESSOR_AVAILABLE = True
    print("✅ Intelligent preprocessor imported successfully")
except ImportError as e:
    PREPROCESSOR_AVAILABLE = False
    print(f"⚠️ Warning: Intelligent preprocessor not available: {e}")

# Azure OpenAI imports
try:
    from openai import AzureOpenAI
    AZURE_AVAILABLE = True
except ImportError:
    AzureOpenAI = None
    AZURE_AVAILABLE = False

@dataclass
class StatuteContext:
    """Data class for statute context analysis"""
    statute_id: str
    statute_name: str
    constitutional_lineage: Dict = None
    legal_context: Dict = None
    amendment_targets: List[str] = None
    legal_references: List[str] = None
    confidence_score: float = 0.0
    analysis_timestamp: datetime = None
    
    def __post_init__(self):
        if self.constitutional_lineage is None:
            self.constitutional_lineage = {}
        if self.legal_context is None:
            self.legal_context = {}
        if self.amendment_targets is None:
            self.amendment_targets = []
        if self.legal_references is None:
            self.legal_references = []
        if self.analysis_timestamp is None:
            self.analysis_timestamp = datetime.now()

@dataclass
class StatuteRelationship:
    """Data class for statute relationships"""
    statute_a_id: str
    statute_b_id: str
    relationship_type: str
    confidence_score: float
    context_analysis: Dict
    gpt_analysis: Dict = None
    manual_override: bool = False
    override_reason: str = ""

class IntelligentContextAnalyzer:
    """Intelligent context analysis for statutes"""
    
    def __init__(self, gpt_client, config: Dict):
        self.gpt_client = gpt_client
        self.config = config
        self.cache = gpt_cache if GPT_UTILS_AVAILABLE else {}
        
        # Initialize preprocessor if available
        if PREPROCESSOR_AVAILABLE:
            self.preprocessor = IntelligentPreprocessor(config)
            print("✅ Intelligent preprocessor initialized")
        else:
            self.preprocessor = None
            print("⚠️ Intelligent preprocessor not available")
        
    def analyze_constitutional_lineage(self, statute: Dict) -> Dict:
        """Analyze constitutional lineage of a statute"""
        
        # Use preprocessing if available
        if self.preprocessor:
            preprocessing_result = self.preprocessor.preprocess_statute(statute)
            
            # Log preprocessing results
            print(f"🔍 Preprocessing result: {preprocessing_result.rule_based_classification}")
            print(f"🔍 Should use GPT: {preprocessing_result.should_use_gpt}")
            print(f"🔍 Confidence: {preprocessing_result.confidence_score}")
            
            # If preprocessing gives high confidence, return rule-based result
            if not preprocessing_result.should_use_gpt:
                print("✅ Using rule-based classification (no GPT needed)")
                return self._convert_preprocessing_to_gpt_format(preprocessing_result, statute)
            
            # If language translation is needed, handle it
            if preprocessing_result.translation_required:
                print(f"🌐 Translation required from {preprocessing_result.language_detected}")
                statute = self._prepare_translated_statute(statute, preprocessing_result)
        
        prompt = f"""
        You are a Pakistani constitutional law expert with 25+ years experience.
        
        Analyze if this statute is related to the Constitution of Pakistan:
        
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
        
        IMPORTANT: Respond ONLY with valid JSON. Do not include any other text, explanations, or formatting.
        """
        
        try:
            response = self.gpt_client.chat.completions.create(
                model=self.config["azure_openai"]["model"],
                messages=[
                    {"role": "system", "content": "You are a Pakistani constitutional law expert. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config["azure_openai"]["temperature"],
                max_tokens=self.config["azure_openai"]["max_tokens"]
            )
            
            # Get the response content
            content = response.choices[0].message.content.strip()
            print(f"GPT Response (constitutional): {content}")
            print(f"Response type: {type(content)}")
            print(f"Response length: {len(content)}")
            print(f"Response repr: {repr(content)}")
            
            # Check if content is empty or None
            if not content:
                print("❌ GPT returned empty content")
                return self._get_fallback_constitutional_analysis(statute)
            
            # Try to extract JSON if there's extra text
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            # Try to parse JSON
            try:
                result = json.loads(content)
                print(f"✅ JSON parsing successful: {result}")
                return result
            except json.JSONDecodeError as json_error:
                print(f"❌ JSON parsing failed: {json_error}")
                print(f"❌ Error at line {json_error.lineno}, column {json_error.colno}")
                print(f"Raw content: {repr(content)}")
                
                # Try to find JSON-like content in the response
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    print(f"🔍 Found JSON-like content: {json_match.group()}")
                    try:
                        result = json.loads(json_match.group())
                        print(f"✅ Extracted JSON successful: {result}")
                        return result
                    except json.JSONDecodeError:
                        print("❌ Extracted content still not valid JSON")
                        pass
                
                # If all else fails, return fallback
                print("⚠️ Using fallback analysis")
                return self._get_fallback_constitutional_analysis(statute)
                
        except Exception as e:
            print(f"Error analyzing constitutional lineage: {e}")
            print(f"Exception type: {type(e).__name__}")
            return self._get_fallback_constitutional_analysis(statute)
    
    def _convert_preprocessing_to_gpt_format(self, preprocessing_result: PreprocessingResult, statute: Dict) -> Dict:
        """Convert preprocessing result to GPT format"""
        rule_class = preprocessing_result.rule_based_classification
        
        if rule_class['type'] == 'constitutional_amendment':
            return {
                "is_constitutional": True,
                "constitutional_base": "Constitution of Pakistan",
                "amendment_number": "Unknown",
                "amendment_type": "amendment",
                "target_articles": [],
                "confidence": int(rule_class['confidence'] * 100)
            }
        elif rule_class['type'] == 'constitutional_order':
            return {
                "is_constitutional": True,
                "constitutional_base": "Constitution of Pakistan",
                "amendment_number": "Order",
                "amendment_type": "order",
                "target_articles": [],
                "confidence": int(rule_class['confidence'] * 100)
            }
        elif rule_class['type'] == 'constitutional_act':
            return {
                "is_constitutional": True,
                "constitutional_base": "Constitution of Pakistan",
                "amendment_number": "None",
                "amendment_type": "act",
                "target_articles": [],
                "confidence": int(rule_class['confidence'] * 100)
            }
        else:
            return {
                "is_constitutional": False,
                "constitutional_base": "None",
                "amendment_number": "None",
                "amendment_type": "none",
                "target_articles": [],
                "confidence": int(rule_class['confidence'] * 100)
            }
    
    def _prepare_translated_statute(self, statute: Dict, preprocessing_result: PreprocessingResult) -> Dict:
        """Prepare statute with translation if needed"""
        # For now, return original statute
        # In future, implement actual translation
        print(f"⚠️ Translation not yet implemented for {preprocessing_result.language_detected}")
        return statute
    
    def analyze_legal_context(self, statute: Dict) -> Dict:
        """Analyze legal context and references"""
        
        # Use preprocessing if available
        if self.preprocessor:
            preprocessing_result = self.preprocessor.preprocess_statute(statute)
            
            # If preprocessing gives high confidence, return rule-based result
            if not preprocessing_result.should_use_gpt:
                print("✅ Using rule-based legal context classification (no GPT needed)")
                return self._convert_preprocessing_to_legal_context_format(preprocessing_result, statute)
        
        text = f"{statute.get('Preamble', '')} {statute.get('Sections', [])}"
        
        prompt = f"""
        You are a legal document analyst specializing in statutory amendments.
        
        Extract legal context from this statute:
        
        Text: {text[:1000]}...
        
        Find:
        1. Legal references (Article X, Section Y, Act Z)
        2. Amendment targets (what is being modified)
        3. Relationship type (amendment, repeal, addition, consolidation)
        4. Legal lineage (what statutes this amends)
        
        Respond in this exact JSON format:
        {{
            "legal_references": ["Article 51", "Section 3 of Act 1973"],
            "amendment_targets": ["Article 51", "Section 3"],
            "relationship_type": "amendment",
            "legal_lineage": ["Constitution of Pakistan", "Act 1973"],
            "confidence": 90
        }}
        
        IMPORTANT: Respond ONLY with valid JSON. Do not include any other text, explanations, or formatting.
        """
        
        try:
            response = self.gpt_client.chat.completions.create(
                model=self.config["azure_openai"]["model"],
                messages=[
                    {"role": "system", "content": "You are a legal document analyst. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config["azure_openai"]["temperature"],
                max_tokens=self.config["azure_openai"]["max_tokens"]
            )
            
            # Get the response content
            content = response.choices[0].message.content.strip()
            print(f"GPT Response (legal context): {content}")
            print(f"Response type: {type(content)}")
            print(f"Response length: {len(content)}")
            print(f"Response repr: {repr(content)}")
            
            # Check if content is empty or None
            if not content:
                print("❌ GPT returned empty content")
                return self._get_fallback_legal_context(statute)
            
            # Try to extract JSON if there's extra text
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            # Try to parse JSON
            try:
                result = json.loads(content)
                print(f"✅ JSON parsing successful: {result}")
                return result
            except json.JSONDecodeError as json_error:
                print(f"❌ JSON parsing failed: {json_error}")
                print(f"❌ Error at line {json_error.lineno}, column {json_error.colno}")
                print(f"Raw content: {repr(content)}")
                
                # Try to find JSON-like content in the response
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    print(f"🔍 Found JSON-like content: {json_match.group()}")
                    try:
                        result = json.loads(json_match.group())
                        print(f"✅ Extracted JSON successful: {result}")
                        return result
                    except json.JSONDecodeError:
                        print("❌ Extracted content still not valid JSON")
                        pass
                
                # If all else fails, return fallback
                print("⚠️ Using fallback analysis")
                return self._get_fallback_legal_context(statute)
                
        except Exception as e:
            print(f"Error analyzing legal context: {e}")
            print(f"Exception type: {type(e).__name__}")
            return self._get_fallback_legal_context(statute)
    
    def _convert_preprocessing_to_legal_context_format(self, preprocessing_result: PreprocessingResult, statute: Dict) -> Dict:
        """Convert preprocessing result to legal context format"""
        rule_class = preprocessing_result.rule_based_classification
        
        if rule_class['type'] == 'constitutional_amendment':
            return {
                "legal_references": ["Constitution of Pakistan"],
                "amendment_targets": ["Constitutional articles"],
                "relationship_type": "amendment",
                "legal_lineage": ["Constitution of Pakistan"],
                "confidence": int(rule_class['confidence'] * 100)
            }
        elif rule_class['type'] == 'ordinary_amendment':
            return {
                "legal_references": ["Previous Act"],
                "amendment_targets": ["Act sections"],
                "relationship_type": "amendment",
                "legal_lineage": ["Previous Act"],
                "confidence": int(rule_class['confidence'] * 100)
            }
        else:
            return {
                "legal_references": [],
                "amendment_targets": [],
                "relationship_type": "none",
                "legal_lineage": [],
                "confidence": int(rule_class['confidence'] * 100)
            }
    
    def analyze_relationship(self, statute_a: Dict, statute_b: Dict) -> Dict:
        """Analyze relationship between two statutes"""
        
        # Use preprocessing for pair analysis if available
        if self.preprocessor:
            preprocessing_a, preprocessing_b = self.preprocessor.preprocess_statute_pair(statute_a, statute_b)
            
            # Check if we can determine relationship without GPT
            if self._can_determine_relationship_without_gpt(preprocessing_a, preprocessing_b):
                print("✅ Determining relationship using preprocessing (no GPT needed)")
                return self._determine_relationship_with_preprocessing(preprocessing_a, preprocessing_b, statute_a, statute_b)
        
        # Check constitutional lineage first
        lineage_a = self.analyze_constitutional_lineage(statute_a)
        lineage_b = self.analyze_constitutional_lineage(statute_b)
        
        # Check legal context
        context_a = self.analyze_legal_context(statute_a)
        context_b = self.analyze_legal_context(statute_b)
        
        # Determine relationship
        relationship = self._determine_relationship(lineage_a, lineage_b, context_a, context_b)
        
        return {
            "should_merge": relationship["should_merge"],
            "reason": relationship["reason"],
            "relationship_type": relationship["type"],
            "confidence": relationship["confidence"],
            "analysis": {
                "lineage_a": lineage_a,
                "lineage_b": lineage_b,
                "context_a": context_a,
                "context_b": context_b
            }
        }
    
    def _determine_relationship(self, lineage_a: Dict, lineage_b: Dict, 
                              context_a: Dict, context_b: Dict) -> Dict:
        """Determine if two statutes should be merged based on context"""
        # Constitutional amendment chain
        if (lineage_a.get("is_constitutional") and lineage_b.get("is_constitutional") and
            lineage_a.get("constitutional_base") == lineage_b.get("constitutional_base")):
            return {
                "should_merge": True,
                "reason": f"Both are constitutional amendments to {lineage_a['constitutional_base']}",
                "type": "constitutional_amendment_chain",
                "confidence": min(lineage_a.get("confidence", 0), lineage_b.get("confidence", 0))
            }
        
        # Legal lineage relationship
        if self._has_legal_lineage_relationship(context_a, context_b):
            return {
                "should_merge": True,
                "reason": "Statutes have legal lineage relationship",
                "type": "legal_lineage",
                "confidence": 85
            }
        
        # Amendment relationship
        if self._is_amendment_relationship(context_a, context_b):
            return {
                "should_merge": True,
                "reason": "One statute amends the other",
                "type": "amendment_relationship",
                "confidence": 80
            }
        
        return {
            "should_merge": False,
            "reason": "No clear relationship detected",
            "type": "no_relationship",
            "confidence": 0
        }
    
    def _has_legal_lineage_relationship(self, context_a: Dict, context_b: Dict) -> bool:
        """Check if statutes have legal lineage relationship"""
        lineage_a = set(context_a.get("legal_lineage", []))
        lineage_b = set(context_b.get("legal_lineage", []))
        return bool(lineage_a.intersection(lineage_b))
    
    def _is_amendment_relationship(self, context_a: Dict, context_b: Dict) -> bool:
        """Check if one statute amends the other"""
        targets_a = set(context_a.get("amendment_targets", []))
        references_b = set(context_b.get("legal_references", []))
        targets_b = set(context_b.get("amendment_targets", []))
        references_a = set(context_a.get("legal_references", []))
        
        return bool(targets_a.intersection(references_b)) or bool(targets_b.intersection(references_a))
    
    def _get_fallback_constitutional_analysis(self, statute: Dict) -> Dict:
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
    
    def _get_fallback_legal_context(self, statute: Dict) -> Dict:
        """Fallback legal context when GPT fails"""
        return {
            "legal_references": [],
            "amendment_targets": [],
            "relationship_type": "unknown",
            "legal_lineage": [],
            "confidence": 50
        }
    
    def _can_determine_relationship_without_gpt(self, preprocessing_a: PreprocessingResult, preprocessing_b: PreprocessingResult) -> bool:
        """Check if relationship can be determined without GPT"""
        # High confidence rule-based classifications
        if (preprocessing_a.confidence_score > 0.9 and preprocessing_b.confidence_score > 0.9):
            return True
        
        # Clear constitutional vs non-constitutional mismatch
        if (preprocessing_a.rule_based_classification['constitutional_related'] != 
            preprocessing_b.rule_based_classification['constitutional_related']):
            return True
        
        # Significant year difference
        if preprocessing_a.year_discrepancy or preprocessing_b.year_discrepancy:
            return True
        
        return False
    
    def _determine_relationship_with_preprocessing(self, preprocessing_a: PreprocessingResult, preprocessing_b: PreprocessingResult, 
                                                 statute_a: Dict, statute_b: Dict) -> Dict:
        """Determine relationship using preprocessing results"""
        
        # Constitutional relationship mismatch
        if (preprocessing_a.rule_based_classification['constitutional_related'] != 
            preprocessing_b.rule_based_classification['constitutional_related']):
            return {
                "should_merge": False,
                "reason": "Constitutional relationship mismatch",
                "type": "no_relationship",
                "confidence": 95,
                "analysis": {
                    "preprocessing_a": preprocessing_a.rule_based_classification,
                    "preprocessing_b": preprocessing_b.rule_based_classification,
                    "method": "rule_based"
                }
            }
        
        # Both constitutional amendments
        if (preprocessing_a.rule_based_classification['constitutional_related'] and 
            preprocessing_b.rule_based_classification['constitutional_related']):
            return {
                "should_merge": True,
                "reason": "Both are constitutional amendments",
                "type": "constitutional_amendment_chain",
                "confidence": min(preprocessing_a.confidence_score, preprocessing_b.confidence_score) * 100,
                "analysis": {
                    "preprocessing_a": preprocessing_a.rule_based_classification,
                    "preprocessing_b": preprocessing_b.rule_based_classification,
                    "method": "rule_based"
                }
            }
        
        # Year discrepancy
        if preprocessing_a.year_discrepancy or preprocessing_b.year_discrepancy:
            return {
                "should_merge": False,
                "reason": "Significant year difference detected",
                "type": "no_relationship",
                "confidence": 70,
                "analysis": {
                    "preprocessing_a": preprocessing_a.rule_based_classification,
                    "preprocessing_b": preprocessing_b.rule_based_classification,
                    "method": "rule_based"
                }
            }
        
        # Default: no clear relationship
        return {
            "should_merge": False,
            "reason": "No clear relationship detected by preprocessing",
            "type": "no_relationship",
            "confidence": 70,
            "analysis": {
                "preprocessing_a": preprocessing_a.rule_based_classification,
                "preprocessing_b": preprocessing_b.rule_based_classification,
                "method": "rule_based"
            }
        }
    
    def test_gpt_connection(self) -> Dict:
        """Test GPT connection with a simple prompt"""
        test_prompt = """
        Respond with this exact JSON: {"test": "success", "message": "GPT connection working"}
        
        IMPORTANT: Respond ONLY with valid JSON. Do not include any other text.
        """
        
        try:
            print("🧪 Sending test prompt to GPT...")
            response = self.gpt_client.chat.completions.create(
                model=self.config["azure_openai"]["model"],
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. Always respond with valid JSON only."},
                    {"role": "user", "content": test_prompt}
                ],
                temperature=0.1,
                max_tokens=100
            )
            
            print(f"✅ GPT API call successful")
            print(f"Response object type: {type(response)}")
            print(f"Response choices: {len(response.choices)}")
            
            if not response.choices:
                print("❌ No choices in response")
                return {"success": False, "error": "No choices in response"}
            
            choice = response.choices[0]
            print(f"Choice type: {type(choice)}")
            print(f"Choice message type: {type(choice.message)}")
            
            content = choice.message.content
            print(f"Content type: {type(content)}")
            print(f"Content: {repr(content)}")
            
            if content is None:
                print("❌ Content is None")
                return {"success": False, "error": "Content is None"}
            
            content = content.strip()
            print(f"Stripped content: {repr(content)}")
            print(f"Content length: {len(content)}")
            
            # Try to parse JSON
            try:
                result = json.loads(content)
                print(f"✅ JSON parsing successful: {result}")
                return {"success": True, "response": result, "raw_content": content}
            except json.JSONDecodeError as json_error:
                print(f"❌ JSON parsing failed: {json_error}")
                print(f"❌ Error at line {json_error.lineno}, column {json_error.colno}")
                print(f"Raw test content: {repr(content)}")
                
                # Try to find JSON-like content
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    print(f"🔍 Found JSON-like content: {json_match.group()}")
                    try:
                        result = json.loads(json_match.group())
                        print(f"✅ Extracted JSON successful: {result}")
                        return {"success": True, "response": result, "raw_content": content, "extracted": True}
                    except json.JSONDecodeError:
                        print("❌ Extracted content still not valid JSON")
                
                return {"success": False, "error": str(json_error), "raw_content": content}
                
        except Exception as e:
            print(f"❌ GPT Test connection failed: {e}")
            print(f"Exception type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e), "exception_type": type(e).__name__}

class IntelligentGroupingGUI:
    """Main GUI for intelligent statute grouping"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Intelligent Statute Grouping - Context-Aware Analysis")
        
        # Load configuration
        self.config = self.load_config()
        
        # Initialize components
        self.init_components()
        self.init_ui()
        
        # Data storage
        self.statutes = []
        self.statute_contexts = {}
        self.relationships = []
        self.groups = {}
        
        # Processing state
        self.is_processing = False
        self.current_batch = 0
        
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
                "model": "gpt-4o"
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
        
        # Initialize context analyzer
        if self.gpt_client:
            self.context_analyzer = IntelligentContextAnalyzer(self.gpt_client, self.config)
        else:
            self.context_analyzer = None
        
        # Initialize MongoDB connection
        try:
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
        self.root.geometry(f"{self.config['ui']['window_width']}x{self.config['ui']['window_height']}")
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
        self.create_context_analysis_tab()
        self.create_preprocessing_tab()
        self.create_relationships_tab()
        self.create_grouping_tab()
        self.create_statistics_tab()
        self.create_logs_tab()
        
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
        
        # Analysis controls
        analysis_frame = ttk.Frame(control_frame)
        analysis_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(analysis_frame, text="Analysis:").pack(side=tk.LEFT)
        ttk.Button(analysis_frame, text="Test GPT", command=self.test_gpt_connection).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Button(analysis_frame, text="Test Basic", command=self.test_basic_functionality).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Button(analysis_frame, text="Start Context Analysis", command=self.start_context_analysis).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Button(analysis_frame, text="Analyze Relationships", command=self.analyze_relationships).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Button(analysis_frame, text="Create Groups", command=self.create_intelligent_groups).pack(side=tk.LEFT, padx=(5, 5))
        
        # Export controls
        export_frame = ttk.Frame(control_frame)
        export_frame.pack(fill=tk.X)
        
        ttk.Label(export_frame, text="Export:").pack(side=tk.LEFT)
        ttk.Button(export_frame, text="Export Groups", command=self.export_groups).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Button(export_frame, text="Export Analysis", command=self.export_analysis).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Button(export_frame, text="Export Report", command=self.export_report).pack(side=tk.LEFT, padx=(5, 5))
    
    def create_context_analysis_tab(self):
        """Create the context analysis tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Context Analysis")
        
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
        
        # Right panel - Context details
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)
        
        ttk.Label(right_frame, text="Context Analysis", font=('Arial', 12, 'bold')).pack(pady=5)
        
        # Context details notebook
        context_notebook = ttk.Notebook(right_frame)
        context_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Constitutional lineage tab
        const_tab = ttk.Frame(context_notebook)
        context_notebook.add(const_tab, text="Constitutional Lineage")
        self.create_constitutional_tab(const_tab)
        
        # Legal context tab
        legal_tab = ttk.Frame(context_notebook)
        context_notebook.add(legal_tab, text="Legal Context")
        self.create_legal_context_tab(legal_tab)
    
    def create_constitutional_tab(self, parent):
        """Create constitutional lineage analysis tab"""
        # Constitutional analysis display
        self.const_text = scrolledtext.ScrolledText(parent, height=15, width=60)
        self.const_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Analysis controls
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(control_frame, text="Analyze Constitutional Lineage", 
                  command=self.analyze_selected_constitutional).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Clear", 
                  command=lambda: self.const_text.delete(1.0, tk.END)).pack(side=tk.LEFT, padx=5)
    
    def create_legal_context_tab(self, parent):
        """Create legal context analysis tab"""
        # Legal context display
        self.legal_text = scrolledtext.ScrolledText(parent, height=15, width=60)
        self.legal_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Analysis controls
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(control_frame, text="Analyze Legal Context", 
                  command=self.analyze_selected_legal_context).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Clear", 
                  command=lambda: self.legal_text.delete(1.0, tk.END)).pack(side=tk.LEFT, padx=5)
    
    def create_relationships_tab(self):
        """Create the relationships analysis tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Relationships")
        
        # Relationships treeview
        columns = ('Statute A', 'Statute B', 'Type', 'Confidence', 'Reason', 'Status')
        self.relationships_tree = ttk.Treeview(tab, columns=columns, show='headings')
        
        for col in columns:
            self.relationships_tree.heading(col, text=col)
            self.relationships_tree.column(col, width=150)
        
        self.relationships_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Relationship controls
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(control_frame, text="Analyze All Relationships", 
                  command=self.analyze_all_relationships).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Validate Selected", 
                  command=self.validate_selected_relationship).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Override Selected", 
                  command=self.override_selected_relationship).pack(side=tk.LEFT, padx=5)
    
    def create_grouping_tab(self):
        """Create the intelligent grouping tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Intelligent Grouping")
        
        # Groups treeview
        columns = ('Group ID', 'Base Name', 'Statutes', 'Type', 'Confidence', 'Status')
        self.groups_tree = ttk.Treeview(tab, columns=columns, show='headings')
        
        for col in columns:
            self.groups_tree.heading(col, text=col)
            self.groups_tree.column(col, width=150)
        
        self.groups_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Grouping controls
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(control_frame, text="Create Intelligent Groups", 
                  command=self.create_intelligent_groups).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Merge Selected Groups", 
                  command=self.merge_selected_groups).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Split Selected Group", 
                  command=self.split_selected_group).pack(side=tk.LEFT, padx=5)
    
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
    
    def create_logs_tab(self):
        """Create the logs tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Logs")
        
        # Logs display
        self.logs_text = scrolledtext.ScrolledText(tab, height=20, width=80)
        self.logs_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Log controls
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(control_frame, text="Clear Logs", 
                  command=self.clear_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Save Logs", 
                  command=self.save_logs).pack(side=tk.LEFT, padx=5)
    
    def create_preprocessing_tab(self):
        """Create the preprocessing tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Preprocessing")
        
        # Create split view
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - Statute list
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        
        ttk.Label(left_frame, text="Statutes", font=('Arial', 12, 'bold')).pack(pady=5)
        
        # Statute listbox for preprocessing
        self.preprocessing_statute_listbox = tk.Listbox(left_frame, selectmode=tk.SINGLE)
        self.preprocessing_statute_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.preprocessing_statute_listbox.bind('<<ListboxSelect>>', self.on_preprocessing_statute_select)
        
        # Right panel - Preprocessing results
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)
        
        ttk.Label(right_frame, text="Preprocessing Analysis", font=('Arial', 12, 'bold')).pack(pady=5)
        
        # Preprocessing results notebook
        preprocessing_notebook = ttk.Notebook(right_frame)
        preprocessing_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Rule-based classification tab
        rule_tab = ttk.Frame(preprocessing_notebook)
        preprocessing_notebook.add(rule_tab, text="Rule-Based Classification")
        
        ttk.Label(rule_tab, text="Rule-Based Classification Results", font=('Arial', 10, 'bold')).pack(pady=5)
        self.rule_classification_text = scrolledtext.ScrolledText(rule_tab, height=15, width=60)
        self.rule_classification_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Language detection tab
        lang_tab = ttk.Frame(preprocessing_notebook)
        preprocessing_notebook.add(lang_tab, text="Language Detection")
        
        ttk.Label(lang_tab, text="Language Analysis", font=('Arial', 10, 'bold')).pack(pady=5)
        self.language_text = scrolledtext.ScrolledText(lang_tab, height=15, width=60)
        self.language_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Section analysis tab
        section_tab = ttk.Frame(preprocessing_notebook)
        preprocessing_notebook.add(section_tab, text="Section Analysis")
        
        ttk.Label(section_tab, text="Section Similarity & Renumbering", font=('Arial', 10, 'bold')).pack(pady=5)
        self.section_analysis_text = scrolledtext.ScrolledText(section_tab, height=15, width=60)
        self.section_analysis_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Preprocessing controls
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(control_frame, text="Run Preprocessing", 
                  command=self.run_preprocessing_analysis).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Clear Results", 
                  command=self.clear_preprocessing_results).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Export Preprocessing", 
                  command=self.export_preprocessing_results).pack(side=tk.LEFT, padx=5)
    
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
            self.log_message(f"Loaded {len(self.statutes)} statutes from database")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load statutes: {e}")
            self.status_bar.config(text="Error loading statutes")
    
    def update_statutes_display(self):
        """Update the statutes listbox"""
        self.statute_listbox.delete(0, tk.END)
        for statute in self.statutes:
            name = statute.get('Statute_Name', 'Unknown')
            self.statute_listbox.insert(tk.END, name)
        
        # Also update preprocessing tab statute list
        if hasattr(self, 'preprocessing_statute_listbox'):
            self.update_preprocessing_statutes_display()
    
    def on_statute_select(self, event):
        """Handle statute selection"""
        selection = self.statute_listbox.curselection()
        if selection:
            index = selection[0]
            statute = self.statutes[index]
            self.display_statute_context(statute)
    
    def display_statute_context(self, statute):
        """Display context analysis for selected statute"""
        # Display constitutional lineage
        if self.context_analyzer:
            const_analysis = self.context_analyzer.analyze_constitutional_lineage(statute)
            const_text = json.dumps(const_analysis, indent=2)
            self.const_text.delete(1.0, tk.END)
            self.const_text.insert(1.0, const_text)
            
            legal_analysis = self.context_analyzer.analyze_legal_context(statute)
            legal_text = json.dumps(legal_analysis, indent=2)
            self.legal_text.delete(1.0, tk.END)
            self.legal_text.insert(1.0, legal_text)
    
    def start_context_analysis(self):
        """Start context analysis for all statutes"""
        if not self.statutes:
            messagebox.showwarning("Warning", "No statutes loaded")
            return
        
        if not self.context_analyzer:
            messagebox.showerror("Error", "Context analyzer not available")
            return
        
        # Start analysis in background thread
        thread = threading.Thread(target=self._run_context_analysis)
        thread.daemon = True
        thread.start()
    
    def _run_context_analysis(self):
        """Run context analysis in background"""
        try:
            self.is_processing = True
            self.status_bar.config(text="Running context analysis...")
            
            total = len(self.statutes)
            for i, statute in enumerate(self.statutes):
                if not self.is_processing:
                    break
                
                # Update progress
                self.current_batch = i + 1
                self.status_bar.config(text=f"Analyzing statute {i+1}/{total}")
                self.root.update()
                
                # Analyze context
                statute_id = str(statute.get('_id', ''))
                if statute_id not in self.statute_contexts:
                    const_analysis = self.context_analyzer.analyze_constitutional_lineage(statute)
                    legal_analysis = self.context_analyzer.analyze_legal_context(statute)
                    
                    self.statute_contexts[statute_id] = StatuteContext(
                        statute_id=statute_id,
                        statute_name=statute.get('Statute_Name', ''),
                        constitutional_lineage=const_analysis,
                        legal_context=legal_analysis,
                        confidence_score=min(const_analysis.get('confidence', 0), legal_analysis.get('confidence', 0))
                    )
                
                # Small delay to prevent overwhelming the API
                time.sleep(0.1)
            
            self.status_bar.config(text="Context analysis completed")
            self.log_message(f"Completed context analysis for {len(self.statute_contexts)} statutes")
            
        except Exception as e:
            self.status_bar.config(text=f"Error: {e}")
            self.log_message(f"Error during context analysis: {e}")
        finally:
            self.is_processing = False
    
    def analyze_relationships(self):
        """Analyze relationships between statutes"""
        if len(self.statute_contexts) < 2:
            messagebox.showwarning("Warning", "Need at least 2 statutes with context analysis")
            return
        
        # Start analysis in background thread
        thread = threading.Thread(target=self._run_relationship_analysis)
        thread.daemon = True
        thread.start()
    
    def _run_relationship_analysis(self):
        """Run relationship analysis in background"""
        try:
            self.is_processing = True
            self.status_bar.config(text="Analyzing relationships...")
            
            statute_ids = list(self.statute_contexts.keys())
            total_combinations = len(statute_ids) * (len(statute_ids) - 1) // 2
            current = 0
            
            self.relationships = []
            
            for i, id_a in enumerate(statute_ids):
                for j, id_b in enumerate(statute_ids[i+1:], i+1):
                    if not self.is_processing:
                        break
                    
                    current += 1
                    self.status_bar.config(text=f"Analyzing relationship {current}/{total_combinations}")
                    self.root.update()
                    
                    # Get statutes
                    statute_a = next((s for s in self.statutes if str(s.get('_id', '')) == id_a), None)
                    statute_b = next((s for s in self.statutes if str(s.get('_id', '')) == id_b), None)
                    
                    if statute_a and statute_b:
                        # Analyze relationship
                        relationship = self.context_analyzer.analyze_relationship(statute_a, statute_b)
                        
                        self.relationships.append(StatuteRelationship(
                            statute_a_id=id_a,
                            statute_b_id=id_b,
                            relationship_type=relationship['relationship_type'],
                            confidence_score=relationship['confidence'],
                            context_analysis=relationship['analysis']
                        ))
                    
                    # Small delay
                    time.sleep(0.1)
            
            # Update relationships display
            self.update_relationships_display()
            
            self.status_bar.config(text="Relationship analysis completed")
            self.log_message(f"Completed relationship analysis: {len(self.relationships)} relationships found")
            
        except Exception as e:
            self.status_bar.config(text=f"Error: {e}")
            self.log_message(f"Error during relationship analysis: {e}")
        finally:
            self.is_processing = False
    
    def update_relationships_display(self):
        """Update the relationships treeview"""
        # Clear existing items
        for item in self.relationships_tree.get_children():
            self.relationships_tree.delete(item)
        
        # Add relationships
        for rel in self.relationships:
            statute_a_name = self.statute_contexts.get(rel.statute_a_id, {}).get('statute_name', 'Unknown')
            statute_b_name = self.statute_contexts.get(rel.statute_b_id, {}).get('statute_name', 'Unknown')
            
            self.relationships_tree.insert('', 'end', values=(
                statute_a_name,
                statute_b_name,
                rel.relationship_type,
                f"{rel.confidence_score:.1f}%",
                rel.context_analysis.get('reason', ''),
                'Pending' if not rel.manual_override else 'Overridden'
            ))
    
    def create_intelligent_groups(self):
        """Create intelligent groups based on context analysis"""
        if not self.relationships:
            messagebox.showwarning("Warning", "No relationships analyzed")
            return
        
        try:
            self.status_bar.config(text="Creating intelligent groups...")
            
            # Group statutes based on relationships
            self.groups = self._create_groups_from_relationships()
            
            # Update groups display
            self.update_groups_display()
            
            self.status_bar.config(text=f"Created {len(self.groups)} intelligent groups")
            self.log_message(f"Created {len(self.groups)} intelligent groups")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create groups: {e}")
            self.status_bar.config(text="Error creating groups")
    
    def _create_groups_from_relationships(self) -> Dict:
        """Create groups from analyzed relationships"""
        groups = {}
        processed = set()
        
        for rel in self.relationships:
            if rel.should_merge and rel.confidence_score >= self.config['context_analysis']['confidence_threshold']:
                # Create or extend group
                group_key = f"group_{len(groups)}"
                
                if group_key not in groups:
                    groups[group_key] = {
                        'base_name': f"Intelligent Group {len(groups) + 1}",
                        'statutes': [],
                        'type': rel.relationship_type,
                        'confidence': rel.confidence_score,
                        'status': 'Active'
                    }
                
                # Add statutes if not already processed
                if rel.statute_a_id not in processed:
                    groups[group_key]['statutes'].append(rel.statute_a_id)
                    processed.add(rel.statute_a_id)
                
                if rel.statute_b_id not in processed:
                    groups[group_key]['statutes'].append(rel.statute_b_id)
                    processed.add(rel.statute_b_id)
        
        return groups
    
    def update_groups_display(self):
        """Update the groups treeview"""
        # Clear existing items
        for item in self.groups_tree.get_children():
            self.groups_tree.delete(item)
        
        # Add groups
        for group_id, group_data in self.groups.items():
            self.groups_tree.insert('', 'end', values=(
                group_id,
                group_data['base_name'],
                len(group_data['statutes']),
                group_data['type'],
                f"{group_data['confidence']:.1f}%",
                group_data['status']
            ))
    
    def export_groups(self):
        """Export intelligent groups"""
        if not self.groups:
            messagebox.showwarning("Warning", "No groups to export")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                export_data = {
                    'export_timestamp': datetime.now().isoformat(),
                    'total_groups': len(self.groups),
                    'groups': self.groups,
                    'statute_contexts': {k: v.__dict__ for k, v in self.statute_contexts.items()},
                    'relationships': [r.__dict__ for r in self.relationships]
                }
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
                
                messagebox.showinfo("Success", f"Groups exported to {filename}")
                self.log_message(f"Exported groups to {filename}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {e}")
    
    def export_analysis(self):
        """Export context analysis results"""
        if not self.statute_contexts:
            messagebox.showwarning("Warning", "No analysis to export")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                export_data = {
                    'export_timestamp': datetime.now().isoformat(),
                    'total_statutes': len(self.statute_contexts),
                    'statute_contexts': {k: v.__dict__ for k, v in self.statute_contexts.items()}
                }
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
                
                messagebox.showinfo("Success", f"Analysis exported to {filename}")
                self.log_message(f"Exported analysis to {filename}")
                
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
                self.log_message(f"Exported report to {filename}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export report: {e}")
    
    def _generate_report(self) -> str:
        """Generate comprehensive report"""
        report = f"""# Intelligent Statute Grouping Report

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary
- Total Statutes: {len(self.statutes)}
- Statutes Analyzed: {len(self.statute_contexts)}
- Relationships Found: {len(self.relationships)}
- Groups Created: {len(self.groups)}

## Constitutional Analysis
"""
        
        const_count = sum(1 for ctx in self.statute_contexts.values() 
                         if ctx.constitutional_lineage.get('is_constitutional', False))
        report += f"- Constitutional Amendments: {const_count}\n"
        
        report += "\n## Legal Context Analysis\n"
        for ctx in self.statute_contexts.values():
            report += f"- {ctx.statute_name}: {ctx.legal_context.get('relationship_type', 'Unknown')}\n"
        
        report += "\n## Groups\n"
        for group_id, group_data in self.groups.items():
            report += f"- {group_id}: {len(group_data['statutes'])} statutes, {group_data['type']}\n"
        
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
        stats = f"""Intelligent Grouping Statistics
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Data Overview:
- Total Statutes: {len(self.statutes)}
- Statutes with Context Analysis: {len(self.statute_contexts)}
- Relationships Analyzed: {len(self.relationships)}
- Groups Created: {len(self.groups)}

Context Analysis:
- Constitutional Amendments: {sum(1 for ctx in self.statute_contexts.values() if ctx.constitutional_lineage.get('is_constitutional', False))}
- Average Confidence Score: {np.mean([ctx.confidence_score for ctx in self.statute_contexts.values()]) if self.statute_contexts else 0:.1f}%

Relationship Types:
"""
        
        if self.relationships:
            rel_types = Counter(r.relationship_type for r in self.relationships)
            for rel_type, count in rel_types.items():
                stats += f"- {rel_type}: {count}\n"
        
        stats += f"\nGroup Analysis:\n"
        if self.groups:
            avg_group_size = np.mean([len(g['statutes']) for g in self.groups.values()])
            stats += f"- Average Group Size: {avg_group_size:.1f} statutes\n"
            stats += f"- Largest Group: {max([len(g['statutes']) for g in self.groups.values()])} statutes\n"
        
        return stats
    
    def log_message(self, message: str):
        """Add message to logs"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        
        self.logs_text.insert(tk.END, log_entry)
        self.logs_text.see(tk.END)
        
        # Keep only last N entries
        lines = self.logs_text.get(1.0, tk.END).split('\n')
        if len(lines) > self.config['ui']['max_log_entries']:
            self.logs_text.delete(1.0, tk.END)
            self.logs_text.insert(1.0, '\n'.join(lines[-self.config['ui']['max_log_entries']:]))
    
    def clear_logs(self):
        """Clear logs display"""
        self.logs_text.delete(1.0, tk.END)
    
    def save_logs(self):
        """Save logs to file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                logs_content = self.logs_text.get(1.0, tk.END)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(logs_content)
                
                messagebox.showinfo("Success", f"Logs saved to {filename}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save logs: {e}")
    
    def analyze_selected_constitutional(self):
        """Analyze constitutional lineage for selected statute"""
        selection = self.statute_listbox.curselection()
        if selection:
            index = selection[0]
            statute = self.statutes[index]
            
            if self.context_analyzer:
                analysis = self.context_analyzer.analyze_constitutional_lineage(statute)
                self.const_text.delete(1.0, tk.END)
                self.const_text.insert(1.0, json.dumps(analysis, indent=2))
    
    def analyze_selected_legal_context(self):
        """Analyze legal context for selected statute"""
        selection = self.statute_listbox.curselection()
        if selection:
            index = selection[0]
            statute = self.statutes[index]
            
            if self.context_analyzer:
                analysis = self.context_analyzer.analyze_legal_context(statute)
                self.legal_text.delete(1.0, tk.END)
                self.legal_text.insert(1.0, json.dumps(analysis, indent=2))
    
    def analyze_all_relationships(self):
        """Analyze all relationships"""
        self.analyze_relationships()
    
    def validate_selected_relationship(self):
        """Validate selected relationship"""
        selection = self.relationships_tree.selection()
        if selection:
            # Implementation for relationship validation
            pass
    
    def override_selected_relationship(self):
        """Override selected relationship"""
        selection = self.relationships_tree.selection()
        if selection:
            # Implementation for relationship override
            pass
    
    def merge_selected_groups(self):
        """Merge selected groups"""
        selection = self.groups_tree.selection()
        if len(selection) >= 2:
            # Implementation for group merging
            pass
    
    def split_selected_group(self):
        """Split selected group"""
        selection = self.groups_tree.selection()
        if selection:
            # Implementation for group splitting
            pass
    
    def test_gpt_connection(self):
        """Test GPT connection and log results"""
        if not self.context_analyzer:
            self.log_message("❌ GPT client not available")
            return
        
        self.log_message("🧪 Testing GPT connection...")
        
        # Run test in background thread
        def run_test():
            try:
                result = self.context_analyzer.test_gpt_connection()
                if result["success"]:
                    self.log_message("✅ GPT connection test successful")
                    self.log_message(f"Response: {result['response']}")
                else:
                    self.log_message(f"❌ GPT connection test failed: {result['error']}")
                    self.log_message(f"Raw content: {result['raw_content']}")
            except Exception as e:
                self.log_message(f"❌ GPT test error: {e}")
        
        threading.Thread(target=run_test, daemon=True).start()
    
    def test_basic_functionality(self):
        """Test basic GUI functionality without GPT"""
        self.log_message("🧪 Testing basic functionality...")
        
        # Test MongoDB connection
        if self.mongo_client:
            try:
                count = self.collection.count_documents({})
                self.log_message(f"✅ MongoDB: Found {count} documents")
            except Exception as e:
                self.log_message(f"❌ MongoDB error: {e}")
        else:
            self.log_message("❌ MongoDB not connected")
        
        # Test configuration
        self.log_message(f"✅ Config loaded: {len(self.config)} sections")
        self.log_message(f"✅ GPT available: {self.context_analyzer is not None}")
        
        # Test data loading
        if self.statutes:
            self.log_message(f"✅ Statutes loaded: {len(self.statutes)}")
        else:
            self.log_message("⚠️ No statutes loaded yet")
    
    def on_preprocessing_statute_select(self, event):
        """Handle statute selection in preprocessing tab"""
        selection = self.preprocessing_statute_listbox.curselection()
        if selection:
            index = selection[0]
            statute = self.statutes[index]
            self.display_preprocessing_results(statute)
    
    def display_preprocessing_results(self, statute):
        """Display preprocessing results for selected statute"""
        if not self.context_analyzer or not self.context_analyzer.preprocessor:
            self.rule_classification_text.delete(1.0, tk.END)
            self.rule_classification_text.insert(1.0, "Preprocessor not available")
            return
        
        try:
            # Run preprocessing analysis
            preprocessing_result = self.context_analyzer.preprocessor.preprocess_statute(statute)
            
            # Display rule-based classification
            rule_text = json.dumps(preprocessing_result.rule_based_classification, indent=2)
            self.rule_classification_text.delete(1.0, tk.END)
            self.rule_classification_text.insert(1.0, rule_text)
            
            # Display language detection
            lang_text = f"Language Detected: {preprocessing_result.language_detected}\n"
            lang_text += f"Translation Required: {preprocessing_result.translation_required}\n"
            lang_text += f"Confidence Score: {preprocessing_result.confidence_score:.2f}\n"
            lang_text += f"Should Use GPT: {preprocessing_result.should_use_gpt}\n\n"
            lang_text += "Preprocessing Notes:\n"
            for note in preprocessing_result.preprocessing_notes:
                lang_text += f"• {note}\n"
            
            self.language_text.delete(1.0, tk.END)
            self.language_text.insert(1.0, lang_text)
            
            # Display section analysis
            section_text = json.dumps(preprocessing_result.section_similarity, indent=2)
            self.section_analysis_text.delete(1.0, tk.END)
            self.section_analysis_text.insert(1.0, section_text)
            
        except Exception as e:
            error_text = f"Error in preprocessing: {e}"
            self.rule_classification_text.delete(1.0, tk.END)
            self.rule_classification_text.insert(1.0, error_text)
            self.language_text.delete(1.0, tk.END)
            self.language_text.insert(1.0, error_text)
            self.section_analysis_text.delete(1.0, tk.END)
            self.section_analysis_text.insert(1.0, error_text)
    
    def run_preprocessing_analysis(self):
        """Run preprocessing analysis for all statutes"""
        if not self.statutes:
            messagebox.showwarning("Warning", "No statutes loaded")
            return
        
        if not self.context_analyzer or not self.context_analyzer.preprocessor:
            messagebox.showerror("Error", "Preprocessor not available")
            return
        
        self.status_bar.config(text="Running preprocessing analysis...")
        self.root.update()
        
        # Run in background thread
        def run_analysis():
            try:
                results = []
                for i, statute in enumerate(self.statutes):
                    try:
                        result = self.context_analyzer.preprocessor.preprocess_statute(statute)
                        results.append({
                            'statute_name': statute.get('Statute_Name', 'Unknown'),
                            'result': result
                        })
                        
                        # Update progress
                        progress = (i + 1) / len(self.statutes) * 100
                        self.root.after(0, lambda p=progress: self.status_bar.config(text=f"Preprocessing: {p:.1f}%"))
                        
                    except Exception as e:
                        self.log_message(f"Error preprocessing {statute.get('Statute_Name', 'Unknown')}: {e}")
                
                # Update preprocessing tab display
                self.root.after(0, lambda: self.update_preprocessing_statutes_display())
                self.root.after(0, lambda: self.status_bar.config(text=f"Preprocessing complete: {len(results)} statutes analyzed"))
                self.log_message(f"Preprocessing analysis complete: {len(results)} statutes")
                
            except Exception as e:
                self.root.after(0, lambda: self.status_bar.config(text="Preprocessing error"))
                self.log_message(f"Preprocessing error: {e}")
        
        threading.Thread(target=run_analysis, daemon=True).start()
    
    def update_preprocessing_statutes_display(self):
        """Update the preprocessing statutes listbox"""
        self.preprocessing_statute_listbox.delete(0, tk.END)
        for statute in self.statutes:
            name = statute.get('Statute_Name', 'Unknown')
            self.preprocessing_statute_listbox.insert(tk.END, name)
    
    def clear_preprocessing_results(self):
        """Clear preprocessing results display"""
        self.rule_classification_text.delete(1.0, tk.END)
        self.language_text.delete(1.0, tk.END)
        self.section_analysis_text.delete(1.0, tk.END)
    
    def export_preprocessing_results(self):
        """Export preprocessing results to file"""
        if not self.statutes or not self.context_analyzer or not self.context_analyzer.preprocessor:
            messagebox.showwarning("Warning", "No preprocessing results to export")
            return
        
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                title="Export Preprocessing Results"
            )
            
            if filename:
                results = []
                for statute in self.statutes:
                    try:
                        result = self.context_analyzer.preprocessor.preprocess_statute(statute)
                        results.append({
                            'statute_name': statute.get('Statute_Name', 'Unknown'),
                            'statute_id': statute.get('_id', 'Unknown'),
                            'preprocessing_result': {
                                'should_use_gpt': result.should_use_gpt,
                                'confidence_score': result.confidence_score,
                                'rule_based_classification': result.rule_based_classification,
                                'language_detected': result.language_detected,
                                'translation_required': result.translation_required,
                                'section_similarity': result.section_similarity,
                                'year_discrepancy': result.year_discrepancy,
                                'title_similarity': result.title_similarity
                            }
                        })
                    except Exception as e:
                        results.append({
                            'statute_name': statute.get('Statute_Name', 'Unknown'),
                            'statute_id': statute.get('_id', 'Unknown'),
                            'error': str(e)
                        })
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, default=str)
                
                messagebox.showinfo("Success", f"Preprocessing results exported to {filename}")
                self.log_message(f"Preprocessing results exported to {filename}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export preprocessing results: {e}")
            self.log_message(f"Export error: {e}")

def main():
    """Main entry point"""
    root = tk.Tk()
    app = IntelligentGroupingGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

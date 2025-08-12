# 🔧 INTELLIGENT GROUPING TECHNICAL IMPLEMENTATION GUIDE
## Step-by-Step Implementation for Context-Aware Statute & Section Grouping

---

## 📋 IMPLEMENTATION OVERVIEW

This guide provides **exact code changes** needed to implement intelligent grouping in your existing LawChronicle pipeline. Each section shows the specific files to modify and the exact code to add.

---

## 🚀 PHASE 1: CONTEXT ANALYSIS ENGINE

### **Step 1.1: Create Context Analyzer Class**

**File**: `utils/statute_context_analyzer.py` (NEW FILE)

```python
"""
Statute Context Analyzer for LawChronicle
Provides intelligent context-aware analysis for statute grouping
"""

import json
import logging
from typing import Dict, List, Optional, Tuple
from utils.gpt_cache import gpt_cache
from utils.gpt_rate_limiter import rate_limited_gpt_call
from utils.gpt_prompt_optimizer import optimize_gpt_prompt

logger = logging.getLogger(__name__)

class StatuteContextAnalyzer:
    """
    Analyzes legal context and relationships between statutes
    """
    
    def __init__(self, gpt_client):
        self.gpt_client = gpt_client
        self.cache = gpt_cache
        
    @rate_limited_gpt_call
    @optimize_gpt_prompt
    def analyze_constitutional_lineage(self, statute: Dict) -> Dict:
        """
        Detect if statute is part of constitutional amendment chain
        """
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
        """
        
        try:
            response = self.gpt_client.analyze(prompt)
            result = json.loads(response)
            return result
        except Exception as e:
            logger.error(f"Error analyzing constitutional lineage: {e}")
            return self._get_fallback_constitutional_analysis(statute)
    
    @rate_limited_gpt_call
    @optimize_gpt_prompt
    def analyze_legal_context(self, statute: Dict) -> Dict:
        """
        Extract legal references and amendment targets
        """
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
        """
        
        try:
            response = self.gpt_client.analyze(prompt)
            result = json.loads(response)
            return result
        except Exception as e:
            logger.error(f"Error analyzing legal context: {e}")
            return self._get_fallback_legal_context(statute)
    
    def analyze_relationship(self, statute_a: Dict, statute_b: Dict) -> Dict:
        """
        Analyze relationship between two statutes
        """
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
        """
        Determine if two statutes should be merged based on context
        """
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
```

### **Step 1.2: Extend Existing Statute Grouping**

**File**: `05_statute_versioning/group_statutes_by_base.py`

**Add these imports at the top:**
```python
from utils.statute_context_analyzer import StatuteContextAnalyzer
```

**Add this after the existing imports:**
```python
# Initialize context analyzer
context_analyzer = StatuteContextAnalyzer(gpt_client)  # You'll need to pass your GPT client
```

**Modify the `should_merge_statutes` function:**
```python
def should_merge_statutes(statute_a: Dict, statute_b: Dict) -> dict:
    """
    Enhanced merge logic with context awareness
    """
    # Existing logic (keep all)
    province_check = check_province_match(statute_a, statute_b)
    if not province_check["merge"]:
        return province_check
    
    # NEW: Context analysis (add this section)
    try:
        context_analysis = context_analyzer.analyze_relationship(statute_a, statute_b)
        if context_analysis["should_merge"]:
            return {
                "merge": True,
                "reason": f"Context: {context_analysis['reason']}",
                "context": context_analysis,
                "confidence": context_analysis.get("confidence", 0)
            }
    except Exception as e:
        logger.warning(f"Context analysis failed: {e}, falling back to similarity check")
    
    # Existing similarity logic (keep as fallback)
    similarity_check = check_similarity(statute_a, statute_b)
    return similarity_check
```

---

## 🚀 PHASE 2: CONDITIONAL PROMPT SYSTEM

### **Step 2.1: Extend Prompt Optimizer**

**File**: `utils/gpt_prompt_optimizer.py`

**Add this new method to the existing class:**
```python
def select_context_prompt(self, context_type: str, statute_data: Dict) -> str:
    """
    Select appropriate prompt based on statute context
    """
    context_prompts = {
        "constitutional_amendment": {
            "system": "You are a Pakistani constitutional law expert with 25+ years experience.",
            "user_template": "Analyze if '{statute_name}' is a constitutional amendment..."
        },
        "section_amendment": {
            "system": "You are a legal document analyst specializing in statutory amendments.",
            "user_template": "Extract amendment sections from '{statute_name}'..."
        },
        "statute_equivalence": {
            "system": "You are a legal historian analyzing statute relationships.",
            "user_template": "Determine if '{statute_a}' and '{statute_b}' are related..."
        }
    }
    
    if context_type not in context_prompts:
        context_type = "statute_equivalence"  # Default fallback
    
    prompt_template = context_prompts[context_type]
    
    # Use existing optimization logic
    return self.optimize_prompt(prompt_template["user_template"].format(**statute_data))
```

### **Step 2.2: Create Context Prompt Manager**

**File**: `utils/context_prompt_manager.py` (NEW FILE)

```python
"""
Context-Aware Prompt Manager for LawChronicle
Manages different prompt types based on legal context
"""

import json
import logging
from typing import Dict, List, Optional
from utils.gpt_prompt_optimizer import optimize_gpt_prompt

logger = logging.getLogger(__name__)

class ContextPromptManager:
    """
    Manages context-specific prompts for different legal analysis tasks
    """
    
    def __init__(self):
        self.context_prompts = self._load_context_prompts()
    
    def _load_context_prompts(self) -> Dict:
        """Load context-specific prompt templates"""
        return {
            "constitutional_amendment": {
                "system": "You are a Pakistani constitutional law expert with 25+ years experience.",
                "user_template": """
                Analyze if this statute is a constitutional amendment:
                
                Statute Name: {statute_name}
                Province: {province}
                Preamble: {preamble}
                
                Determine:
                1. Is this a constitutional amendment? (Yes/No)
                2. What constitutional article/section does it modify?
                3. What amendment number is this?
                4. What is the relationship type?
                5. Confidence level (0-100%)
                
                Respond in JSON format.
                """
            },
            "section_amendment": {
                "system": "You are a legal document analyst specializing in statutory amendments.",
                "user_template": """
                Extract amendment sections from this statute:
                
                Statute Name: {statute_name}
                Sections: {sections}
                
                Find:
                1. Which sections are being amended?
                2. What is the nature of each amendment?
                3. What statutes are being modified?
                4. Amendment relationships and dependencies
                
                Respond in JSON format.
                """
            },
            "statute_equivalence": {
                "system": "You are a legal historian analyzing statute relationships.",
                "user_template": """
                Determine if these statutes are related:
                
                Statute A: {statute_a_name}
                Statute B: {statute_b_name}
                
                Analyze:
                1. Are they the same statute with different names?
                2. Is one an amendment of the other?
                3. Do they have common legal lineage?
                4. What is the relationship type?
                
                Respond in JSON format.
                """
            }
        }
    
    def get_prompt(self, context_type: str, **kwargs) -> str:
        """Get context-specific prompt with data substitution"""
        if context_type not in self.context_prompts:
            context_type = "statute_equivalence"  # Default fallback
        
        prompt_template = self.context_prompts[context_type]
        
        # Substitute variables in template
        try:
            user_prompt = prompt_template["user_template"].format(**kwargs)
            system_prompt = prompt_template["system"]
            
            # Combine system and user prompts
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            # Use existing optimization
            return optimize_gpt_prompt(full_prompt)
            
        except KeyError as e:
            logger.error(f"Missing template variable: {e}")
            return self._get_fallback_prompt(context_type)
    
    def _get_fallback_prompt(self, context_type: str) -> str:
        """Get fallback prompt when template substitution fails"""
        return f"Analyze this legal document for {context_type} context and respond in JSON format."
```

---

## 🚀 PHASE 3: ENHANCED SCHEMA INTEGRATION

### **Step 3.1: Extend Database Schema**

**File**: `02_db_normalization/normalize_structure.py`

**Add this function after existing normalization logic:**
```python
def enhance_statute_schema_with_context(statute: Dict) -> Dict:
    """
    Add context-aware fields to existing statute schema
    """
    enhanced = statute.copy()
    
    # Add new context fields
    enhanced["legal_lineage"] = {
        "is_constitutional": False,
        "constitutional_base": None,
        "amendment_chain": [],
        "amendment_number": None,
        "amendment_type": None,
        "confidence": 0
    }
    
    enhanced["context_analysis"] = {
        "legal_references": [],
        "amendment_targets": [],
        "relationship_type": "unknown",
        "legal_lineage": [],
        "confidence": 0
    }
    
    enhanced["grouping_metadata"] = {
        "context_grouped": False,
        "grouping_reason": None,
        "grouping_confidence": 0,
        "last_analysis": None
    }
    
    return enhanced
```

**Modify the main normalization function to call this:**
```python
def normalize_statute_structure(statute: Dict) -> Dict:
    # Existing normalization logic
    normalized = normalize_existing_fields(statute)
    
    # NEW: Add context-aware fields
    enhanced = enhance_statute_schema_with_context(normalized)
    
    return enhanced
```

### **Step 3.2: Update Section Versioning Schema**

**File**: `06_section_versioning/assign_section_versions.py`

**Add this function for enhanced section grouping:**
```python
def group_sections_by_context(sections: List[Dict]) -> Dict:
    """
    Enhanced section grouping with amendment awareness
    """
    # NEW: Context-aware grouping
    try:
        context_groups = context_analyzer.group_sections_by_context(sections)
    except Exception as e:
        logger.warning(f"Context grouping failed: {e}, using traditional method")
        context_groups = {}
    
    # Existing logic (keep as fallback)
    traditional_groups = group_by_traditional_method(sections)
    
    # Merge and validate
    return merge_context_and_traditional_groups(context_groups, traditional_groups)

def merge_context_and_traditional_groups(context_groups: Dict, traditional_groups: Dict) -> Dict:
    """
    Merge context-aware and traditional grouping results
    """
    merged_groups = traditional_groups.copy()
    
    # Add context information to traditional groups
    for group_key, sections in merged_groups.items():
        for section in sections:
            if "context_analysis" not in section:
                section["context_analysis"] = {
                    "amendment_context": "unknown",
                    "relationship_type": "unknown",
                    "confidence": 0
                }
    
    # Override with context groups where available
    for context_key, context_sections in context_groups.items():
        if context_key in merged_groups:
            # Merge context information
            for i, section in enumerate(merged_groups[context_key]):
                if i < len(context_sections):
                    section["context_analysis"].update(context_sections[i].get("context_analysis", {}))
    
    return merged_groups
```

---

## 🔧 INTEGRATION POINTS SUMMARY

### **Files Modified:**
1. **`utils/statute_context_analyzer.py`** - NEW FILE
2. **`utils/context_prompt_manager.py`** - NEW FILE  
3. **`05_statute_versioning/group_statutes_by_base.py`** - MODIFIED
4. **`utils/gpt_prompt_optimizer.py`** - MODIFIED
5. **`02_db_normalization/normalize_structure.py`** - MODIFIED
6. **`06_section_versioning/assign_section_versions.py`** - MODIFIED

### **Key Integration Points:**
- **Phase 5**: Statute versioning with context analysis
- **Phase 6**: Section versioning with amendment awareness
- **Utils**: Extended GPT integration and prompt management

### **Data Flow Changes:**
1. **Normalization**: Add context fields to schema
2. **Grouping**: Context analysis before similarity checking
3. **Versioning**: Amendment-aware section grouping
4. **Caching**: Context-specific prompt caching

---

## 🧪 TESTING & VALIDATION

### **Test Cases to Implement:**

#### **1. Constitutional Amendment Detection**
```python
def test_constitutional_amendment_detection():
    """Test constitutional amendment chain detection"""
    test_statutes = [
        {"Statute_Name": "Constitution of Pakistan", "Preamble": "Original constitution..."},
        {"Statute_Name": "Constitution (18th Amendment) Order 1985", "Preamble": "Amendment to Article 51..."}
    ]
    
    analyzer = StatuteContextAnalyzer(gpt_client)
    relationship = analyzer.analyze_relationship(test_statutes[0], test_statutes[1])
    
    assert relationship["should_merge"] == True
    assert relationship["relationship_type"] == "constitutional_amendment_chain"
```

#### **2. Legal Lineage Analysis**
```python
def test_legal_lineage_analysis():
    """Test legal lineage relationship detection"""
    test_statutes = [
        {"Statute_Name": "Act 1973", "Preamble": "Original act..."},
        {"Statute_Name": "Act 1973 (Amendment) 1985", "Preamble": "Amendment to Act 1973..."}
    ]
    
    analyzer = StatuteContextAnalyzer(gpt_client)
    relationship = analyzer.analyze_relationship(test_statutes[0], test_statutes[1])
    
    assert relationship["should_merge"] == True
    assert relationship["relationship_type"] == "amendment_relationship"
```

---

## 📊 PERFORMANCE OPTIMIZATION

### **Caching Strategy:**
- **Context Analysis**: Cache constitutional lineage analysis (7-day TTL)
- **Prompt Templates**: Cache optimized prompts (30-day TTL)
- **Relationship Analysis**: Cache statute relationships (7-day TTL)

### **Batch Processing:**
- **Parallel Analysis**: Process multiple statutes simultaneously
- **Context Batching**: Group similar context types for batch processing
- **Memory Management**: Stream large datasets to avoid memory issues

### **Fallback Mechanisms:**
- **Rule-Based Fallbacks**: Use pattern matching when GPT fails
- **Confidence Thresholds**: Only use high-confidence context analysis
- **Graceful Degradation**: Fall back to existing similarity logic

---

## 🚀 DEPLOYMENT CHECKLIST

### **Pre-Deployment:**
- [ ] Test with constitutional amendment data
- [ ] Validate legal accuracy with experts
- [ ] Performance testing with full dataset
- [ ] Error handling and logging validation

### **Deployment:**
- [ ] Deploy context analyzer to staging
- [ ] Test integration with existing pipeline
- [ ] Monitor performance and accuracy
- [ ] Gradual rollout to production

### **Post-Deployment:**
- [ ] Monitor accuracy improvements
- [ ] Track performance metrics
- [ ] Collect feedback from legal experts
- [ ] Iterate and improve prompts

---

## 📚 NEXT STEPS

1. **Review this implementation guide** with your team
2. **Start with Phase 1** (Context Analysis Engine)
3. **Test with constitutional amendment data** to validate approach
4. **Implement incrementally** to minimize risk
5. **Monitor and optimize** based on real-world performance

---

**This implementation will transform your LawChronicle pipeline from basic name-matching to intelligent, context-aware legal document analysis that understands constitutional relationships and preserves legal lineage.** 🚀

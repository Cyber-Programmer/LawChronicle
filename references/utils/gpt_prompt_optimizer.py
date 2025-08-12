"""
Smart Prompt Optimization for GPT API calls.
Analyzes and optimizes prompts for better responses and higher success rates.
"""

import re
import json
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging
from utils.gpt_cache import gpt_cache
from utils.gpt_monitor import gpt_monitor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class PromptAnalysis:
    """Analysis results for a prompt."""
    clarity_score: float
    specificity_score: float
    structure_score: float
    length_score: float
    overall_score: float
    suggestions: List[str]
    optimized_prompt: str
    confidence: float

class PromptOptimizer:
    """Analyzes and optimizes prompts for better GPT responses."""
    
    def __init__(self):
        self.optimization_rules = {
            "clarity": self._analyze_clarity,
            "specificity": self._analyze_specificity,
            "structure": self._analyze_structure,
            "length": self._analyze_length
        }
        
        # Common prompt patterns and their optimizations
        self.prompt_patterns = {
            r"find.*date": self._optimize_date_finding,
            r"compare.*similar": self._optimize_comparison,
            r"extract.*information": self._optimize_extraction,
            r"analyze.*text": self._optimize_analysis,
            r"select.*best": self._optimize_selection
        }
    
    def analyze_prompt(self, prompt: str) -> PromptAnalysis:
        """Analyze a prompt and provide optimization suggestions."""
        
        # Check cache first
        cache_key = f"prompt_analysis:{hashlib.md5(prompt.encode()).hexdigest()}"
        cached_result = gpt_cache.get(cache_key)
        if cached_result:
            return PromptAnalysis(**cached_result)
        
        # Perform analysis
        clarity_score = self._analyze_clarity(prompt)
        specificity_score = self._analyze_specificity(prompt)
        structure_score = self._analyze_structure(prompt)
        length_score = self._analyze_length(prompt)
        
        # Calculate overall score
        overall_score = (clarity_score + specificity_score + structure_score + length_score) / 4
        
        # Generate suggestions
        suggestions = self._generate_suggestions(prompt, {
            "clarity": clarity_score,
            "specificity": specificity_score,
            "structure": structure_score,
            "length": length_score
        })
        
        # Optimize prompt
        optimized_prompt = self._optimize_prompt(prompt)
        
        # Calculate confidence
        confidence = self._calculate_confidence(overall_score, len(suggestions))
        
        # Create analysis result
        analysis = PromptAnalysis(
            clarity_score=clarity_score,
            specificity_score=specificity_score,
            structure_score=structure_score,
            length_score=length_score,
            overall_score=overall_score,
            suggestions=suggestions,
            optimized_prompt=optimized_prompt,
            confidence=confidence
        )
        
        # Cache the result
        gpt_cache.set(cache_key, analysis.__dict__)
        
        return analysis
    
    def _analyze_clarity(self, prompt: str) -> float:
        """Analyze prompt clarity (0-1 score)."""
        score = 1.0
        
        # Check for vague words
        vague_words = ["good", "bad", "nice", "better", "worse", "appropriate", "suitable"]
        vague_count = sum(1 for word in vague_words if word.lower() in prompt.lower())
        score -= vague_count * 0.1
        
        # Check for ambiguous pronouns
        ambiguous_pronouns = ["it", "this", "that", "these", "those"]
        pronoun_count = sum(1 for word in ambiguous_pronouns if word.lower() in prompt.lower())
        score -= pronoun_count * 0.05
        
        # Check for clear instructions
        instruction_words = ["extract", "find", "identify", "compare", "analyze", "select"]
        has_instruction = any(word in prompt.lower() for word in instruction_words)
        if not has_instruction:
            score -= 0.3
        
        return max(0.0, score)
    
    def _analyze_specificity(self, prompt: str) -> float:
        """Analyze prompt specificity (0-1 score)."""
        score = 1.0
        
        # Check for specific details
        specific_indicators = ["date", "number", "name", "location", "time", "format"]
        specific_count = sum(1 for indicator in specific_indicators if indicator in prompt.lower())
        score += specific_count * 0.1
        
        # Check for context
        context_words = ["statute", "section", "legal", "document", "text"]
        context_count = sum(1 for word in context_words if word in prompt.lower())
        score += context_count * 0.05
        
        # Penalize overly generic prompts
        if len(prompt.split()) < 10:
            score -= 0.2
        
        return min(1.0, max(0.0, score))
    
    def _analyze_structure(self, prompt: str) -> float:
        """Analyze prompt structure (0-1 score)."""
        score = 1.0
        
        # Check for clear sections
        sections = prompt.split('\n\n')
        if len(sections) >= 2:
            score += 0.2
        
        # Check for bullet points or numbered lists
        if re.search(r'^\s*[-*•]\s', prompt, re.MULTILINE) or re.search(r'^\s*\d+\.\s', prompt, re.MULTILINE):
            score += 0.2
        
        # Check for clear question format
        if prompt.strip().endswith('?'):
            score += 0.1
        
        # Check for excessive length without structure
        if len(prompt) > 500 and len(sections) < 3:
            score -= 0.3
        
        return max(0.0, score)
    
    def _analyze_length(self, prompt: str) -> float:
        """Analyze prompt length appropriateness (0-1 score)."""
        word_count = len(prompt.split())
        
        if word_count < 10:
            return 0.3  # Too short
        elif word_count < 50:
            return 0.9  # Good length
        elif word_count < 200:
            return 0.7  # Acceptable but long
        else:
            return 0.4  # Too long
    
    def _generate_suggestions(self, prompt: str, scores: Dict[str, float]) -> List[str]:
        """Generate optimization suggestions based on scores."""
        suggestions = []
        
        if scores["clarity"] < 0.7:
            suggestions.append("Add more specific instructions and avoid vague terms")
        
        if scores["specificity"] < 0.6:
            suggestions.append("Include more specific details and context")
        
        if scores["structure"] < 0.6:
            suggestions.append("Organize the prompt into clear sections")
        
        if scores["length"] < 0.5:
            suggestions.append("Add more context and details")
        elif scores["length"] > 0.8:
            suggestions.append("Consider breaking into multiple focused prompts")
        
        return suggestions
    
    def _optimize_prompt(self, prompt: str) -> str:
        """Apply pattern-based optimizations to the prompt."""
        optimized = prompt
        
        # Apply pattern-specific optimizations
        for pattern, optimizer in self.prompt_patterns.items():
            if re.search(pattern, prompt, re.IGNORECASE):
                optimized = optimizer(optimized)
        
        # Apply general optimizations
        optimized = self._apply_general_optimizations(optimized)
        
        return optimized
    
    def _optimize_date_finding(self, prompt: str) -> str:
        """Optimize date finding prompts."""
        if "date" not in prompt.lower():
            prompt += "\n\nPlease provide the date in DD-MMM-YYYY format."
        
        if "best" in prompt.lower() and "reason" not in prompt.lower():
            prompt += "\n\nPlease explain your reasoning for selecting this date."
        
        return prompt
    
    def _optimize_comparison(self, prompt: str) -> str:
        """Optimize comparison prompts."""
        if "similar" in prompt.lower():
            prompt += "\n\nPlease provide a similarity score (0-1) and explain your reasoning."
        
        return prompt
    
    def _optimize_extraction(self, prompt: str) -> str:
        """Optimize extraction prompts."""
        if "extract" in prompt.lower():
            prompt += "\n\nPlease provide the extracted information in a structured format."
        
        return prompt
    
    def _optimize_analysis(self, prompt: str) -> str:
        """Optimize analysis prompts."""
        if "analyze" in prompt.lower():
            prompt += "\n\nPlease provide your analysis with supporting evidence."
        
        return prompt
    
    def _optimize_selection(self, prompt: str) -> str:
        """Optimize selection prompts."""
        if "select" in prompt.lower() and "best" in prompt.lower():
            prompt += "\n\nPlease rank the options and explain your selection criteria."
        
        return prompt
    
    def _apply_general_optimizations(self, prompt: str) -> str:
        """Apply general prompt optimizations."""
        # Add context if missing
        if "context" not in prompt.lower() and len(prompt.split()) < 20:
            prompt = f"Context: You are analyzing legal documents.\n\n{prompt}"
        
        # Add output format if not specified
        if "format" not in prompt.lower() and "json" not in prompt.lower():
            prompt += "\n\nPlease provide your response in a clear, structured format."
        
        # Add confidence level request
        if "confidence" not in prompt.lower():
            prompt += "\n\nPlease indicate your confidence level (high/medium/low) in your response."
        
        return prompt
    
    def _calculate_confidence(self, overall_score: float, suggestion_count: int) -> float:
        """Calculate confidence in the optimization."""
        confidence = overall_score
        
        # Higher confidence with fewer suggestions
        if suggestion_count == 0:
            confidence += 0.2
        elif suggestion_count <= 2:
            confidence += 0.1
        else:
            confidence -= 0.1
        
        return min(1.0, max(0.0, confidence))

# Global instance
prompt_optimizer = PromptOptimizer()

def optimize_gpt_prompt(func):
    """Decorator to automatically optimize prompts before GPT calls."""
    def wrapper(*args, **kwargs):
        # Find the prompt argument
        prompt = None
        if args and isinstance(args[0], str):
            prompt = args[0]
        elif 'prompt' in kwargs:
            prompt = kwargs['prompt']
        
        if prompt:
            # Analyze and optimize the prompt
            analysis = prompt_optimizer.analyze_prompt(prompt)
            
            # Use optimized prompt if confidence is high
            if analysis.confidence > 0.7:
                if args and isinstance(args[0], str):
                    args = (analysis.optimized_prompt,) + args[1:]
                elif 'prompt' in kwargs:
                    kwargs['prompt'] = analysis.optimized_prompt
            
            # Log optimization
            gpt_monitor.log_call("prompt_optimization", success=True)
        
        return func(*args, **kwargs)
    return wrapper

def get_prompt_analysis(prompt: str) -> PromptAnalysis:
    """Get detailed analysis of a prompt."""
    return prompt_optimizer.analyze_prompt(prompt)

# Example usage
def demo_prompt_optimization():
    """Demonstrate prompt optimization capabilities."""
    
    test_prompts = [
        "Find the date in this text",
        "Compare these two statutes and tell me if they are similar",
        "Extract all the important information from this legal document",
        "Analyze this text and give me the best answer",
        "Select the most appropriate date from the following options"
    ]
    
    print("Prompt Optimization Demo\n")
    
    for i, prompt in enumerate(test_prompts, 1):
        print(f"Original Prompt {i}: {prompt}")
        
        analysis = get_prompt_analysis(prompt)
        
        print(f"Overall Score: {analysis.overall_score:.2f}")
        print(f"Confidence: {analysis.confidence:.2f}")
        print(f"Suggestions: {', '.join(analysis.suggestions)}")
        print(f"Optimized: {analysis.optimized_prompt}")
        print("-" * 50)

if __name__ == "__main__":
    demo_prompt_optimization() 
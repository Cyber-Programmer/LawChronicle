"""
GPT Usage Monitoring Dashboard

This module provides monitoring and analytics for GPT API usage optimization.
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
from utils.gpt_cache import gpt_cache

class GPTMonitor:
    """Monitor GPT API usage and optimization metrics."""
    
    def __init__(self):
        self.usage_stats = {
            "total_calls": 0,
            "cached_calls": 0,
            "batch_calls": 0,
            "fallback_calls": 0,
            "rate_limited_calls": 0,
            "api_calls": 0,
            "errors": 0,
            "start_time": datetime.now(),
            "call_history": []
        }
    
    def log_call(self, call_type: str, success: bool = True, error: str = None):
        """Log a GPT call."""
        self.usage_stats["total_calls"] += 1
        
        if call_type == "cached":
            self.usage_stats["cached_calls"] += 1
        elif call_type == "batch":
            self.usage_stats["batch_calls"] += 1
        elif call_type == "fallback":
            self.usage_stats["fallback_calls"] += 1
        elif call_type == "rate_limited":
            self.usage_stats["rate_limited_calls"] += 1
        elif call_type == "api":
            self.usage_stats["api_calls"] += 1
        
        if not success:
            self.usage_stats["errors"] += 1
        
        self.usage_stats["call_history"].append({
            "timestamp": datetime.now().isoformat(),
            "type": call_type,
            "success": success,
            "error": error
        })
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization statistics."""
        total = self.usage_stats["total_calls"]
        if total == 0:
            return {"message": "No calls recorded yet"}
        
        cache_hit_rate = (self.usage_stats["cached_calls"] / total * 100) if total > 0 else 0
        batch_efficiency = (self.usage_stats["batch_calls"] / total * 100) if total > 0 else 0
        fallback_efficiency = (self.usage_stats["fallback_calls"] / total * 100) if total > 0 else 0
        rate_limited_rate = (self.usage_stats["rate_limited_calls"] / total * 100) if total > 0 else 0
        api_call_rate = (self.usage_stats["api_calls"] / total * 100) if total > 0 else 0
        
        # Calculate cost savings (assuming $0.03 per 1K tokens for GPT-4)
        estimated_cost_saved = self.usage_stats["cached_calls"] * 0.03  # Simplified calculation
        
        return {
            "total_calls": total,
            "cache_hit_rate_percent": round(cache_hit_rate, 2),
            "batch_efficiency_percent": round(batch_efficiency, 2),
            "fallback_efficiency_percent": round(fallback_efficiency, 2),
            "rate_limited_calls": self.usage_stats["rate_limited_calls"],
            "api_call_rate_percent": round(api_call_rate, 2),
            "error_rate_percent": round((self.usage_stats["errors"] / total * 100), 2),
            "estimated_cost_saved_usd": round(estimated_cost_saved, 2),
            "uptime_hours": round((datetime.now() - self.usage_stats["start_time"]).total_seconds() / 3600, 2)
        }
    
    def print_dashboard(self):
        """Print a formatted dashboard."""
        stats = self.get_optimization_stats()
        cache_stats = gpt_cache.get_stats()
        
        print("\n" + "="*60)
        print("🤖 GPT OPTIMIZATION DASHBOARD")
        print("="*60)
        
        print(f"📊 Total Calls: {stats['total_calls']}")
        print(f"⏱️  Uptime: {stats['uptime_hours']} hours")
        print(f"💰 Estimated Cost Saved: ${stats['estimated_cost_saved_usd']}")
        
        print(f"\n🎯 Optimization Metrics:")
        print(f"   Cache Hit Rate: {stats['cache_hit_rate_percent']}%")
        print(f"   Batch Efficiency: {stats['batch_efficiency_percent']}%")
        print(f"   Fallback Efficiency: {stats['fallback_efficiency_percent']}%")
        print(f"   API Call Rate: {stats['api_call_rate_percent']}%")
        print(f"   Error Rate: {stats['error_rate_percent']}%")
        
        print(f"\n💾 Cache Statistics:")
        print(f"   Cache Size: {cache_stats['cache_size']} entries")
        print(f"   Cache Hit Rate: {cache_stats['hit_rate_percent']}%")
        print(f"   Cache Hits: {cache_stats['hits']}")
        print(f"   Cache Misses: {cache_stats['misses']}")
        
        print(f"\n📈 Performance Summary:")
        if stats['cache_hit_rate_percent'] > 70:
            print("   ✅ Excellent cache performance!")
        elif stats['cache_hit_rate_percent'] > 50:
            print("   ⚠️  Good cache performance, room for improvement")
        else:
            print("   ❌ Low cache performance, consider optimization")
        
        if stats['api_call_rate_percent'] < 30:
            print("   ✅ Excellent API call reduction!")
        elif stats['api_call_rate_percent'] < 50:
            print("   ⚠️  Good API call reduction")
        else:
            print("   ❌ High API call rate, consider more optimization")
        
        print("="*60)
    
    def save_report(self, filename: str = "gpt_optimization_report.json"):
        """Save optimization report to file."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "usage_stats": self.usage_stats,
            "optimization_stats": self.get_optimization_stats(),
            "cache_stats": gpt_cache.get_stats()
        }
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📄 Report saved to: {filename}")

# Global monitor instance
gpt_monitor = GPTMonitor()

def monitor_gpt_call(call_type: str, func):
    """Decorator to monitor GPT function calls."""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            gpt_monitor.log_call(call_type, success=True)
            return result
        except Exception as e:
            gpt_monitor.log_call(call_type, success=False, error=str(e))
            raise
    return wrapper 
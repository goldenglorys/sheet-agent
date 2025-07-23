import time
import psutil
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class AnalysisMetrics:
    """Tracks comprehensive metrics during analysis execution."""

    def __init__(self):
        self.start_time: Optional[float] = None
        self.phase_timers: Dict[str, float] = {}
        self.metrics: Dict[str, Any] = {
            "timing": {
                "total_analysis_time": 0.0,
                "preprocessing_time": 0.0,
                "ai_processing_time": 0.0,
                "sandbox_execution_time": 0.0,
                "file_operations_time": 0.0,
            },
            "ai_usage": {
                "total_ai_calls": 0,
                "total_tokens_used": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "estimated_cost_usd": 0.0,
            },
            "analysis_quality": {
                "cumulative_rows_detected": 0,
                "data_rows_processed": 0,
                "schema_confidence_score": 0.0,
                "validation_errors": [],
            },
            "system_resources": {
                "peak_memory_mb": 0.0,
                "workbook_size_mb": 0.0,
                "output_file_size_mb": 0.0,
            },
        }

    def __enter__(self):
        """Start comprehensive tracking."""
        self.start_time = time.time()
        self._record_memory_usage()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Finalize metrics collection."""
        if self.start_time:
            self.metrics["timing"]["total_analysis_time"] = (
                time.time() - self.start_time
            )
        self._record_memory_usage()
        self._log_final_metrics()

    def start_phase(self, phase_name: str):
        """Begin timing a specific phase."""
        self.phase_timers[phase_name] = time.time()

    def end_phase(self, phase_name: str):
        """End timing and record phase duration."""
        if phase_name in self.phase_timers:
            duration = time.time() - self.phase_timers[phase_name]
            self.metrics["timing"][f"{phase_name}_time"] = duration
            del self.phase_timers[phase_name]

    def record_ai_call(
        self,
        tokens_used: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost: float = 0.0,
    ):
        """Record AI API call metrics."""
        self.metrics["ai_usage"]["total_ai_calls"] += 1
        self.metrics["ai_usage"]["total_tokens_used"] += tokens_used
        self.metrics["ai_usage"]["prompt_tokens"] += prompt_tokens
        self.metrics["ai_usage"]["completion_tokens"] += completion_tokens
        self.metrics["ai_usage"]["estimated_cost_usd"] += cost

    def record_file_size(self, file_path: Path, file_type: str):
        """Record file size metrics."""
        if file_path.exists():
            size_mb = file_path.stat().st_size / (1024 * 1024)
            if file_type == "workbook":
                self.metrics["system_resources"]["workbook_size_mb"] = size_mb
            elif file_type == "output":
                self.metrics["system_resources"]["output_file_size_mb"] = size_mb

    def record_analysis_quality(
        self,
        cumulative_rows: int = 0,
        data_rows: int = 0,
        confidence: float = 0.0,
        errors: list = None,
    ):
        """Record analysis quality metrics."""
        self.metrics["analysis_quality"]["cumulative_rows_detected"] = cumulative_rows
        self.metrics["analysis_quality"]["data_rows_processed"] = data_rows
        self.metrics["analysis_quality"]["schema_confidence_score"] = confidence
        self.metrics["analysis_quality"]["validation_errors"] = errors or []

    def _record_memory_usage(self):
        """Track peak memory usage."""
        try:
            current_memory = psutil.Process().memory_info().rss / (1024 * 1024)  # MB
            current_peak = self.metrics["system_resources"]["peak_memory_mb"]
            self.metrics["system_resources"]["peak_memory_mb"] = max(
                current_peak, current_memory
            )
        except Exception:
            # Graceful fallback if psutil not available
            pass

    def _log_final_metrics(self):
        """Log comprehensive metrics summary."""
        timing = self.metrics["timing"]
        ai_usage = self.metrics["ai_usage"]

        logger.info("=== ANALYSIS METRICS SUMMARY ===")
        logger.info(f"Total Time: {timing['total_analysis_time']:.2f}s")
        logger.info(f"AI Calls: {ai_usage['total_ai_calls']}")
        logger.info(f"Total Tokens: {ai_usage['total_tokens_used']}")
        logger.info(f"Estimated Cost: ${ai_usage['estimated_cost_usd']:.4f}")
        logger.info(
            f"Peak Memory: {self.metrics['system_resources']['peak_memory_mb']:.1f}MB"
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Return complete metrics dictionary."""
        return self.metrics.copy()

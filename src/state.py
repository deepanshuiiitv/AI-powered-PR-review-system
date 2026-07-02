from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class ReviewState:
    """
    State object for agentic PR review workflow.
    Passed through all agent nodes and updated as decisions are made.
    """

    # - BASIC PR DATA -
    pr_url: Optional[str] = None
    owner: Optional[str] = None
    repo: Optional[str] = None
    pr_number: Optional[int] = None

    # - PR CONTENT -
    pr_data: Dict[str, Any] = field(default_factory=dict)  # metadata
    pr_files: List[Dict[str, Any]] = field(default_factory=list)  # file list
    pr_diff: Optional[str] = None  # raw unified diff

    # - PREPROCESSING RESULTS -
    is_complex: bool = False  # simple=False, complex=True
    risk_level: str = "low"  # low, medium, high
    analysis_hints: List[str] = field(default_factory=list)  # files of interest

    # - PARSING RESULTS -
    parsed_diff_chunks: List[str] = field(default_factory=list)
    parsed_metadata: Dict[str, Any] = field(default_factory=dict)

    # - PLANNING -
    planned_tools: List[str] = field(default_factory=list)
    planner_reasoning: Optional[str] = None

    # - TOOL EXECUTION RESULTS -
    findings: Dict[str, Any] = field(default_factory=dict)  # aggregated findings
    critical_issues: List[Dict[str, Any]] = field(default_factory=list)
    security_issues: List[Dict[str, Any]] = field(default_factory=list)
    code_quality_issues: List[Dict[str, Any]] = field(default_factory=list)
    performance_issues: List[Dict[str, Any]] = field(default_factory=list)
    test_coverage_issues: List[Dict[str, Any]] = field(default_factory=list)
    positive_aspects: List[str] = field(default_factory=list)
    recommendations: List[Dict[str, Any]] = field(default_factory=list)

    # - DECISION LOOP TRACKING -
    loop_iteration: int = 0
    max_iterations: int = 3
    needs_more_analysis: bool = False
    deep_security_done: bool = False

    # - FINAL RESULTS -
    final_score: Optional[float] = None
    final_verdict: Optional[str] = None  # APPROVE, REQUEST_CHANGES, COMMENT
    final_summary: Optional[str] = None
    formatted_report: Optional[str] = None

    # - ERRORS/LOGGING -
    errors: List[str] = field(default_factory=list)

    def add_error(self, error: str):
        """Log an error"""
        self.errors.append(error)

    def reset_findings(self):
        """Clear findings for next iteration"""
        self.findings = {}
        self.critical_issues = []
        self.security_issues = []
        self.code_quality_issues = []
        self.performance_issues = []
        self.test_coverage_issues = []
        self.recommendations = []
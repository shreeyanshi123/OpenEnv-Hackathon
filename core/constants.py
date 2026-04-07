"""
Centralized constants for the CI/CD Pipeline Diagnosis Environment.
"""

# Episode Limits
MAX_STEPS = 15
STEP_PENALTY = 0.02

# Diagnosis Scoring Thresholds
DIAGNOSIS_GOOD_THRESHOLD = 0.6
DIAGNOSIS_PARTIAL_THRESHOLD = 0.3

# Fix Scoring Thresholds
FIX_GOOD_THRESHOLD = 0.7
FIX_PARTIAL_THRESHOLD = 0.4

# Structural & Keyword Matching Weights
KEYWORD_WEIGHT = 0.6
STRUCTURE_WEIGHT = 0.4
LINE_OVERLAP_THRESHOLD = 0.6

# Inference / Evaluation
SUCCESS_SCORE_THRESHOLD = 0.3

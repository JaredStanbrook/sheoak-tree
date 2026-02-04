"""ML package status.

This package is in active migration from file-based sequence persistence to a
database-backed pipeline. Keep runtime dependencies on legacy training scripts
isolated until migration milestones are complete.
"""

ML_PIPELINE_STATUS = "migration_in_progress"

# Core continuity pack

Store Core-owned bounded transcript exports and subordinate work receipts here. Each source thread has exactly one owner and one transcript root. A complete export contains sanitized selected JSONL records, display-safe Markdown parts, chronological indexes, and a post-navigation manifest binding the stable source prefix and output inventory.

Use `tools/export_agent_thread_continuity.py`; do not hand-edit generated transcript records, copy another owner's archive, or reconstruct an unavailable source from summaries. The continuity index links export metadata and never replaces canonical documents or immutable research records.

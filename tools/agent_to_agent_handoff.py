"""Compatibility entry point for the generic plan-handoff tool."""

from agent_to_agent_plan_handoff import main as _plan_handoff_main


def main(argv: list[str] | None = None) -> int:
    """Run the generic plan-handoff implementation through the legacy alias."""

    return _plan_handoff_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())

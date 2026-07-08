from __future__ import annotations

from typing import Any


class TaskPlanner:
    """Turns intents into safe, reviewable steps before any external action runs."""

    def create_plan(self, *, intent: str, agent: str, text: str, context: dict[str, Any]) -> list[dict[str, Any]]:
        if intent == "trading_scan":
            return [
                {"step": "open_trading_module", "status": "pending", "requires_confirmation": False},
                {"step": "load_live_market_data", "status": "pending", "requires_confirmation": False},
                {"step": "calculate_risk_entry_stop_target", "status": "pending", "requires_confirmation": False},
                {"step": "explain_opportunities", "status": "pending", "requires_confirmation": False},
            ]
        if intent == "screen_summary":
            return [
                {"step": "request_screen_permission", "status": "pending", "requires_confirmation": True},
                {"step": "capture_screen_read_only", "status": "pending", "requires_confirmation": True},
                {"step": "summarize_visible_context", "status": "pending", "requires_confirmation": False},
            ]
        if intent == "browser_action":
            return [
                {"step": "open_browser_or_tab", "status": "pending", "requires_confirmation": False},
                {"step": "search_or_navigate", "status": "pending", "requires_confirmation": False},
                {"step": "summarize_results", "status": "pending", "requires_confirmation": False},
            ]
        if intent == "weather_query":
            return [
                {"step": "detect_weather_location", "status": "pending", "requires_confirmation": False},
                {"step": "fetch_live_weather", "status": "pending", "requires_confirmation": False},
                {"step": "explain_rain_temperature_and_next_steps", "status": "pending", "requires_confirmation": False},
            ]
        if intent == "reader_request":
            return [
                {"step": "identify_requested_file_or_folder", "status": "pending", "requires_confirmation": False},
                {"step": "check_file_safety_rules", "status": "pending", "requires_confirmation": False},
                {"step": "request_file_read_permission_if_needed", "status": "pending", "requires_confirmation": True},
                {"step": "summarize_content", "status": "pending", "requires_confirmation": False},
            ]
        if intent == "home_control":
            return [
                {"step": "connect_home_assistant", "status": "pending", "requires_confirmation": True},
                {"step": "preview_device_action", "status": "pending", "requires_confirmation": True},
                {"step": "execute_after_confirmation", "status": "blocked", "requires_confirmation": True},
            ]
        if intent == "code_task":
            return [
                {"step": "inspect_project_files", "status": "pending", "requires_confirmation": False},
                {"step": "run_safe_tests_or_lint", "status": "pending", "requires_confirmation": False},
                {"step": "propose_or_apply_project_patch", "status": "pending", "requires_confirmation": False},
            ]
        return [
            {
                "step": f"handle_with_{agent}",
                "status": "pending",
                "requires_confirmation": False,
                "summary": text[:160],
                "module": context.get("module"),
            }
        ]

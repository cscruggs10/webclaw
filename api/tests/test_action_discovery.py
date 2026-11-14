"""Action discovery falls back to ERPClaw's list-all-actions listing."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills import router  # noqa: E402


def test_actions_from_listing_flattens_core_and_modules():
    listing = {
        "core_actions": ["trial-balance", "balance-sheet", "add-account"],
        "module_actions": {"fleet": ["list-trucks", "balance-sheet"], "bad": "x"},
    }
    assert router.actions_from_listing(listing) == [
        "add-account", "balance-sheet", "list-trucks", "trial-balance",
    ]
    assert router.actions_from_listing({"module_actions": {}}) == []
    assert router.actions_from_listing(None) == []


def test_list_actions_uses_list_all_actions(monkeypatch):
    calls = []

    async def fake_execute(skill, action, params):
        calls.append(action)
        if action == "list-all-actions":
            return {"status": "ok", "core_actions": ["profit-and-loss", "balance-sheet"],
                    "module_actions": {}}
        return {"status": "error", "error": "Unknown action: __discover__",
                "hint": "Run --action list-all-actions to see available actions"}

    monkeypatch.setattr(router, "execute_skill", fake_execute)
    monkeypatch.setattr(router, "get_skill_actions", lambda path: None)
    result = asyncio.run(router.list_actions("erpclaw"))
    assert result == {"status": "ok", "skill": "erpclaw",
                      "actions": ["balance-sheet", "profit-and-loss"]}
    assert calls == ["__discover__", "list-all-actions"]

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_reports_the_current_five_reviewed_records():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "5 条已人工复核记录" in readme
    assert "4 条已人工复核记录" not in readme


def test_user_instructions_explain_all_three_speech_states():
    instructions = (ROOT / "resources" / "使用说明.txt").read_text(
        encoding="utf-8"
    )

    assert "已检测到英文语音" in instructions
    assert "未检测到英文语音，但系统默认语音可用" in instructions
    assert "未检测到可用语音引擎" in instructions
    assert "仅禁用朗读" in instructions

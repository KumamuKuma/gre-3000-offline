from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_reports_the_current_reviewed_record_count():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "203 条已人工复核记录" in readme
    assert "145 条已人工复核记录" not in readme
    assert "128 条已人工复核记录" not in readme
    assert "4 条已人工复核记录" not in readme


def test_user_instructions_explain_all_three_speech_states():
    instructions = (ROOT / "resources" / "使用说明.txt").read_text(
        encoding="utf-8"
    )

    assert "已检测到英文语音" in instructions
    assert "未检测到英文语音，但系统默认语音可用" in instructions
    assert "未检测到可用语音引擎" in instructions
    assert "仅禁用朗读" in instructions


def test_release_documentation_matches_the_current_study_features():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    instructions = (ROOT / "resources" / "使用说明.txt").read_text(
        encoding="utf-8"
    )

    for text in (readme, instructions):
        assert "选择 List" in text or "主动选择 List" in text
        assert "简义模式" in text
        assert "四选一模式" in text
        assert "按星级学习" in text
        assert "完整词表" in text
        assert "0 至 3 星" in text or "0、1、2 或 3 星" in text
        assert "完成本轮" in text
        assert "同词根" in text
        assert "拼写相近" in text
        assert "真经 GRE 等价词" in text
        assert "机经 7.0" in text
        assert "自动朗读一次" in text
        assert "随机学习" not in text
        assert "重新洗牌" not in text
        assert "生词本" not in text
        assert "手动增加或减少已背次数" not in text

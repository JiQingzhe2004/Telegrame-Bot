from bot.domain.policy import confidence_gate, downgrade_by_permissions, progressive_action


def test_progressive_action_levels():
    first = progressive_action(level=1, strike_score=0, level3_mute_seconds=604800)
    second = progressive_action(level=2, strike_score=1, level3_mute_seconds=604800)
    third = progressive_action(level=2, strike_score=2, level3_mute_seconds=604800)
    fourth = progressive_action(level=3, strike_score=3, level3_mute_seconds=604800)
    assert first.action == "warn"
    assert second.action == "mute" and second.duration_seconds == 600
    assert third.action == "mute" and third.duration_seconds == 86400
    assert fourth.action == "mute" and fourth.duration_seconds == 604800


def test_confidence_gate():
    assert confidence_gate("mute", confidence=0.2, threshold=0.75) == "warn"
    assert confidence_gate("delete", confidence=0.2, threshold=0.75) == "delete"


def test_permission_downgrade():
    out = downgrade_by_permissions("mute", can_delete=False, can_restrict=False, can_ban=False)
    assert out == "warn"

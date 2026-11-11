from robotd.personality import GREEN, PURPLE, Personality, RuleBrain


def test_head_touch_is_happy():
    reaction = Personality().on_touch("head")
    assert reaction.emotion == "happy"
    assert reaction.led == GREEN


def test_chin_touch_is_curious():
    reaction = Personality().on_touch("chin")
    assert reaction.emotion == "curious"
    assert reaction.led == PURPLE


def test_far_away_is_calm():
    reaction = Personality().on_distance(4000)
    assert reaction.emotion == "idle"


def test_nearby_is_alert():
    reaction = Personality().on_distance(900)
    assert reaction.emotion == "alert"


def test_name_turns_head_and_speaks():
    reaction = Personality().on_name("小豆")
    assert reaction.emotion == "happy"
    assert reaction.pan > 0
    assert reaction.speech


def test_goodnight_changes_mood():
    personality = Personality()
    reaction = personality.on_text("晚安")
    assert reaction.emotion == "sleepy"
    assert personality.mood.value == "sleepy"


def test_rule_brain_answers_greeting():
    assert "在" in RuleBrain().reply("你好呀")


def test_empty_text_does_not_crash():
    assert RuleBrain().reply("   ")

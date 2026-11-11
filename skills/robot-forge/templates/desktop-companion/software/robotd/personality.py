"""Mood, expression and the offline rule brain.

The personality layer is deliberately small and deterministic. It decides what
the robot feels and what it says when no language model is available, so the
robot still has a character when the host is offline or the network is off.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

GREEN = (40, 220, 90)
PURPLE = (150, 90, 255)
ORANGE = (255, 120, 20)
BLUE = (40, 110, 255)
DIM = (10, 10, 14)


class Mood(str, Enum):
    calm = "calm"
    happy = "happy"
    curious = "curious"
    sleepy = "sleepy"
    alert = "alert"


@dataclass
class Reaction:
    """One observable reaction: face, colour, head pose and optional speech."""

    emotion: str
    led: tuple[int, int, int]
    pan: int
    tilt: int
    speech: str = ""


class RuleBrain:
    """Tiny keyword brain used when no external model is configured."""

    GREETINGS = ("你好", "在吗", "嗨", "hello", "hi")
    THANKS = ("谢谢", "thanks")
    GOODNIGHT = ("晚安", "睡觉", "睡吧")

    def reply(self, text: str, context: dict | None = None) -> str:
        cleaned = text.strip()
        if not cleaned:
            return "我在。"
        lowered = cleaned.lower()
        if any(word in lowered for word in self.GOODNIGHT):
            return "晚安，我把灯关小一点。"
        if any(word in lowered for word in self.GREETINGS):
            return "我在呢。今天过得怎么样？"
        if any(word in lowered for word in self.THANKS):
            return "不客气。"
        if "名字" in cleaned:
            return "我叫小豆。"
        if "几" in cleaned and "点" in cleaned:
            return "我看不到时钟，不过你说是几点就是几点。"
        if "?" in cleaned or "？" in cleaned:
            return "这个问题我还答不好，等我连上大脑再试试。"
        return "嗯，我听到了。"


class Personality:
    """State machine turning events into reactions."""

    def __init__(self, brain: RuleBrain | None = None) -> None:
        self.brain = brain or RuleBrain()
        self.mood = Mood.calm
        self.turns = 0

    def on_touch(self, zone: str) -> Reaction:
        if zone == "head":
            self.mood = Mood.happy
            return Reaction("happy", GREEN, pan=0, tilt=14, speech="嘿嘿。")
        self.mood = Mood.curious
        return Reaction("curious", PURPLE, pan=6, tilt=22)

    def on_distance(self, mm: int) -> Reaction:
        if mm <= 0 or mm > 1500:
            self.mood = Mood.calm
            return Reaction("idle", DIM, pan=0, tilt=8)
        self.mood = Mood.alert
        return Reaction("alert", BLUE, pan=0, tilt=-4)

    def on_name(self, text: str = "小豆") -> Reaction:
        self.mood = Mood.happy
        self.turns += 1
        speech = self.brain.reply(text or "小豆")
        return Reaction("happy", ORANGE, pan=18, tilt=6, speech=speech)

    def on_text(self, text: str) -> Reaction:
        self.turns += 1
        reply = self.brain.reply(text)
        if any(word in text for word in RuleBrain.GOODNIGHT):
            self.mood = Mood.sleepy
            return Reaction("sleepy", DIM, pan=0, tilt=0, speech=reply)
        self.mood = Mood.happy
        return Reaction("happy", ORANGE, pan=8, tilt=6, speech=reply)

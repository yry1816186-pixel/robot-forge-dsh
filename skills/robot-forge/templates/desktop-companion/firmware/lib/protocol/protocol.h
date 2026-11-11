#pragma once

#include <cstddef>

// Pure C++ parser for the host <-> firmware line protocol. It deliberately has
// no Arduino dependency so the same code runs in the native unit tests.

enum class MsgType {
  Unknown,
  Emo,
  Pose,
  Led,
  Mic,
  Vol,
  Touch,
  Dist,
  Ready,
  Err,
};

struct Message {
  MsgType type = MsgType::Unknown;
  bool ok = false;
  int a = 0;
  int b = 0;
  int c = 0;
  char word[16] = {0};
};

Message parseLine(const char* line, size_t len);
const char* msgTypeName(MsgType type);

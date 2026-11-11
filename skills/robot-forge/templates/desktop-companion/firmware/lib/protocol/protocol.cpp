#include "protocol.h"

#include <cctype>
#include <cstdlib>
#include <cstring>

namespace {

constexpr int kMaxTokens = 5;
constexpr size_t kWordMax = sizeof(Message::word);

bool lowerEquals(const char* text, const char* expected) {
  while (*text && *expected) {
    if (std::tolower(static_cast<unsigned char>(*text)) != *expected) {
      return false;
    }
    ++text;
    ++expected;
  }
  return *text == '\0' && *expected == '\0';
}

bool parseWord(const char* text, char* out) {
  size_t n = std::strlen(text);
  if (n == 0 || n >= kWordMax) {
    return false;
  }
  for (size_t i = 0; i < n; ++i) {
    out[i] = static_cast<char>(std::tolower(static_cast<unsigned char>(text[i])));
  }
  out[n] = '\0';
  return true;
}

bool parseInt(const char* text, int* out) {
  if (!text || !*text) {
    return false;
  }
  char* end = nullptr;
  long value = std::strtol(text, &end, 10);
  if (!end || *end != '\0' || value < -100000 || value > 100000) {
    return false;
  }
  *out = static_cast<int>(value);
  return true;
}

}  // namespace

Message parseLine(const char* line, size_t len) {
  Message msg;
  if (!line || len == 0 || len > 120) {
    return msg;
  }
  char buffer[121] = {0};
  std::memcpy(buffer, line, len);
  buffer[len] = '\0';

  char* tokens[kMaxTokens] = {nullptr};
  int count = 0;
  char* cursor = buffer;
  while (*cursor) {
    while (*cursor == ' ' || *cursor == '\t' || *cursor == '\r' || *cursor == '\n') {
      ++cursor;
    }
    if (!*cursor) {
      break;
    }
    if (count == kMaxTokens) {
      return msg;
    }
    tokens[count++] = cursor;
    while (*cursor && *cursor != ' ' && *cursor != '\t' && *cursor != '\r' && *cursor != '\n') {
      ++cursor;
    }
    if (*cursor) {
      *cursor++ = '\0';
    }
  }
  if (count == 0) {
    return msg;
  }

  const char* verb = tokens[0];
  const int argc = count - 1;

  if (lowerEquals(verb, "emo")) {
    if (argc == 1 && parseWord(tokens[1], msg.word) &&
        (std::strcmp(msg.word, "idle") == 0 || std::strcmp(msg.word, "happy") == 0 ||
         std::strcmp(msg.word, "curious") == 0 || std::strcmp(msg.word, "sleepy") == 0 ||
         std::strcmp(msg.word, "alert") == 0)) {
      msg.type = MsgType::Emo;
      msg.ok = true;
    }
    return msg;
  }
  if (lowerEquals(verb, "pose")) {
    if (argc == 2 && parseInt(tokens[1], &msg.a) && parseInt(tokens[2], &msg.b) &&
        msg.a >= -45 && msg.a <= 45 && msg.b >= -10 && msg.b <= 60) {
      msg.type = MsgType::Pose;
      msg.ok = true;
    }
    return msg;
  }
  if (lowerEquals(verb, "led")) {
    if (argc == 3 && parseInt(tokens[1], &msg.a) && parseInt(tokens[2], &msg.b) &&
        parseInt(tokens[3], &msg.c) && msg.a >= 0 && msg.a <= 255 && msg.b >= 0 &&
        msg.b <= 255 && msg.c >= 0 && msg.c <= 255) {
      msg.type = MsgType::Led;
      msg.ok = true;
    }
    return msg;
  }
  if (lowerEquals(verb, "mic")) {
    if (argc == 1 && parseWord(tokens[1], msg.word) &&
        (std::strcmp(msg.word, "on") == 0 || std::strcmp(msg.word, "off") == 0)) {
      msg.type = MsgType::Mic;
      msg.ok = true;
    }
    return msg;
  }
  if (lowerEquals(verb, "vol")) {
    if (argc == 1 && parseInt(tokens[1], &msg.a) && msg.a >= 0 && msg.a <= 100) {
      msg.type = MsgType::Vol;
      msg.ok = true;
    }
    return msg;
  }
  if (lowerEquals(verb, "touch")) {
    if (argc == 1 && parseWord(tokens[1], msg.word) &&
        (std::strcmp(msg.word, "head") == 0 || std::strcmp(msg.word, "chin") == 0)) {
      msg.type = MsgType::Touch;
      msg.ok = true;
    }
    return msg;
  }
  if (lowerEquals(verb, "dist")) {
    if (argc == 1 && parseInt(tokens[1], &msg.a) && msg.a >= 0 && msg.a <= 8190) {
      msg.type = MsgType::Dist;
      msg.ok = true;
    }
    return msg;
  }
  if (lowerEquals(verb, "ready")) {
    if (argc == 0) {
      msg.type = MsgType::Ready;
      msg.ok = true;
    }
    return msg;
  }
  if (lowerEquals(verb, "err")) {
    if (argc == 1 && parseWord(tokens[1], msg.word)) {
      msg.type = MsgType::Err;
      msg.ok = true;
    }
    return msg;
  }
  return msg;
}

const char* msgTypeName(MsgType type) {
  switch (type) {
    case MsgType::Emo: return "EMO";
    case MsgType::Pose: return "POSE";
    case MsgType::Led: return "LED";
    case MsgType::Mic: return "MIC";
    case MsgType::Vol: return "VOL";
    case MsgType::Touch: return "TOUCH";
    case MsgType::Dist: return "DIST";
    case MsgType::Ready: return "READY";
    case MsgType::Err: return "ERR";
    default: return "UNKNOWN";
  }
}
"""Minimal Standard MIDI File (type 1) writer."""


def _vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def _meta(kind, payload):
    return bytes([0xFF, kind]) + _vlq(len(payload)) + payload


class Track:
    def __init__(self, name, channel=0):
        self.channel = channel
        self.events = [(0, 0, _meta(0x03, name.encode("utf-8")))]

    def note(self, start, length, pitch, velocity=90, lyric=None):
        if lyric:
            self.events.append((start, 1, _meta(0x05, lyric.encode("utf-8"))))
        self.events.append((start, 2, bytes([0x90 | self.channel, pitch, velocity])))
        self.events.append((start + length, 0, bytes([0x80 | self.channel, pitch, 0])))

    def marker(self, tick, text):
        self.events.append((tick, 1, _meta(0x06, text.encode("utf-8"))))

    def tempo(self, bpm):
        us = round(60_000_000 / bpm)
        self.events.append((0, 1, _meta(0x51, us.to_bytes(3, "big"))))
        self.events.append((0, 1, _meta(0x58, bytes([4, 2, 24, 8]))))

    def chunk(self):
        data, last = bytearray(), 0
        for tick, _, msg in sorted(self.events, key=lambda e: (e[0], e[1])):
            data += _vlq(tick - last) + msg
            last = tick
        data += _vlq(0) + _meta(0x2F, b"")
        return b"MTrk" + len(data).to_bytes(4, "big") + bytes(data)


def write(path, tracks, ppq=480):
    header = b"MThd" + (6).to_bytes(4, "big") + (1).to_bytes(2, "big")
    header += len(tracks).to_bytes(2, "big") + ppq.to_bytes(2, "big")
    with open(path, "wb") as f:
        f.write(header + b"".join(t.chunk() for t in tracks))

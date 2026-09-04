"""Give the chirp channel a sound, so you can hear the dish instead of just
watching yellow rings.

Nothing here feeds back into the simulation. It listens to whatever the world
is already doing - who is chirping, how loud, how far from you - and turns
that into short synthesized blips. No sample files: each blip is generated on
the fly as a decaying tone, so its pitch and length can vary with how loud the
emission actually was.
"""
import math

import numpy as np
import pygame

SAMPLE_RATE = 22050


def _tone(freq, duration, volume=1.0):
    """A short, percussive blip: a sine wave with an exponential decay
    envelope, so it reads as a chirp rather than a held note."""
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    envelope = np.exp(-t * (5.0 / duration))
    wave = np.sin(2 * math.pi * freq * t) * envelope * volume
    pcm = (wave * 32767).astype(np.int16)
    stereo = np.column_stack([pcm, pcm])
    return pygame.sndarray.make_sound(np.ascontiguousarray(stereo))


class ChirpAudio:
    """Plays a blip for every chirp that starts near the listener.

    Edge-triggered on purpose: a sustained chirp should sound like one event,
    not a buzz repeated every frame, so a blip only fires the moment an
    organism crosses from quiet to chirping.
    """

    def __init__(self):
        self.ready = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2)
            pygame.mixer.set_num_channels(16)
            # pitch varies a little so a crowd chirping together doesn't sound
            # like one instrument - built once, reused for every play
            self._tones = [_tone(560 + i * 40, 0.09) for i in range(6)]
            self.ready = True
        except pygame.error:
            pass  # no audio device (headless, CI, etc.) - stay silent
        self._was_chirping = set()

    def update(self, organisms, listener_xy, hearing_range, muted=False):
        if not self.ready:
            return
        lx, ly = listener_xy
        now_chirping = set()
        plays = []
        for o in organisms:
            loud = o.chirp > 0.15
            key = id(o)
            if loud:
                now_chirping.add(key)
                if key not in self._was_chirping:
                    d = math.hypot(o.x - lx, o.y - ly)
                    if d < hearing_range:
                        plays.append((d, o.chirp))
        self._was_chirping = now_chirping
        if muted or not plays:
            return
        # cap how many fire in one frame - a chirping crowd should not become
        # sixteen blips stacked into noise
        plays.sort(key=lambda p: p[0])
        for d, loudness in plays[:6]:
            vol = max(0.0, min(1.0, (1.0 - d / hearing_range))) * min(1.0, loudness)
            tone = self._tones[int(loudness * (len(self._tones) - 1))]
            tone.set_volume(vol * 0.5)
            tone.play()

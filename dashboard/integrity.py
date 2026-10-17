"""
integrity.py - Feed integrity / tamper analysis.

For every camera we watch the frames themselves and flag the kinds of
tampering a real attacker (or a fault) would cause:

  - FEED_LOSS   : no fresh frame for a while (camera unplugged / stream cut)
  - BLACK_FRAME : frame almost entirely dark (lens covered / signal cut)
  - FROZEN_FEED : identical frames repeating (replay / still image injected)

This is detection only - the dashboard reacts to what the feed does, it does
not fabricate feeds. Each check returns a 0..1 severity used by the trust score.
"""

import time

import numpy as np


class IntegrityAnalyzer:
    def __init__(self, freeze_diff=0.6, black_threshold=12.0,
                 loss_seconds=3.0, history=20):
        # mean per-pixel change below freeze_diff => frames are near-identical.
        # A real camera (even on a still scene) has sensor noise well above this;
        # a replayed/injected still image or a hung stream sits at ~0.
        self.freeze_diff = freeze_diff
        self.black_threshold = black_threshold     # mean brightness below => black
        self.loss_seconds = loss_seconds
        self._prev_small = None
        self._frozen_count = 0
        self._history = history
        self.last_frame_time = 0.0

    @staticmethod
    def _downscale(frame):
        g = frame
        if frame.ndim == 3:
            g = frame.mean(axis=2)
        return np.asarray(
            np.round(np.array(g[::8, ::8], dtype=np.float32)), dtype=np.float32
        )

    def update(self, frame):
        """Call on every decoded frame. Returns dict of flags + scores."""
        now = time.time()
        flags = {"feed_loss": False, "black_frame": False, "frozen_feed": False}
        scores = {"feed_loss": 0.0, "black_frame": 0.0, "frozen_feed": 0.0}

        if frame is None:
            age = now - self.last_frame_time if self.last_frame_time else self.loss_seconds + 1
            if age >= self.loss_seconds:
                flags["feed_loss"] = True
                scores["feed_loss"] = 1.0
            return self._finish(flags, scores)

        self.last_frame_time = now

        # --- black frame ---
        brightness = float(frame.mean())
        if brightness < self.black_threshold:
            flags["black_frame"] = True
            scores["black_frame"] = min(1.0, (self.black_threshold - brightness)
                                        / self.black_threshold + 0.4)

        # --- frozen feed (frame barely changes across time) ---
        small = self._downscale(frame)
        if self._prev_small is not None and small.shape == self._prev_small.shape:
            mean_diff = float(np.abs(small - self._prev_small).mean())
            if mean_diff < self.freeze_diff:
                self._frozen_count += 1
            else:
                self._frozen_count = 0
            if self._frozen_count >= 15:   # near-identical frames for a while
                flags["frozen_feed"] = True
                scores["frozen_feed"] = min(1.0, self._frozen_count / 30.0)
        self._prev_small = small

        return self._finish(flags, scores)

    def _finish(self, flags, scores):
        feed_health = 1.0 - max(scores.values()) if scores else 1.0
        return {
            "flags": flags,
            "scores": scores,
            "feed_health": round(max(0.0, feed_health), 3),
            "alerts": [k.upper() for k, v in flags.items() if v],
        }

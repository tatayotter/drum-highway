r"""
Drum Highway Companion
======================

A small Windows app that makes your e-drum pads sound with very low latency, and passes your hits on
to Drum Highway in the browser.

    kit (USB MIDI) -> Companion -> drum samples through ASIO / WASAPI exclusive  (a few ms)
                               \-> Drum Highway in Chrome/Edge over a local connection (for the highway + scoring)

Browsers can only play sound through Windows' shared audio path (roughly 20-40 ms extra). The Companion
plays the drum sounds itself, through ASIO (ASIO4ALL works with built-in sound cards) or WASAPI exclusive mode.

Run from source:  pip install sounddevice soundfile numpy python-rtmidi websockets   then   python drum_companion.py
"""
import asyncio
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("SD_ENABLE_ASIO", "1")  # ask sounddevice for its ASIO-enabled PortAudio build on Windows
import numpy as np

try:
    import sounddevice as sd
except Exception as e:  # pragma: no cover - only when PortAudio is missing
    sd, SD_ERROR = None, e
else:
    SD_ERROR = None
try:
    import soundfile as sf
except Exception:  # pragma: no cover
    sf = None
try:
    import rtmidi
except Exception:  # pragma: no cover
    rtmidi = None
import websockets

APP_NAME = "Drum Highway Companion"
VERSION = "1.0.0"
WS_PORT = 21928  # Drum Highway connects to ws://127.0.0.1:21928
SR_DEFAULT = 48000

# ---------------------------------------------------------------- drum slots and MIDI notes
SLOTS = ["kick", "snare", "hh", "hhOpen", "hhPedal", "crash", "ride", "tom1", "tom2", "tom3"]
SLOT_NAMES = {"kick": "Kick", "snare": "Snare", "hh": "Hi-hat (closed)", "hhOpen": "Hi-hat (open)", "hhPedal": "Hi-hat pedal",
              "crash": "Crash", "ride": "Ride", "tom1": "Tom 1", "tom2": "Tom 2", "tom3": "Floor tom"}
# General MIDI drum notes (what most modules send, the TDX-15 included). Editable in config.json.
DEFAULT_NOTES = {
    "kick": [36, 35], "snare": [38, 40, 37], "hh": [42, 22], "hhOpen": [46, 26], "hhPedal": [44],
    "crash": [49, 57, 55, 52], "ride": [51, 53, 59], "tom1": [48, 50], "tom2": [45, 47], "tom3": [43, 41],
}
# Filename rules for picking samples out of a folder (same idea as Drum Highway's kit loader)
RULES = {
    "kick": dict(inc=r"kick|\bbd\b|bassdrum|bass drum|\bkik\b"),
    "snare": dict(inc=r"snare|\bsd\b|\bsnr\b", avoid=r"rim|roll|flam|brush|ghost|stick"),
    "hh": dict(inc=r"hat|\bhh\b|hihat|\bchh\b", prefer=r"closed|\bchh\b|clsd|tight|\bcl\b|close", avoid=r"open|\bohh\b|pedal|foot|half"),
    "hhOpen": dict(inc=r"hat|\bhh\b|hihat|\bohh\b", need=r"open|\bohh\b"),
    "hhPedal": dict(inc=r"hat|\bhh\b|hihat", need=r"pedal|foot"),
    "crash": dict(inc=r"crash", avoid=r"choke"),
    "ride": dict(inc=r"ride", avoid=r"bell|crash"),
    "tom1": dict(inc=r"tom", prefer=r"\bhi\b|high|rack|tom ?1\b|small|\bht\b", avoid=r"floor|low|\bmid\b|\bft\b"),
    "tom2": dict(inc=r"tom", prefer=r"\bmid\b|tom ?2\b|med|\bmt\b", avoid=r"floor|\bhi\b|high|low|\bft\b"),
    "tom3": dict(inc=r"tom", prefer=r"floor|low|tom ?3\b|\bft\b|ftom", avoid=r"\bhi\b|high|\bmid\b|rack"),
}
AUDIO_EXT = (".wav", ".flac", ".ogg", ".aif", ".aiff", ".mp3")


def pick_samples(folder):
    """Return {slot: path} chosen by file name, best match first."""
    files = [p for p in Path(folder).rglob("*") if p.suffix.lower() in AUDIO_EXT]
    out = {}
    for slot, r in RULES.items():
        best, best_score = None, -1e9
        for p in files:
            name = re.sub(r"[_\-.]+", " ", str(p.relative_to(folder)).lower())
            if not re.search(r["inc"], name):
                continue
            if "need" in r and not re.search(r["need"], name):
                continue
            score = 0
            if "prefer" in r and re.search(r["prefer"], name):
                score += 5
            if "avoid" in r and re.search(r["avoid"], name):
                score -= 8
            score -= len(name) / 200  # shorter, plainer names first
            if re.search(r"\b(1|01|a)\b", name):
                score += 0.5
            if score > best_score:
                best, best_score = p, score
        if best is not None:
            out[slot] = str(best)
    return out


# ---------------------------------------------------------------- sounds
def load_sample(path, sr):
    data, file_sr = sf.read(path, dtype="float32", always_2d=True)
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    data = data[:, :2]
    if file_sr != sr:  # linear resample: fine for one-shots
        n = int(round(len(data) * sr / file_sr))
        x_old = np.linspace(0, 1, len(data), endpoint=False)
        x_new = np.linspace(0, 1, n, endpoint=False)
        data = np.stack([np.interp(x_new, x_old, data[:, c]) for c in range(2)], axis=1).astype(np.float32)
    # trim leading silence so the hit starts on the first sample
    loud = np.nonzero(np.abs(data).max(axis=1) > 0.003)[0]
    if len(loud):
        data = data[max(0, loud[0] - 8):]
    peak = float(np.abs(data).max()) or 1.0
    return np.ascontiguousarray(data / max(peak, 0.25) * 0.9)


def synth_kit(sr):
    """Built-in sounds so the Companion works before any sample folder is chosen."""
    rng = np.random.default_rng(7)

    def env(n, decay):
        return np.exp(-np.arange(n) / (sr * decay)).astype(np.float32)

    def sweep(f0, f1, dur, decay):
        n = int(sr * dur)
        t = np.arange(n) / sr
        f = f1 + (f0 - f1) * np.exp(-t * 30)
        return (np.sin(2 * np.pi * np.cumsum(f) / sr) * env(n, decay)).astype(np.float32)

    def noise(dur, decay, hp=True):
        n = int(sr * dur)
        x = rng.standard_normal(n).astype(np.float32)
        if hp:
            x = np.diff(x, prepend=0) * 0.5
        return x * env(n, decay)

    def st(x):
        x = x / (np.abs(x).max() or 1) * 0.9
        return np.ascontiguousarray(np.stack([x, x], axis=1).astype(np.float32))

    snare = noise(0.25, 0.06, hp=False) * 0.7
    snare[: int(sr * 0.25)] += sweep(260, 180, 0.25, 0.04) * 0.6
    ride = noise(1.2, 0.35) * 0.5
    ride += np.sin(2 * np.pi * 3400 * np.arange(len(ride)) / sr).astype(np.float32) * env(len(ride), 0.3) * 0.2
    return {
        "kick": st(sweep(140, 48, 0.45, 0.12)),
        "snare": st(snare),
        "hh": st(noise(0.08, 0.02)),
        "hhOpen": st(noise(0.6, 0.18)),
        "hhPedal": st(noise(0.06, 0.012) * 0.6),
        "crash": st(noise(1.8, 0.5)),
        "ride": st(ride),
        "tom1": st(sweep(260, 190, 0.5, 0.15)),
        "tom2": st(sweep(200, 140, 0.55, 0.17)),
        "tom3": st(sweep(140, 90, 0.7, 0.2)),
    }


# ---------------------------------------------------------------- audio engine
class Voice:
    __slots__ = ("slot", "data", "pos", "gain", "fade")

    def __init__(self, slot, data, gain):
        self.slot, self.data, self.pos, self.gain, self.fade = slot, data, 0, gain, -1


class Engine:
    """Mixes triggered samples in the audio callback. trigger() may be called from any thread."""

    MAX_VOICES = 48
    CHOKE_FRAMES = 256

    def __init__(self):
        self.sr = SR_DEFAULT
        self.samples = {}
        self.voices = []
        self.pending = []
        self.lock = threading.Lock()
        self.volume = 0.8
        self.pad_volume = {s: 1.0 for s in SLOTS}
        self.stream = None
        self.info = "Audio not started"

    def trigger(self, slot, vel):
        data = self.samples.get(slot)
        if data is None:
            return
        g = (max(1, min(127, vel)) / 127.0) ** 1.5 * self.volume * self.pad_volume.get(slot, 1.0)
        with self.lock:
            self.pending.append(Voice(slot, data, g))

    def render(self, frames):
        out = np.zeros((frames, 2), dtype=np.float32)
        with self.lock:
            new, self.pending = self.pending, []
        for v in new:
            if v.slot in ("hh", "hhPedal"):  # closing the hat chokes an open hat that's still ringing
                for o in self.voices:
                    if o.slot == "hhOpen" and o.fade < 0:
                        o.fade = self.CHOKE_FRAMES
            self.voices.append(v)
        if len(self.voices) > self.MAX_VOICES:
            self.voices = self.voices[-self.MAX_VOICES:]
        keep = []
        for v in self.voices:
            n = min(frames, len(v.data) - v.pos)
            if v.fade >= 0:
                n = min(n, v.fade)
            if n > 0:
                chunk = v.data[v.pos:v.pos + n] * v.gain
                if v.fade >= 0:
                    ramp = (np.arange(v.fade, v.fade - n, -1, dtype=np.float32) / self.CHOKE_FRAMES)[:, None]
                    chunk = chunk * ramp
                    v.fade -= n
                out[:n] += chunk
                v.pos += n
            if v.pos < len(v.data) and v.fade != 0:
                keep.append(v)
        self.voices = keep
        np.tanh(out, out=out)  # soft limit instead of hard clipping when many hits overlap
        return out

    def _callback(self, outdata, frames, time_info, status):
        outdata[:] = self.render(frames)

    def start(self, device=None, blocksize=128, exclusive=True):
        self.stop()
        if sd is None:
            self.info = f"Audio unavailable: {SD_ERROR}"
            return False
        dev = sd.query_devices(device) if device is not None else sd.query_devices(kind="output")
        api = sd.query_hostapis(dev["hostapi"])["name"]
        sr = int(dev["default_samplerate"]) or SR_DEFAULT
        extra = None
        if "WASAPI" in api and exclusive:
            extra = sd.WasapiSettings(exclusive=True)
        last_err = None
        for rate in [sr, 48000, 44100]:
            try:
                self.stream = sd.OutputStream(device=device, samplerate=rate, blocksize=blocksize, channels=2, dtype="float32",
                                              latency="low", extra_settings=extra, callback=self._callback)
                self.stream.start()
                if rate != self.sr:
                    self.sr = rate
                    self.reload()
                lat = self.stream.latency * 1000 if self.stream.latency else blocksize / rate * 1000
                self.info = f"{api} · {dev['name']} · {rate // 1000} kHz · buffer {blocksize} · ≈{lat:.1f} ms output latency"
                return True
            except Exception as e:
                last_err = e
                self.stream = None
        self.info = f"Could not open {dev['name']} ({api}): {last_err}"
        return False

    def stop(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

    # samples ---------------------------------------------------
    def reload(self, files=None):
        if files is not None:
            self.files = files
        files = getattr(self, "files", {}) or {}
        kit = synth_kit(self.sr)
        loaded = []
        for slot, path in files.items():
            if sf is None or not path or not os.path.exists(path):
                continue
            try:
                kit[slot] = load_sample(path, self.sr)
                loaded.append(slot)
            except Exception:
                pass
        if "hhPedal" not in loaded and "hh" in loaded:  # no pedal sample: a soft closed hat
            kit["hhPedal"] = kit["hh"] * 0.5
        self.samples = kit
        return loaded


# ---------------------------------------------------------------- hits from the kit
class HitRouter:
    """Turns MIDI note-ons into sounds and forwards them to Drum Highway."""

    def __init__(self, engine, bridge):
        self.engine, self.bridge = engine, bridge
        self.notes = {k: list(v) for k, v in DEFAULT_NOTES.items()}
        self.on_log = None
        self.sound = True

    def slot_for(self, note):
        for slot, ns in self.notes.items():
            if note in ns:
                return slot
        return None

    def midi(self, msg):
        if not msg:
            return
        status = msg[0] & 0xF0
        if status == 0x90 and len(msg) >= 3 and msg[2] > 0:
            note, vel = msg[1], msg[2]
            slot = self.slot_for(note)
            if slot and self.sound:
                self.engine.trigger(slot, vel)
            self.bridge.send({"t": "hit", "note": note, "vel": vel})
            if self.on_log:
                self.on_log(note, vel, slot)
        elif status == 0xB0 and len(msg) >= 3:
            self.bridge.send({"t": "cc", "cc": msg[1], "value": msg[2]})


class MidiIn:
    def __init__(self, router):
        self.router, self.port, self.name = router, None, None

    @staticmethod
    def ports():
        if rtmidi is None:
            return []
        m = rtmidi.MidiIn()
        try:
            return m.get_ports()
        finally:
            m.delete()

    def open(self, name):
        self.close()
        if rtmidi is None or not name:
            return False
        names = self.ports()
        if name not in names:
            return False
        self.port = rtmidi.MidiIn()
        self.port.ignore_types(sysex=True, timing=True, active_sense=True)
        self.port.set_callback(lambda ev, _=None: self.router.midi(ev[0]))
        self.port.open_port(names.index(name))
        self.name = name
        return True

    def close(self):
        if self.port is not None:
            try:
                self.port.close_port()
                self.port.delete()
            except Exception:
                pass
        self.port, self.name = None, None


# ---------------------------------------------------------------- link to Drum Highway (local WebSocket)
class Bridge:
    def __init__(self, port=WS_PORT):
        self.port = port
        self.clients = set()
        self.loop = None
        self.status = "Starting…"
        self.sound_on = True
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def _run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._serve())
        except OSError as e:
            self.status = f"Port {self.port} is busy (is the Companion already running?): {e}"

    async def _serve(self):
        async with websockets.serve(self._client, "127.0.0.1", self.port, max_size=2 ** 16):
            self.status = f"Waiting for Drum Highway (port {self.port})"
            await asyncio.Future()

    async def _client(self, ws):
        self.clients.add(ws)
        self._update()
        try:
            await ws.send(json.dumps({"t": "hello", "app": APP_NAME, "version": VERSION, "sound": self.sound_on}))
            async for _ in ws:  # the page doesn't need to send anything; keep the connection open
                pass
        except Exception:
            pass
        finally:
            self.clients.discard(ws)
            self._update()

    def _update(self):
        n = len(self.clients)
        self.status = f"Drum Highway connected ({n})" if n else f"Waiting for Drum Highway (port {self.port})"

    def send(self, obj):
        if not self.clients or self.loop is None:
            return
        msg = json.dumps(obj)
        self.loop.call_soon_threadsafe(self._broadcast, msg)

    def _broadcast(self, msg):
        for ws in list(self.clients):
            asyncio.ensure_future(self._safe_send(ws, msg))

    @staticmethod
    async def _safe_send(ws, msg):
        try:
            await ws.send(msg)
        except Exception:
            pass

    def set_sound(self, on):
        self.sound_on = on
        self.send({"t": "hello", "app": APP_NAME, "version": VERSION, "sound": on})


# ---------------------------------------------------------------- settings
def config_path():
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    p = Path(base) / "DrumHighwayCompanion"
    p.mkdir(parents=True, exist_ok=True)
    return p / "config.json"


def load_config():
    try:
        return json.loads(config_path().read_text("utf-8"))
    except Exception:
        return {}


def save_config(cfg):
    try:
        config_path().write_text(json.dumps(cfg, indent=2), "utf-8")
    except Exception:
        pass


def output_devices():
    """[(label, index)] best low-latency options first: ASIO, then WASAPI, then the rest."""
    if sd is None:
        return []
    apis = sd.query_hostapis()
    rank = lambda name: 0 if "ASIO" in name else 1 if "WASAPI" in name else 3 if "MME" in name else 2
    out = []
    for i, d in enumerate(sd.query_devices()):
        if d["max_output_channels"] >= 2 or (d["max_output_channels"] >= 1 and "ASIO" in apis[d["hostapi"]]["name"]):
            api = apis[d["hostapi"]]["name"].replace("Windows ", "")
            out.append((rank(api), f"{api}: {d['name']}", i))
    out.sort()
    return [(label, i) for _, label, i in out]


# ---------------------------------------------------------------- window
def run_gui():
    import tkinter as tk
    from tkinter import filedialog, ttk

    cfg = load_config()
    engine, bridge = Engine(), Bridge()
    router = HitRouter(engine, bridge)
    router.notes.update({k: v for k, v in cfg.get("notes", {}).items() if k in SLOTS})
    midi_in = MidiIn(router)
    engine.volume = cfg.get("volume", 0.8)
    engine.reload(cfg.get("files", {}))
    bridge.start()

    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("560x520")
    root.minsize(520, 480)
    BG, PANEL, INK, MUTED, ACCENT = "#101217", "#171a20", "#eceef2", "#8c93a3", "#7c8cff"
    root.configure(bg=BG)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=BG, foreground=INK, fieldbackground=PANEL, font=("Segoe UI", 10))
    style.configure("TLabel", background=BG, foreground=INK)
    style.configure("Muted.TLabel", foreground=MUTED, font=("Segoe UI", 9))
    style.configure("Head.TLabel", font=("Segoe UI Semibold", 15))
    style.configure("Sec.TLabel", foreground=MUTED, font=("Segoe UI Semibold", 8))
    style.configure("TButton", background=PANEL, foreground=INK, borderwidth=1, padding=6)
    style.map("TButton", background=[("active", "#232833")])
    style.configure("Accent.TButton", background=ACCENT, foreground="#0b0d1a")
    style.map("Accent.TButton", background=[("active", "#a6b1ff")])
    style.configure("TCheckbutton", background=BG, foreground=INK)
    style.configure("TCombobox", fieldbackground=PANEL, background=PANEL, foreground=INK, arrowcolor=INK)
    root.option_add("*TCombobox*Listbox.background", PANEL)
    root.option_add("*TCombobox*Listbox.foreground", INK)

    frm = ttk.Frame(root, padding=18, style="TFrame")
    style.configure("TFrame", background=BG)
    frm.pack(fill="both", expand=True)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Drum Highway Companion", style="Head.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
    ttk.Label(frm, text="Plays your drum sounds with low latency and sends your hits to Drum Highway.",
              style="Muted.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

    def section(r, text):
        ttk.Label(frm, text=text.upper(), style="Sec.TLabel").grid(row=r, column=0, columnspan=3, sticky="w", pady=(10, 4))

    # --- kit
    section(2, "Your kit")
    ttk.Label(frm, text="MIDI input").grid(row=3, column=0, sticky="w")
    midi_var = tk.StringVar(value=cfg.get("midi", ""))
    midi_box = ttk.Combobox(frm, textvariable=midi_var, state="readonly")
    midi_box.grid(row=3, column=1, sticky="ew", padx=8)

    def refresh_midi():
        names = MidiIn.ports()
        midi_box["values"] = names
        if midi_var.get() not in names:
            guess = next((n for n in names if re.search(r"tdx|aroma|drum|kit|usb", n, re.I)), names[0] if names else "")
            midi_var.set(guess)
        open_midi()

    def open_midi(*_):
        ok = midi_in.open(midi_var.get())
        cfg["midi"] = midi_var.get(); save_config(cfg)
        midi_status.set(f"Listening to {midi_var.get()}" if ok else ("No MIDI input found. Plug in your kit and press Refresh." if not midi_box["values"] else "Pick your kit"))

    midi_box.bind("<<ComboboxSelected>>", open_midi)
    ttk.Button(frm, text="Refresh", command=refresh_midi).grid(row=3, column=2)
    midi_status = tk.StringVar()
    ttk.Label(frm, textvariable=midi_status, style="Muted.TLabel").grid(row=4, column=1, columnspan=2, sticky="w", padx=8)

    # --- audio
    section(5, "Sound output")
    ttk.Label(frm, text="Output").grid(row=6, column=0, sticky="w")
    devs = output_devices()
    dev_var = tk.StringVar(value=cfg.get("device", devs[0][0] if devs else ""))
    dev_box = ttk.Combobox(frm, textvariable=dev_var, values=[d[0] for d in devs], state="readonly")
    dev_box.grid(row=6, column=1, columnspan=2, sticky="ew", padx=(8, 0))
    ttk.Label(frm, text="Buffer").grid(row=7, column=0, sticky="w", pady=(6, 0))
    buf_var = tk.StringVar(value=str(cfg.get("buffer", 128)))
    ttk.Combobox(frm, textvariable=buf_var, values=["32", "64", "128", "256", "512"], state="readonly", width=8).grid(row=7, column=1, sticky="w", padx=8, pady=(6, 0))
    excl_var = tk.BooleanVar(value=cfg.get("exclusive", True))
    ttk.Checkbutton(frm, text="WASAPI exclusive mode", variable=excl_var).grid(row=7, column=1, sticky="e", pady=(6, 0))
    audio_status = tk.StringVar(value=engine.info)
    ttk.Label(frm, textvariable=audio_status, style="Muted.TLabel", wraplength=500).grid(row=8, column=0, columnspan=3, sticky="w", pady=(4, 0))

    def start_audio(*_):
        label = dev_var.get()
        idx = next((i for l, i in devs if l == label), None)
        engine.start(idx, int(buf_var.get()), excl_var.get())
        audio_status.set(engine.info + ("" if engine.stream else "  Try a bigger buffer or another output."))
        cfg.update(device=label, buffer=int(buf_var.get()), exclusive=excl_var.get()); save_config(cfg)

    ttk.Button(frm, text="Apply", command=start_audio).grid(row=9, column=2, sticky="e", pady=(6, 0))
    ttk.Label(frm, text="Lowest delay: pick an ASIO output (install free ASIO4ALL for built-in sound), buffer 64–128.",
              style="Muted.TLabel", wraplength=380).grid(row=9, column=0, columnspan=2, sticky="w", pady=(6, 0))

    # --- sounds
    section(10, "Drum sounds")
    snd_status = tk.StringVar()

    def show_kit():
        files = cfg.get("files", {})
        if files:
            names = ", ".join(SLOT_NAMES[s] for s in SLOTS if s in files)
            missing = [SLOT_NAMES[s] for s in SLOTS if s not in files and s != "hhPedal"]
            snd_status.set(f"From {Path(cfg.get('folder', '')).name}: {names}." + (f" Built-in sound for {', '.join(missing)}." if missing else ""))
        else:
            snd_status.set("Using built-in sounds. Choose your sample folder (e.g. Real Drums Vol. 1).")

    def choose_folder():
        d = filedialog.askdirectory(title="Choose your drum sample folder")
        if not d:
            return
        files = pick_samples(d)
        cfg.update(folder=d, files=files); save_config(cfg)
        engine.reload(files)
        show_kit()

    ttk.Button(frm, text="Choose sample folder…", command=choose_folder).grid(row=11, column=0, columnspan=2, sticky="w")
    ttk.Label(frm, textvariable=snd_status, style="Muted.TLabel", wraplength=500).grid(row=12, column=0, columnspan=3, sticky="w", pady=(4, 0))
    ttk.Label(frm, text="Volume").grid(row=13, column=0, sticky="w", pady=(6, 0))
    vol = tk.DoubleVar(value=engine.volume * 100)

    def set_vol(*_):
        engine.volume = vol.get() / 100
        cfg["volume"] = engine.volume; save_config(cfg)

    ttk.Scale(frm, from_=0, to=150, variable=vol, command=set_vol).grid(row=13, column=1, columnspan=2, sticky="ew", padx=8, pady=(6, 0))
    sound_var = tk.BooleanVar(value=cfg.get("sound", True))

    def set_sound():
        router.sound = sound_var.get(); bridge.set_sound(router.sound)
        cfg["sound"] = router.sound; save_config(cfg)

    ttk.Checkbutton(frm, text="Play drum sounds (turn off if your module makes the sound)", variable=sound_var,
                    command=set_sound).grid(row=14, column=0, columnspan=3, sticky="w", pady=(6, 0))
    router.sound = sound_var.get(); bridge.sound_on = router.sound

    # --- link
    section(15, "Drum Highway")
    link_status = tk.StringVar(value=bridge.status)
    ttk.Label(frm, textvariable=link_status).grid(row=16, column=0, columnspan=3, sticky="w")
    ttk.Label(frm, text="In Drum Highway, open Kit setup and switch on “Use Drum Highway Companion”.",
              style="Muted.TLabel").grid(row=17, column=0, columnspan=3, sticky="w")
    last_hit = tk.StringVar(value="Hit a pad to test.")
    ttk.Label(frm, textvariable=last_hit, style="Muted.TLabel").grid(row=18, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def on_log(note, vel, slot):
        root.after(0, last_hit.set, f"Last hit: note {note}, velocity {vel} → {SLOT_NAMES.get(slot, 'not mapped')}")

    router.on_log = on_log

    def tick():
        link_status.set(bridge.status)
        root.after(500, tick)

    def on_close():
        midi_in.close(); engine.stop(); root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    show_kit()
    refresh_midi()
    start_audio()
    tick()
    root.mainloop()


if __name__ == "__main__":
    run_gui()

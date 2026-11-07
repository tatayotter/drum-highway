# Drum Highway

A note-highway practice app for electronic drum kits. Play along with MIDI songs and a built-in drill library, see the notation as you play, and get scored on your timing.

**Open it:** https://tatayotter.github.io/drum-highway/ in Chrome or Edge, then click the install icon in the address bar to get it as its own app (works offline after the first visit).

## Setup

1. Connect your drum module to the computer by USB, and press **Connect** in the app.
2. For zero-latency drum sounds, plug headphones into your drum module and feed the computer's audio into the module's AUX IN. Then turn off **Play sounds when I hit** (Sound tab) and run **Calibrate latency** (Kit setup tab).
3. No kit handy? The keys shown under each lane play that drum.

Everything you load (MIDI library, drum samples, backing audio, settings) stays in your own browser.

## Drum Highway Companion (optional, Windows)

If your pads don't make their own sound, or you want to use your own drum samples, the Companion plays them with very low latency (ASIO or WASAPI exclusive) and passes your hits to Drum Highway.

1. Download [DrumHighwayCompanion.exe](https://github.com/tatayotter/drum-highway/releases/download/companion/DrumHighwayCompanion.exe) and run it. Windows may warn that it's from an unknown publisher: click **More info → Run anyway**.
2. Pick your kit and a sound output. For the lowest delay, install the free [ASIO4ALL](https://asio4all.org/) driver and pick the ASIO output, buffer 64–128.
3. Choose your sample folder (or keep the built-in sounds).
4. In Drum Highway, open **Kit setup** and switch on **Use Drum Highway Companion**.

Source: [`companion/drum_companion.py`](companion/drum_companion.py).

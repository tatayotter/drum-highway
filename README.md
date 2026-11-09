# Drum Highway

A note-highway practice app for electronic drum kits. Play along with MIDI songs and a built-in drill library, see the notation as you play, and get scored on your timing.

**Open it:** https://tatayotter.github.io/drum-highway/ in Chrome or Edge, then click the install icon in the address bar to get it as its own app (works offline after the first visit).

## Setup

1. Connect your drum module to the computer by USB, and press **Connect** in the app.
2. For zero-latency drum sounds, plug headphones into your drum module and feed the computer's audio into the module's AUX IN. Then turn off **Play sounds when I hit** (Sound tab) and run **Calibrate latency** (Kit setup tab).
3. No kit handy? The keys shown under each lane play that drum.

Everything you load (MIDI library, drum samples, backing audio, settings) stays in your own browser.

## Practice tools (Practice tab)

- **Wait mode:** the notes stop at the hit line until you hit the right drum. Use it to learn a new part, then turn it off to play it in time.
- **Run report:** after each run you see whether you rush or drag, how steady you are, which drum needs work, the hardest bars of a song (with a button to loop them slowly), and how well you played accents and ghost notes.
- **Dynamics:** accents must be hit hard and ghost notes softly. You can set the velocity limits for your kit. On the keyboard, hold Shift to play an accent.

## Songs that come with the app

**Drum Highway originals:** 12 songs written for this app, built in, from Beginner to Advanced (rock, disco, ballad, funk, blues shuffle, tribal toms, punk, linear funk, 16th-note kick). Each one has a bass, chord and melody backing part and teaches one skill. Pick them at the top of the Song list. They are free to share with the app.

## Clone Hero / YARG / Rock Band charts

Press **Load charts** and choose a song folder (or a folder full of song folders). Drum Highway reads `notes.mid` or `notes.chart`, `song.ini` and the audio stems. It plays every stem except the drums, so you hear the real recording without the original drummer. Pick Easy, Medium, Hard or Expert in the **Difficulty** box. Charts with only one `song.ogg` still work, but the original drums stay in the audio. Packed `.sng` files need to be unpacked first.

## Drum Highway Companion (optional, Windows)

If your pads don't make their own sound, or you want to use your own drum samples, the Companion plays them with very low latency (ASIO or WASAPI exclusive) and passes your hits to Drum Highway.

1. Download [DrumHighwayCompanion.exe](https://github.com/tatayotter/drum-highway/releases/download/companion/DrumHighwayCompanion.exe) and run it. Windows may warn that it's from an unknown publisher: click **More info → Run anyway**.
2. Pick your kit and a sound output. For the lowest delay, install the free [ASIO4ALL](https://asio4all.org/) driver and pick the ASIO output, buffer 64–128.
3. Choose your sample folder (or keep the built-in sounds).
4. In Drum Highway, open **Kit setup** and switch on **Use Drum Highway Companion**.

Source: [`companion/drum_companion.py`](companion/drum_companion.py).

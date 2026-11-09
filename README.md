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
- **Progress:** the button next to Start shows your practice streak and today's minutes against your daily goal. Click it for minutes per day, accuracy over time for each song or drill, and your recent runs.
- **Sheet music:** "Load one song" also opens MusicXML (`.musicxml`, `.mxl`, e.g. exported from MuseScore). The drum part becomes the highway and the other parts play as backing. Repeats and 1st/2nd endings are followed.
- **Full-page notation:** turn on "Full-page sheet music" (or press N) to read the whole song as sheet music instead of the highway. When stopped, click a bar to start there.
- **Hi-hat:** open and closed hi-hat are scored (Q on the keyboard plays an open hi-hat). Kit setup has an optional hi-hat pedal lane (key V) for the foot "chick" notes.
- **Dynamics:** accents must be hit hard and ghost notes softly. You can set the velocity limits for your kit. On the keyboard, hold Shift to play an accent.

## Course

Graded lessons from Debut to Grade 8, about 175 lessons. Along with rudiments, grooves, fills, toms, timing and triplets, the course covers:

- Flams and drags, plus longer rolls.
- 3/4, 6/8, 5/4, 7/8, 9/8 and 11/8.
- Polyrhythms and groupings: 3 over 4, 3 over 2, groups of 5 and 7.
- Jazz, Latin (samba, songo, Mozambique, clave, cascara), New Orleans, gospel, hip-hop and drum & bass.
- Hi-hat foot lessons. Turn on the hi-hat pedal lane in Kit setup to get the foot scored.

Everything works with a single bass drum pedal. There are no double-pedal exercises.

**Lessons.** Each lesson is split into steps: hands only, feet only, together at a slower tempo, then full tempo. Lessons that use only one part of the body step up the tempo instead. Every lesson also has:

- **Watch first:** the app plays it for you.
- **Learn it:** wait mode.
- **Play it.**
- A tip written for that lesson.

**Backing music.** Lessons and drills play over backing music: bass and keys in a style that fits the groove (rock, funk, shuffle, jazz, Latin and others). You can turn it off. Timing drills with a gap in the click have no music, so you have to keep time on your own.

**Stars.** Lessons earn up to three stars:

- ★ pass at a slower practice tempo
- ★★ pass at full tempo
- ★★★ 95% at full tempo

**Grade songs.** The 15 original songs are the grade pieces.

**Exams.** Each grade's exam has five parts:

- Three set pieces.
- A sight-reading piece that is new on every attempt and is shown only as sheet music.
- An improvised fill: you play your own fill in every fourth bar and land on the crash.

**Today's practice** suggests a warm-up, your next lesson and a review each day.

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

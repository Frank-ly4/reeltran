Must download and add 'ffmpeg' and 'ffprobe' for this to work.  Also, input your own API in your environment variables for ChatGPT to get translations.

The app reads it from your environment using:
os.getenv("OPENAI_API_KEY")

To set, run the following in the terminal:
Mac/Linux: export OPENAI_API_KEY="sk-xxxx"
Windows: setx OPENAI_API_KEY "sk-xxxx"

# Reel Translator

A desktop app for downloading short-form video audio (such as Instagram Reels), transcribing the spoken content, and producing a nuanced English translation.

The app is built with:

- **Tkinter** for the desktop UI
- **yt-dlp** for audio extraction
- **OpenAI audio transcription** for speech-to-text
- **GPT-4o** for nuanced translation into English

---

## What the app does

Given a Reel URL, the app will:

1. Download the audio
2. Transcribe the spoken source language
3. Translate the result into natural English
4. Display the output in a readable line-by-line format
5. Save the output to a text file, including the original URL

---

## Current behavior

### Input
- Paste a Reel URL
- Choose a source language from the dropdown, or leave it on **Autodetect**

### Output
The app currently outputs each transcription segment like this:

```text
Original: すいません今食べてるフランクフルトより僕のフランクフルトの方が小さかった場合そちらのフランクルトご馳走しますよ
EN: Excuse me, if the frankfurter I'm eating now is smaller than yours, I'll treat you to this frankfurter.

It also includes a header with:

detected or selected language

date/time

original URL

Example: TRANSCRIPTION (ja) | 2026-03-14 15:22 | URL: https://...

Why this app changed over time

This project started as a local Whisper-based transcription tool focused on Thai and then evolved into a more general, higher-quality hosted transcription app.

The changes below document what was updated and why.

Update log / project history
1. Original version: local Whisper + Thai-specific workflow
What it did

The app originally:

used local Whisper

loaded the turbo model

transcribed audio locally

passed the transcript to GPT for English translation

included a Thai-specific prompt

hardcoded the transcription language as Thai

Why this became a limitation

That design worked for Thai-focused use, but it had several problems:

it was locked to Thai

it could not cleanly support other languages

it used a language-specific prompt that would bias non-Thai clips

it included a hard-coded OpenAI API key, which is unsafe

Why we moved away from this

The goal shifted from “Thai transcription helper” to a more flexible multilingual reel translator with better accuracy and a cleaner setup.

2. Added source-language dropdown with Autodetect
What changed

A Source language dropdown was added to the UI with:

Autodetect

Spanish

French

Japanese

Korean

Hindi

Mandarin Chinese

Thai

Cambodian / Khmer

Italian

German

Vietnamese

Arabic

Russian

Why we did this

This gives the user a simple choice:

use Autodetect if the source language is unknown

choose a language manually when known

This improves usability and allows the transcription system to use a language hint when available.

Why this matters

Language hints can improve:

transcription speed

recognition stability

accuracy in noisy or short clips

At the same time, Autodetect keeps the app flexible for casual use.

3. Removed the language-specific prompt
What changed

The old transcription flow used a Thai-specific initial prompt. That was removed.

Why we did this

A hardcoded Thai-oriented prompt makes sense only for Thai audio. Once the app became multilingual, that prompt became a liability because it could:

bias recognition toward Thai

reduce flexibility

make the code harder to reason about

Result

The app now uses a neutral multilingual transcription path.

4. Kept GPT-4o for translation
What changed

The app continued using GPT-4o for translation.

Why we did this

The translation goal was not just literal conversion, but nuanced English translation that preserves:

tone

slang

implied meaning

conversational feel

GPT-4o was kept because:

translation quality was already good

the user preferred to keep using it

it fit the “online anyway” workflow

the translation step was already fast enough

Design choice

The translation model name was placed in a constant so it can be changed later if desired.

5. Considered translation parallelization, but deliberately did not add it
What we discussed

We considered parallelizing translation for faster performance.

Why we did not implement it

At this stage, the app is mostly used for short reels, around one minute long.

For short clips:

one translation request is simpler

context is preserved better

batching segments in one request is already fast

extra complexity is not worth it yet

Conclusion

We intentionally kept the translation flow simple.

If longer clips become common later, adaptive parallelization can be added.

6. Moved from local Whisper to hosted OpenAI transcription
What changed

The app no longer uses local Whisper as its primary transcription engine.

Instead, transcription moved to OpenAI-hosted transcription.

Why we did this

The user explicitly preferred:

best transcription quality

online operation

acceptable API cost

Hosted transcription offered:

improved accuracy

simpler deployment

no local Whisper dependency

no local model loading delay

consistent behavior across devices

Why this was a good fit

The app is used while online, so the local/offline advantage of Whisper was less important than transcription quality.

7. Removed local Whisper dependency
What changed

The code was simplified so that local Whisper was removed from the current flow.

Why we did this

Once the decision was made to use hosted transcription, keeping Whisper around as a second main path would have added:

more code branches

more maintenance

more confusion

more dependencies

Since the goal was “best transcription first,” the hosted path became the main implementation.

Note

A fallback to local Whisper could still be added later if desired, but it was intentionally not included in the current version.

8. Secured the API key using environment variables
What changed

The OpenAI API key was removed from source code and replaced with: os.getenv("OPENAI_API_KEY")

Why we did this

Hard-coding API keys in source files is unsafe.

Using an environment variable:

keeps credentials out of the codebase

reduces accidental leaks

makes the app safer to share or version-control

follows standard deployment practice

Result

The app now expects the API key to be provided through the environment.

9. Simplified requirements and dependency handling
What changed

The dependency list was cleaned up to match actual imports.

The current requirements.txt is intentionally minimal.

Why we did this

Earlier versions included packages that were no longer central to the final architecture.

Keeping requirements lean:

makes installation easier

avoids confusion

reflects the actual codebase more accurately

10. First hosted transcription version used full-text output only
What changed

The first hosted transcription implementation used a simple full transcript output.

That meant the app produced:

one block of source text

one block of English translation

Why that happened

That was the simplest hosted implementation path and matched the plain text output mode.

Why we changed it again

Although the transcription quality was strong, the output became harder to read because the user preferred line-by-line structure.

11. Restored line-by-line output using segmented hosted transcription
What changed

The transcription flow was updated again to use a segmented hosted transcription format so the app could recover per-segment structure.

Instead of one long block, the app now:

receives segmented transcription data

translates segment-by-segment in a single batched GPT request

renders each original segment with its English counterpart

Why we did this

This restored the readability of the old Whisper-style output while keeping the better hosted transcription quality.

Why this matters

The line-by-line format is much easier to:

scan quickly

compare original and translation

reuse for notes, captions, and study

12. Used segmented hosted transcription, but then removed timestamps from the final display
What changed

A segmented transcription format was used internally, which made time-based segments available again.

However, the timestamps were then removed from the visible output.

Why we did this

The user liked line-by-line structure but did not want timestamps cluttering the output.

So the app now uses segmentation internally for formatting, but the final output shows only:

Original

EN

Result

The output is cleaner and easier to read, while still preserving the benefits of segmentation.

13. Renamed SRC to Original
What changed

The output label was changed from: SRC: to Original:

Why we did this

Original is clearer and more user-friendly than SRC.

It makes the file easier to read for:

non-technical users

future review

saved transcripts

14. Added the original URL to saved output
What changed

The app now includes the original reel URL in the output header.

Why we did this

Once transcripts started being saved, it became important to preserve the source link so the user can later:

revisit the original reel

verify context

compare translation against the original media

organize saved files more easily

Result

Saved transcripts are now much more useful as standalone records.

15. Evaluated diarization, but intentionally did not add it
What we discussed

We considered adding speaker diarization, such as:
Speaker 1:
Speaker 2:
Speaker 1:

Why we did not implement it

For this app’s current use case, diarization was not necessary enough to justify the extra complexity.

Reasons:

diarization is not perfectly reliable for social/reel audio

reels often include noisy or edited audio

the app’s current focus is transcription + translation quality

adding diarization would introduce more complexity and more failure points

Conclusion

Diarization was intentionally deferred unless later testing shows a strong need for it.

Current architecture
Transcription

Hosted OpenAI audio transcription

segmented output used internally for line-by-line formatting

optional language hint from dropdown

Autodetect supported

Translation

GPT-4o

batched line-by-line translation

tuned for nuanced English output

UI

Tkinter desktop app

Reel URL field

language dropdown

process button

status label

progress bar

scrollable output

save button

Why the current design is a good balance

The current app aims to optimize for:

high transcription quality

good translation nuance

simple UI

fast short-form video workflow

clean saved output

low code complexity

This design intentionally avoids overengineering.

We explicitly chose not to add:

diarization

local Whisper fallback

adaptive parallel translation

subtitle export

speaker labeling

Those may become useful later, but they were left out to keep the app focused and reliable.

Setup
Requirements

Python 3.10+

FFmpeg available in the app directory or system path

OpenAI API key in an environment variable

Install dependencies

pip install -r requirements.txt

Set your API key
macOS / Linux
export OPENAI_API_KEY="sk-..."

Windows PowerShell
setx OPENAI_API_KEY "sk-..."

After setting the variable, open a new shell before launching the app if needed.

Running the app: python app.py

How to use

Launch the app

Paste a Reel URL

Choose a source language, or leave it on Autodetect

Click Process Reel

Wait for:

audio download

transcription

translation

Review the output

Save it to a text file if desired

Current output format

The current output format is:
TRANSCRIPTION (language) | YYYY-MM-DD HH:MM | URL: https://...

Original: ...
EN: ...

Original: ...
EN: ...

This format was chosen because it is:

easy to read

easy to compare

easy to save

easy to copy into notes or documents

Known limitations
1. No visible timestamps

The app uses segmentation internally, but timestamps are not shown in the output.

This was intentional for readability.

2. No speaker labels

The app does not attempt to identify or label speakers.

3. Optimized for short-form content

The current design is best suited for short reels and clips, not long-form transcript management.

4. Translation is English-only

The app currently translates into English.

Future ideas

These were discussed but intentionally postponed:

Optional diarization

Possible if speaker-separated output becomes important.

Subtitle export

Could add:

.srt

.vtt

Parallel translation for longer clips

Useful only if long clips become common.

Multiple output modes

Possible future options:

full transcript block

line-by-line

subtitle style

bilingual export

Hosted/local backend toggle

Could be added later if offline support becomes important again.

Summary of the most important changes

In plain English, the app evolved like this:

Started as a local Whisper-based Thai-oriented tool

Became multilingual with a language dropdown

Removed Thai-specific behavior

Secured the API key

Switched to hosted OpenAI transcription for better quality

Restored line-by-line formatting using segmented transcription

Removed timestamps from visible output for cleaner readability

Renamed SRC to Original

Added the original URL to saved files

That sequence reflects the guiding goal of the project:

maximize transcription quality and readability without making the app unnecessarily complicated

License / notes

This README documents the app’s behavior and design decisions based on the current project direction and the changes made during development.

If the architecture changes later, this file should be updated so the design history remains clear.
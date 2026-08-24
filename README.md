# Rise Course Text Extractor

A local, lightweight Python utility that extracts learner-facing text from an unzipped Articulate Rise course export and saves it as clean Markdown for quality assurance, editing, search, documentation, and AI-assisted review.

The script is designed for learning designers, developers, editors, accessibility reviewers, and anyone who needs a readable text version of a Rise course without manually copying content block by block.

> **Important:** This is a community-built, unofficial utility. It is not affiliated with, endorsed by, or supported by Articulate. Rise and Storyline are trademarks of their respective owner.

## Why use it?

Rise courses can contain text in many places, including:

- standard text and heading blocks
- accordions, tabs, flashcards, processes, and knowledge checks
- Custom Blocks
- inline HTML Code Blocks
- ZIP-uploaded Code Block projects
- embedded Storyline interactions
- captions and transcript files
- localized or structured text fields

A normal PDF export may not expose every screen, layer, state, or custom interaction cleanly. This script reads the published course package directly and creates a more complete, scan-friendly text file.

The resulting Markdown can be used to:

- check spelling, grammar, terminology, and consistency
- compare course content against a QA checklist or style guide
- create an AI-ready text version of a course
- reduce repeated copying, pasting, PDF conversion, and manual preprocessing
- support documentation, search, translation review, and content inventories

Because the extraction runs locally and does not require AI, it may also reduce unnecessary repeated AI processing. Any environmental benefit will vary by workflow and has not been quantified.

## What it produces

The script creates two files:

```text
out/
├── course.md
└── extraction-report.json
```

### `course.md`

A clean, structured Markdown version of the text found in the course.

### `extraction-report.json`

A technical report showing what the script found, extracted, skipped, or could not confidently process. Review this file before assuming the Markdown is complete.

## Privacy and local processing

The script runs locally on your computer using Python's standard library.

- It does not upload your course.
- It does not call an AI model.
- It does not call an external API.
- It does not require an internet connection after Python has been installed.
- It does not modify the original Rise export.

Your extracted `course.md` may contain the full learner-facing content of your course. Treat the output with the same care as the original course, especially if the course contains confidential, licensed, personal, or unpublished material.

## What it can extract

The script attempts to recover text from:

- course and lesson titles
- native Rise text and interaction blocks
- rich-text and HTML fields
- localization references found in the published package
- Rise Custom Blocks
- inline Code Blocks
- ZIP-uploaded Code Block projects with an HTML entry point
- embedded Storyline slide data
- image alt text when present in supported structures
- WebVTT caption and transcript files

## Known limitations

No automated extractor can guarantee perfect coverage across every Rise or Storyline publishing variation.

The script may not recover:

- text baked into images
- spoken audio without captions or transcripts
- video-only text
- text created entirely at runtime from an external service
- canvas-rendered text
- heavily minified or obfuscated JavaScript
- unsupported future changes to Rise or Storyline export structures
- text that is intentionally hidden from all learners

Custom Code Blocks are especially variable. The script uses filtering to distinguish authored learner text from CSS classes, JavaScript events, dimensions, selectors, and other implementation artifacts. Review the output and extraction report for unusual omissions or stray code strings.

## Requirements

- Windows 10 or later, or a supported version of macOS
- Python 3
- An unzipped Articulate Rise **Web** export

No third-party Python packages are required.

## Download the project

### Option 1: Download from GitHub

1. Open this repository.
2. Select **Code**.
3. Select **Download ZIP**.
4. Unzip the downloaded repository.

### Option 2: Clone with Git

```bash
git clone YOUR_REPOSITORY_URL
cd YOUR_REPOSITORY_FOLDER
```

Replace the placeholders with your repository URL and folder name.

---

# Windows setup

## 1. Install Python

1. Go to [Download Python](https://www.python.org/downloads/).
2. Download the current supported Python 3 installer for Windows.
3. Open the installer.
4. Check **Add python.exe to PATH**.
5. Select **Install Now**.
6. When installation finishes, close and reopen Command Prompt.

## 2. Confirm that Python works

Open **Command Prompt** and run:

```bat
python --version
```

You should see a Python 3 version number.

If `python` is not recognized, try:

```bat
py --version
```

If `py` works, use `py` instead of `python` in the commands below.

## 3. Export and unzip the Rise course

1. In Articulate Rise, publish or export the course for **Web**.
2. Download the ZIP package.
3. Right-click the ZIP file and select **Extract All**.
4. Confirm that the extracted folder contains a `content` folder somewhere inside it.

The script searches recursively for:

```text
runtime-data.js
```

## 4. Open Command Prompt in the script folder

1. Open the folder containing `rise_extract.py` in File Explorer.
2. Click the File Explorer address bar.
3. Type `cmd`.
4. Press Enter.

## 5. Run the extractor

```bat
python rise_extract.py "C:\path\to\your\unzipped\rise-course" -o out
```

Example:

```bat
python rise_extract.py "C:\Users\YourName\Downloads\my-rise-course" -o out
```

If your computer uses the Python launcher, run:

```bat
py rise_extract.py "C:\path\to\your\unzipped\rise-course" -o out
```

## 6. Open the results

When the script finishes, open the new `out` folder next to the script. It should contain:

```text
course.md
extraction-report.json
```

---

# macOS setup

## 1. Check whether Python 3 is already available

Open **Terminal** and run:

```bash
python3 --version
```

If Terminal shows a Python 3 version number, continue to the next section.

## 2. Install Python if needed

1. Go to [Python releases for macOS](https://www.python.org/downloads/macos/).
2. Download a current supported macOS installer.
3. Open the downloaded `.pkg` file.
4. Follow the installer prompts.
5. Close and reopen Terminal.
6. Verify the installation:

```bash
python3 --version
```

## 3. Export and unzip the Rise course

1. In Articulate Rise, publish or export the course for **Web**.
2. Download the ZIP package.
3. Double-click the ZIP file in Finder to unzip it.
4. Confirm that the extracted folder contains a `content` folder somewhere inside it.

## 4. Open Terminal in the project folder

One easy method:

1. Open Terminal.
2. Type `cd `, including the space after `cd`.
3. Drag the folder containing `rise_extract.py` from Finder into Terminal.
4. Press Return.

## 5. Run the extractor

```bash
python3 rise_extract.py "/path/to/your/unzipped/rise-course" -o out
```

A convenient way to enter the course path is to type the command through the opening quotation mark, drag the unzipped course folder into Terminal, then finish the quotation mark and output option.

Example:

```bash
python3 rise_extract.py "/Users/YourName/Downloads/my-rise-course" -o out
```

## 6. Open the results

In Finder, open the new `out` folder next to the script. It should contain:

```text
course.md
extraction-report.json
```

---

# Using the Markdown for QA or AI review

Before sending the Markdown to another system:

1. Open `course.md` in a text editor.
2. Spot-check several sections against the published Rise course.
3. Review `extraction-report.json` for warnings or unsupported content.
4. Remove any confidential or sensitive information that should not be shared.
5. Provide your QA checklist, style guide, terminology list, and review instructions to the tool performing the review.

The Markdown is an extraction aid, not proof that every learner-visible item was captured.

## Suggested AI review prompt

```text
Review the attached Markdown as extracted course content. Check it against the provided QA checklist. Treat block labels as navigation aids, not learner-facing text. Do not report Markdown headings or extraction labels as course defects. For every issue, identify the lesson, block, quoted text, issue type, and recommended correction. Flag incomplete fragments, but distinguish likely extraction artifacts from genuine course errors.
```

# Troubleshooting

## Python was not found

### Windows

Try:

```bat
py --version
```

If that works, replace `python` with `py` in the run command. Otherwise, reinstall Python and select **Add python.exe to PATH**.

### macOS

Use:

```bash
python3 --version
```

On macOS, the command is usually `python3`, not `python`.

## `runtime-data.js` could not be found

Make sure you:

- exported the Rise course for Web
- unzipped the export
- passed the extracted course folder, not an unrelated parent folder
- did not delete or reorganize the export contents

## The Markdown is unexpectedly short

Check `extraction-report.json` for:

- unresolved localization references
- missing asset folders
- Storyline parsing failures
- Code Blocks with no recoverable text

Also confirm that you are using the latest version of the script.

## Storyline text is missing

Embedded Storyline packages can vary by publishing version and configuration. Check the `storyline_blocks` section of `extraction-report.json` for missing or unparsed slide files.

## Code Block output contains CSS or JavaScript fragments

Open an issue and include:

- the unexpected output fragment
- the relevant Code Block's `index.html` or inline source, if you are permitted to share it
- the matching section of `extraction-report.json`

Do not post proprietary course content or confidential files in a public issue.

## Some Code Block text is missing

The script deliberately filters strings that look like CSS classes, event names, dimensions, selectors, and framework artifacts. If legitimate learner text is filtered, open an issue with a small, non-confidential reproduction.

# Recommended repository files

```text
rise-course-text-extractor/
├── README.md
├── rise_extract.py
├── LICENSE
├── .gitignore
└── examples/
    └── README.md
```

Suggested `.gitignore`:

```gitignore
__pycache__/
*.pyc
.DS_Store
rise_extract_out/
out/
course.md
extraction-report.json
*.zip
```

The output files are ignored because they may contain course content.

# Security and responsible use

- Only process course exports that you are authorized to access.
- Do not commit published course packages or extracted course text unless you have permission.
- Review repository history before making a repository public.
- Test with a synthetic or openly shareable course whenever possible.
- Keep `course.md`, `extraction-report.json`, and Rise export ZIP files out of source control by default.
- The script reads local files and writes local output. Review future contributions carefully before running modified versions.

# Data and organization check

The public script should not contain organization-specific course content, internal URLs, email addresses, employee information, credentials, API keys, access tokens, or local user paths.

Before publishing, search the script and the full repository for:

```text
company names
organization abbreviations
email addresses
internal domains
employee names
C:\Users\
/Users/
API keys
tokens
passwords
course titles
client names
```

Also inspect Git history. Deleting a sensitive file in the latest commit does not automatically remove it from earlier commits.

# Environmental note

This utility performs deterministic text extraction locally rather than repeatedly using an AI model to interpret an entire course package or PDF. In workflows where it replaces repeated AI preprocessing, it may reduce unnecessary model calls and associated computing. The actual energy, water, and carbon effects depend on the systems and workflow involved, so this project does not claim a measured emissions reduction.

# Contributing

Bug reports and small reproducible test cases are welcome.

When reporting a problem:

1. Remove confidential or proprietary content.
2. Describe the Rise block type involved.
3. Include the relevant section of `extraction-report.json`.
4. Include a minimal sample export or source fragment if sharing is permitted.
5. Explain what text should have appeared and what appeared instead.

Please test changes against multiple export types when possible, including:

- native Rise blocks
- localized courses
- Custom Blocks
- inline Code Blocks
- ZIP-uploaded Code Blocks
- embedded Storyline interactions
- captions and transcripts

# Disclaimer

This software is provided as-is, without warranty. Published course structures can change, and extracted output may be incomplete or contain artifacts. Always review and validate the output before using it for quality assurance, compliance, accessibility, translation, publishing, or other consequential decisions.

# License

Released into the public domain under the [Unlicense](https://unlicense.org/). You are free to use, modify, and distribute this project for any purpose.
See the LICENSE file for the complete terms.

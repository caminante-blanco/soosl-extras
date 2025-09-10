# Media Setup Guide for SooSL Batch Importer

This guide explains how to correctly name and organize your media files (videos and images) to be used with the `batch_importer.py` script. Following these conventions is essential for the script to correctly parse your files and import them into a SooSL project.

## Core Concept: The Filename Structure

The script determines the **Gloss**, **Author**, and **Sort Order** of a sign directly from its filename. The filename is parsed by splitting it by underscores (`_`).

The general format is:

`[AUTHOR_PREFIX]_[GLOSS_WORD_1]_[GLOSS_WORD_2]_[...]_[ALT_INDEX].ext`

---

### 1. Gloss (Required)

The gloss is the name or transcription of the sign.

-   It is the central and **only required** part of the filename.
-   If a gloss contains multiple words, separate them with underscores. The script will convert these underscores into spaces.

**Examples:**
-   `HOUSE.mp4` → Gloss: "HOUSE"
-   `THANK_YOU.mov` → Gloss: "THANK YOU"
-   `I_GIVE_TO_YOU.mp4` → Gloss: "I GIVE TO YOU"

### 2. Author Prefix (Optional)

The author prefix is an optional identifier at the **beginning** of the filename.

-   It is used to assign an author to the sign media.
-   For a prefix to be recognized, it **must** be listed in an `authors.txt` file located in the root of your import directory.

**Example:**
-   If `authors.txt` contains `TJG`, then the filename `TJG_HELLO.mp4` will be imported with "TJG" as the author and "HELLO" as the gloss.
-   Without the `authors.txt` file, the same filename would be incorrectly interpreted as having the gloss "TJG HELLO".

### 3. Alternate Index (Optional)

The alternate index is an optional number at the **end** of the filename.

-   It is used to control the sort order when multiple media files share the same gloss, which is especially important in "Group" import modes.
-   Videos are prioritized over images. For files of the same type (e.g., two videos), a lower index number gives higher priority.
-   If omitted, the index defaults to `0`.

**Examples:**
-   `TREE_0.mp4` (will be the primary media over `TREE_1.mp4`)
-   `TREE_1.mp4`
-   `TREE_2.jpg` (will be an extra media file, sorted after the videos)

---

## The `authors.txt` File

This is a plain text file that you can create in the root of your media import directory.

-   **Purpose:** To define a list of valid author prefixes that the script should recognize.
-   **Format:** One author prefix per line.
-   **Optional:** If this file is not found, the script will ask if you want to create one. If you decline, no part of the filename will be treated as an author prefix.

**Example `authors.txt`:**

TJG
ML
JDOE

---

## Directory Structure

The script will search for media files **recursively**. This means it will scan the directory you select and all of its subdirectories.

**Example Directory Layout:**

import_folder/
├── authors.txt
├── HOUSE/
│   ├── ML_HOUSE_0.mp4
│   └── TJG_HOUSE_1.mp4
├── THANK_YOU/
│   ├── THANK_YOU_0.mp4
│   └── THANK_YOU_1.jpg
└── TREE.mov 

---

## Supported File Formats

#### Video Formats
-   `.mp4`
-   `.mov`
-   `.avi`
-   `.mkv`

#### Image Formats
-   `.bmp`
-   `.gif`
-   `.jpg`
-   `.jpeg`
-   `.png`
-   `.pbm`
-   `.pgm`
-   `.ppm`
-   `.xbm`
-   `.xpm`
-   `.svg`

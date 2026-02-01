# What the Downloads Look Like

This document describes how downloaded media files are named and organized on disk.
It is the ground truth for future worker design (grouping into media units, extracting
decorations, and preparing data for Kodi).

## 1. Folder and Media Unit Structure

### 1.1 Bottom-Level Folders

- We focus on **bottom-level folders** (no subfolders inside).
- Each such folder typically contains **multiple media units**.
- All files in a folder are usually downloads from one or a small set of sites.
- Filenames in a folder have **high internal cohesion**:
  - Files belonging to the same media unit are very similar.
  - Different media units are mostly dissimilar.

### 1.2 Media Units

A **media unit** is the logical “thing” we care about (e.g. one movie, one episode).

- A media unit consists of:
  - One PRIMARY video file:
    - e.g. `.mp4`, `.mkv`, `.avi`, …
  - Zero or more ASSET / sidecar files:
    - e.g. `.jpg` (poster/thumbnail),
    - `.nfo` (Kodi metadata),
    - `.srt` (subtitles),
    - possibly others in the future.
- All files of a media unit:
  - Live in the **same folder**.
  - Share a **core name** (derived from the site’s download filename).
  - Share a set of **decorations** (site, production house, actor, uploader, timestamp, resolution, etc.),
    although not every file necessarily has every decoration.

## 2. Filename Anatomy

A typical filename can be thought of as:

```text
[random_prefix][core_name][decorations][extension]
```

### 2.1 Random Prefix

- Some files have a **random-looking prefix** at the very start of the filename.
- Properties:
  - The prefix is **different for every single file**.
  - In a folder, for those files that have it, the **length** of the prefix is the same.
  - Example:

    ```text
    sdfw moviename1-01012025-0116.jpg
    er4q moviename1_720p-01012025-0115.mp4
    ```

    - `sdfw` and `er4q` are random prefixes (same length, different content).
    - After the prefix, the meaningful part of the name begins.

- Workers must **not rely on the prefix content** for grouping.
- The prefix is noise; the structure we care about starts after it.

### 2.2 Core Name

- The **core name** comes from the website’s download filename.
- It is the main identifier for a media unit.
- All files of a media unit share the same core name (after any random prefix).
- Example:

  ```text
  sdfw moviename1-01012025-0116.jpg
  er4q moviename1_720p-01012025-0115.mp4
  moviename1.nfo
  ```

  - Core name: `moviename1`
  - The jpg, mp4, and nfo all contain `moviename1` as the core.

- Across different media units in the same folder, core names differ:
  - `moviename1`, `moviename2`, `moviename3`, etc.

### 2.3 Decorations

Decorations are extra tokens added around the core name. They come from:

- The **site** (e.g. resolution only on the video).
- The **downloader** (e.g. date/time, actor, site name, production group).
- The **user** (e.g. manual renames like `ffff` prefix for folder thumbnails).

Examples of decorations:

- Resolution:
  - `_720p`, `_1080p`, `_2160p`, etc.
  - Often only on the video file.
- Date/time:
  - e.g. `-01012025-0116` appended at the end.
- Site / download source:
  - e.g. a token that appears in all files from a given site.
- Production house:
  - e.g. a token that recurs across many media units from the same producer.
- Uploader:
  - e.g. a token between dashes before the timestamp.
- Actor:
  - e.g. an actor name appended by the downloader.

Properties:

- Within a **media unit**:
  - Most decorations are shared across all files of that unit (though some may be missing on some files).
- Within a **folder**:
  - Some decorations recur across many media units (e.g. site, production house, uploader).
- Over time:
  - We will build a catalog of known decorations and their meanings:
    - e.g. “these 12 tokens are production houses”, “these tokens are sites”, etc.
  - Rules may be **per top-folder**:
    - Different top-level directories may correspond to different sites or naming conventions.

Workers in early phases should:

- Treat decorations as **opaque tokens**.
- Focus on:
  - Discovering which tokens are shared within a unit.
  - Discovering which tokens recur across the folder.
- Later, a human or a configuration layer will assign semantics:
  - “This token is a production house.”
  - “This pattern is an uploader.”
  - “This token is a site name.”

### 2.4 Extensions and Roles

- PRIMARY (video) extensions:
  - e.g. `.mp4`, `.mkv`, `.avi` (exact set to be defined).
- ASSET (sidecar) extensions:
  - e.g. `.jpg`, `.nfo`, `.srt`, etc.
- Role of a file is determined by its extension:
  - PRIMARY: main video content.
  - ASSET: metadata, images, subtitles, etc.

## 3. Folder-Level Cohesion

- Each bottom-level folder is treated as a **high-cohesion cluster**:
  - Files in the folder are mostly related to a small number of media units.
  - Filenames share a lot of structure.
- Grouping strategy (conceptual):
  - For a given folder, look at **all filenames together**.
  - Identify:
    - Which substrings are common across a set of files (core name).
    - Which substrings are shared across many units (decorations).
    - Which substrings are unique per file (random prefix, per-file noise).
- The worker does **not** need to know the meaning of decorations up front.
  - It only needs to:
    - Group files into media units.
    - Surface decorations per unit and per folder for later interpretation.

## 4. Kodi-Related Conventions (High-Level)

These are target behaviors for future workers (not implemented in PRE-PROJECT):

### 4.1 Media-Unit Thumbnails

- For each media unit:
  - Preferred thumbnail:
    - Use the downloaded `.jpg` that belongs to that unit.
  - Fallback:
    - If no jpg exists for that unit, use `ffmpeg` to extract a frame from the video and save as a jpg.
  - The jpg filename should match the video filename (for Kodi file view).

### 4.2 Folder Thumbnails and `ffff` Convention

- Kodi uses `folder.jpg` as the thumbnail for a folder in folder view.
- Rules:
  - If `folder.jpg` is missing:
    - Use the **oldest jpg in the folder** as `folder.jpg` (copy, not move).
  - User override:
    - If the user renames a jpg to start with `ffff` (e.g. `ffffmoviename1.jpg`):
      - This signals: “this jpg should be the folder thumbnail”.
      - A worker should:
        - Copy that jpg as `folder.jpg`.
        - Rename the original back by stripping the `ffff` prefix so it again matches the media unit’s naming pattern.

These conventions will be enforced by a dedicated worker in a later phase.

## 5. Long-Term Interpretation Layer

- Over time, we will:
  - Discover decorations per folder and per top-folder.
  - Build a catalog of known decorations:
    - Production houses, sites, uploaders, actors, etc.
  - Define **per-top-folder rules**:
    - e.g. “In this top folder, a token between dashes before the timestamp is the uploader.”
- Workers will:
  - First pass: discover structure (media units, decorations).
  - Later passes: apply known rules to populate `library_items.metadata` and NFO content.

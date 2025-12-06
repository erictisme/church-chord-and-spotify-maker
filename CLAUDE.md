# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a static web application for church worship song management and Word document generation. The entire application is contained in a single `index.html` file with embedded CSS and JavaScript - no build process or dependencies required.

**Live URL**: https://erictisme.github.io/church-chord-and-spotify-maker/
**Deployment**: GitHub Pages from main branch

## Architecture

### Core Components
- **Single Page App**: `index.html` contains all HTML, CSS, and JavaScript (~2500 lines)
- **Song Library**: 225+ markdown files in `eric-songs/all-songs/` with chord charts and metadata
- **Catalog Index**: `eric-songs/indices/tsv-catalog.json` contains searchable metadata for all songs
- **Generated Documents**: Output goes to `eric-all-weeks/` and `created-weeks/`

### Data Flow
1. **Song Loading**: Fetches catalog from GitHub raw URL, no backend required
2. **Song Selection**: Client-side filtering, search, and selection with live preview
3. **Document Generation**: Fetches individual song markdown files, applies transposition, formats output
4. **Output**: Copy-to-clipboard for pasting into Word/Google Docs

### Song Data Structure
Each song has:
- **Markdown file**: `eric-songs/all-songs/song-name-KEY.md` with frontmatter and chord chart
- **Catalog entry**: JSON object in `tsv-catalog.json` with metadata for search/filtering

**Song Frontmatter Format**:
```yaml
---
title: Song Title
artist: Artist Name
themes: [worship, praise, cross]
pace: slow|medium|fast
era: contemporary|traditional|kids
key: C|D|E|F|G|A|B (with sharps/flats)
first_seen: YYYY-MM-DD
latest_version: YYYY-MM-DD
---
```

## Development Commands

### Testing the Application
```bash
# Open locally (no server needed)
open index.html

# Test with live reload server (optional)
python3 -m http.server 8000
# Then visit http://localhost:8000
```

### Adding New Songs
1. Create markdown file: `eric-songs/all-songs/song-title-KEY.md`
2. Update catalog: Add entry to `eric-songs/indices/tsv-catalog.json`
3. Commit both files together

### Deployment
Automatic via GitHub Pages when pushing to main branch. No build step required.

## Key Features & Implementation

### Song Management
- **Search**: Real-time filtering by title/artist/themes in `handleSearch()`
- **Filtering**: Theme-based filtering with visual tags in `toggleFilter()`
- **Transposition**: Client-side chord transposition in `transposeChord()`
- **Preview**: Live document preview with automatic regeneration

### AI Integration
- **Gemini API**: Optional AI song suggestions based on scripture/theme
- **API Key Storage**: Uses localStorage, no backend auth required
- **Feature Toggle**: AI section can be hidden if no API key

### Document Generation
- **Format**: Plain text optimized for Word/Google Docs (Arial font)
- **Output**: Service header + song overview + full chord sheets
- **Transposition**: Shows both written key and sounding key with capo
- **Copy-Paste Workflow**: Generates text for manual paste into Word processors

## File Conventions

### Song Files
- **Naming**: `song-title-KEY.md` (lowercase, hyphens, key suffix)
- **Content**: YAML frontmatter + markdown with chord notation
- **Chord Format**: Text-based chords above lyrics (Arial font compatible)

### Catalog Updates
When adding songs, both the markdown file AND catalog entry must be updated together to maintain sync.

### Font Handling
- **Current Songs**: Formatted for Arial font (manual spacing)
- **Future Enhancement**: Planning to add `font` metadata field for monospace songs from Ultimate Guitar tabs

## External Dependencies

- **GitHub Raw URLs**: For loading song catalog and individual song files
- **Gemini AI API**: Optional, for AI song suggestions
- **Browser APIs**: Clipboard API for copy functionality
- **GitHub Pages**: For hosting, automatic deployment

## Troubleshooting

### Song Loading Issues
- Verify `tsv-catalog.json` syntax with JSON validator
- Check that song filenames in catalog match actual files
- Ensure GitHub Pages deployment completed (may take 2 minutes)

### Development Setup
No local development environment needed - edit files and test by opening `index.html` directly in browser.
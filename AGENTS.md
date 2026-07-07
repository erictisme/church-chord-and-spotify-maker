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
- **Current Songs**: Formatted for Arial font (manual spacing) - `font: 'arial'` (default)
- **UG Imports**: Songs imported from Ultimate Guitar use `font: 'monospace'` for proper chord alignment
- **CSS Classes**: `.song-block.monospace` applies Courier New font for imported tabs

### Ultimate Guitar Import System
The app supports importing songs directly from Ultimate Guitar:
- **Import Modal**: Opens via "Import from Ultimate Guitar" section
- **Workflow**: User copies chord content from UG, pastes in modal, fills metadata
- **Font**: Imported songs automatically use monospace font
- **Copyright**: Attribution notice added automatically to imported songs
- **Session Storage**: Imports are stored in `importedSongs[]` array (session only, not persisted)
- **Raw Content**: Imported songs store chords in `rawContent` property instead of fetching from file

### Preview Layout Options
- **1-Column**: Default single column layout (Arial-optimized)
- **2-Column**: CSS columns layout for newspaper-style display
- **Toggle**: Buttons in preview header to switch between layouts
- **CSS**: `.preview-content.two-column` applies column layout with `column-span: all` for overview

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

## Design System & UX Standards

All UI work should use the CSS variables defined in `:root`. This ensures consistency across the app.

### Typography Scale
| Variable | Size | Usage |
|----------|------|-------|
| `--font-xs` | 11px | Tiny labels, metadata |
| `--font-sm` | 13px | Secondary text, buttons |
| `--font-base` | 14px | Body text (default) |
| `--font-md` | 16px | Emphasized body, inputs |
| `--font-lg` | 20px | Section headers |
| `--font-xl` | 24px | Panel titles |
| `--font-2xl` | 32px | Page titles |

### Font Families
| Variable | Stack | Usage |
|----------|-------|-------|
| `--font-system` | System UI fonts | General UI |
| `--font-chord` | Arial, sans-serif | Chord sheets (existing songs) |
| `--font-mono` | Courier New | Ultimate Guitar tabs (monospace songs) |

### Colors
| Variable | Hex | Usage |
|----------|-----|-------|
| `--color-primary` | #7C3AED | Buttons, links, accents |
| `--color-accent` | #C1121F | Copy button, warnings |
| `--color-success` | #059669 | Add/confirm actions |
| `--color-spotify` | #1DB954 | Spotify button |

### Spacing Scale
Use `--space-xs` (4px) through `--space-2xl` (30px) for consistent spacing.

### Border Radius
Use `--radius-sm` (4px) through `--radius-xl` (12px) for consistent rounded corners.
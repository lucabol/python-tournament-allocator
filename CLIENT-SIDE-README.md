# Client-Side Tournament Allocator

A fully client-side web application for managing tournament schedules, built with HTML, CSS, and JavaScript. No backend server or installation required!

## Overview

This is a standalone HTML application that runs entirely in your browser. All data is stored locally using browser LocalStorage, making it perfect for:
- Quick tournament setup without server infrastructure
- Offline tournament management
- Privacy-focused data handling (data never leaves your browser)
- Easy deployment (just open the HTML file!)

## Features

- **Pool Management**: Create pools with multiple teams
- **Court Scheduling**: Manage multiple courts with custom time slots
- **Automatic Schedule Generation**: Uses simplified greedy algorithm
  - All pool matches assigned to same court
  - Automatic time slot calculation based on match duration and breaks
- **Results Tracking**: Record match results and calculate standings
- **Bracket Generation**: Create elimination brackets from pool standings
- **Data Import/Export**: Save and load tournament data as JSON
- **Sample Data**: Quick start with pre-loaded sample tournament
- **Print Support**: Print-friendly schedule views

## Getting Started

### Quick Start

1. **Open the application**: Simply open `tournament-allocator.html` in any modern web browser
2. **Load sample data**: Click "Load Sample Data" to see a pre-configured tournament
3. **Generate schedule**: Click "Generate Schedule" to create the tournament schedule

### From Scratch

1. **Add Courts** (Courts tab):
   - Enter court name (e.g., "Court 1")
   - Set start and end times
   - Click "Add Court"

2. **Create Pools** (Teams tab):
   - Enter pool name (e.g., "Pool A")
   - Set number of teams to advance (e.g., 2)
   - Click "Add Pool"

3. **Add Teams** (Teams tab):
   - Select a pool from dropdown
   - Enter team name
   - Click "Add Team"

4. **Configure Settings** (Settings tab):
   - Set match duration (default: 25 minutes)
   - Set break between matches (default: 5 minutes)
   - Choose bracket type (Single or Double Elimination)
   - Enable/disable Silver Bracket

5. **Generate Schedule** (Schedule tab):
   - Click "Generate Schedule"
   - View the complete tournament schedule

6. **Enter Results** (Results tab):
   - Enter scores for each pool play match
   - View live standings updates
   - Top teams automatically advance to bracket

7. **View Bracket** (Bracket tab):
   - Click "Generate Bracket" after completing pool play
   - View seeded elimination bracket

## Scheduling Algorithm

The application uses a simplified greedy algorithm as specified:

### Pool Play
- All matches from the same pool are assigned to the same court
- Matches are scheduled sequentially with configured breaks between them
- Pools are assigned to courts in round-robin fashion

### Bracket Play
- Bracket matches are scheduled after pool play with a 2-hour delay
- Matches are distributed across available courts
- Suggested court assignments:
  - Court 1: Gold Winner Bracket
  - Court 2: Gold Loser Bracket (if double elimination)
  - Court 3: Silver Winner Bracket
  - Court 4: Silver Loser Bracket

## Data Management

### Export Data
Click "Export Data" to download your tournament configuration as a JSON file. This includes:
- All pools and teams
- Court configurations
- Settings
- Schedule
- Results

### Import Data
Click "Import Data" to load a previously exported JSON file. This will replace all current data.

### Browser Storage
Data is automatically saved to browser LocalStorage after every change. Your tournament data persists between browser sessions unless you:
- Clear browser data
- Use private/incognito mode without saving
- Click "Reset All"

## Browser Compatibility

Works with all modern browsers:
- Chrome/Edge (Chromium-based)
- Firefox
- Safari
- Opera

**Note**: Requires JavaScript enabled and LocalStorage support.

## Deployment

### Local Use
Just double-click `tournament-allocator.html` to open it in your browser.

### Web Hosting
Upload `tournament-allocator.html` to any web server or hosting service:
- GitHub Pages
- Netlify
- Vercel
- Any static file hosting

No server-side processing required!

### File Sharing
Simply share the HTML file via:
- Email
- USB drive
- Cloud storage (Dropbox, Google Drive, etc.)

Recipients can open it directly in their browser.

## Tips and Best Practices

1. **Regular Exports**: Export your tournament data regularly as backup
2. **Browser Consistency**: Use the same browser for the entire tournament to maintain data
3. **Testing**: Use sample data to test the application before your event
4. **Printing**: Use the print function for physical copies of schedules
5. **Multiple Tournaments**: Use different browser profiles or export/import to manage multiple tournaments

## Limitations

- No real-time collaboration (single browser session)
- No complex constraint solving (uses simplified greedy algorithm)
- Limited to browser LocalStorage capacity (typically 5-10MB)
- No automatic conflict detection beyond basic scheduling

## Troubleshooting

**Q: My data disappeared!**
A: Check if you're in private/incognito mode or if browser data was cleared. Always export data as backup.

**Q: Can I run this on mobile?**
A: Yes! The interface is responsive and works on tablets and phones.

**Q: How do I share my tournament with others?**
A: Export your data as JSON and share the file. Others can import it into their own copy of the application.

**Q: Can multiple people update the same tournament?**
A: No, this is a single-user application. One person should maintain the tournament and share exports.

## Differences from Original Application

This client-side version differs from the Python/Flask backend version:

1. **No Backend**: Completely client-side, no server required
2. **Simplified Scheduling**: Uses greedy algorithm instead of constraint solver (OR-Tools)
3. **Browser Storage**: LocalStorage instead of YAML/CSV files
4. **Simplified Bracket**: Basic single/double elimination (no complex constraint handling)
5. **No Real-time Sync**: Single browser session only

## Technical Details

- **Size**: ~45KB single HTML file
- **Dependencies**: None (pure vanilla JavaScript)
- **Storage**: Browser LocalStorage API
- **Architecture**: Single-page application (SPA)

## License

Same as the original project.

## Support

For issues or questions, please refer to the main repository.

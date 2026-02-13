# Tournament Allocator — User Guide

Welcome! This guide walks you through everything you need to run a tournament using the Tournament Allocator web app. Whether you're organizing a beach volleyball tournament or any other bracket-style competition, this guide will get you up and running fast.

---

## 1. Getting Started

### Create an Account

Open the app in your browser. You'll land on the **Login** page. If you don't have an account yet, click the **Register** link at the bottom.

On the registration page, enter:
- **Username** — letters, numbers, and hyphens (at least 2 characters)
- **Password** — at least 4 characters
- **Confirm Password** — type it again to make sure

Click **Register** and you're in.

### Log In

Enter your username and password on the Login page, then click **Login**. You'll stay logged in until you click **Logout** (shown in the top-right corner of the navigation bar, next to your username).

### Create Your First Tournament

After logging in, you'll be taken to the **Tournaments** page. This is your home base for managing all your tournaments.

To create a tournament:
1. Type a name in the text field under **Create New Tournament** (e.g., "Summer Beach Volley 2026").
2. Click **Create**.

Your new tournament is now the active one. You'll see its name appear in the top-left corner of the navigation bar (replacing the default "Tournament Allocator" text). An **Active** badge appears next to it in the tournament list.

### Switching Between Tournaments

If you have multiple tournaments, go to the **Tournaments** page (first link in the navigation bar). Your tournaments are listed in a table showing name, creation date, and actions. Click the **Switch** button next to any tournament to make it the active one. All other pages (Teams, Courts, Schedule, etc.) will now show data for that tournament.

### Deleting a Tournament

On the **Tournaments** page, click the red **Delete** button next to the tournament you want to remove. You'll be asked to confirm — this action cannot be undone.

---

## 2. Managing Teams and Pools

### The Teams Page

Click **Teams** in the navigation bar. This is where you set up who's playing and how they're grouped into pools.

### Creating Pools

Under **Add New Pool**, type a pool name (e.g., "Pool A") and set how many teams should advance from that pool to the elimination bracket. The default is 2. Click **Add Pool**.

Each pool appears as a card showing its teams, match count, and advancement settings.

### Adding Teams to Pools

Inside each pool card, you'll see a text field and a green **Add Team** button. Type a team name and click the button. Repeat for each team in that pool.

### Renaming Teams and Pools

Team names and pool names are editable right in place — just click on the name, type the new one, and press Tab or click away. The change saves automatically.

### Removing Teams and Pools

- To remove a team, click the small red **×** button next to the team name.
- To remove an entire pool (and all its teams), click the red **Delete Pool** button at the top of the pool card. You'll be asked to confirm.

### Setting How Many Teams Advance

Each pool card has a **Top ___ advance** control. Change the number to set how many teams from that pool move on to the elimination bracket. For example, if you set it to 3, the top 3 finishers in that pool will advance.

### Loading Teams from YAML

If you have your team data in a YAML file, click the **Load** button under "Load from YAML" on the Teams page. Click the **?** icon to see the expected format. Note: loading a YAML file replaces all existing teams and clears the schedule.

### Generating Test Data

Want to try the app quickly? Click the **Test** button in the top-right corner of the Teams page header. This creates sample pools and teams so you can explore the full workflow without entering real data.

---

## 3. Setting Up Courts

### The Courts Page

Click **Courts** in the navigation bar. Here you define the physical courts available for your tournament and when they're open.

### Adding a Court

Fill in the form under **Add New Court**:
- **Court Name** — e.g., "Court 1", "Main Court"
- **Opens At** — the time this court becomes available (defaults to 08:00)
- **Closes At** — the time this court stops being available (defaults to 22:00)

Click **Add Court**. The court appears in the table below.

### Editing Court Names

Court names are editable in the table — click the name, type a new one, and click away.

### Removing Courts

Click the red **Delete** button in the court's row. You'll be asked to confirm.

### Loading Courts from YAML

Like teams, you can load court data from a YAML file using the **Load** button under "Load from YAML." Click the **?** icon to see the expected format.

### How Court Availability Affects Scheduling

The schedule optimizer uses your court open/close times to figure out when matches can happen. More courts and longer hours mean more flexibility. If the optimizer can't fit all your matches, try adding courts or extending their hours.

The table shows how many hours each court is available, calculated automatically from open and close times. Courts support past-midnight schedules — if a court opens at 18:00 and closes at 02:00, it's treated as an 8-hour window spanning midnight.

### Generating Test Courts

Click the **Test** button in the page header to create sample courts.

---

## 4. Tournament Settings

### The Settings Page

Click **Settings** in the navigation bar. This page controls the rules and format for your tournament. Changes are saved instantly as you make them — no save button needed.

### General Settings

At the top of the page, you can configure:

- **Logo** — Click **Upload Logo** to upload your club or tournament logo. It appears on the Print page and the Live page header. Supported formats: PNG, JPG, GIF, SVG, WebP.
- **Club Name** — Your organization's name (e.g., "Montgó Beach Volley Club").
- **Tournament Name** — The display name for this tournament (e.g., "Summer Tournament 2026").
- **Date** — A text field for the tournament date (e.g., "July 2026").

### Scheduling Settings

- **Match Duration (minutes)** — How long each match is expected to take. This determines how time slots are allocated in the schedule. Range: 15–180 minutes.
- **Number of Days** — How many days your tournament spans (1–14).
- **Break Between Matches (minutes)** — Minimum rest time a team gets between consecutive matches. Range: 0–120 minutes.
- **Day End Time** — The latest a match can end. Supports past-midnight times (e.g., set to "02:00" if matches can run past midnight).
- **Pool to Bracket Delay (minutes)** — A buffer between the end of pool play and the start of bracket play. Useful for lunch breaks or transition time. Range: 0–480 minutes.

### Format Settings

- **Pool in Same Court** — When checked, all matches for a given pool are scheduled on the same court. Unchecked means the optimizer can spread pool matches across any available court.
- **Elimination Bracket Type** — Choose **Single Elimination** (one loss and you're out) or **Double Elimination** (you need to lose twice).
- **Scoring Format** — Choose **Single Set** (one set per match) or **Best of 3 Sets** (win 2 out of 3 sets).
- **Silver Bracket** — When enabled, teams that don't advance from pool play compete in a separate consolation bracket for a Silver Championship. Only relevant for double elimination tournaments.

### Team-Specific Time Constraints

Some teams might have scheduling restrictions (e.g., a team that can't play before 10:00 AM). Under **Team-Specific Constraints**:

1. Select a team from the dropdown.
2. Set **Must Play After** and/or **Must End Before** times.
3. Optionally add a note explaining the reason.
4. Click **Add Constraint**.

Existing constraints appear in a table below, where you can delete them.

### Reset All Data

At the bottom of the Settings page, the **Reset All Data** button deletes all teams, courts, schedules, results, and settings for the current tournament. Use with caution.

---

## 5. Generating the Schedule

### The Schedule Page

Click **Schedule** in the navigation bar. This is where the magic happens — the app creates an optimized match schedule based on your teams, courts, and settings.

### Generating a Schedule

Click the green **🔄 Generate Schedule** button. The optimizer runs for a few seconds (or longer for large tournaments) and produces a schedule. The button shows a spinner while it's working.

### How the Optimizer Works

The schedule is generated using a constraint-based optimizer (Google OR-Tools CP-SAT solver). It considers:
- Court availability windows
- Match duration
- Minimum break time between matches for each team
- Team-specific time constraints
- Pool-in-same-court preference
- Day end time limits

The optimizer tries to minimize the total schedule length while respecting all constraints.

### Reading the Schedule Grid

The schedule is displayed as a grid with:
- **Rows** = time slots (in 5-minute increments)
- **Columns** = courts
- **Cells** = matches (showing "Team A vs Team B")

Each match cell shows:
- The two team names
- The pool name (for pool play matches) or round name (for bracket matches)
- A match code badge for bracket matches

Multi-day tournaments show a separate grid for each day. Bracket matches appear under a "Bracket Phase" section.

On mobile, the schedule displays as a collapsible list grouped by day, showing time, court, and teams for each match.

### Stats Bar

Above the schedule, a stats bar shows:
- **Total Matches** — how many matches were generated
- **Scheduled** — how many were successfully placed on courts
- **Unscheduled** — how many couldn't be placed (shown in red if any)

### What to Do if Scheduling Fails

If some matches are unscheduled, try:
- Adding more courts
- Extending court hours
- Increasing the number of tournament days
- Reducing the break between matches
- Extending the day end time

### Regenerating the Schedule

You can click **Generate Schedule** again at any time. This completely replaces the previous schedule. If you've already entered match results, be careful — regenerating will create a fresh schedule.

---

## 6. Tracking Match Results

### The Pools Page

Click **Pools** in the navigation bar. This page shows all pool play matches with score input fields, plus a live standings table.

At the top, a stats bar shows how many matches are scheduled, completed, and remaining.

### Entering Scores

Each match appears as a card with the two team names and score input fields next to each team. The layout depends on your scoring format:

- **Single Set** — one score input per team. Type the score for each team (e.g., 21 and 15).
- **Best of 3** — three score inputs per team, one for each set. Fill in as many sets as were played.

Scores are saved automatically as you type (with a short debounce delay). You don't need to click a save button.

When a valid result is entered (one team has a higher score), the match card turns green, the winning team's name is highlighted in bold, and the standings table updates in real time.

### How Standings Are Calculated

The standings table below the matches shows, for each pool:
- **#** — current ranking position
- **Team** — team name
- **W** — wins
- **L** — losses
- **Sets** — sets won vs. sets lost
- **Δ Sets** — set differential (sets won minus sets lost)
- **Δ Pts** — point differential (total points scored minus total points conceded)

Teams are ranked by wins first, then by set differential, then by point differential as tiebreakers.

Teams that will advance to the bracket are highlighted in green (the number is determined by the "advance" setting you configured for each pool).

### Generating Test Results

Click the **Test** button in the page header to auto-generate random results for all pool matches. This is great for testing the bracket flow.

### Live Link

At the top of the Pools page, you'll see a **Live link** bar with a URL and a **📋 Copy** button. Share this link with players and spectators so they can follow the tournament live (see Section 8).

---

## 7. Brackets

Click **Bracket** in the navigation bar. The bracket page you see depends on your tournament's elimination bracket type setting.

### Single Elimination Bracket

If your tournament is set to **Single Elimination**, you'll see the **Single Elimination Bracket** page.

The page shows:
- **Gold Bracket** — the main elimination bracket
- **Silver Bracket** — the consolation bracket (only if Silver Bracket is enabled)

For each bracket:
- A stats summary shows teams advancing, bracket size, number of rounds, and first-round byes.
- **Seeded Teams** lists each team with their seed number and which pool they came from.
- **Bracket Rounds** shows each round (Quarterfinal, Semifinal, Final, etc.) with match cards.

Match cards show:
- 🟢 **Green dot** = ready to play (both teams are known)
- **✓** = match completed
- **⏳** = waiting for teams from earlier rounds

Enter scores the same way as pool play — type scores directly into the input fields next to each team name. When a valid score is entered, the winner automatically advances to the next round.

At the bottom, a **Schedule Elimination Rounds** button lets you generate court/time assignments for the bracket matches.

### Double Elimination Bracket

If set to **Double Elimination**, you'll see a more complex bracket with three sections:

**Winners Bracket (🔵)** — Teams that haven't lost yet. Each match card shows a match code (e.g., "W1-M1") and indicates where the loser will go ("Loser → L1-M1").

**Losers Bracket (🔴)** — Teams with one loss. Another loss means elimination. The description says: "Teams with one loss. One more loss means elimination."

**Grand Final (🏆)** — The winners bracket champion vs. the losers bracket champion. Since the losers bracket champion has already lost once, if they win the Grand Final, a **Bracket Reset** match is played to determine the true champion.

The bracket reset only appears when needed (if the losers bracket champion wins the Grand Final).

Each bracket match has a **Test** button in the page header to auto-generate random bracket results for quick testing.

### Silver Bracket

When enabled (in Settings), a Silver Bracket appears below the Gold Bracket. It works the same way as the Gold Bracket but is for teams that didn't advance from pool play. It has its own seeded teams, rounds, and champion.

### How Seeding Works

Teams are seeded into the bracket based on their pool finish position:
1. All 1st-place teams from each pool get the top seeds
2. All 2nd-place teams from each pool get the next seeds
3. And so on...

Within each finishing position, teams are ordered alphabetically by pool name. Until pool play is complete, placeholder names like "#1 Pool A" are shown.

### Bracket Reset (Double Elimination)

In double elimination, the winners bracket champion enters the Grand Final with zero losses. The losers bracket champion has one loss. If the losers bracket champion wins the Grand Final, both teams have one loss — so a Bracket Reset match is played. The winner of the reset is the tournament champion.

---

## 8. Live Page

### What the Live Page Is

The **Live** page is a public, read-only view of your tournament designed for spectators and players. No login is required to view it.

### How to Share the Live Link

There are two ways to get the link:
- On the **Pools** page, the live link is shown at the top with a **📋 Copy** button.
- On the **Dashboard** page, click the **📡 Copy Live Link** button under Quick Actions.

The URL follows the pattern: `/<your-username>/<tournament-slug>`. Each tournament has its own unique public URL.

### What Spectators See

The Live page shows:
- **Up Next** — a hero section showing the next unfinished match on each court, with time and court info.
- **Full Schedule** — a collapsible section with every match, showing times, courts, teams, and scores for completed matches.
- **Pool Standings** — a collapsible section with standings tables for each pool.
- **Gold Bracket** — a collapsible section with the full elimination bracket (winners bracket, losers bracket, grand final).
- **Silver Bracket** — a collapsible section (if enabled) with the consolation bracket.
- **Champion banners** — when a champion is determined, a banner appears at the top.

There's also a **🔍 Find my team…** search bar at the top. Spectators can type a team name to highlight that team's matches and hide unrelated ones.

### Auto-Refresh Behavior

The Live page uses Server-Sent Events (SSE) to update automatically whenever you enter scores or make changes. A connection indicator in the header shows:
- **Green dot + "Live"** = connected and receiving real-time updates
- **"Reconnecting…"** = temporarily disconnected, trying to reconnect
- **"Disconnected"** = connection lost

If the browser doesn't support SSE, the page falls back to polling every 30 seconds.

---

## 9. Printing

### The Print Page

Click **Print** in the navigation bar. This opens a formal, print-friendly document view of your entire tournament.

### What's Included

The print page is organized into numbered sections:
1. **Participating Teams and Pool Assignments** — all pools and their teams, plus advancement counts.
2. **Venue and Court Allocation** — court names and operating hours.
3. **Tournament Regulations and Format** — match duration, rest period, scoring format, elimination format, silver bracket status, and court assignment policy.
4. **Official Match Schedule** — every match with time, court, pool, and team matchup.
5. **Pool Phase Standings** — final standings for each pool (advancing teams highlighted in green).
6. **Elimination Phase** — seeding, all bracket rounds and results, grand final, and champion. Includes Silver Bracket if enabled.

### Tournament Header

At the top of the page, a header shows your uploaded logo, club name, tournament name, and date (all configured on the Settings page).

### Printing

Click the **Print** button at the top of the page. The navigation bar, footer, and buttons are automatically hidden when printing. The layout is optimized for paper with proper page breaks.

---

## 10. Export and Import

### Tournament Export/Import

On the **Dashboard** page, under **Quick Actions**:
- Click **💾 Export Tournament** to download the current tournament as a ZIP file.
- Click **📂 Import Tournament** to upload a ZIP file. This replaces all data in the current tournament — you'll be asked to confirm.

The ZIP includes teams, courts, constraints, schedule, results, print settings, and logo.

You can also download the schedule as a CSV file by clicking **📥 Download CSV** (only available after generating a schedule).

### User Export/Import

On the **Tournaments** page, under **Backup & Restore**:
- Click **💾 Export All Tournaments** to download all your tournaments as a single ZIP file.
- Click **📂 Import Tournaments** to upload a ZIP. Imported tournaments are merged with your existing ones — tournaments with the same name are updated, and new ones are added. Your existing tournaments that aren't in the ZIP are preserved.

### Site Export/Import (Admin Only)

Only the user named "admin" can see this section, which appears at the bottom of the **Tournaments** page in a red danger-zone box labeled **🔒 Site Administration (Admin Only)**.

- **💾 Export Site Backup** downloads a ZIP of the entire site: all users, all tournaments, and all settings.
- **📂 Import Site Backup** replaces everything on the site. Because this is destructive, you must type the word **REPLACE** in a confirmation dialog to proceed.

This is useful for migrating the app between hosting platforms or restoring from a full backup.

---

## 11. Tips and Tricks

- **Quick start**: Use the **Test** buttons on the Teams and Courts pages to generate sample data. Then generate a schedule and use the **Test** button on the Pools page to auto-fill results. This lets you explore the full tournament flow in minutes.

- **Fit your venue**: Adjust the number of courts and their hours to match your actual venue. The optimizer works best when there's enough court time for all matches.

- **Large tournaments**: The schedule optimizer may take a few seconds for tournaments with many teams and courts. If it takes too long or can't fit all matches, try relaxing constraints (shorter breaks, more courts, longer days).

- **Keep players informed**: Share the Live page link with players and spectators. It updates in real time as you enter scores, so everyone stays in the loop.

- **Back up before big changes**: Export your tournament before regenerating the schedule or making major edits. You can always import it back if something goes wrong.

- **Past-midnight tournaments**: Courts and day end times support past-midnight scheduling. Set a court's closing time to "02:00" and the day end time to "02:00" to schedule matches that run after midnight.

- **YAML bulk loading**: If you have lots of teams or courts, prepare them in a YAML file and use the **Load** button on the Teams or Courts page to import them all at once. Click the **?** icon to see the expected format.

- **Team search on Live page**: Spectators can use the search bar on the Live page to find their team's matches quickly — it highlights matching matches and hides the rest.

- **Dashboard overview**: The Dashboard page shows your tournament's current phase (Setup → Pool Play → Bracket → Complete), a progress bar, next steps, and quick links. Check it regularly for a snapshot of where things stand.

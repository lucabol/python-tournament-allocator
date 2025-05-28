import datetime
from itertools import combinations

class AllocationManager:
    def __init__(self, teams, courts, constraints):
        self.teams = {team.name: team for team in teams}
        self.courts = courts
        self.constraints = constraints
        self.schedule = {court.name: [] for court in courts} # court_name: [(start_time, end_time, match_tuple)]

    def _parse_time(self, time_str):
        return datetime.datetime.strptime(time_str, '%H:%M').time()

    def _datetime_from_time(self, time_obj, base_date=None):
        base_date = base_date or datetime.date.today()
        return datetime.datetime.combine(base_date, time_obj)

    def _check_court_availability(self, court, match_start_time, match_end_time):
        court_start_dt = self._datetime_from_time(self._parse_time(court.start_time), match_start_time.date())
        
        if match_start_time < court_start_dt: # Cannot start before court opens
            return False

        # Add check for court end time if available in court model
        # For now, assuming courts operate long enough for matches within the day_end_limit_dt

        for scheduled_start, scheduled_end, _ in self.schedule[court.name]:
            if max(scheduled_start, match_start_time) < min(scheduled_end, match_end_time):
                return False # Overlap
        return True

    def _check_team_constraints(self, team_names, match_start_time, debug=False):
        match_duration = datetime.timedelta(minutes=self.constraints.get('match_duration_minutes', 60))
        match_end_time = match_start_time + match_duration
        min_break_minutes = self.constraints.get('min_break_between_matches_minutes', 0)
        
        if debug:
            print(f"    Checking constraints for {team_names} at {match_start_time.strftime('%H:%M')}")
        
        for team_name_in_match in team_names:
            current_team_name = str(team_name_in_match)

            if current_team_name not in self.teams:
                if debug:
                    print(f"      Warning: Team {current_team_name} not found in loaded teams")
                continue

            # Check team-specific time constraints
            for constraint in self.constraints.get('team_specific_constraints', []):
                if constraint['team_name'] == current_team_name:
                    if 'play_after' in constraint:
                        play_after_dt = self._datetime_from_time(self._parse_time(constraint['play_after']), match_start_time.date())
                        if match_start_time < play_after_dt:
                            if debug:
                                print(f"      ✗ {current_team_name} play_after constraint violated: {match_start_time.strftime('%H:%M')} < {play_after_dt.strftime('%H:%M')}")
                            return False
                    if 'play_before' in constraint:
                        play_before_dt = self._datetime_from_time(self._parse_time(constraint['play_before']), match_start_time.date())
                        if match_end_time > play_before_dt:
                            if debug:
                                print(f"      ✗ {current_team_name} play_before constraint violated: {match_end_time.strftime('%H:%M')} > {play_before_dt.strftime('%H:%M')}")
                            return False 
            
            # Check for conflicts with existing matches for this team
            team_existing_matches = []
            for court_schedule in self.schedule.values():
                for scheduled_start, scheduled_end, scheduled_match_teams in court_schedule:
                    if current_team_name in map(str, scheduled_match_teams):
                        team_existing_matches.append((scheduled_start, scheduled_end))
            
            if debug and team_existing_matches:
                print(f"      {current_team_name} has {len(team_existing_matches)} existing matches")
            
            for existing_start, existing_end in team_existing_matches:
                # 1. Check for overlapping matches (impossible - team can't be in two places)
                if max(existing_start, match_start_time) < min(existing_end, match_end_time):
                    if debug:
                        print(f"      ✗ {current_team_name} overlapping match: {existing_start.strftime('%H:%M')}-{existing_end.strftime('%H:%M')} overlaps {match_start_time.strftime('%H:%M')}-{match_end_time.strftime('%H:%M')}")
                    return False  # Overlapping matches
                
                # 2. Check minimum break time
                if min_break_minutes > 0:
                    required_break = datetime.timedelta(minutes=min_break_minutes)
                    
                    # New match after existing match
                    if existing_end <= match_start_time:
                        if match_start_time - existing_end < required_break:
                            if debug:
                                print(f"      ✗ {current_team_name} insufficient break: {(match_start_time - existing_end).total_seconds() / 60:.0f} min < {min_break_minutes} min required")
                            return False
                    
                    # New match before existing match
                    if match_end_time <= existing_start:
                        if existing_start - match_end_time < required_break:
                            if debug:
                                print(f"      ✗ {current_team_name} insufficient break: {(existing_start - match_end_time).total_seconds() / 60:.0f} min < {min_break_minutes} min required")
                            return False
        
        if debug:
            print(f"    ✓ All constraints satisfied for {team_names}")
        return True


    def allocate_teams_to_courts(self):
        print("Starting allocation process...")
        match_duration = datetime.timedelta(minutes=self.constraints.get('match_duration_minutes', 60))
        
        matches_to_schedule = self._generate_pool_play_matches()
        if not matches_to_schedule:
            print("No matches generated. Check tournament settings in constraints.json.")
            return self.schedule

        # Sort courts by start time
        self.courts.sort(key=lambda c: self._parse_time(c.start_time))
        
        day_end_time_limit_str = self.constraints.get("day_end_time_limit", "22:00")
        time_slot_increment_minutes = self.constraints.get('time_slot_increment_minutes', 15)
        time_slot_increment = datetime.timedelta(minutes=time_slot_increment_minutes)
        
        # Generate all possible time slots for the day
        base_date = datetime.date.today()
        earliest_court_time = min(self._parse_time(court.start_time) for court in self.courts)
        day_start_dt = self._datetime_from_time(earliest_court_time, base_date)
        day_end_dt = self._datetime_from_time(self._parse_time(day_end_time_limit_str), base_date)
        
        if day_end_dt.time() < earliest_court_time:
            day_end_dt += datetime.timedelta(days=1)
        
        # Create a systematic approach: try each match on each court at each possible time
        for match_tuple, match_info in matches_to_schedule:
            team1_name, team2_name = match_tuple
            scheduled_this_match = False
            
            print(f"Trying to schedule: {match_tuple} ({match_info})")
            
            # Try all time slots from earliest to latest
            current_time = day_start_dt
            while current_time <= day_end_dt - match_duration and not scheduled_this_match:
                potential_start_time = current_time
                potential_end_time = potential_start_time + match_duration
                
                # Try this time slot on all courts (prioritize courts with fewer matches)
                sorted_courts = sorted(self.courts, key=lambda c: len(self.schedule[c.name]))
                
                for court in sorted_courts:
                    # Check if court is open at this time
                    court_start_dt = self._datetime_from_time(self._parse_time(court.start_time), base_date)
                    if potential_start_time < court_start_dt:
                        continue  # Court not open yet
                    
                    # Check court availability and team constraints
                    if self._check_court_availability(court, potential_start_time, potential_end_time):
                        if self._check_team_constraints((team1_name, team2_name), potential_start_time):
                            # Successfully scheduled!
                            self.schedule[court.name].append((potential_start_time, potential_end_time, match_tuple))
                            self.schedule[court.name].sort(key=lambda x: x[0])
                            print(f"  ✓ Scheduled: {match_tuple} ({match_info}) on {court.name} at {potential_start_time.strftime('%H:%M')} - {potential_end_time.strftime('%H:%M')}")
                            scheduled_this_match = True
                            break
                
                if not scheduled_this_match:
                    current_time += time_slot_increment
            
            if not scheduled_this_match:
                print(f"  ✗ Warning: Could not schedule match {match_tuple} ({match_info}). No suitable court/time found.")
                # Debug: Check why the last few attempts failed
                print(f"    Debugging last few time slots for {match_tuple}:")
                debug_time = day_end_dt - match_duration - datetime.timedelta(hours=2)  # Check last 2 hours
                while debug_time <= day_end_dt - match_duration:
                    debug_end_time = debug_time + match_duration
                    print(f"    Time slot {debug_time.strftime('%H:%M')}-{debug_end_time.strftime('%H:%M')}:")
                    for court in self.courts[:3]:  # Check first 3 courts only
                        court_start_dt = self._datetime_from_time(self._parse_time(court.start_time), debug_time.date())
                        if debug_time >= court_start_dt:
                            court_available = self._check_court_availability(court, debug_time, debug_end_time)
                            if court_available:
                                self._check_team_constraints((team1_name, team2_name), debug_time, debug=True)
                            else:
                                print(f"      {court.name}: Court not available")
                    debug_time += datetime.timedelta(hours=1)
                    if debug_time > day_end_dt - match_duration:
                        break

        print("Allocation process finished.")
        return self.schedule

    def get_schedule_output(self):
        output = []
        for court_name, matches_on_court in self.schedule.items():
            court_info = {"court_name": court_name, "matches": []}
            for start_dt, end_dt, match_teams in matches_on_court:
                court_info["matches"].append({
                    "start_time": start_dt.strftime('%H:%M'),
                    "end_time": end_dt.strftime('%H:%M'),
                    "teams": match_teams
                })
            output.append(court_info)
        return output
import datetime
from itertools import combinations

class AllocationManager:

    def _has_team_overlap(self, team_names, start_time, end_time):
        """Return True if any team in team_names has an overlapping match at the given time."""
        for team_name in team_names:
            for court_schedule in self.schedule.values():
                for _, scheduled_start, scheduled_end, scheduled_match_teams in court_schedule:
                    if team_name in map(str, scheduled_match_teams):
                        if max(scheduled_start, start_time) < min(scheduled_end, end_time):
                            return True
        return False
    def __init__(self, teams, courts, constraints):
        self.teams = {team.name: team for team in teams}
        self.courts = courts
        self.constraints = constraints
        # schedule: {court_name: [(date, start_time, end_time, match_tuple)]}
        self.schedule = {court.name: [] for court in courts}

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

        for _, scheduled_start, scheduled_end, _ in self.schedule[court.name]:
            if max(scheduled_start, match_start_time) < min(scheduled_end, match_end_time):
                return False # Overlap
        return True

    def _check_team_constraints(self, team_names, match_start_time, debug=False, reason_out=None):
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
                if reason_out is not None:
                    reason_out.append(f"Team {current_team_name} not found")
                continue

            # Check team-specific time constraints
            for constraint in self.constraints.get('team_specific_constraints', []):
                if constraint['team_name'] == current_team_name:
                    if 'play_after' in constraint:
                        play_after_dt = self._datetime_from_time(self._parse_time(constraint['play_after']), match_start_time.date())
                        if match_start_time < play_after_dt:
                            if debug:
                                print(f"      ✗ {current_team_name} play_after constraint violated: {match_start_time.strftime('%H:%M')} < {play_after_dt.strftime('%H:%M')}")
                            if reason_out is not None:
                                reason_out.append(f"{current_team_name} play_after violated: {match_start_time.strftime('%H:%M')} < {play_after_dt.strftime('%H:%M')}")
                            return False
                    if 'play_before' in constraint:
                        play_before_dt = self._datetime_from_time(self._parse_time(constraint['play_before']), match_start_time.date())
                        if match_end_time > play_before_dt:
                            if debug:
                                print(f"      ✗ {current_team_name} play_before constraint violated: {match_end_time.strftime('%H:%M')} > {play_before_dt.strftime('%H:%M')}")
                            if reason_out is not None:
                                reason_out.append(f"{current_team_name} play_before violated: {match_end_time.strftime('%H:%M')} > {play_before_dt.strftime('%H:%M')}")
                            return False 
            
            # Check for conflicts with existing matches for this team
            team_existing_matches = []
            for court_schedule_items in self.schedule.values(): # Iterate through list of matches for each court
                for scheduled_item_day, scheduled_item_start, scheduled_item_end, scheduled_item_teams_tuple in court_schedule_items:
                    # If this 'scheduled_item' is the exact match currently being validated by _check_team_constraints,
                    # skip it to avoid comparing a match against itself.
                    # 'team_names' and 'match_start_time' are the primary arguments to _check_team_constraints,
                    # identifying the match under validation.
                    if scheduled_item_teams_tuple == team_names and scheduled_item_start == match_start_time:
                        continue

                    if current_team_name in map(str, scheduled_item_teams_tuple):
                        team_existing_matches.append((scheduled_item_start, scheduled_item_end))
            
            if debug and team_existing_matches:
                print(f"      {current_team_name} has {len(team_existing_matches)} existing matches")
            
            for existing_start, existing_end in team_existing_matches:
                # 1. Check for overlapping matches (impossible - team can't be in two places)
                if max(existing_start, match_start_time) < min(existing_end, match_end_time):
                    if debug:
                        print(f"      ✗ {current_team_name} overlapping match: {existing_start.strftime('%H:%M')}-{existing_end.strftime('%H:%M')} overlaps {match_start_time.strftime('%H:%M')}-{match_end_time.strftime('%H:%M')}")
                    if reason_out is not None:
                        reason_out.append(f"{current_team_name} overlapping match: {existing_start.strftime('%H:%M')}-{existing_end.strftime('%H:%M')} and {match_start_time.strftime('%H:%M')}-{match_end_time.strftime('%H:%M')}")
                    return False  # Overlapping matches
                # 2. Check minimum break time
                if min_break_minutes > 0:
                    required_break = datetime.timedelta(minutes=min_break_minutes)
                    # New match after existing match
                    if existing_end <= match_start_time:
                        if match_start_time - existing_end < required_break:
                            if debug:
                                print(f"      ✗ {current_team_name} insufficient break: {(match_start_time - existing_end).total_seconds() / 60:.0f} min < {min_break_minutes} min required")
                            if reason_out is not None:
                                reason_out.append(f"{current_team_name} insufficient break: {(match_start_time - existing_end).total_seconds() / 60:.0f} min < {min_break_minutes} min required")
                            return False
                    # New match before existing match
                    if match_end_time <= existing_start:
                        if existing_start - match_end_time < required_break:
                            if debug:
                                print(f"      ✗ {current_team_name} insufficient break: {(existing_start - match_end_time).total_seconds() / 60:.0f} min < {min_break_minutes} min required")
                            if reason_out is not None:
                                reason_out.append(f"{current_team_name} insufficient break: {(existing_start - match_end_time).total_seconds() / 60:.0f} min < {min_break_minutes} min required")
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

        self.courts.sort(key=lambda c: self._parse_time(c.start_time))
        day_end_time_limit_str = self.constraints.get("day_end_time_limit", "22:00")
        time_slot_increment_minutes = self.constraints.get('time_slot_increment_minutes', 15)
        time_slot_increment = datetime.timedelta(minutes=time_slot_increment_minutes)
        days_number = int(self.constraints.get('days_number', 1))

        base_date = datetime.date.today()
        earliest_court_time = min(self._parse_time(court.start_time) for court in self.courts)
        day_start_time = earliest_court_time
        day_end_time = self._parse_time(day_end_time_limit_str)

        # Prepare a list of all days
        all_dates = [base_date + datetime.timedelta(days=i) for i in range(days_number)]

        for idx, (match_tuple, match_info) in enumerate(matches_to_schedule):
            team1_name, team2_name = match_tuple
            scheduled_this_match = False
            print(f"Trying to schedule: {match_tuple} ({match_info})")

            # Try all days, then all time slots in each day
            for day_idx, day in enumerate(all_dates):
                day_num = day_idx + 1
                day_start_dt = self._datetime_from_time(day_start_time, day)
                day_end_dt = self._datetime_from_time(day_end_time, day)
                current_time = day_start_dt
                while current_time <= day_end_dt - match_duration and not scheduled_this_match:
                    potential_start_time = current_time
                    potential_end_time = potential_start_time + match_duration
                    
                    # Check for team overlaps BEFORE trying any courts for this time slot
                    if self._has_team_overlap((team1_name, team2_name), potential_start_time, potential_end_time):
                        current_time += time_slot_increment
                        continue  # Skip this entire time slot due to overlap
                    
                    sorted_courts = sorted(self.courts, key=lambda c: len(self.schedule[c.name]))
                    for court in sorted_courts:
                        court_start_dt = self._datetime_from_time(self._parse_time(court.start_time), day)
                        if potential_start_time < court_start_dt:
                            continue
                        if self._check_court_availability(court, potential_start_time, potential_end_time):
                            if self._check_team_constraints((team1_name, team2_name), potential_start_time):
                                self.schedule[court.name].append((day_num, potential_start_time, potential_end_time, match_tuple))
                                self.schedule[court.name].sort(key=lambda x: (x[0], x[1]))
                                print(f"  ✓ Scheduled: {match_tuple} ({match_info}) on {court.name} on Day {day_num} at {potential_start_time.strftime('%H:%M')} - {potential_end_time.strftime('%H:%M')}")
                                scheduled_this_match = True
                                break
                    if not scheduled_this_match:
                        current_time += time_slot_increment
                if scheduled_this_match:
                    break
            if not scheduled_this_match:
                print(f"  ✗ Warning: Could not schedule match {match_tuple} ({match_info}). No suitable court/time found.")
        print("Allocation process finished.")
        # --- Post-allocation checks ---
        self._post_allocation_checks(matches_to_schedule)
        return self.schedule

    def _post_allocation_checks(self, matches_to_schedule):
        print("\n--- Post-allocation checks ---")
        # 1. Check all games scheduled
        scheduled_matches = set()
        for court_matches in self.schedule.values():
            for _, _, _, match_tuple in court_matches:
                scheduled_matches.add(match_tuple)
        all_matches = set(match for match, _ in matches_to_schedule)
        if scheduled_matches == all_matches:
            print("[✓] All games have been scheduled.")
        else:
            missing = all_matches - scheduled_matches
            print(f"[✗] Not all games scheduled. Missing: {missing}")

        # 2. Check all constraints are respected
        all_constraints_ok = True
        for court_matches in self.schedule.values():
            for day_num, start_dt, _, match_tuple in court_matches:
                reason = []
                if not self._check_team_constraints(match_tuple, start_dt, reason_out=reason):
                    reason_str = reason[0] if reason else "Unknown"
                    print(f"[✗] {match_tuple} on Day {day_num} at {start_dt.strftime('%H:%M')}: {reason_str}")
                    all_constraints_ok = False
        if all_constraints_ok:
            print("[✓] All constraints are respected.")
        else:
            print("[✗] Some constraints were violated.")

    def get_schedule_output(self):
        output = []
        for court_name, matches_on_court in self.schedule.items():
            court_info = {"court_name": court_name, "matches": []}
            for day_num, start_dt, end_dt, match_teams in matches_on_court:
                court_info["matches"].append({
                    "day": f"Day {day_num}",
                    "start_time": start_dt.strftime('%H:%M'),
                    "end_time": end_dt.strftime('%H:%M'),
                    "teams": match_teams
                })
            output.append(court_info)
        return output
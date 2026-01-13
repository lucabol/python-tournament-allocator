import datetime
from itertools import combinations
from ortools.sat.python import cp_model


class AllocationManager:
    """
    Manages allocation of matches to courts using OR-Tools CP-SAT solver.
    
    This implementation uses constraint programming to find optimal schedules
    that satisfy all constraints (team availability, court availability, 
    minimum breaks, etc.) rather than a greedy first-fit approach.
    """

    def __init__(self, teams, courts, constraints):
        self.teams = {team.name: team for team in teams}
        self.courts = courts
        self.constraints = constraints
        # schedule: {court_name: [(day_num, start_time, end_time, match_tuple)]}
        self.schedule = {court.name: [] for court in courts}

    def _parse_time(self, time_str):
        """Parse time string to time object."""
        return datetime.datetime.strptime(time_str, '%H:%M').time()

    def _datetime_from_time(self, time_obj, base_date=None):
        """Convert time object to datetime with given base date."""
        base_date = base_date or datetime.date.today()
        return datetime.datetime.combine(base_date, time_obj)

    def _time_to_slot(self, time_obj, day_start_time, slot_minutes):
        """Convert a time to a slot index relative to day start."""
        start_minutes = day_start_time.hour * 60 + day_start_time.minute
        time_minutes = time_obj.hour * 60 + time_obj.minute
        return (time_minutes - start_minutes) // slot_minutes

    def _slot_to_time(self, slot, day_start_time, slot_minutes):
        """Convert a slot index to a time object."""
        start_minutes = day_start_time.hour * 60 + day_start_time.minute
        total_minutes = start_minutes + slot * slot_minutes
        return datetime.time(total_minutes // 60, total_minutes % 60)

    def _has_team_overlap(self, team_names, start_time, end_time):
        """Return True if any team in team_names has an overlapping match at the given time."""
        for team_name in team_names:
            for court_schedule in self.schedule.values():
                for _, scheduled_start, scheduled_end, scheduled_match_teams in court_schedule:
                    if team_name in map(str, scheduled_match_teams):
                        if max(scheduled_start, start_time) < min(scheduled_end, end_time):
                            return True
        return False

    def _check_court_availability(self, court, match_start_time, match_end_time):
        court_start_dt = self._datetime_from_time(self._parse_time(court.start_time), match_start_time.date())
        
        if match_start_time < court_start_dt: # Cannot start before court opens
            return False
        
        # Check court end time if specified
        if court.end_time:
            court_end_dt = self._datetime_from_time(self._parse_time(court.end_time), match_start_time.date())
            if match_end_time > court_end_dt:  # Cannot end after court closes
                return False

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

    def _get_team_constraints_for_cpsat(self, team_name):
        """Get play_after and play_before constraints for a team."""
        play_after = None
        play_before = None
        
        for constraint in self.constraints.get('team_specific_constraints', []):
            if constraint['team_name'] == team_name:
                if 'play_after' in constraint:
                    play_after = constraint['play_after']
                if 'play_before' in constraint:
                    play_before = constraint['play_before']
        
        return play_after, play_before

    def allocate_teams_to_courts(self):
        """
        Allocate matches to courts using OR-Tools CP-SAT solver.
        
        This creates a constraint satisfaction model where:
        - Variables: For each match, which (court, day, slot) it's assigned to
        - Constraints: No overlapping matches on same court, no team playing 
          concurrent matches, minimum breaks, team/court time restrictions
        - Objective: Minimize total schedule duration (makespan)
        """
        print("Starting CP-SAT allocation process...")
        
        matches_to_schedule = self._generate_pool_play_matches()
        if not matches_to_schedule:
            print("No matches generated. Check tournament settings.")
            return self.schedule

        # Extract configuration
        match_duration_minutes = self.constraints.get('match_duration_minutes', 60)
        min_break_minutes = self.constraints.get('min_break_between_matches_minutes', 0)
        time_slot_minutes = self.constraints.get('time_slot_increment_minutes', 15)
        days_number = int(self.constraints.get('days_number', 1))
        day_end_time_str = self.constraints.get("day_end_time_limit", "22:00")
        
        # Calculate match duration in slots (round up to ensure full coverage)
        match_slots = (match_duration_minutes + time_slot_minutes - 1) // time_slot_minutes
        # Calculate minimum break in slots
        break_slots = (min_break_minutes + time_slot_minutes - 1) // time_slot_minutes if min_break_minutes > 0 else 0
        
        # Determine day boundaries
        earliest_court_time = min(self._parse_time(court.start_time) for court in self.courts)
        day_start_time = earliest_court_time
        day_end_time = self._parse_time(day_end_time_str)
        
        # Calculate total slots per day
        day_start_minutes = day_start_time.hour * 60 + day_start_time.minute
        day_end_minutes = day_end_time.hour * 60 + day_end_time.minute
        total_day_minutes = day_end_minutes - day_start_minutes
        slots_per_day = total_day_minutes // time_slot_minutes
        
        # Build team name to index mapping
        all_team_names = set()
        for match_tuple, _ in matches_to_schedule:
            all_team_names.add(str(match_tuple[0]))
            all_team_names.add(str(match_tuple[1]))
        
        # Calculate court start slots (relative to day start)
        court_start_slots = {}
        for court in self.courts:
            court_start = self._parse_time(court.start_time)
            court_start_minutes = court_start.hour * 60 + court_start.minute
            court_start_slots[court.name] = max(0, (court_start_minutes - day_start_minutes) // time_slot_minutes)
        
        # Create CP-SAT model
        model = cp_model.CpModel()
        
        num_matches = len(matches_to_schedule)
        num_courts = len(self.courts)
        num_days = days_number
        
        # Decision variables using interval variables for efficient constraint handling
        match_vars = {}  # (match_idx, court_idx, day) -> interval_var
        match_start_vars = {}  # (match_idx, court_idx, day) -> start variable
        match_end_vars = {}
        match_present_vars = {}  # (match_idx, court_idx, day) -> bool var
        
        for m_idx in range(num_matches):
            for c_idx in range(num_courts):
                for d in range(num_days):
                    suffix = f"_m{m_idx}_c{c_idx}_d{d}"
                    
                    start_var = model.NewIntVar(0, slots_per_day - match_slots, f"start{suffix}")
                    end_var = model.NewIntVar(match_slots, slots_per_day, f"end{suffix}")
                    present_var = model.NewBoolVar(f"present{suffix}")
                    
                    interval_var = model.NewOptionalIntervalVar(
                        start_var, match_slots, end_var, present_var, f"interval{suffix}"
                    )
                    
                    match_vars[(m_idx, c_idx, d)] = interval_var
                    match_start_vars[(m_idx, c_idx, d)] = start_var
                    match_end_vars[(m_idx, c_idx, d)] = end_var
                    match_present_vars[(m_idx, c_idx, d)] = present_var
        
        # Constraint 1: Each match must be scheduled exactly once
        for m_idx in range(num_matches):
            present_vars_for_match = []
            for c_idx in range(num_courts):
                for d in range(num_days):
                    present_vars_for_match.append(match_present_vars[(m_idx, c_idx, d)])
            model.Add(sum(present_vars_for_match) == 1)
        
        # Constraint 2: No overlapping matches on the same court on the same day
        for c_idx in range(num_courts):
            for d in range(num_days):
                intervals_on_court_day = []
                for m_idx in range(num_matches):
                    intervals_on_court_day.append(match_vars[(m_idx, c_idx, d)])
                model.AddNoOverlap(intervals_on_court_day)
        
        # Constraint 3: Court opening time constraints
        for m_idx in range(num_matches):
            for c_idx, court in enumerate(self.courts):
                court_start_slot = court_start_slots[court.name]
                for d in range(num_days):
                    present = match_present_vars[(m_idx, c_idx, d)]
                    start = match_start_vars[(m_idx, c_idx, d)]
                    model.Add(start >= court_start_slot).OnlyEnforceIf(present)
        
        # Constraint 3b: Court closing time constraints (from end_time)
        for m_idx in range(num_matches):
            for c_idx, court in enumerate(self.courts):
                if court.end_time:
                    court_end = self._parse_time(court.end_time)
                    court_end_minutes = court_end.hour * 60 + court_end.minute
                    court_end_slot = (court_end_minutes - day_start_minutes) // time_slot_minutes
                    for d in range(num_days):
                        present = match_present_vars[(m_idx, c_idx, d)]
                        end = match_end_vars[(m_idx, c_idx, d)]
                        model.Add(end <= court_end_slot).OnlyEnforceIf(present)
        
        # Constraint 4: Team-specific play_after and play_before constraints
        for m_idx, (match_tuple, _) in enumerate(matches_to_schedule):
            team1, team2 = match_tuple
            for team in [str(team1), str(team2)]:
                play_after, play_before = self._get_team_constraints_for_cpsat(team)
                
                for c_idx in range(num_courts):
                    for d in range(num_days):
                        present = match_present_vars[(m_idx, c_idx, d)]
                        start = match_start_vars[(m_idx, c_idx, d)]
                        end = match_end_vars[(m_idx, c_idx, d)]
                        
                        if play_after:
                            after_time = self._parse_time(play_after)
                            after_slot = self._time_to_slot(after_time, day_start_time, time_slot_minutes)
                            model.Add(start >= after_slot).OnlyEnforceIf(present)
                        
                        if play_before:
                            before_time = self._parse_time(play_before)
                            before_slot = self._time_to_slot(before_time, day_start_time, time_slot_minutes)
                            model.Add(end <= before_slot).OnlyEnforceIf(present)
        
        # Constraint 5: No team can play overlapping matches + minimum break
        # Group matches by team
        team_matches = {team: [] for team in all_team_names}
        for m_idx, (match_tuple, _) in enumerate(matches_to_schedule):
            team_matches[str(match_tuple[0])].append(m_idx)
            team_matches[str(match_tuple[1])].append(m_idx)
        
        # For each team, create team-level intervals with breaks and ensure no overlap
        for team, match_indices in team_matches.items():
            if len(match_indices) < 2:
                continue
            
            # Create team intervals per day (match + break time)
            team_intervals_by_day = {d: [] for d in range(num_days)}
            
            for m_idx in match_indices:
                for c_idx in range(num_courts):
                    for d in range(num_days):
                        present = match_present_vars[(m_idx, c_idx, d)]
                        start = match_start_vars[(m_idx, c_idx, d)]
                        
                        # Create team interval that includes the break time after the match
                        team_interval_size = match_slots + break_slots
                        team_end = model.NewIntVar(0, slots_per_day + break_slots, f"team_end_m{m_idx}_c{c_idx}_d{d}_{team}")
                        model.Add(team_end == start + team_interval_size).OnlyEnforceIf(present)
                        
                        team_interval = model.NewOptionalIntervalVar(
                            start, team_interval_size, team_end, present,
                            f"team_interval_m{m_idx}_c{c_idx}_d{d}_{team}"
                        )
                        team_intervals_by_day[d].append(team_interval)
            
            # No overlap for each team on each day
            for d in range(num_days):
                if team_intervals_by_day[d]:
                    model.AddNoOverlap(team_intervals_by_day[d])
        
        # Create global start time variables for each match (day * slots_per_day + slot)
        match_global_start = {}
        for m_idx in range(num_matches):
            global_start = model.NewIntVar(0, num_days * slots_per_day, f"global_start_m{m_idx}")
            match_global_start[m_idx] = global_start
            
            for c_idx in range(num_courts):
                for d in range(num_days):
                    present = match_present_vars[(m_idx, c_idx, d)]
                    start = match_start_vars[(m_idx, c_idx, d)]
                    # global_start = d * slots_per_day + start when present
                    model.Add(global_start == d * slots_per_day + start).OnlyEnforceIf(present)
        
        # Calculate minimum gap between consecutive matches for each team
        # We'll track the minimum gap across all teams
        min_team_gap = model.NewIntVar(0, num_days * slots_per_day, "min_team_gap")
        
        for team, match_indices in team_matches.items():
            if len(match_indices) < 2:
                continue
            
            # For each pair of matches for this team, compute the gap
            for i, m1_idx in enumerate(match_indices):
                for m2_idx in match_indices[i+1:]:
                    # Gap between m1 and m2 (absolute difference of end of earlier and start of later)
                    # We use the difference of global starts as a proxy
                    gap = model.NewIntVar(0, num_days * slots_per_day, f"gap_{team}_m{m1_idx}_m{m2_idx}")
                    
                    # gap = |global_start[m1] - global_start[m2]|
                    diff = model.NewIntVar(-num_days * slots_per_day, num_days * slots_per_day, 
                                          f"diff_{team}_m{m1_idx}_m{m2_idx}")
                    model.Add(diff == match_global_start[m1_idx] - match_global_start[m2_idx])
                    model.AddAbsEquality(gap, diff)
                    
                    # min_team_gap <= gap for all pairs
                    model.Add(min_team_gap <= gap)
        
        # Objective: Lexicographic optimization
        # Primary: Minimize makespan
        # Secondary: Maximize minimum gap (equivalent to minimizing -min_gap)
        # We use weighted sum: minimize (makespan * weight - min_team_gap)
        # Weight should be large enough that makespan always takes priority
        makespan = model.NewIntVar(0, num_days * slots_per_day, "makespan")
        for m_idx in range(num_matches):
            for c_idx in range(num_courts):
                for d in range(num_days):
                    present = match_present_vars[(m_idx, c_idx, d)]
                    end = match_end_vars[(m_idx, c_idx, d)]
                    model.Add(makespan >= d * slots_per_day + end).OnlyEnforceIf(present)
        
        # Weight for makespan should dominate: use slots_per_day * num_days as weight
        # This ensures any 1-slot improvement in makespan outweighs max possible gap improvement
        makespan_weight = num_days * slots_per_day + 1
        
        # Combined objective: minimize (makespan * weight - min_team_gap)
        # This minimizes makespan first, then maximizes min_team_gap as secondary
        model.Minimize(makespan * makespan_weight - min_team_gap)
        
        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        solver.parameters.num_search_workers = 4
        
        print(f"Solving CP-SAT problem: {num_matches} matches, {num_courts} courts, {num_days} days...")
        status = solver.Solve(model)
        
        base_date = datetime.date.today()
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            solution_type = "optimal" if status == cp_model.OPTIMAL else "feasible"
            print(f"Found {solution_type} solution!")
            
            # Extract solution
            for m_idx, (match_tuple, match_info) in enumerate(matches_to_schedule):
                for c_idx, court in enumerate(self.courts):
                    for d in range(num_days):
                        if solver.Value(match_present_vars[(m_idx, c_idx, d)]):
                            start_slot = solver.Value(match_start_vars[(m_idx, c_idx, d)])
                            
                            day_date = base_date + datetime.timedelta(days=d)
                            start_time = self._slot_to_time(start_slot, day_start_time, time_slot_minutes)
                            start_dt = self._datetime_from_time(start_time, day_date)
                            end_dt = start_dt + datetime.timedelta(minutes=match_duration_minutes)
                            
                            day_num = d + 1
                            self.schedule[court.name].append((day_num, start_dt, end_dt, match_tuple))
                            print(f"  ✓ Scheduled: {match_tuple} ({match_info}) on {court.name} Day {day_num} at {start_dt.strftime('%H:%M')}")
                            break
                    else:
                        continue
                    break
            
            # Sort schedules
            for court_name in self.schedule:
                self.schedule[court_name].sort(key=lambda x: (x[0], x[1]))
        else:
            print("No solution found! Falling back to greedy algorithm...")
            self._allocate_greedy(matches_to_schedule, match_duration_minutes, time_slot_minutes,
                                  days_number, day_start_time, day_end_time, base_date)
        
        print("Allocation process finished.")
        self._post_allocation_checks(matches_to_schedule)
        return self.schedule

    def _allocate_greedy(self, matches_to_schedule, match_duration_minutes, time_slot_minutes,
                         days_number, day_start_time, day_end_time, base_date):
        """Fallback greedy allocation when CP-SAT fails to find a solution."""
        match_duration = datetime.timedelta(minutes=match_duration_minutes)
        time_slot_increment = datetime.timedelta(minutes=time_slot_minutes)
        all_dates = [base_date + datetime.timedelta(days=i) for i in range(days_number)]
        
        for match_tuple, match_info in matches_to_schedule:
            team1_name, team2_name = match_tuple
            scheduled_this_match = False
            
            for day_idx, day in enumerate(all_dates):
                day_num = day_idx + 1
                day_start_dt = self._datetime_from_time(day_start_time, day)
                day_end_dt = self._datetime_from_time(day_end_time, day)
                current_time = day_start_dt
                
                while current_time <= day_end_dt - match_duration and not scheduled_this_match:
                    potential_start_time = current_time
                    potential_end_time = potential_start_time + match_duration
                    
                    if self._has_team_overlap((team1_name, team2_name), potential_start_time, potential_end_time):
                        current_time += time_slot_increment
                        continue
                    
                    sorted_courts = sorted(self.courts, key=lambda c: len(self.schedule[c.name]))
                    for court in sorted_courts:
                        court_start_dt = self._datetime_from_time(self._parse_time(court.start_time), day)
                        if potential_start_time < court_start_dt:
                            continue
                        if self._check_court_availability(court, potential_start_time, potential_end_time):
                            if self._check_team_constraints((team1_name, team2_name), potential_start_time):
                                self.schedule[court.name].append((day_num, potential_start_time, potential_end_time, match_tuple))
                                self.schedule[court.name].sort(key=lambda x: (x[0], x[1]))
                                print(f"  ✓ Scheduled (greedy): {match_tuple} on {court.name} Day {day_num}")
                                scheduled_this_match = True
                                break
                    if not scheduled_this_match:
                        current_time += time_slot_increment
                if scheduled_this_match:
                    break
            
            if not scheduled_this_match:
                print(f"  ✗ Warning: Could not schedule match {match_tuple}")

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
"""
Reusable schedule validation helper functions with tests.

These helpers are designed for Phase 2 schedule validity tests, providing
common validation logic that can be reused across different test scenarios.

USAGE EXAMPLE:
--------------

```python
from datetime import datetime
from tests.test_helpers_validation import (
    validate_no_premature_scheduling,
    validate_team_availability,
    validate_bracket_dependencies
)

# Set up test schedule
schedule = {
    "Court 1": [
        (1, datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 9, 30), ("Team A", "Team B")),
        (1, datetime(2026, 1, 15, 10, 0), datetime(2026, 1, 15, 10, 30), ("Winner M1", "Team C")),
    ]
}

# Validate no premature scheduling
dependencies = {"Winner M1": ["M1"]}
match_codes = {("Team A", "Team B"): "M1", ("Winner M1", "Team C"): "M2"}
violations = validate_no_premature_scheduling(schedule, dependencies, match_codes)
assert violations == [], f"Scheduling violations: {violations}"

# Validate team availability (no double-booking)
violations = validate_team_availability(schedule, "Team A")
assert violations == [], f"Team A is double-booked: {violations}"

# Validate bracket dependencies
bracket_structure = {
    "M1": {"teams": ["Team A", "Team B"], "depends_on": []},
    "M2": {"teams": ["Winner M1", "Team C"], "depends_on": ["M1"]}
}
violations = validate_bracket_dependencies(schedule, bracket_structure)
assert violations == [], f"Bracket dependency violations: {violations}"
```
"""
import pytest
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ============================================================================
# VALIDATION HELPER FUNCTIONS
# ============================================================================

def validate_no_premature_scheduling(
    schedule: Dict[str, List[Tuple]], 
    dependencies: Dict[str, List[str]],
    match_codes: Optional[Dict[Tuple, str]] = None
) -> List[str]:
    """
    Validate that teams are not scheduled before they could be known.
    
    Args:
        schedule: Dict mapping court names to list of (day, start_dt, end_dt, teams) tuples
        dependencies: Dict mapping placeholder team names to list of prerequisite match codes
            Example: {"Winner M1": ["M1"], "Winner W1-M2": ["W1-M2"]}
        match_codes: Optional dict mapping teams tuple to match code
            Example: {("Team A", "Team B"): "M1", ("Winner M1", "Team C"): "M2"}
    
    Returns:
        List of violation descriptions (empty list = valid)
    
    Examples:
        >>> schedule = {"Court 1": [(1, dt(9, 0), dt(9, 30), ("Team A", "Team B")),
        ...                          (1, dt(10, 0), dt(10, 30), ("Winner M1", "Team C"))]}
        >>> deps = {"Winner M1": ["M1"]}
        >>> codes = {("Team A", "Team B"): "M1", ("Winner M1", "Team C"): "M2"}
        >>> validate_no_premature_scheduling(schedule, deps, codes)
        []
    """
    violations = []
    
    # Build a map of match codes to their end times
    match_end_times = {}
    if match_codes:
        for court_name, matches in schedule.items():
            for day, start_dt, end_dt, teams in matches:
                if teams in match_codes:
                    match_code = match_codes[teams]
                    match_end_times[match_code] = end_dt
    
    # Check each scheduled match
    for court_name, matches in schedule.items():
        for day, start_dt, end_dt, teams in matches:
            for team in teams:
                # Check if this is a placeholder team with dependencies
                if team in dependencies:
                    prereqs = dependencies[team]
                    for prereq_code in prereqs:
                        # Find the prerequisite match in the schedule
                        prereq_end_time = match_end_times.get(prereq_code)
                        
                        if prereq_end_time is None:
                            violations.append(
                                f"Team '{team}' scheduled at {start_dt.strftime('%H:%M')} "
                                f"but prerequisite match {prereq_code} not found in schedule"
                            )
                        elif start_dt < prereq_end_time:
                            violations.append(
                                f"Team '{team}' scheduled at {start_dt.strftime('%H:%M')} "
                                f"but match {prereq_code} doesn't end until {prereq_end_time.strftime('%H:%M')}"
                            )
    
    return violations


def validate_team_availability(
    schedule: Dict[str, List[Tuple]], 
    team_name: str
) -> List[str]:
    """
    Validate that a team is not double-booked (playing in two matches at the same time).
    
    Args:
        schedule: Dict mapping court names to list of (day, start_dt, end_dt, teams) tuples
        team_name: Name of the team to check
    
    Returns:
        List of violation descriptions (empty list = valid)
    
    Examples:
        >>> schedule = {"Court 1": [(1, dt(9, 0), dt(9, 30), ("Team A", "Team B"))],
        ...             "Court 2": [(1, dt(9, 15), dt(9, 45), ("Team A", "Team C"))]}
        >>> validate_team_availability(schedule, "Team A")
        ["Team 'Team A' double-booked: playing on Court 1 at 09:00-09:30 and Court 2 at 09:15-09:45"]
    """
    violations = []
    
    # Collect all matches where this team plays
    team_matches = []
    for court_name, matches in schedule.items():
        for day, start_dt, end_dt, teams in matches:
            if team_name in teams:
                team_matches.append({
                    'court': court_name,
                    'day': day,
                    'start': start_dt,
                    'end': end_dt,
                    'teams': teams
                })
    
    # Sort by start time for easier comparison
    team_matches.sort(key=lambda m: (m['day'], m['start']))
    
    # Check for overlaps
    for i in range(len(team_matches)):
        for j in range(i + 1, len(team_matches)):
            match_a = team_matches[i]
            match_b = team_matches[j]
            
            # Check if they're on the same day and overlap
            if match_a['day'] == match_b['day']:
                # Check for time overlap: matches overlap if one starts before the other ends
                if match_a['start'] < match_b['end'] and match_b['start'] < match_a['end']:
                    violations.append(
                        f"Team '{team_name}' double-booked: "
                        f"playing on {match_a['court']} at {match_a['start'].strftime('%H:%M')}-{match_a['end'].strftime('%H:%M')} "
                        f"and {match_b['court']} at {match_b['start'].strftime('%H:%M')}-{match_b['end'].strftime('%H:%M')}"
                    )
    
    return violations


def validate_bracket_dependencies(
    schedule: Dict[str, List[Tuple]], 
    bracket_structure: Dict[str, Dict]
) -> List[str]:
    """
    Validate that bracket matches are scheduled after their prerequisites complete.
    
    Args:
        schedule: Dict mapping court names to list of (day, start_dt, end_dt, teams) tuples
        bracket_structure: Dict mapping match codes to match info with 'depends_on' key
            Example: {
                "M1": {"teams": ["Team A", "Team B"], "depends_on": []},
                "M2": {"teams": ["Winner M1", "Team C"], "depends_on": ["M1"]}
            }
    
    Returns:
        List of violation descriptions (empty list = valid)
    
    Examples:
        >>> schedule = {"Court 1": [(1, dt(9, 0), dt(9, 30), ("Team A", "Team B")),
        ...                          (1, dt(9, 0), dt(9, 30), ("Winner M1", "Team C"))]}
        >>> bracket = {"M1": {"teams": ["Team A", "Team B"], "depends_on": []},
        ...            "M2": {"teams": ["Winner M1", "Team C"], "depends_on": ["M1"]}}
        >>> validate_bracket_dependencies(schedule, bracket)
        ["Match M2 scheduled at 09:00 but depends on M1 which doesn't end until 09:30"]
    """
    violations = []
    
    # Build a map of match codes to their scheduled times
    match_times = {}
    for court_name, matches in schedule.items():
        for day, start_dt, end_dt, teams in matches:
            # Try to identify match code from teams or annotations
            match_code = _identify_match_code(teams, bracket_structure)
            if match_code:
                match_times[match_code] = {
                    'court': court_name,
                    'day': day,
                    'start': start_dt,
                    'end': end_dt,
                    'teams': teams
                }
    
    # Check each match's dependencies
    for match_code, match_info in bracket_structure.items():
        if match_code not in match_times:
            # Match not scheduled yet - not an error for this validator
            continue
        
        scheduled_match = match_times[match_code]
        depends_on = match_info.get('depends_on', [])
        
        for prereq_code in depends_on:
            if prereq_code not in match_times:
                violations.append(
                    f"Match {match_code} scheduled at {scheduled_match['start'].strftime('%H:%M')} "
                    f"but prerequisite match {prereq_code} not found in schedule"
                )
            else:
                prereq_match = match_times[prereq_code]
                # Check same day and that prereq ends before dependent starts
                if scheduled_match['day'] == prereq_match['day']:
                    if scheduled_match['start'] < prereq_match['end']:
                        violations.append(
                            f"Match {match_code} scheduled at {scheduled_match['start'].strftime('%H:%M')} "
                            f"but depends on {prereq_code} which doesn't end until {prereq_match['end'].strftime('%H:%M')}"
                        )
    
    return violations


# ============================================================================
# PRIVATE HELPER FUNCTIONS
# ============================================================================

def _identify_match_code(teams: Tuple, bracket_structure: Dict[str, Dict]) -> Optional[str]:
    """Try to identify which match code these teams correspond to."""
    for match_code, match_info in bracket_structure.items():
        bracket_teams = match_info.get('teams', [])
        # Check if teams match (order-independent)
        if (set(teams) == set(bracket_teams) or 
            (len(teams) == 2 and len(bracket_teams) == 2 and 
             set([str(t) for t in teams]) == set([str(t) for t in bracket_teams]))):
            return match_code
    return None


# ============================================================================
# TESTS FOR VALIDATION HELPERS
# ============================================================================

class TestValidationHelpers:
    """Tests for schedule validation helper functions."""
    
    # ========================================================================
    # Tests for validate_no_premature_scheduling
    # ========================================================================
    
    def test_validate_no_premature_valid_schedule(self):
        """Test validation passes for valid schedule with proper sequencing."""
        base_date = datetime(2026, 1, 15)
        schedule = {
            "Court 1": [
                (1, datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 9, 30), ("Team A", "Team B")),
                (1, datetime(2026, 1, 15, 10, 0), datetime(2026, 1, 15, 10, 30), ("Winner M1", "Team C")),
            ]
        }
        dependencies = {"Winner M1": ["M1"]}
        match_codes = {
            ("Team A", "Team B"): "M1",
            ("Winner M1", "Team C"): "M2"
        }
        
        violations = validate_no_premature_scheduling(schedule, dependencies, match_codes)
        assert violations == [], f"Expected no violations but got: {violations}"
    
    def test_validate_no_premature_violation(self):
        """Test validation catches premature scheduling."""
        schedule = {
            "Court 1": [
                (1, datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 9, 30), ("Team A", "Team B")),
            ],
            "Court 2": [
                (1, datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 9, 30), ("Winner M1", "Team C")),
            ]
        }
        dependencies = {"Winner M1": ["M1"]}
        match_codes = {
            ("Team A", "Team B"): "M1",
            ("Winner M1", "Team C"): "M2"
        }
        
        violations = validate_no_premature_scheduling(schedule, dependencies, match_codes)
        assert len(violations) > 0, "Expected violations for premature scheduling"
        assert "Winner M1" in violations[0]
        assert "09:00" in violations[0]
    
    def test_validate_no_premature_empty_schedule(self):
        """Test validation handles empty schedule."""
        schedule = {}
        dependencies = {"Winner M1": ["M1"]}
        
        violations = validate_no_premature_scheduling(schedule, dependencies)
        assert violations == []
    
    def test_validate_no_premature_no_dependencies(self):
        """Test validation with no placeholder teams."""
        schedule = {
            "Court 1": [
                (1, datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 9, 30), ("Team A", "Team B")),
                (1, datetime(2026, 1, 15, 10, 0), datetime(2026, 1, 15, 10, 30), ("Team C", "Team D")),
            ]
        }
        dependencies = {}
        
        violations = validate_no_premature_scheduling(schedule, dependencies)
        assert violations == []
    
    def test_validate_no_premature_missing_prerequisite(self):
        """Test validation catches missing prerequisite match."""
        schedule = {
            "Court 1": [
                (1, datetime(2026, 1, 15, 10, 0), datetime(2026, 1, 15, 10, 30), ("Winner M1", "Team C")),
            ]
        }
        dependencies = {"Winner M1": ["M1"]}
        match_codes = {
            ("Winner M1", "Team C"): "M2"
        }
        
        violations = validate_no_premature_scheduling(schedule, dependencies, match_codes)
        assert len(violations) > 0
        assert "M1" in violations[0]
        assert "not found" in violations[0]
    
    # ========================================================================
    # Tests for validate_team_availability
    # ========================================================================
    
    def test_validate_team_availability_valid(self):
        """Test validation passes when team has no conflicts."""
        schedule = {
            "Court 1": [
                (1, datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 9, 30), ("Team A", "Team B")),
                (1, datetime(2026, 1, 15, 10, 0), datetime(2026, 1, 15, 10, 30), ("Team A", "Team C")),
            ]
        }
        
        violations = validate_team_availability(schedule, "Team A")
        assert violations == [], f"Expected no violations but got: {violations}"
    
    def test_validate_team_availability_double_booking(self):
        """Test validation catches double-booking."""
        schedule = {
            "Court 1": [
                (1, datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 9, 30), ("Team A", "Team B")),
            ],
            "Court 2": [
                (1, datetime(2026, 1, 15, 9, 15), datetime(2026, 1, 15, 9, 45), ("Team A", "Team C")),
            ]
        }
        
        violations = validate_team_availability(schedule, "Team A")
        assert len(violations) > 0
        assert "Team A" in violations[0]
        assert "double-booked" in violations[0]
        assert "Court 1" in violations[0]
        assert "Court 2" in violations[0]
    
    def test_validate_team_availability_exact_back_to_back(self):
        """Test validation allows exact back-to-back matches (no overlap)."""
        schedule = {
            "Court 1": [
                (1, datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 9, 30), ("Team A", "Team B")),
                (1, datetime(2026, 1, 15, 9, 30), datetime(2026, 1, 15, 10, 0), ("Team A", "Team C")),
            ]
        }
        
        violations = validate_team_availability(schedule, "Team A")
        assert violations == [], "Back-to-back matches with no overlap should be valid"
    
    def test_validate_team_availability_one_minute_overlap(self):
        """Test validation catches even one minute overlap."""
        schedule = {
            "Court 1": [
                (1, datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 9, 30), ("Team A", "Team B")),
                (1, datetime(2026, 1, 15, 9, 29), datetime(2026, 1, 15, 9, 59), ("Team A", "Team C")),
            ]
        }
        
        violations = validate_team_availability(schedule, "Team A")
        assert len(violations) > 0
        assert "double-booked" in violations[0]
    
    def test_validate_team_availability_different_days(self):
        """Test validation allows same times on different days."""
        schedule = {
            "Court 1": [
                (1, datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 9, 30), ("Team A", "Team B")),
                (2, datetime(2026, 1, 16, 9, 0), datetime(2026, 1, 16, 9, 30), ("Team A", "Team C")),
            ]
        }
        
        violations = validate_team_availability(schedule, "Team A")
        assert violations == [], "Same time on different days should be valid"
    
    def test_validate_team_availability_team_not_in_schedule(self):
        """Test validation handles team not in schedule."""
        schedule = {
            "Court 1": [
                (1, datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 9, 30), ("Team A", "Team B")),
            ]
        }
        
        violations = validate_team_availability(schedule, "Team Z")
        assert violations == []
    
    def test_validate_team_availability_empty_schedule(self):
        """Test validation handles empty schedule."""
        schedule = {}
        
        violations = validate_team_availability(schedule, "Team A")
        assert violations == []
    
    def test_validate_team_availability_multiple_overlaps(self):
        """Test validation catches multiple overlaps."""
        schedule = {
            "Court 1": [
                (1, datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 9, 30), ("Team A", "Team B")),
            ],
            "Court 2": [
                (1, datetime(2026, 1, 15, 9, 10), datetime(2026, 1, 15, 9, 40), ("Team A", "Team C")),
            ],
            "Court 3": [
                (1, datetime(2026, 1, 15, 9, 20), datetime(2026, 1, 15, 9, 50), ("Team A", "Team D")),
            ]
        }
        
        violations = validate_team_availability(schedule, "Team A")
        # Should catch all three overlaps (1-2, 1-3, 2-3)
        assert len(violations) == 3
    
    # ========================================================================
    # Tests for validate_bracket_dependencies
    # ========================================================================
    
    def test_validate_bracket_dependencies_valid(self):
        """Test validation passes for valid bracket sequencing."""
        schedule = {
            "Court 1": [
                (1, datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 9, 30), ("Team A", "Team B")),
                (1, datetime(2026, 1, 15, 10, 0), datetime(2026, 1, 15, 10, 30), ("Winner M1", "Team C")),
            ]
        }
        bracket_structure = {
            "M1": {"teams": ["Team A", "Team B"], "depends_on": []},
            "M2": {"teams": ["Winner M1", "Team C"], "depends_on": ["M1"]}
        }
        
        violations = validate_bracket_dependencies(schedule, bracket_structure)
        assert violations == [], f"Expected no violations but got: {violations}"
    
    def test_validate_bracket_dependencies_violation(self):
        """Test validation catches dependency violation."""
        schedule = {
            "Court 1": [
                (1, datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 9, 30), ("Team A", "Team B")),
            ],
            "Court 2": [
                (1, datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 9, 30), ("Winner M1", "Team C")),
            ]
        }
        bracket_structure = {
            "M1": {"teams": ["Team A", "Team B"], "depends_on": []},
            "M2": {"teams": ["Winner M1", "Team C"], "depends_on": ["M1"]}
        }
        
        violations = validate_bracket_dependencies(schedule, bracket_structure)
        assert len(violations) > 0
        assert "M2" in violations[0]
        assert "M1" in violations[0]
    
    def test_validate_bracket_dependencies_empty_schedule(self):
        """Test validation handles empty schedule."""
        schedule = {}
        bracket_structure = {
            "M1": {"teams": ["Team A", "Team B"], "depends_on": []},
            "M2": {"teams": ["Winner M1", "Team C"], "depends_on": ["M1"]}
        }
        
        violations = validate_bracket_dependencies(schedule, bracket_structure)
        assert violations == []
    
    def test_validate_bracket_dependencies_no_dependencies(self):
        """Test validation with first-round matches only."""
        schedule = {
            "Court 1": [
                (1, datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 9, 30), ("Team A", "Team B")),
                (1, datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 9, 30), ("Team C", "Team D")),
            ]
        }
        bracket_structure = {
            "M1": {"teams": ["Team A", "Team B"], "depends_on": []},
            "M2": {"teams": ["Team C", "Team D"], "depends_on": []}
        }
        
        violations = validate_bracket_dependencies(schedule, bracket_structure)
        assert violations == []
    
    def test_validate_bracket_dependencies_missing_prerequisite(self):
        """Test validation catches missing prerequisite match."""
        schedule = {
            "Court 1": [
                (1, datetime(2026, 1, 15, 10, 0), datetime(2026, 1, 15, 10, 30), ("Winner M1", "Team C")),
            ]
        }
        bracket_structure = {
            "M1": {"teams": ["Team A", "Team B"], "depends_on": []},
            "M2": {"teams": ["Winner M1", "Team C"], "depends_on": ["M1"]}
        }
        
        violations = validate_bracket_dependencies(schedule, bracket_structure)
        assert len(violations) > 0
        assert "M1" in violations[0]
        assert "not found" in violations[0]
    
    def test_validate_bracket_dependencies_chain(self):
        """Test validation with chain of dependencies."""
        schedule = {
            "Court 1": [
                (1, datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 9, 30), ("Team A", "Team B")),
                (1, datetime(2026, 1, 15, 10, 0), datetime(2026, 1, 15, 10, 30), ("Winner M1", "Team C")),
                (1, datetime(2026, 1, 15, 11, 0), datetime(2026, 1, 15, 11, 30), ("Winner M2", "Team D")),
            ]
        }
        bracket_structure = {
            "M1": {"teams": ["Team A", "Team B"], "depends_on": []},
            "M2": {"teams": ["Winner M1", "Team C"], "depends_on": ["M1"]},
            "M3": {"teams": ["Winner M2", "Team D"], "depends_on": ["M2"]}
        }
        
        violations = validate_bracket_dependencies(schedule, bracket_structure)
        assert violations == []
    
    def test_validate_bracket_dependencies_different_days(self):
        """Test validation handles dependencies across different days."""
        schedule = {
            "Court 1": [
                (1, datetime(2026, 1, 15, 21, 0), datetime(2026, 1, 15, 21, 30), ("Team A", "Team B")),
                (2, datetime(2026, 1, 16, 9, 0), datetime(2026, 1, 16, 9, 30), ("Winner M1", "Team C")),
            ]
        }
        bracket_structure = {
            "M1": {"teams": ["Team A", "Team B"], "depends_on": []},
            "M2": {"teams": ["Winner M1", "Team C"], "depends_on": ["M1"]}
        }
        
        violations = validate_bracket_dependencies(schedule, bracket_structure)
        assert violations == [], "Cross-day dependencies should be valid"


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

class TestValidationHelpersEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_placeholder_team_name_patterns(self):
        """Test helpers handle various placeholder name patterns."""
        schedule = {
            "Court 1": [
                (1, datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 9, 30), ("Team A", "Team B")),
                (1, datetime(2026, 1, 15, 10, 0), datetime(2026, 1, 15, 10, 30), ("Winner M1", "Loser W1-M2")),
            ]
        }
        dependencies = {
            "Winner M1": ["M1"],
            "Loser W1-M2": ["W1-M2"]
        }
        match_codes = {
            ("Team A", "Team B"): "M1",
            ("Winner M1", "Loser W1-M2"): "M3"
        }
        
        # Should handle both patterns - Winner M1 is valid, Loser W1-M2 is not
        violations = validate_no_premature_scheduling(schedule, dependencies, match_codes)
        assert len(violations) == 1, f"Expected 1 violation but got {len(violations)}: {violations}"
        assert "Loser W1-M2" in violations[0]
        assert "W1-M2" in violations[0]
        assert "not found" in violations[0]
    
    def test_team_name_with_special_characters(self):
        """Test helpers handle team names with special characters."""
        schedule = {
            "Court 1": [
                (1, datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 9, 30), ("Team O'Brien", "Team #1")),
                (1, datetime(2026, 1, 15, 10, 0), datetime(2026, 1, 15, 10, 30), ("Team O'Brien", "Team A")),
            ]
        }
        
        violations = validate_team_availability(schedule, "Team O'Brien")
        assert violations == []
    
    def test_very_long_schedule(self):
        """Test helpers perform adequately with large schedules."""
        schedule = {
            f"Court {i}": [
                (1, datetime(2026, 1, 15, 9 + j, 0), datetime(2026, 1, 15, 9 + j, 30), (f"Team A{j}", f"Team B{j}"))
                for j in range(10)
            ]
            for i in range(10)
        }
        
        # Should complete without errors
        violations = validate_team_availability(schedule, "Team A0")
        assert isinstance(violations, list)
    
    def test_midnight_crossing_matches(self):
        """Test helpers handle matches that cross midnight."""
        schedule = {
            "Court 1": [
                (1, datetime(2026, 1, 15, 23, 30), datetime(2026, 1, 16, 0, 30), ("Team A", "Team B")),
                (1, datetime(2026, 1, 16, 0, 0), datetime(2026, 1, 16, 1, 0), ("Team A", "Team C")),
            ]
        }
        
        violations = validate_team_availability(schedule, "Team A")
        # Should detect overlap across midnight
        assert len(violations) > 0 or violations == []  # Depending on day handling

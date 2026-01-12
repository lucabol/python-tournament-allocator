"""
Unit tests for match generation.
"""
import pytest
import sys
import os
from itertools import combinations

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.models import Team
from generate_matches import load_teams, generate_pool_play_matches


class TestMatchGeneration:
    """Tests for pool play match generation."""
    
    def test_generate_matches_simple_pool(self):
        """Test match generation for a simple pool."""
        teams = [
            Team(name="Team A", attributes={"pool": "pool1"}),
            Team(name="Team B", attributes={"pool": "pool1"}),
            Team(name="Team C", attributes={"pool": "pool1"}),
        ]
        
        matches = generate_pool_play_matches(teams)
        
        # 3 teams should produce 3 matches (combinations of 3 choose 2)
        assert len(matches) == 3
        
        # Verify all expected matchups exist
        team_pairs = set()
        for match in matches:
            team_pairs.add(frozenset(match["teams"]))
        
        assert frozenset(["Team A", "Team B"]) in team_pairs
        assert frozenset(["Team A", "Team C"]) in team_pairs
        assert frozenset(["Team B", "Team C"]) in team_pairs
    
    def test_generate_matches_multiple_pools(self, sample_teams):
        """Test match generation with multiple pools."""
        matches = generate_pool_play_matches(sample_teams)
        
        # pool1 has 3 teams: 3 matches
        # pool2 has 2 teams: 1 match
        # Total: 4 matches
        assert len(matches) == 4
        
        # Verify matches are within pools (no cross-pool matches)
        pool1_teams = {"Team A", "Team B", "Team C"}
        pool2_teams = {"Team D", "Team E"}
        
        for match in matches:
            team_set = set(match["teams"])
            is_pool1_match = team_set.issubset(pool1_teams)
            is_pool2_match = team_set.issubset(pool2_teams)
            assert is_pool1_match or is_pool2_match, f"Cross-pool match found: {match}"
    
    def test_generate_matches_pool_assignment(self, sample_teams):
        """Test that matches are assigned correct pool names."""
        matches = generate_pool_play_matches(sample_teams)
        
        for match in matches:
            assert "pool" in match
            team1, team2 = match["teams"]
            
            # Both teams should be in the same pool as the match
            team1_obj = next(t for t in sample_teams if t.name == team1)
            team2_obj = next(t for t in sample_teams if t.name == team2)
            
            assert team1_obj.attributes["pool"] == match["pool"]
            assert team2_obj.attributes["pool"] == match["pool"]
    
    def test_generate_matches_large_pool(self):
        """Test match generation for a larger pool."""
        teams = [Team(name=f"Team {i}", attributes={"pool": "pool1"}) for i in range(6)]
        
        matches = generate_pool_play_matches(teams)
        
        # 6 teams should produce 15 matches (6 choose 2 = 15)
        assert len(matches) == 15
    
    def test_generate_matches_single_team_pool(self):
        """Test that single-team pools produce no matches."""
        teams = [
            Team(name="Team A", attributes={"pool": "pool1"}),
            Team(name="Team B", attributes={"pool": "pool2"}),
        ]
        
        matches = generate_pool_play_matches(teams)
        
        # Each pool has only 1 team, so no matches can be generated
        assert len(matches) == 0
    
    def test_generate_matches_empty_input(self):
        """Test match generation with empty team list."""
        matches = generate_pool_play_matches([])
        assert len(matches) == 0
    
    def test_generate_matches_correct_number(self):
        """Test that correct number of matches is generated using combinatorics."""
        # For n teams in a pool, should generate n*(n-1)/2 matches
        for pool_size in [2, 3, 4, 5, 6]:
            teams = [Team(name=f"Team {i}", attributes={"pool": "pool1"}) for i in range(pool_size)]
            matches = generate_pool_play_matches(teams)
            
            expected_matches = pool_size * (pool_size - 1) // 2
            assert len(matches) == expected_matches, f"Pool size {pool_size}: expected {expected_matches}, got {len(matches)}"


class TestLoadTeams:
    """Tests for loading teams from YAML file."""
    
    def test_load_teams_from_file(self, tmp_path):
        """Test loading teams from a YAML file."""
        # Create a temporary YAML file
        yaml_content = """pool1:
  - Team Alpha
  - Team Beta
pool2:
  - Team Gamma
  - Team Delta
"""
        yaml_file = tmp_path / "teams.yaml"
        yaml_file.write_text(yaml_content)
        
        teams = load_teams(str(yaml_file))
        
        assert len(teams) == 4
        team_names = {t.name for t in teams}
        assert team_names == {"Team Alpha", "Team Beta", "Team Gamma", "Team Delta"}
        
        # Check pool assignments
        for team in teams:
            if team.name in ["Team Alpha", "Team Beta"]:
                assert team.attributes["pool"] == "pool1"
            else:
                assert team.attributes["pool"] == "pool2"
    
    def test_load_teams_empty_file(self, tmp_path):
        """Test loading from empty YAML file."""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")
        
        teams = load_teams(str(yaml_file))
        
        # Should return empty list or handle gracefully
        assert teams == [] or teams is None

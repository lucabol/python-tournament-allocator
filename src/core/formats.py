class TournamentFormat:
    def __init__(self, teams):
        self.teams = teams

    def pool_play(self):
        # Logic for organizing pool play matches
        matches = []
        num_teams = len(self.teams)
        for i in range(num_teams):
            for j in range(i + 1, num_teams):
                matches.append((self.teams[i], self.teams[j]))
        return matches

    def single_elimination(self):
        # Logic for organizing single elimination matches
        matches = []
        num_teams = len(self.teams)
        if num_teams < 2:
            return matches
        
        # Create matches in a knockout format
        while len(self.teams) > 1:
            round_matches = []
            for i in range(0, len(self.teams), 2):
                if i + 1 < len(self.teams):
                    round_matches.append((self.teams[i], self.teams[i + 1]))
            matches.append(round_matches)
            # Advance winners to the next round (for simplicity, we assume the first team wins)
            self.teams = self.teams[::2]
        
        return matches
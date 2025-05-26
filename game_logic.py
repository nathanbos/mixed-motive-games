# game_logic.py

class Player:
    def __init__(self, player_id, player_type="human"):
        """
        Initializes a Player.

        Args:
            player_id (str): A unique identifier for the player.
            player_type (str): Type of player, e.g., "human" or "ai".
        """
        if not isinstance(player_id, str) or not player_id:
            raise ValueError("player_id must be a non-empty string.")
        if player_type not in ["human", "ai"]:
            raise ValueError("player_type must be 'human' or 'ai'.")

        self.player_id = player_id
        self.player_type = player_type
        self.history = [] # To store past decisions, payoffs, etc.

    def __str__(self):
        return f"Player(ID: {self.player_id}, Type: {self.player_type})"

    def __repr__(self):
        return f"Player('{self.player_id}', '{self.player_type}')"

    def record_decision(self, round_number, decision, payoff):
        """
        Records the player's decision and payoff for a given round.

        Args:
            round_number (int): The round number.
            decision (any): The decision made by the player (e.g., "cooperate", "defect").
            payoff (float or int): The payoff received by the player for that round.
        """
        self.history.append({
            "round": round_number,
            "decision": decision,
            "payoff": payoff
        })

# Example Usage (you can put this at the bottom of the file for testing,
# but remove or comment it out before committing):
if __name__ == "__main__":
    try:
        player1 = Player("Alice", "human")
        player2 = Player("Bob_AI", "ai")
        print(player1)
        print(player2)
        player1.record_decision(round_number=1, decision="cooperate", payoff=3)
        player2.record_decision(round_number=1, decision="defect", payoff=5)
        print(player1.history)
        print(player2.history)

        # Test invalid input
        # player3 = Player("", "human") # Should raise ValueError
        # player4 = Player("Carol", "robot") # Should raise ValueError

    except ValueError as e:
        print(f"Error: {e}")


# game_logic.py

# ... (Player class code from before should be above this) ...

# game_logic.py

# ... (Player class code from before should be above this) ...

class Game:
    def __init__(self, game_id, num_rounds=10):
        """
        Initializes a Game.

        Args:
            game_id (str): A unique identifier for the game.
            num_rounds (int): The total number of rounds to be played in the game.
        """
        if not isinstance(game_id, str) or not game_id:
            raise ValueError("game_id must be a non-empty string.")
        if not isinstance(num_rounds, int) or num_rounds <= 0:
            raise ValueError("num_rounds must be a positive integer.")

        self.game_id = game_id
        self.num_rounds = num_rounds
        self.current_round = 0
        self.players = [] # List of Player objects
        self.game_history = [] # List to store decisions and payoffs for each round for all players

    def add_player(self, player):
        """
        Adds a Player object to the game.

        Args:
            player (Player): An instance of the Player class.
        """
        if not isinstance(player, Player):
            raise ValueError("Invalid player object provided.")
        if player in self.players:
            print(f"Warning: Player {player.player_id} is already in the game.")
            return
        self.players.append(player)
        print(f"Player {player.player_id} added to game {self.game_id}.")

    def _get_player_decisions_for_round(self):
        """
        Collects decisions from all players for the current round.
        For now, we'll simulate AI decisions and prompt for human decisions.
        This will be expanded significantly later.

        Returns:
            dict: A dictionary mapping player_id to their decision (e.g., "cooperate" or "defect").
        """
        decisions = {}
        for player in self.players:
# Inside the Game class, in the _get_player_decisions_for_round method:

            if player.player_type == "human": # <-- Add quotes around "human"
                # In a real web app, this input would come from the UI.
                # For now, we'll use input() or a placeholder.
                while True:
                    decision = input(f"Player {player.player_id} (human), enter your decision (cooperate/defect): ").lower() # Corrected this line too
                    if decision in ["cooperate", "defect"]:
                        decisions[player.player_id] = decision
                        break
                    else:
                        print("Invalid decision. Please enter 'cooperate' or 'defect'.")
            elif player.player_type == "ai": # <-- Add quotes around "ai" just in case, though your error was with "human"
                # Basic AI: For now, let's make AI always cooperate as a placeholder.
                # We'll define specific AI strategies later.
                decisions[player.player_id] = "cooperate" # Placeholder AI decision
                print(f"Player {player.player_id} (AI) chose to cooperate.")
        return decisions

    def _calculate_payoffs_for_round(self, decisions):
        """
        Calculates payoffs for each player based on the decisions made in a round.
        This is the core logic for a specific social dilemma.

        Args:
            decisions (dict): A dictionary mapping player_id to their decision.

        Returns:
            dict: A dictionary mapping player_id to their calculated payoff for the round.
        """
        payoffs = {}
        num_cooperators = sum(1 for decision in decisions.values() if decision == "cooperate")
        num_defectors = len(self.players) - num_cooperators

        # --- Example Payoff Logic (N-Player Public Goods Game variant) ---
        # Each cooperator contributes 1 unit to a common pot.
        # The pot is multiplied by a factor (e.g., 1.6).
        # The total pot is then divided equally among all players.
        # Defectors contribute nothing but still get a share of the pot.
        # Cooperators also pay their contribution cost.

        contribution_cost = 1.0  # Cost for a cooperator to contribute
        multiplication_factor = 1.6 # Factor by which the common pot is multiplied

        if not self.players:
            return {}

        total_contributions = num_cooperators * contribution_cost
        total_pot = total_contributions * multiplication_factor
        share_per_player = total_pot / len(self.players) if self.players else 0

        for player_id, decision in decisions.items():
            if decision == "cooperate":
                payoffs[player_id] = share_per_player - contribution_cost
            else: # Defect
                payoffs[player_id] = share_per_player
        # --- End Example Payoff Logic ---

        return payoffs

    def play_round(self):
        """
        Plays a single round of the game:
        1. Increments round number.
        2. Gets decisions from players.
        3. Calculates payoffs.
        4. Records decisions and payoffs.
        5. Prints round summary.
        """
        if self.current_round >= self.num_rounds:
            print("Game has already ended.")
            return False
        if not self.players or len(self.players) < 2 : # Typically, dilemmas need at least 2 players
            print("Not enough players to start a round. Please add at least 2 players.")
            return False

        self.current_round += 1
        print(f"\n--- Round {self.current_round} of {self.num_rounds} ---")

        decisions = self._get_player_decisions_for_round()
        payoffs = self._calculate_payoffs_for_round(decisions)

        round_summary = {
            "round": self.current_round,
            "decisions": decisions,
            "payoffs": payoffs
        }
        self.game_history.append(round_summary)

        # Record decision in each player's history
        for player in self.players:
            player_id = player.player_id
            player.record_decision(
                round_number=self.current_round,
                decision=decisions.get(player_id),
                payoff=payoffs.get(player_id)
            )

        print("Decisions:", decisions)
        print("Payoffs:", payoffs)
        
        # Print player total scores so far
        print("--- Total Scores After Round", self.current_round, "---")
        for player in self.players:
            total_score = sum(item['payoff'] for item in player.history if item['payoff'] is not None)
            print(f"Player {player.player_id}: {total_score:.2f}")

        return True

    def play_game(self):
        """
        Plays the game for the total number of rounds.
        """
        print(f"Starting Game: {self.game_id} with {len(self.players)} players for {self.num_rounds} rounds.")
        while self.current_round < self.num_rounds:
            if not self.play_round():
                print("Game ended prematurely.")
                break
        print(f"\n--- Game {self.game_id} Over ---")
        print("Final Scores:")
        for player in self.players:
            total_score = sum(item['payoff'] for item in player.history if item['payoff'] is not None)
            print(f"Player {player.player_id}: {total_score:.2f}")
        print("Game History:", self.game_history)

    def __str__(self):
        return f"Game(ID: {self.game_id}, Rounds: {self.current_round}/{self.num_rounds}, Players: {len(self.players)})"

# Update the example usage:
if __name__ == "__main__":
    try:
        # Test Player Class
        player1 = Player("Alice", "human")
        player2 = Player("Bob_AI", "ai")
        player3 = Player("Charlie", "human")
        print(player1)
        print(player2)
        print(player3)
        player1.record_decision(round_number=0, decision="initial_cooperate", payoff=0) # Example pre-game history
        print(player1.history)
        print("-" * 20)

        # Test Game Class
        my_game = Game("TestGame001", num_rounds=3)
        print(my_game)

        my_game.add_player(player1)
        my_game.add_player(player2)
        my_game.add_player(player3)
        
        # Try adding the same player again
        my_game.add_player(player1)


        print(f"\nStarting game with players: {[p.player_id for p in my_game.players]}")

        # Play the game (this will prompt for human input)
        my_game.play_game()

        # Test invalid inputs for Game class (optional, can be commented out)
        # game_invalid_id = Game("", num_rounds=5)
        # game_invalid_rounds = Game("Game002", num_rounds=0)

    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        
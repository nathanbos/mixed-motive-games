import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables from .env file
load_dotenv()

# Configure Gemini API key at the module level
GEMINI_API_KEY = os.environ.get("MY_GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("WARNING: MY_GEMINI_API_KEY not found in environment. LLMAgent will not work.")

class Player:
    def __init__(self, player_id, player_type="human"):
        if not isinstance(player_id, str) or not player_id:
            raise ValueError("player_id must be a non-empty string.")
        if player_type not in ["human", "ai", "ai_llm"]:
            raise ValueError("player_type must be 'human', 'ai', or 'ai_llm'.")

        self.player_id = player_id
        self.player_type = player_type
        self.history = []

    def __str__(self):
        return f"Player(ID: {self.player_id}, Type: {self.player_type})"

    def __repr__(self):
        return f"Player('{self.player_id}', '{self.player_type}')"

    def record_decision(self, round_number, decision, payoff):
        self.history.append({
            "round": round_number,
            "decision": decision,
            "payoff": payoff
        })

class LLMAgent(Player):
    def __init__(self, player_id, strategy_prompt):
        super().__init__(player_id, player_type="ai_llm")
        self.strategy_prompt = strategy_prompt
        
        if not GEMINI_API_KEY:
            raise ValueError("Gemini API key is not configured. LLMAgent cannot be initialized.")
        
        self.model = genai.GenerativeModel(
            model_name='gemini-1.5-flash-latest',
            safety_settings={
                'HATE': 'BLOCK_NONE',
                'HARASSMENT': 'BLOCK_NONE',
                'SEXUAL': 'BLOCK_NONE',
                'DANGEROUS': 'BLOCK_NONE'
            }
        )
        print(f"LLMAgent {self.player_id} initialized with Gemini model.")

    def make_decision(self, game_state_summary):
        if not self.model:
            print(f"LLMAgent {self.player_id} model not initialized.")
            return 0, "Error: Model not initialized."

        full_prompt = (
            f"You are an AI player (ID: {self.player_id}) in a multi-round investment game.\n"
            f"Your designated strategy is: '{self.strategy_prompt}'\n\n"
            f"Current Game State:\n{game_state_summary}\n\n"
            f"Your task is to decide how much to invest this round.\n"
            f"Available actions: Choose a number between 0 and 5 (inclusive).\n"
            f"Based on your strategy and the game state, what is your decision?\n"
            f"Respond with your decision first, in the format 'INVESTMENT: <amount>', "
            f"where <amount> is your chosen number.\n"
            f"Optionally, on a new line, you can add a brief explanation or statement."
        )

        print(f"\n--- LLMAgent {self.player_id} Prompting LLM ---")
        print(f"Prompt Preview:\n{full_prompt[:350]}...")

        try:
            response = self.model.generate_content(full_prompt)
            response_text = response.text.strip()
            print(f"LLM Response for {self.player_id}: {response_text}")

            decision = 0.0  # Default to 0 if parsing fails
            explanation = response_text
            
            lines = response_text.split('\n', 1)
            if lines[0].startswith("INVESTMENT:"):
                try:
                    choice_str = lines[0].replace("INVESTMENT:", "").strip()
                    # Ensure the choice is a valid number and within the allowed range
                    investment = float(choice_str)
                    decision = max(0.0, min(5.0, investment)) # Clamp between 0 and 5
                    explanation = lines[1].strip() if len(lines) > 1 else "No explanation provided."
                except (ValueError, IndexError):
                    explanation = f"LLM provided an invalid number: {choice_str}. Defaulting to 0."
            else:
                explanation = "LLM did not follow INVESTMENT format. Defaulting to 0."

        except Exception as e:
            print(f"Error calling Gemini API for player {self.player_id}: {e}")
            decision = 0.0
            explanation = f"API Error: {e}"
        
        return decision, explanation

class Game:
    def __init__(self, game_id, num_rounds=10):
        self.game_id = game_id
        self.num_rounds = num_rounds
        self.current_round = 0
        self.players = []
        self.game_history = []
        self.investment_limit = 5.0

    def add_player(self, player):
        if not isinstance(player, Player):
            raise ValueError("Invalid player object provided.")
        if player in self.players:
            print(f"Warning: Player {player.player_id} is already in the game.")
            return
        self.players.append(player)
        print(f"Player {player.player_id} added to game {self.game_id}.")

    def _get_player_decisions_for_round(self):
        decisions = {}

        for player in self.players:
            if player.player_type == "human":
                while True:
                    try:
                        decision_input = float(input(f"Player {player.player_id} (human), enter investment (0-5): "))
                        if 0 <= decision_input <= self.investment_limit:
                            decisions[player.player_id] = decision_input
                            break
                        else:
                            print(f"Invalid amount. Please enter a number between 0 and {self.investment_limit}.")
                    except ValueError:
                        print("Invalid input. Please enter a number.")
            
            elif isinstance(player, LLMAgent):
                game_state_summary = self._create_game_state_summary_for_player(player)
                decision, explanation = player.make_decision(game_state_summary)
                decisions[player.player_id] = decision
                print(f"Player {player.player_id} (LLM AI) chose to invest: {decision:.2f}. Reason: {explanation}")

            elif player.player_type == "ai":
                # This case is no longer used by our main test block but is kept for compatibility
                decisions[player.player_id] = 0.0
                print(f"Player {player.player_id} (Basic AI) chose to invest: 0.00")
        
        return decisions

    def _create_game_state_summary_for_player(self, current_player):
        summary = f"Game ID: {self.game_id}, Total Rounds: {self.num_rounds}, Current Round: {self.current_round}\n"
        summary += f"Your Player ID: {current_player.player_id}\n"
        summary += "Your History (Round, Investment, Payoff):\n"
        if not current_player.history:
            summary += "  No history yet for you in this game.\n"
        for entry in current_player.history:
            summary += f"  R{entry['round']}: Invested {entry['decision']:.2f}, Got payoff {entry['payoff']:.2f}\n"
        
        summary += "Other Players' Investments Last Round (if any):\n"
        if self.current_round > 1 and self.game_history:
            last_round_data = self.game_history[-1]
            found_others = False
            for pid, decision in last_round_data['decisions'].items():
                if pid != current_player.player_id:
                    summary += f"  Player {pid} invested: {decision:.2f} in round {last_round_data['round']}\n"
                    found_others = True
            if not found_others:
                summary += "  No other players' actions to show from last round.\n"
        else:
            summary += "  No previous round data for other players available.\n"
        
        summary += (
            f"Payoff Rules: You have {self.investment_limit} to invest. You keep what you don't invest. "
            "All investments go into a common pot, which is multiplied by 1.5. "
            "This multiplied pot is then divided equally among all players. Your final payoff for the round is "
            "(what you kept) + (your share of the pot)."
        )
        return summary

    def _calculate_payoffs_for_round(self, decisions):
        payoffs = {}
        multiplication_factor = 1.5

        if not self.players:
            return {}

        total_investment = sum(decisions.values())
        total_pot = total_investment * multiplication_factor
        share_per_player = total_pot / len(self.players) if self.players else 0

        for player_id, investment in decisions.items():
            amount_kept = self.investment_limit - investment
            final_payoff = amount_kept + share_per_player
            payoffs[player_id] = final_payoff

        return payoffs

    def play_round(self):
        if self.current_round >= self.num_rounds:
            print("Game has already ended.")
            return False
        if len(self.players) < 1:
            print("Not enough players to start a round.")
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

        for player in self.players:
            player.record_decision(
                round_number=self.current_round,
                decision=decisions.get(player.player_id),
                payoff=payoffs.get(player.player_id)
            )

        print("Investments:", {p: f"{d:.2f}" for p, d in decisions.items()})
        print("Payoffs:", {p: f"{pay:.2f}" for p, pay in payoffs.items()})
        
        print("--- Total Scores After Round", self.current_round, "---")
        for player in self.players:
            total_score = sum(item['payoff'] for item in player.history if item['payoff'] is not None)
            print(f"Player {player.player_id}: {total_score:.2f}")

        return True

    def play_game(self):
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
        
        # Nicer printing for game history
        print("--- Game History ---")
        for round_data in self.game_history:
            print(f"Round {round_data['round']}:")
            print(f"  Investments: { {p: f'{d:.2f}' for p, d in round_data['decisions'].items()} }")
            print(f"  Payoffs: { {p: f'{pay:.2f}' for p, pay in round_data['payoffs'].items()} }")


if __name__ == "__main__":
    try:
        player_human_alice = Player("Alice", "human")

        # Define strategies for the LLM agents
        llm_strategy_bob = "You are a pure free-rider. Always try to invest 0 and benefit from the contributions of others. When you explain your actions, be confident and claim you are just 'playing smart'."
        player_llm_bob = LLMAgent("Bob_LLM", llm_strategy_bob)

        llm_strategy_carol = "You are a thoughtful investor. You want to contribute to the group pot to help it grow, but you are also cautious about being exploited by players who don't invest. Try to balance group success with your own personal gain."
        player_llm_carol = LLMAgent("Carol_LLM", llm_strategy_carol)

        my_game = Game("EnvelopeGame001", num_rounds=3)
        my_game.add_player(player_human_alice)
        my_game.add_player(player_llm_bob) # Add the new LLM Bob
        my_game.add_player(player_llm_carol)

        print(f"\nStarting game with players: {[p.player_id for p in my_game.players]}")
        my_game.play_game()

    except ValueError as e:
        print(f"Configuration or Value Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()

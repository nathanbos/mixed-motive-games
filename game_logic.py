import os
import json
import uuid
import random
import datetime # Import the datetime module
from dotenv import load_dotenv
import google.generativeai as genai
import openai
import anthropic
import pandas as pd

# --- Configuration ---
PLAYERS_FILE = 'players.json'
PERSONALITIES_FILE = 'personalities.json'
GAME_LOG_FILE = 'game_log.json'
RECORDS_DIR = 'game_records'

# Load environment variables from .env file
load_dotenv()

# Configure API keys at the module level
GEMINI_API_KEY = os.environ.get("MY_GEMINI_API_KEY")
OPENAI_API_KEY = os.environ.get("MY_OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.environ.get("MY_ANTHROPIC_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- Player and Agent Classes ---
# ... existing Player and LLMAgent class code ...
class Player:
    def __init__(self, name, player_type="human", bank=100.0, personality="N/A", strategy="N/A", history=None, player_id=None):
        self.player_id = player_id if player_id is not None else str(uuid.uuid4())
        self.name = name
        self.player_type = player_type
        self.bank = float(bank)
        self.personality = personality
        self.strategy = strategy
        self.history = history if history is not None else []

    def to_dict(self):
        return {
            'player_id': self.player_id, 'name': self.name, 'player_type': self.player_type,
            'bank': self.bank, 'personality': self.personality, 'strategy': self.strategy,
        }

    @classmethod
    def from_dict(cls, data):
        data_copy = data.copy()
        if 'player_type' not in data_copy: data_copy['player_type'] = 'human'
        if data_copy.get('player_type') == 'ai_llm':
            return LLMAgent.from_dict(data_copy)
        return cls(**data_copy)

    def __str__(self):
        return f"Player(Name: {self.name}, Type: {self.player_type}, Bank: {self.bank:.2f})"

class LLMAgent(Player):
    def __init__(self, name, player_type, bank, personality, strategy, history=None, player_id=None, provider='gemini', model=None):
        super().__init__(name, player_type, bank, personality, strategy, history, player_id)
        self.provider = provider.lower()
        self.model_name = model
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        if self.provider == 'gemini':
            if not GEMINI_API_KEY: raise ValueError("Gemini API key is not configured.")
            self.model_name = self.model_name or 'gemini-2.5-pro-latest'
            self.client = genai.GenerativeModel(self.model_name)
        elif self.provider == 'openai':
            if not OPENAI_API_KEY: raise ValueError("OpenAI API key is not configured.")
            self.model_name = self.model_name or 'gpt-4o'
            self.client = openai.OpenAI(api_key=OPENAI_API_KEY)
        elif self.provider == 'anthropic':
            if not ANTHROPIC_API_KEY: raise ValueError("Anthropic API key is not configured.")
            self.model_name = self.model_name or 'claude-3-opus-20240229'
            self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}.")
        print(f"LLMAgent {self.name} initialized with provider: {self.provider.upper()} using model: {self.model_name}")
    
    def to_dict(self):
        data = super().to_dict()
        data['provider'] = self.provider
        data['model'] = self.model_name
        return data

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data['name'], player_type=data['player_type'], bank=data['bank'],
            personality=data['personality'], strategy=data['strategy'], history=data.get('history', []),
            player_id=data.get('player_id'), provider=data.get('provider', 'gemini'), model=data.get('model')
        )

    def _call_llm_api(self, prompt):
        """Internal method to call the appropriate LLM API."""
        if self.provider == 'gemini':
            return self.client.generate_content(prompt).text
        elif self.provider == 'openai':
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        elif self.provider == 'anthropic':
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        return ""

    def make_decision(self, game_state_summary):
        full_prompt = (
            f"You are an AI player named {self.name}.\nYour strategy is: '{self.strategy}'\n\n"
            f"Here is the game history so far:\n{game_state_summary}\n\n"
            f"Task: Based on the history and your strategy, decide how much to invest this round. Choose an INTEGER between 0 and 5.\n"
            f"Respond ONLY with your decision in the format 'INVESTMENT: <amount>'."
        )
        print(f"\n--- LLMAgent {self.name} ({self.provider.upper()}/{self.model_name}) Deciding Investment ---")
        try:
            response_text = self._call_llm_api(full_prompt).strip()
            print(f"LLM Response for {self.name}: {response_text}")
            decision = 0
            if response_text.upper().startswith("INVESTMENT:"):
                choice_str = response_text.upper().replace("INVESTMENT:", "").strip()
                decision = max(0, min(5, int(float(choice_str))))
            return decision, response_text
        except Exception as e:
            print(f"Error calling {self.provider.upper()} API for player {self.name}: {e}")
            return 0, f"API Error: {e}"

    def make_statement(self, discussion_context):
        full_prompt = (
            f"You are an AI player named {self.name}.\nYour strategy is: '{self.strategy}'\n\n"
            f"Here is the full context of the game so far:\n{discussion_context}\n\n"
            f"Task: Make one statement to the group. Consider the entire game history, previous discussions, and the most recent investment results. Do not repeat things you have said before. Make your statement relevant to the current situation."
        )
        print(f"\n--- LLMAgent {self.name} ({self.provider.upper()}/{self.model_name}) Making Statement ---")
        try:
            return self._call_llm_api(full_prompt).strip()
        except Exception as e:
            print(f"Error calling {self.provider.upper()} API for statement from {self.name}: {e}")
            return "..."

# --- Data Management Functions ---
def load_json_data(filename):
    if not os.path.exists(filename): return []
    with open(filename, 'r') as f:
        try: return json.load(f)
        except json.JSONDecodeError: return []
def save_json_data(data, filename):
    with open(filename, 'w') as f: json.dump(data, f, indent=2)
def save_players(players_list):
    save_json_data([p.to_dict() for p in players_list], PLAYERS_FILE)
def load_players():
    return [Player.from_dict(p_data) for p_data in load_json_data(PLAYERS_FILE)]
def append_to_game_log(new_entries):
    log_data = load_json_data(GAME_LOG_FILE)
    log_data.extend(new_entries)
    save_json_data(log_data, GAME_LOG_FILE)
def save_game_to_csv(game_log, game_id, timestamp):
    if not game_log: return
    if not os.path.exists(RECORDS_DIR): os.makedirs(RECORDS_DIR)
    df = pd.DataFrame(game_log)
    # --- CHANGE: Use timestamp in the filename ---
    filepath = os.path.join(RECORDS_DIR, f"game-record_{timestamp}_{game_id}.csv")
    df.to_csv(filepath, index=False)
    print(f"Game record saved to {filepath}")

# --- Game Class ---
class Game:
    def __init__(self, game_id, participating_players, num_rounds=10, multiplier=1.5, timestamp=None):
        self.game_id = game_id
        # --- CHANGE: Store a timestamp for the game ---
        self.timestamp = timestamp or datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        self.num_rounds = num_rounds
        self.multiplier = multiplier
        self.current_round = 0
        self.investment_limit = 5
        self.players = participating_players
        self.current_game_log = []
        self.game_earnings = {p.player_id: 0.0 for p in self.players}
        self.last_discussion = {}
        self.last_investment_results = {}
        self.phase = "INVESTMENT"

    def to_dict(self):
        return {
            "game_id": self.game_id, "timestamp": self.timestamp, "num_rounds": self.num_rounds,
            "multiplier": self.multiplier, "current_round": self.current_round,
            "investment_limit": self.investment_limit, "players": [p.to_dict() for p in self.players],
            "current_game_log": self.current_game_log, "game_earnings": self.game_earnings,
            "last_discussion": self.last_discussion, "last_investment_results": self.last_investment_results,
            "phase": self.phase
        }

    @classmethod
    def from_dict(cls, data):
        players = [Player.from_dict(p_data) for p_data in data['players']]
        game = cls(
            data['game_id'], players, data['num_rounds'],
            data['multiplier'], timestamp=data.get('timestamp')
        )
        game.current_round = data['current_round']
        game.current_game_log = data['current_game_log']
        game.game_earnings = data['game_earnings']
        game.last_discussion = data.get('last_discussion', {})
        game.last_investment_results = data.get('last_investment_results', {})
        game.phase = data.get('phase', 'INVESTMENT')
        return game
# ... existing get_human_player, process_investment_round, process_discussion_round methods ...
    def get_human_player(self):
        return next((p for p in self.players if p.name.startswith('Human_')), None)

    def process_investment_round(self, human_decision=None):
        self.current_round += 1
        decisions = {}
        explanations = {}
        human_player = self.get_human_player()

        for player in self.players:
            if human_player and player.player_id == human_player.player_id: continue
            if isinstance(player, LLMAgent):
                summary = self._create_game_state_summary(player)
                decision, explanation = player.make_decision(summary)
                decisions[player.player_id], explanations[player.player_id] = decision, explanation
            else:
                decisions[player.player_id], explanations[player.player_id] = 0, "Default NPC behavior"

        if human_player and human_decision is not None:
            decisions[human_player.player_id], explanations[human_player.player_id] = human_decision, "Human decision"
        
        payoffs = self._calculate_payoffs(decisions)
        self.last_investment_results = {"decisions": decisions, "payoffs": payoffs, "explanations": explanations}
        
        self.phase = "DISCUSSION"

    def process_discussion_round(self, human_statement=None):
        statements = {}
        human_player = self.get_human_player()
        if human_player and human_statement is not None:
            statements[human_player.player_id] = human_statement

        for player in self.players:
            if isinstance(player, LLMAgent):
                discussion_context = self._create_context_for_statement(player)
                statements[player.player_id] = player.make_statement(discussion_context)
            elif player.player_type == 'human' and player.player_id != (human_player and human_player.player_id):
                 statements[player.player_id] = "..."
        
        self.last_discussion = statements
        # --- CHANGE: Associate discussion with the round that just happened ---
        self._log_completed_round(statements)

        if self.current_round >= self.num_rounds:
            self.phase = "GAMEOVER"
            # --- CHANGE: Pass timestamp to the save function ---
            save_game_to_csv(self.current_game_log, self.game_id, self.timestamp)
        else:
            self.phase = "INVESTMENT"

    def _log_completed_round(self, statements):
        """Creates and saves the log entry for the round that just finished."""
        decisions = self.last_investment_results.get('decisions', {})
        payoffs = self.last_investment_results.get('payoffs', {})
        explanations = self.last_investment_results.get('explanations', {})
        avg_inv = sum(decisions.values()) / len(decisions) if decisions else 0

        round_log_entries = []
        for player in self.players:
            payoff = payoffs.get(player.player_id, 0)
            decision = decisions.get(player.player_id, 0)
            player.bank += payoff
            self.game_earnings[player.player_id] += payoff
            
            log_entry = {
                'game_id': self.game_id, 'round': self.current_round, 'player_id': player.player_id,
                'player_name': player.name, 'player_type': player.personality if isinstance(player, LLMAgent) else player.player_type,
                'decision': decision, 'payoff': round(payoff, 2),
                'contribution': 'more' if decision > avg_inv else ('less' if decision < avg_inv else 'same'),
                'statement': statements.get(player.player_id, "N/A"),
                'thinking': explanations.get(player.player_id, "N/A")
            }
            round_log_entries.append(log_entry)
        
        self.current_game_log.extend(round_log_entries)
        append_to_game_log(round_log_entries)

    def _create_context_for_statement(self, current_player):
        history_summary = self._create_game_state_summary(current_player, for_statement=True)
        
        if not self.last_investment_results:
            results_summary = "This is the first round, so there are no investment results to discuss yet."
        else:
            results_summary = f"--- Results of Investment Round {self.current_round} ---\n"
            decisions = self.last_investment_results.get('decisions', {})
            payoffs = self.last_investment_results.get('payoffs', {})
            for p in self.players:
                p_name = f"You ({p.name})" if p.player_id == current_player.player_id else p.name
                results_summary += f"- {p_name} invested {decisions.get(p.player_id, 0)}, earning a payoff of {payoffs.get(p.player_id, 0):.2f}.\n"
        return f"{history_summary}\n{results_summary}"

    def _create_game_state_summary(self, current_player, for_statement=False):
        summary = f"--- Full Game History (Newest to Oldest) ---\n\n"
        rounds_data = {}
        for log_entry in self.current_game_log:
            round_num = log_entry['round']
            if round_num not in rounds_data:
                rounds_data[round_num] = []
            rounds_data[round_num].append(log_entry)

        # --- CHANGE: Display rounds in descending order ---
        for round_num in sorted(rounds_data.keys(), reverse=True):
            summary += f"**Round {round_num} Summary:**\n"
            round_actions = rounds_data[round_num]
            invest_summary = []
            for action in round_actions:
                player_name = action['player_name']
                if action['player_id'] == current_player.player_id:
                    player_name = f"You ({action['player_name']})"
                invest_summary.append(
                    f"{player_name} invested {action['decision']} "
                    f"({action['contribution']} than avg), payoff was {action['payoff']:.2f}."
                )
            summary += "- " + "\n- ".join(invest_summary) + "\n"

            discussion_summary = []
            summary += f"[Discussion after Round {round_num}]\n"
            for action in round_actions:
                player_name = action['player_name']
                if action['player_id'] == current_player.player_id:
                    player_name = "You"
                if action['statement'] and action['statement'] != "N/A":
                    discussion_summary.append(f"- {player_name} said: {action['statement']}")
            if discussion_summary:
                summary += "\n".join(discussion_summary) + "\n"
            else:
                summary += "- No discussion took place.\n"
            summary += "\n"

        if not for_statement:
            # --- CHANGE: Increment round number correctly for the prompt ---
            summary += f"--- Your Turn (Round {self.current_round + 1}) ---\n"
            summary += f"Your Total Bank: {current_player.bank:.2f}\n"
            summary += (
                f"Payoff Rules: Invest an integer from 0 to {self.investment_limit}. You keep what you don't invest. "
                f"The common pot is multiplied by {self.multiplier} and shared equally."
            )
        return summary
    
    def _calculate_payoffs(self, decisions):
        payoffs = {}
        total_investment = sum(decisions.values())
        total_pot = total_investment * self.multiplier
        share = total_pot / len(self.players) if self.players else 0
        for pid, investment in decisions.items():
            payoffs[pid] = (self.investment_limit - investment) + share
        return payoffs

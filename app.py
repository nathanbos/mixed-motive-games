import os
import json
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from flask_session import Session
from game_logic import (
    Player, LLMAgent, Game, load_players, save_players,
    load_json_data, PERSONALITIES_FILE, RECORDS_DIR
)

# --- Flask App Setup ---
app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24)

# Configure server-side sessions
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = "./flask_session"
Session(app)

# Ensure the session directory exists
os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)


# --- New Function to Run All-AI Games ---
def run_full_ai_game(game):
    """
    Runs an all-AI game from start to finish on the server.
    """
    print(f"--- Running full simulation for Game ID: {game.game_id} ---")
    while game.phase != "GAMEOVER":
        if game.phase == "INVESTMENT":
            print(f"Simulating Round {game.current_round + 1} - Investment Phase...")
            game.process_investment_round()
        elif game.phase == "DISCUSSION":
            print(f"Simulating Round {game.current_round} - Discussion Phase...")
            game.process_discussion_round()
    
    print(f"--- Simulation for {game.game_id} complete. ---")
    return game


# --- Web Routes ---

@app.route('/')
def setup_page():
    """Displays the main game setup page."""
    all_players = load_players()
    personalities = load_json_data(PERSONALITIES_FILE)
    
    # Convert player objects to dictionaries for JSON serialization in the template
    persistent_players_dict = [p.to_dict() for p in all_players]

    return render_template(
        'setup.html',
        persistent_players=persistent_players_dict,
        personalities=personalities
    )

@app.route('/start_game', methods=['POST'])
def start_game():
    """Handles the setup form, creates the game, and starts it."""
    all_players = load_players()
    personalities = load_json_data(PERSONALITIES_FILE)

    num_rounds = int(request.form.get('num_rounds', 3))
    multiplier = float(request.form.get('multiplier', 1.5))
    game_provider = request.form.get('game_provider', 'gemini')
    game_model = request.form.get('game_model')

    player_slots = request.form.getlist('player_slot')
    participating_players = []

    for slot_value in player_slots:
        if not slot_value: continue

        parts = slot_value.split(':', 1)
        player_type = parts[0]
        player_id = parts[1] if len(parts) > 1 else None
        
        if player_type == 'human':
            participating_players.append(Player(name=f"Human_{len(participating_players) + 1}"))
        elif player_type == 'persistent':
            player = next((p for p in all_players if p.player_id == player_id), None)
            if player:
                # Refresh strategy from personalities file in case it's updated
                pers = next((p for p in personalities if p['name'] == player.personality), None)
                if pers:
                    player.strategy = pers['strategy']
                participating_players.append(player)

        elif player_type == 'personality':
            personality = next((p for p in personalities if p['name'] == player_id), None)
            if personality:
                new_agent = LLMAgent(
                    name=f"{personality['name']}_{len(participating_players) + 1}",
                    player_type='ai_llm', bank=100.0,
                    personality=personality['name'],
                    strategy=personality['strategy'],
                    provider=game_provider,
                    model=game_model
                )
                participating_players.append(new_agent)

    game_id = f"Game-{uuid.uuid4().hex[:6]}"
    game = Game(game_id, participating_players, num_rounds, multiplier)

    # --- CHANGE: Logic to handle observer vs. interactive games ---
    if not game.get_human_player():
        # This is an all-AI (observer) game. Run it on the server.
        completed_game = run_full_ai_game(game)

        # Update the master player list with final banks
        for final_player in completed_game.players:
            for p in all_players:
                if p.player_id == final_player.player_id:
                    p.bank = final_player.bank
                    break
        save_players(all_players)

        # Save the completed game to the session and go to results
        session['game_state'] = completed_game.to_dict()
        return redirect(url_for('results_page'))
    else:
        # This is an interactive game with a human player.
        session['game_state'] = game.to_dict()
        return redirect(url_for('game_page'))


@app.route('/game')
def game_page():
    """Displays the main interactive game screen."""
    game_state = session.get('game_state')
    if not game_state: return redirect(url_for('setup_page'))
    game = Game.from_dict(game_state)
    return render_template('game.html', game=game)


@app.route('/submit_action', methods=['POST'])
def submit_action():
    """Handles form submissions from the human player (investment or statement)."""
    game_state = session.get('game_state')
    if not game_state: return redirect(url_for('setup_page'))
    game = Game.from_dict(game_state)

    if game.phase == "INVESTMENT":
        investment = int(request.form.get('investment', 0))
        game.process_investment_round(human_decision=investment)
    elif game.phase == "DISCUSSION":
        statement = request.form.get('statement', 'pass')
        game.process_discussion_round(human_statement=statement)

    session['game_state'] = game.to_dict()

    if game.phase == "GAMEOVER":
        all_players = load_players()
        for final_player in game.players:
            for p in all_players:
                if p.player_id == final_player.player_id:
                    p.bank = final_player.bank
                    break
        save_players(all_players)
        return redirect(url_for('results_page'))
    
    return redirect(url_for('game_page'))


@app.route('/run_ai_turn', methods=['POST'])
def run_ai_turn():
    """Handles the button click for advancing turns in observer mode."""
    # This route is now a fallback but can be kept for step-by-step observation if needed later.
    game_state = session.get('game_state')
    if not game_state: return redirect(url_for('setup_page'))
    game = Game.from_dict(game_state)

    if game.phase == "INVESTMENT":
        game.process_investment_round()
    elif game.phase == "DISCUSSION":
        game.process_discussion_round()
    
    session['game_state'] = game.to_dict()

    if game.phase == "GAMEOVER":
        all_players = load_players()
        for final_player in game.players:
            for p in all_players:
                if p.player_id == final_player.player_id:
                    p.bank = final_player.bank
                    break
        save_players(all_players)
        return redirect(url_for('results_page'))

    return redirect(url_for('game_page'))


@app.route('/results')
def results_page():
    """Displays the final results of the game."""
    game_state = session.get('game_state')
    if not game_state: return redirect(url_for('setup_page'))
    game = Game.from_dict(game_state)
    return render_template('results.html', game=game)


@app.route('/download/<game_id>')
def download_record(game_id):
    """
    Finds the correct timestamped filename for download.
    """
    try:
        for filename in os.listdir(RECORDS_DIR):
            if game_id in filename and filename.endswith('.csv'):
                return send_from_directory(RECORDS_DIR, filename, as_attachment=True)
    except FileNotFoundError:
        pass # Directory might not exist yet
    return "Record not found.", 404


if __name__ == '__main__':
    app.run(debug=True)


from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import random
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app)

# Spielstatus
game_data = {
    "balance": 100,
    "history": [],  # Speichert (Zahl, Drittel) für die Statistik
    "current_bet": {"third": None, "amount": 0},  # Benutzerwette
    "running": True,
    "result": None
}

# Drittel bestimmen
def get_third(number):
    if number == 0:
        return "keins"
    elif 1 <= number <= 12:
        return "1. Drittel"
    elif 13 <= number <= 24:
        return "2. Drittel"
    elif 25 <= number <= 36:
        return "3. Drittel"

# Spiel-Thread
def play_game():
    while game_data["running"]:
        time.sleep(10)  # Wartezeit zwischen Spielen
        
        # Zufälliges Ergebnis
        number = random.randint(0, 36)
        third = get_third(number)
        game_data["history"].append((number, third))
        game_data["result"] = {"number": number, "third": third}
        
        # Gewinn/Verlust berechnen
        if game_data["current_bet"]["amount"] > 0:
            if game_data["current_bet"]["third"] == third:
                winnings = game_data["current_bet"]["amount"] * 3  # Auszahlung 2:1
                game_data["balance"] += winnings
                result_text = f"Gewonnen! Du erhältst {winnings}€."
            else:
                game_data["balance"] -= game_data["current_bet"]["amount"]
                result_text = f"Verloren. Du verlierst {game_data['current_bet']['amount']}€."
        else:
            result_text = "Kein Einsatz gemacht."
        
        # Einsatz zurücksetzen
        game_data["current_bet"] = {"third": None, "amount": 0}

        # Statistik berechnen
        total_games = len(game_data["history"])
        third_counts = {
            "1. Drittel": sum(1 for _, t in game_data["history"] if t == "1. Drittel"),
            "2. Drittel": sum(1 for _, t in game_data["history"] if t == "2. Drittel"),
            "3. Drittel": sum(1 for _, t in game_data["history"] if t == "3. Drittel"),
        }
        third_probs = {k: (v / total_games) * 100 if total_games > 0 else 0 for k, v in third_counts.items()}

        # Aktualisierung an Client senden
        socketio.emit('game_update', {
            "result": {"number": number, "third": third},
            "balance": game_data["balance"],
            "result_text": result_text,
            "statistics": {
                "total_games": total_games,
                "third_probs": third_probs
            }
        })

# Flask-Routen
@app.route('/')
def index():
    return render_template('index.html', balance=game_data["balance"])

@app.route('/place_bet', methods=['POST'])
def place_bet():
    data = request.json
    third = data.get('third')
    try:
        amount = int(data.get('amount'))
    except ValueError:
        return jsonify({"error": "Ungültige Eingabe. Bitte ein Drittel und einen Betrag angeben."}), 400

    if third not in ["1. Drittel", "2. Drittel", "3. Drittel"]:
        return jsonify({"error": "Ungültiges Drittel. Wähle 1., 2. oder 3. Drittel."}), 400
    if amount <= 0 or amount > game_data["balance"]:
        return jsonify({"error": "Ungültiger Betrag. Setze innerhalb deines Guthabens."}), 400

    game_data["current_bet"] = {"third": third, "amount": amount}
    return jsonify({"message": f"Einsatz von {amount}€ auf {third} platziert!"})

@app.route('/reset', methods=['POST'])
def reset_balance():
    game_data["balance"] = 100
    return jsonify({"message": "Guthaben wurde zurückgesetzt!", "balance": game_data["balance"]})

# Spiel in einem separaten Thread starten
threading.Thread(target=play_game, daemon=True).start()

if __name__ == '__main__':
    socketio.run(app, debug=True)
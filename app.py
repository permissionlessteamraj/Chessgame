# app.py
from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, leave_room, emit
import chess
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app, async_mode='eventlet')

# Dictionary to manage active games:
# Key: room_id; Value: {'game': chess.Board(), 'players': {sid: color}, 'move_history': []}
games = {}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('createGame')
def on_create_game(data):
    # Generate a unique room ID (shortened)
    room_id = str(uuid.uuid4())[:8]
    join_room(room_id)
    # First player gets white
    games[room_id] = {
        'game': chess.Board(),
        'players': {request.sid: 'white'},
        'move_history': []
    }
    emit('gameCreated', {'room': room_id, 'color': 'white'})
    print(f"Game created: {room_id} by {request.sid}")

@socketio.on('joinGame')
def on_join_game(data):
    room_id = data.get('room')
    if room_id in games:
        game_info = games[room_id]
        if len(game_info['players']) >= 2:
            emit('error', {'message': 'Room is full'})
            return
        join_room(room_id)
        # Second player ko black assign karo
        game_info['players'][request.sid] = 'black'
        emit('gameJoined', {'room': room_id, 'color': 'black', 'fen': game_info['game'].fen()}, room=request.sid)
        # Dono players ko game start ka signal bhejo
        emit('gameStart', {'room': room_id, 'fen': game_info['game'].fen(), 'players': game_info['players']}, room=room_id)
        print(f"Player {request.sid} joined game {room_id}")
    else:
        emit('error', {'message': 'Room not found'})

@socketio.on('move')
def on_move(data):
    room_id = data.get('room')
    move_uci = data.get('move')
    if room_id not in games:
        emit('error', {'message': 'Game room not found'})
        return
    game_info = games[room_id]
    board = game_info['game']
    try:
        move = chess.Move.from_uci(move_uci)
    except Exception:
        emit('invalidMove', {'message': 'Invalid move format'})
        return
    if move in board.legal_moves:
        board.push(move)
        game_info['move_history'].append(move_uci)
        # Sabhi players ko updated game state broadcast karo
        emit('move', {'move': move_uci, 'fen': board.fen()}, room=room_id)
        # Agar game over hua, to result bhejo
        if board.is_game_over():
            if board.is_checkmate():
                result = 'Checkmate!'
            elif board.is_stalemate():
                result = 'Stalemate!'
            elif board.is_insufficient_material():
                result = 'Draw (insufficient material)'
            else:
                result = 'Game over'
            emit('gameOver', {'result': result}, room=room_id)
    else:
        emit('invalidMove', {'message': 'Illegal move'})

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    # Har active game room se disconnected player ko remove karo
    for room_id, game_info in list(games.items()):
        if sid in game_info['players']:
            leave_room(room_id)
            del game_info['players'][sid]
            emit('opponentLeft', {'message': 'Opponent has left the game'}, room=room_id)
            # Agar koi player nahi bacha to room delete karo
            if not game_info['players']:
                del games[room_id]
            break

if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)

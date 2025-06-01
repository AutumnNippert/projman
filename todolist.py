from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import json
import os
import html
import uuid

app = Flask(__name__)
socketio = SocketIO(app)

DATA_FILE = 'todos.json'

# In-memory storage for shared boards
shared_boards = {}

# mapping of client session IDs to todo lists they are viewing for emitting updates
list_client_mapping = {}

def load_todos():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    return {"default": []}

def save_todos():
    with open(DATA_FILE, 'w') as f:
        json.dump(todos, f)

# Load existing todos on startup
todos = load_todos()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/board')
def create_board():
    board_id = str(uuid.uuid4())[:8]
    shared_boards[board_id] = ""
    return redirect(url_for('view_board', board_id=board_id))

@app.route('/board/<board_id>')
def view_board(board_id):
    return render_template('board.html')

@app.route('/api/board/<board_id>')
def api_get_board(board_id):
    content = shared_boards.get(board_id)
    if content is None:
        return jsonify({'error': 'Board not found'}), 404
    return jsonify({'id': board_id, 'content': content})

@socketio.on('connect')
def handle_connect():
    sid = request.sid
    list_client_mapping[sid] = "default"
    emit('todos', {'todos': todos[list_client_mapping[sid]], 'lists': list(todos.keys())}, room=sid)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    list_client_mapping.pop(sid, None)

@socketio.on('switch_list')
def handle_switch(name):
    sid = request.sid
    list_client_mapping[sid] = name
    todos.setdefault(name, [])
    emit('todos', {'todos': todos[name], 'lists': list(todos.keys())}, room=sid)

@socketio.on('create_list')
def handle_create(name):
    sid = request.sid
    list_client_mapping[sid] = name
    if name not in todos:
        todos[name] = []
    save_todos()
    emit('todos', {'todos': todos[name], 'lists': list(todos.keys())}, room=sid)

@socketio.on('add_todo')
def handle_add(data):
    name = data['list']
    text = str(data['text']).strip()[:256]
    text = html.escape(text)
    todos.setdefault(name, []).append({'text': text, 'done': False})
    save_todos()
    broadcast_list_update(name)

@socketio.on('toggle_todo')
def handle_toggle(data):
    name = data['list']
    index = data['index']
    if 0 <= index < len(todos.get(name, [])):
        todos[name][index]['done'] = not todos[name][index]['done']
        save_todos()
        broadcast_list_update(name)

@socketio.on('remove_todo')
def handle_remove(data):
    name = data['list']
    index = data['index']
    if 0 <= index < len(todos.get(name, [])):
        todos[name].pop(index)
        save_todos()
        broadcast_list_update(name)

@socketio.on('edit_todo')
def handle_edit(data):
    name = data['list']
    index = data['index']
    text = str(data['text']).strip()[:256]
    text = html.escape(text)
    if 0 <= index < len(todos.get(name, [])):
        todos[name][index]['text'] = text
        save_todos()
        broadcast_list_update(name)

def broadcast_list_update(list_name):
    for sid, current_list in list_client_mapping.items():
        if current_list == list_name:
            emit('todos', {'todos': todos[list_name], 'lists': list(todos.keys())}, room=sid)

@socketio.on('join_shared_board')
def join_shared_board(board_id):
    join_room(board_id)
    content = shared_boards.get(board_id, "")
    emit('shared_board', content, room=board_id)

@socketio.on('update_shared_board')
def update_shared_board(data):
    board_id = data['id']
    content = data['content'][:10000]
    shared_boards[board_id] = content
    emit('shared_board', content, room=board_id)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0')
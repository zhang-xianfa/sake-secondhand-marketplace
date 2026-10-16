# run.py
from app import create_app,socketio

app = create_app()

if __name__ == '__main__':
    # app.run(debug=True)
    socketio.run(app, debug=True,host='0.0.0.0',port=5000,allow_unsafe_werkzeug=True)
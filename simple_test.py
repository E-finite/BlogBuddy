from flask import Flask

app = Flask(__name__)


@app.route('/')
def home():
    return '<h1>Test werkt!</h1>'


@app.route('/login')
def login():
    return '<h1>Login pagina</h1>'


if __name__ == '__main__':
    print("Starting simple test server on port 8001...")
    app.run(host='0.0.0.0', port=8001, debug=True, use_reloader=False)

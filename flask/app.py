from flask import Flask, render_template
app = Flask(__name__)

@app.route('/')
def receiver():
    return render_template('receiver.html')

if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0')
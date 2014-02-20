from flask import Flask, render_template
from flask_bootstrap import Bootstrap

app = Flask(__name__)

Bootstrap(app)

@app.route('/')
def receiver():
    return render_template('receiver.html')

@app.route('/bs')
def bstest():
    return render_template('bootstraptest.html')

if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0')
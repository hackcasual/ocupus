from flask import Flask, render_template
from flask_bootstrap import Bootstrap
import yaml

app = Flask(__name__)

cameras = yaml.load(file('/home/odroid/ocupus/config/ocupus.yml', 'r'))['cameras']

Bootstrap(app)

@app.route('/')
def receiver():
    return render_template('receiver.html', cameras=cameras)

@app.route('/bs')
def bstest():
    return render_template('bootstraptest.html')

if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0')
from flask import Flask, render_template, request
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run-scraper', methods=['POST'])
def run_scraper():
    # Here you can call your scraper function
    os.system('python scraper.py')
    return 'Scraping started! Check the logs for details.'

if __name__ == '__main__':
    app.run(debug=True)
